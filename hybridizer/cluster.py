import numpy as np
import scipy.constants as csts

from .antenna import AntennaElement, Pos, IMPEDANCE_FREE_SPACE

class Cluster(AntennaElement, Pos):
    ''' Part of ClusterCollection. 
    Is an AntennaElement and Position.
    Has an omnidirectional antenna. 
    Has one receiver which it uses to compute the orientation. 
    Has a field_at_receiver which is the field at the receiver.
    '''

    def __init__(self, x, y, z, id):
        AntennaElement.__init__(self, x, y, z, 'omni', None, None)

        self.receiver = None
        self.field_at_receiver = None
        self.id = id

        self.radiation_as_almost_plane_wave = True
        self.radiation_as_plane_wave = False
        self.verbose = True

    def set_verbose(self, verbose):
        ''' Set the verbose flag. '''

        self.verbose = verbose

    def set_receiver(self, receiver):
        ''' Set the receiver. '''

        self.receiver = receiver
        K = Pos.from_vec(self.vec_to(self.receiver))
        self.set_orientation(K) # optional, TODO
        self.K = K.normalize()

    def compute_local_grid_variables(self, grid):
        ''' Grid parameters w.r.t. the cluster. '''

        # Actually has an influence on speed
        if self.radiation_as_almost_plane_wave:
            method = 1

            # keeps the spherical curvature of a non-plane wave
            if not self.radiation_as_plane_wave:
                self.x_3D = grid.x_3D - self.x
                self.y_3D = grid.y_3D - self.y
                self.z_3D = grid.z_3D - self.z

            # Supposedly slow method, but is actually the same as method 2
            if method == 1:
                if not self.radiation_as_plane_wave:
                    self.r_3D = np.sqrt(self.x_3D**2 + self.y_3D**2 + self.z_3D**2)
                    self.r_3D[self.r_3D < 2e-15] = 2e-15

                self.center_x = grid.center.x - self.x
                self.center_y = grid.center.y - self.y
                self.center_z = grid.center.z - self.z
                self.center_r = np.sqrt(self.center_x**2 + self.center_y**2 + self.center_z**2)

                u = np.array([self.center_x, self.center_y, self.center_z])
                self.theta_center = np.arccos(np.clip(u[2] / self.center_r, -1, 1))
                self.phi_center = np.arctan2(u[1], u[0])

                # use a constant u_theta and u_phi, as a plane wave
                self.u_theta = np.zeros((3, *grid.shape))
                self.u_theta[0, ...] = np.cos(self.theta_center) * np.cos(self.phi_center)
                self.u_theta[1, ...] = np.cos(self.theta_center) * np.sin(self.phi_center)
                self.u_theta[2, ...] = -np.sin(self.theta_center)

                self.u_phi = np.zeros((3, *grid.shape))
                self.u_phi[0, ...] = -np.sin(self.phi_center)
                self.u_phi[1, ...] = np.cos(self.phi_center)

            # Supposedly fast method, but is actually the same as method 1
            if method == 2:
                # thanks to cluster's omni pattern, we dont need to compute theta and phi
                self.r_3D = np.sqrt(self.x_3D**2 + self.y_3D**2 + self.z_3D**2)
                self.r_3D[self.r_3D < 2e-15] = 2e-15

                self.center_x = grid.center.x - self.x
                self.center_y = grid.center.y - self.y
                self.center_z = grid.center.z - self.z

                r2_XY_center = self.center_x**2 + self.center_y**2
                r_center = np.sqrt(r2_XY_center + self.center_z**2)
                ux_3D = self.center_x / r_center
                uy_3D = self.center_y / r_center
                uz_3D = self.center_z / r_center
                n = np.sqrt(r2_XY_center) / r_center

                self.u_theta = np.zeros((3, *grid.shape))
                self.u_theta[0, ...] = ux_3D * uz_3D / n
                self.u_theta[1, ...] = uy_3D * uz_3D / n
                self.u_theta[2, ...] = -n
                self.u_phi = np.zeros((3, *grid.shape))
                self.u_phi[0, ...] = -uy_3D / n
                self.u_phi[1, ...] = ux_3D / n
        else:
            super().compute_local_grid_variables(grid)

    def compute_fields(self, simulation, grid = None):
        ''' Compute the fields for this cluster. '''

        assert hasattr(self, 'receiver'), 'Receiver not set for cluster.'
        assert self.field_at_receiver is not None, 'Field at receiver not set for cluster.'

        # Custom grids are sliced grids
        if grid is None:
            grid = simulation.grid
        else:
            assert simulation.use_sliced_grid
        
        # Pre-processing variables
        self.compute_local_grid_variables(grid)

        self.dist_to_rx = Pos.from_vec(self.vec_to(self.receiver)).vec_size
        
        # note that this is different from the compute_fields in AntennaElement because it is normalized such that pw_factor = 1 when r = dist_to_rx
        k_factor = 1j * 2. * np.pi * simulation.frequency / csts.speed_of_light
        if self.radiation_as_plane_wave:
            if not simulation.grid.is_2D:
                pw_factor = np.exp(k_factor * (self.K.x * (grid.x_3D - self.receiver.x) + self.K.y * (grid.y_3D - self.receiver.y) + self.K.z * (grid.z_3D - self.receiver.z)))
            else:
                pw_factor = np.exp(k_factor * (self.K.x * (grid.x_2D - self.receiver.x) + self.K.y * (grid.y_2D - self.receiver.y) + self.K.z * (grid.z_2D - self.receiver.z)))
        else:
            if not simulation.grid.is_2D:
                pw_factor = np.exp(k_factor * (self.r_3D - self.dist_to_rx)) / self.r_3D * self.dist_to_rx
            else:
                pw_factor = np.exp(k_factor * (self.r_2D - self.dist_to_rx)) / self.r_2D * self.dist_to_rx

        combined_factor = pw_factor * self.field_at_receiver

        # Note: only for the clusters (not antenna elements) do we add a minus sign to the fields
        # This in a way doesn't matter much, it's a matter of convention
        # But it makes a bit more sense for a vert polarized RX to have a positive Ez component from a cluster radiating at the horizon
        if not simulation.grid.is_2D:
            if simulation.use_sliced_grid:
                self.E_subgrid[grid.name] = - combined_factor * self.u_theta
                self.H_subgrid[grid.name] = - 1/IMPEDANCE_FREE_SPACE * combined_factor * self.u_phi
            else:
                self.E = - combined_factor * self.u_theta
                self.H = - 1/IMPEDANCE_FREE_SPACE * combined_factor * self.u_phi
        else:
            if simulation.polarization == 'TEz':
                self.Ez = combined_factor
                self.Hx =  1/IMPEDANCE_FREE_SPACE * self.y_2D/self.r_2D * self.Ez
                self.Hy = -1/IMPEDANCE_FREE_SPACE * self.x_2D/self.r_2D * self.Ez
            elif simulation.polarization == 'TMz':
                self.Hz = combined_factor
                self.Ex = -1/IMPEDANCE_FREE_SPACE * self.y_2D/self.r_2D * self.Hz
                self.Ey =  1/IMPEDANCE_FREE_SPACE * self.x_2D/self.r_2D * self.Hz
            elif simulation.polarization == 'Mixed':
                raise NotImplementedError
