import numpy as np
import pandas as pd
import os
import pickle
import matplotlib, h5py
if os.name == 'nt':
    matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib import cm
from scipy.interpolate import LinearNDInterpolator as interpolator
from scipy.spatial.transform import Rotation as R
import scipy.constants as csts
from pathlib import Path

from .simulation import IMPEDANCE_FREE_SPACE
from .grid import Grid as Grid

class Pos(object):
    ''' A position coordinate, or a vector. '''
    
    def __init__(self, x, y, z):
        self.x = x      
        self.y = y
        self.z = z
        self.pos = np.array([self.x, self.y, self.z])

    @classmethod
    def from_vec(cls, vec):
        return cls(vec[0], vec[1], vec[2])

    def vec_to(self, other_position):
        return other_position.pos - self.pos

    def dist_to(self, other_position):
        return np.linalg.norm(self.vec_to(other_position))

    @property
    def vec_size(self):
        return self.dist_to(Pos(0, 0, 0))

    def get_phi(self):
        ''' The angle from the x axis to the y axis. '''
        
        return np.arctan2(self.y, self.x)

    def get_theta(self):
        ''' The angle from the z axis.'''

        return np.arccos(np.clip(self.z/self.vec_size,-1,1))

    def normalize(self):
        self.pos = self.pos/self.vec_size
        self.x = self.pos[0]
        self.y = self.pos[1]
        self.z = self.pos[2]

        return self

    def rotate(self, phi):
        ''' Rotate the position around (0, 0, 0) clockwise in the (x, y) plane. '''
        
        rotation_matrix = np.array([[np.cos(phi),  np.sin(phi), 0],
                                    [-np.sin(phi), np.cos(phi), 0],
                                    [0,            0,           1]])
        self.pos = rotation_matrix @ self.pos
        self.x = self.pos[0]
        self.y = self.pos[1]
        self.z = self.pos[2]

        return self

    def discretize_on(self, grid, also_change_position=False):
        x_idx_after  = np.searchsorted(grid.x, self.x)
        x_idx_before = np.searchsorted(grid.x, self.x) - 1
        y_idx_after  = np.searchsorted(grid.y, self.y)
        y_idx_before = np.searchsorted(grid.y, self.y) - 1
        if not grid.is_2D:
            z_idx_after  = np.searchsorted(grid.z, self.z)
            z_idx_before = np.searchsorted(grid.z, self.z) - 1

        if x_idx_after == 0:
            x_idx_before = x_idx_after
        elif x_idx_after == len(grid.x):
            x_idx_after = x_idx_before
        if y_idx_after == 0:
            y_idx_before = y_idx_after
        elif y_idx_after == len(grid.y):
            y_idx_after = y_idx_before
        if not grid.is_2D:
            if z_idx_after == 0:
                z_idx_before = z_idx_after
            elif z_idx_after == len(grid.z):
                z_idx_after = z_idx_before

        x_dist_to_after  = abs(grid.x[x_idx_after]  - self.x)
        x_dist_to_before = abs(grid.x[x_idx_before] - self.x)
        y_dist_to_after  = abs(grid.y[y_idx_after]  - self.y)
        y_dist_to_before = abs(grid.y[y_idx_before] - self.y)
        if not grid.is_2D:
            z_dist_to_after  = abs(grid.z[z_idx_after]  - self.z)
            z_dist_to_before = abs(grid.z[z_idx_before] - self.z)

        if x_dist_to_after >= x_dist_to_before:
            self.x_idx = x_idx_before
        elif x_dist_to_after < x_dist_to_before:
            self.x_idx = x_idx_after
        if y_dist_to_after >= y_dist_to_before:
            self.y_idx = y_idx_before
        elif y_dist_to_after < y_dist_to_before:
            self.y_idx = y_idx_after
        if not grid.is_2D:
            if z_dist_to_after >= z_dist_to_before:
                self.z_idx = z_idx_before
            elif z_dist_to_after < z_dist_to_before:
                self.z_idx = z_idx_after

        if also_change_position:
            self.x = grid.x[self.x_idx]
            self.y = grid.y[self.y_idx]
            if not grid.is_2D:
                self.z = grid.z[self.z_idx]
            self.pos = np.array([self.x, self.y, self.z])

        return self

    def __add__(self, other):
        return Pos(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Pos(self.x - other.x, self.y - other.y, self.z - other.z)

class Antenna(object):
    ''' Represent some type of physical antenna. Is a singleton class that only returns antenna information like its directivity pattern. '''
    
    # def __new__(cls, type = 'SHAPE_antenna'):
    #     ''' Singleton functionality for each antenna type, so text files don't need to be run multiple times. '''
        
    #     if not hasattr(cls, 'instances'):
    #         cls.instances = {}
    #     if type not in cls.instances.keys():
    #         cls.instances[type] = super(Antenna, cls).__new__(cls)
            
    #         # initialize
    #         cls.instances[type].type = type
    #         cls.instances[type].set_directivity()
    #     return cls.instances[type]

    def __init__(self, type = 'SHAPE_antenna'):
        ''' Initialize the Antenna object with the specified type. '''
        self.type = type
        self.set_directivity()
        self.verbose = True
    
    def set_directivity(self):
        self.from_txt_file = False
        self.from_h5_file = False
        
        if self.type == 'SHAPE_antenna':
            self.from_txt_file = True
            self.txt_file_is_in_dB = True
        elif 'BM_' in self.type:
            self.from_txt_file = True
            self.txt_file_is_in_dB = False
        elif self.type == 'half_wave_dipole':
            self.set_half_wave_dipole_pattern()
        elif 'plane_wave_antenna' in self.type:
            self.from_h5_file = True
        elif self.type == 'omni':
            self.set_omni_pattern()

        if self.from_txt_file:
            self.directivity_path = Path(__file__).absolute().parent.parent / 'data/antenna_patterns' / f'{self.type}.txt'
            self.read_txt_file()
        if self.from_h5_file:
            self.directivity_path = Path(__file__).absolute().parent.parent / 'data/antenna_patterns' / f'{self.type}.h5'
            self.read_h5_file()
    
    def read_txt_file(self):
        ''' Reads a text file with the directivity pattern, generated by CST Studio. '''
        
        with open(self.directivity_path, 'r') as f:
            self.directivity = []
            for line in f.readlines()[2:]:
                self.directivity.append(np.array([float(word) for word in line.split()]))
            self.directivity = pd.DataFrame(np.array(self.directivity).T, index=['theta', 'phi', 'abs_gain', 'abs_theta', 'phase_theta', 'abs_phi', 'phase_phi', 'ax_ratio'])
        
        self.directivity.loc['theta'] = np.deg2rad(self.directivity.loc['theta'])
        self.directivity.loc['phi']   = np.deg2rad(self.directivity.loc['phi'])
        
        if self.txt_file_is_in_dB:
            self.directivity.loc['abs_gain']  = 10**(self.directivity.loc['abs_gain']/10)
            self.directivity.loc['abs_theta'] = 10**(self.directivity.loc['abs_theta']/10)
            self.directivity.loc['abs_phi']   = 10**(self.directivity.loc['abs_phi']/10)
        
        self.directivity.loc['phase_theta'] = np.deg2rad(self.directivity.loc['phase_theta'])
        self.directivity.loc['phase_phi']   = np.deg2rad(self.directivity.loc['phase_phi'])

        self.directivity.loc['phasor_theta'] = self.directivity.loc['abs_theta'] * np.exp(1j*self.directivity.loc['phase_theta'])
        self.directivity.loc['phasor_phi']   = self.directivity.loc['abs_phi']   * np.exp(1j*self.directivity.loc['phase_phi'])

        # copy data of phi = 0 to phi = 2pi, so that interpolation works
        extra = self.directivity.loc[:, self.directivity.loc['phi'] == 0]
        extra.loc['phi', self.directivity.loc['phi'] == 0] = 2*np.pi
        self.directivity = pd.concat([self.directivity, extra], axis=1)

    def read_h5_file(self):
        ''' Reads an h5 file with the far-field pattern, generated by Sim4Life. '''

        with h5py.File(self.directivity_path, mode='r+') as h5_file:
            key = list(h5_file['FieldGroups'].keys())[0]
            assert 'EM Far Field(theta,phi,f0)' in list(h5_file[f'FieldGroups/{key}/AllFields/'].keys())
            e_theta = h5_file[f'FieldGroups/{key}/AllFields/EM Far Field(theta,phi,f0)/_Object/Snapshots/0/comp0'][0, ...]
            e_phi = h5_file[f'FieldGroups/{key}/AllFields/EM Far Field(theta,phi,f0)/_Object/Snapshots/0/comp1'][0, ...]

            real_theta = e_theta[..., 0]
            imag_theta = e_theta[..., 1]
            e_theta = real_theta + 1j * imag_theta
            abs_theta = np.abs(e_theta)
            phase_theta = np.angle(e_theta)

            real_phi = e_phi[..., 0]
            imag_phi = e_phi[..., 1]
            e_phi = real_phi + 1j * imag_phi
            abs_phi = np.abs(e_phi)
            phase_phi = np.angle(e_phi)

            abs_gain = abs_theta + abs_phi

            nbr_thetas, nbr_phis = e_theta.shape
            thetas = np.deg2rad(np.linspace(0, 180, nbr_thetas))
            phis = np.deg2rad(np.linspace(0, 360, nbr_phis))
            thetas, phis = np.meshgrid(thetas, phis, indexing='ij')

            collection = [thetas, phis, abs_gain, real_theta, imag_theta, abs_theta, phase_theta, real_phi, imag_phi, abs_phi, phase_phi]
            self.directivity = pd.DataFrame(np.stack(collection,axis=-1).reshape(-1, len(collection), order='F').T, 
            index=['theta', 'phi', 'abs_gain', 'real_theta', 'imag_theta', 'abs_theta', 'phase_theta', 'real_phi', 'imag_phi', 'abs_phi', 'phase_phi'])

    def set_half_wave_dipole_pattern(self):
        # this used to be more elegant by passing the function directly, but it's not allowed if you want to pickle this class
        self.directivity = 'half_wave_dipole'
        return self.directivity

    def set_omni_pattern(self):
        self.directivity = 'omni_pattern'
        return self.directivity

    def set_theoretic_plane_wave_pattern(self):
        self.directivity = 'theoretic_plane_wave'
        return self.directivity

    def get_directivity(self, theta, phi, value = 'abs_gain'):
        if self.from_txt_file or self.from_h5_file:
            assert self.directivity is not None, f'Read a directivity file first for antenna type {self.type} before getting a directivity value.'
            
            # handle theta and phi angles out of their spherical coordinate ranges
            theta = theta % (2*np.pi)
            if isinstance(theta, np.ndarray) and isinstance(phi, np.ndarray):
                large_theta = theta > np.pi
                theta[large_theta] = theta[large_theta] - 2*np.pi

                neg_theta = theta < 0.
                theta[neg_theta] = -theta[neg_theta]
                phi[neg_theta] = phi[neg_theta] + np.pi 
            else:
                if theta > np.pi:
                    theta = theta - 2*np.pi
                if theta < 0.:
                    theta = -theta
                    phi = phi + np.pi

            theta = theta % (2*np.pi)
            phi = phi % (2*np.pi)
            
            if not hasattr(self, 'interpolators'):
                self.interpolators = {}

            if value not in self.interpolators:
                cached = False

                wrk_dir = self.directivity_path.parent

                if os.path.isfile(wrk_dir / f'caches/{self.type}_{value}.pkl'):
                    if self.verbose:
                        print('Loading interpolator for', str(value))
                    with open(wrk_dir / f'caches/{self.type}_{value}.pkl', 'rb') as f:
                        self.interpolators[value] = pickle.load(f)
                        cached = True

                if not cached:
                    if self.verbose:
                        print('Creating interpolator for', str(value))
                    self.interpolators[value] = interpolator(list(zip(self.directivity.loc['theta'], self.directivity.loc['phi'])), self.directivity.loc[value])

                    with open(wrk_dir / f'caches/{self.type}_{value}.pkl', 'wb') as f:
                        pickle.dump(self.interpolators[value], f)

            if isinstance(theta, np.ndarray) and isinstance(phi, np.ndarray):
                if theta.shape[0]*theta.shape[1] > 1000:
                    if self.verbose:
                        print(f'Interpolating antenna pattern {value} for antenna {self.type}')
            return self.interpolators[value](theta, phi)
        else:
            if self.directivity == 'half_wave_dipole':
                return np.cos(np.pi/2*np.cos(phi))/np.sin(phi+1e-8)
            
            elif self.directivity == 'omni_pattern':
                return np.ones(theta.shape) if isinstance(theta, np.ndarray) and isinstance(phi, np.ndarray) else 1
            
            elif self.directivity == 'theoretic_plane_wave':
                return np.exp(1j*2*np.pi * 10e9 / 3e8 * np.cos(theta))
            else:
                raise ValueError(f"Unknown directivity type: {self.directivity}")

    def plot_pattern(self, value = 'abs_gain', in_db = False, normalized = True, resolution = 100):
        ''' Creates a 3D plot with the antenna pattern and the 3 axes. The Z-axis is expected to be the propagation direction. '''
        
        grid = Grid(Pos(0, 0, 0), Pos(np.pi, 2*np.pi, 0), resolution = resolution, is_2D = True)

        values = np.zeros(grid.x_2D.shape)
        for i, theta in zip(grid.x_idx, grid.x):
            for j, phi in zip(grid.y_idx, grid.y):
                values[i, j] = self.get_directivity(theta, phi, value)
        if in_db:
            values = np.log10(values)*10
            values -= np.min(values[np.isfinite(values)])
            
        # make figure 
        figtitle = 'Antenna pattern of type ' + self.type 
        fig_existed = plt.fignum_exists(figtitle)
        fig = plt.figure(figsize=(10,8), num=figtitle)
        if fig_existed:
            plt.cla()
        #ax = fig.gca(projection='3d')
        ax = fig.add_subplot(111, projection='3d')
        if not fig_existed:
            ax.view_init(azim=20, elev=20)

        # plot axes
        Rmax = np.max(values[np.isfinite(values)])
        if bool(normalized):
            values /= Rmax
            axes_length = 1/Rmax * 1.5 * float(normalized)
        else:
            axes_length = 0.65
        ax.plot([0, axes_length*Rmax], [0, 0], [0, 0], linewidth=2, color='red', zorder = 0)
        ax.plot([0, 0], [0, axes_length*Rmax], [0, 0], linewidth=2, color='green', zorder = 0)
        ax.plot([0, 0], [0, 0], [0, axes_length*Rmax], linewidth=2, color='blue', zorder = 0)

        #values -= values.min() # uncomment for comparison with S4L for values that can be negative
        X = values * np.cos(grid.y_2D) * np.sin(grid.x_2D)
        Y = values * np.sin(grid.y_2D) * np.sin(grid.x_2D)
        Z = values * np.cos(grid.x_2D)
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, facecolors=cm.jet(values), antialiased=True, shade=True, alpha=1, zorder = 1)

        ax.set_xlim([-axes_length*Rmax, axes_length*Rmax])
        ax.set_ylim([-axes_length*Rmax, axes_length*Rmax])
        ax.set_zlim([-axes_length*Rmax, axes_length*Rmax])

        m = cm.ScalarMappable(cmap=cm.jet)
        m.set_array(values)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')

        fig.colorbar(m, shrink=0.8)
        ax.view_init(azim=20, elev=20)

        plt.pause(.1)
        plt.show()

class AntennaElement(Pos):
    ''' Part of an AntennaCollection. Is a position, has an orientation, an antenna, and has a power value. ''' 
    
    def __init__(self, x, y, z, antenna_type, antenna_size, id):
        Pos.__init__(self, x, y, z)
        #self.set_orientation(Pos(0, 1, 0)) # default value
        self.set_orientation(Pos(0, 0, 1))

        self.antenna = Antenna(antenna_type)
        self.antenna_size = antenna_size
        self.id = id

        self.power_W = 0 # default value
        self.set_verbose(True)

    # add a setter for verbosity
    def set_verbose(self, verbose):
        self.verbose = verbose
        self.antenna.verbose = verbose

    def set_orientation(self, orientation):
        ''' Sets the orientation of the antenna element, i.e., the propagation direction of the antenna. '''
        
        self.orientation = orientation; self.orientation.normalize()
        
        # compute the cross product of the z-axis and orientation
        z_axis = Pos(0,0,1) 
        rot_vec = Pos.from_vec(np.cross(z_axis.pos, self.orientation.pos))
        if rot_vec.vec_size == 0:
            rot_vec = Pos(0, 0, 0)
            angle = 0
        else:
            # normalize this vector and compute the angle between the z-axis and orientation
            rot_vec.normalize()
            angle = np.arccos(np.dot(z_axis.pos, self.orientation.pos))

        self.set_rot_vec(rot_vec, np.rad2deg(angle))

    def set_rot_vec(self, vec, angle):
        ''' Sets the rotation vector of the antenna element. Angle in degrees. '''
        
        if vec.vec_size == 0:
            self.rot_vec = np.array([0,0,1]) # default value

            # rotation matrix and inverse rotation and both the identity matrix
            self.rotation_matrix = R.from_rotvec(self.rot_vec*0)
            self.inverse_rotation_matrix = self.rotation_matrix.inv()
            return 
        else:
            vec.normalize()
            self.rot_vec = vec.pos * np.deg2rad(angle)
            self.rotation_matrix = R.from_rotvec(self.rot_vec)
            #extra_rotation = R.from_rotvec(np.array([0, 1, 0])*np.deg2rad(90))
            #self.rotation_matrix = extra_rotation * self.rotation_matrix
            self.inverse_rotation_matrix = self.rotation_matrix.inv()

            # remove floating point precision issues
            rotation_matrix = self.rotation_matrix.as_matrix()
            inverse_rotation_matrix = self.inverse_rotation_matrix.as_matrix()
            rotation_matrix[np.abs(rotation_matrix)<1e-14] = 0
            inverse_rotation_matrix[np.abs(inverse_rotation_matrix)<1e-14] = 0
            self.rotation_matrix = R.from_matrix(rotation_matrix)
            self.inverse_rotation_matrix = R.from_matrix(inverse_rotation_matrix)

    def get_propagation_direction(self):
        ''' Returns the propagation direction of the antenna element. '''
        
        return self.rotation_matrix.apply(Pos(0,0,1).pos)

    def get_directivity(self, theta, phi, value = 'abs_gain'):
        ''' Returns the directivity of the antenna element in the direction (theta, phi). '''
        
        u = Pos(np.sin(theta)*np.cos(phi), np.sin(theta)*np.sin(phi), np.cos(theta))
        return self.get_directivity_from_vec(u.pos, value)

    def get_directivity_from_vec(self, u, value = 'abs_gain'):
        ''' Returns the directivity of the oriented antenna element in the direction u. '''

        rotated_u = self.inverse_rotation_matrix.apply(u)
        rotated_u = Pos(rotated_u[0], rotated_u[1], rotated_u[2])

        return self.antenna.get_directivity(rotated_u.get_theta(), rotated_u.get_phi(), value)

    def get_directivity_from_vecs(self, value = 'abs_gain'):
        ''' 
        The same as get_directivity_from_vec, but for multiple vectors and more efficient. 
        Provide u_length if you already computed it. 
        '''

        return self.antenna.get_directivity(self.theta_3D, self.phi_3D, value)

    def plot_pattern(self, value = 'abs_gain', in_db = False, normalized = True, resolution = 100, ax = None, stride = 1, alpha = 0.1, only_orientation = False):
        ''' Creates a 3D plot with the oriented antenna pattern and the 3 axes. The propagation vector is shown in black. '''
        
        grid = Grid(Pos(0, 0, 0), Pos(np.pi, 2*np.pi, 0), resolution=resolution, is_2D=True)

        if not only_orientation:
            values = np.zeros(grid.x_2D.shape)
            for i, theta in zip(grid.x_idx, grid.x):
                for j, phi in zip(grid.y_idx, grid.y):
                    values[i, j] = self.get_directivity(theta, phi, value)
            if in_db:
                values = np.log10(values)*10
                values -= np.min(values[np.isfinite(values)])
            
        # make figure
        if ax is None:
            plotting_on_given_ax = False
            figtitle = 'Antenna pattern of element ' + str(self.id) + ' (' + self.antenna.type + ')' 
            fig_existed = plt.fignum_exists(figtitle)
            fig = plt.figure(figsize=(10,8), num=figtitle)
            if fig_existed:
                plt.clf()
            #ax = fig.gca(projection='3d')
            ax = fig.add_subplot(111, projection='3d')
            if not fig_existed:
                ax.view_init(azim=20, elev=20)
        else:
            plotting_on_given_ax = True

        # plot axes
        if not only_orientation:
            Rmax = np.max(values[np.isfinite(values)])
            if bool(normalized):
                values /= Rmax
                axes_length = 1/Rmax * 1.3 * float(normalized)
            else:
                axes_length = 0.65
        else:
            Rmax = 1
            axes_length = 0.65

        # Scale based on axis limits
        if plotting_on_given_ax:
            x_limits = ax.get_xlim3d()
            y_limits = ax.get_ylim3d()
            z_limits = ax.get_zlim3d()
            x_range = x_limits[1] - x_limits[0]
            y_range = y_limits[1] - y_limits[0]
            z_range = z_limits[1] - z_limits[0]
        else:
            # no scaling required
            x_range = 1
            y_range = 1
            z_range = 1

        origin = Pos(self.x, self.y, self.z)
        if not plotting_on_given_ax:
            ax.plot([origin.x, origin.x + axes_length*Rmax*x_range], [origin.y, origin.y], [origin.z, origin.z], linewidth=2, color='red', zorder = 0)
            ax.plot([origin.x, origin.x], [origin.y, origin.y + axes_length*Rmax*y_range], [origin.z, origin.z], linewidth=2, color='green', zorder = 0)
            ax.plot([origin.x, origin.x], [origin.y, origin.y], [origin.z, origin.z + axes_length*Rmax*z_range], linewidth=2, color='blue', zorder = 0)        

        if normalized != False:
            scale = normalized
        else:
            scale = 1

        if not only_orientation:
            #values -= values.min() # uncomment for comparison with S4L for values that can be negative
            X = values * np.cos(grid.y_2D) * np.sin(grid.x_2D)
            Y = values * np.sin(grid.y_2D) * np.sin(grid.x_2D)
            Z = values * np.cos(grid.x_2D)

            X *= scale*x_range
            Y *= scale*y_range
            Z *= scale*z_range

            X += origin.x
            Y += origin.y
            Z += origin.z

            ax.plot_surface(X, Y, Z, rstride=stride, cstride=stride, facecolors=cm.jet(values), antialiased=True, shade=True, alpha=0.1, zorder = 1)

        # plot propagation direction
        u = self.get_propagation_direction()
        ax.plot([origin.x, origin.x + u[0]*scale*x_range], [origin.y, origin.y + u[1]*scale*y_range], [origin.z, origin.z + u[2]*scale*z_range], linewidth=2, color='black', zorder = 2)

        if not plotting_on_given_ax:
            ax.set_xlim([origin.x - axes_length*Rmax, origin.x + axes_length*Rmax])
            ax.set_ylim([origin.y - axes_length*Rmax, origin.y + axes_length*Rmax])
            ax.set_zlim([origin.z - axes_length*Rmax, origin.z + axes_length*Rmax])

        if not only_orientation:
            m = cm.ScalarMappable(cmap=cm.jet)
            m.set_array(values)

        if not plotting_on_given_ax:
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')

        if not plotting_on_given_ax:
            if not fig_existed:
                self.cb = fig.colorbar(m, shrink=0.8)

        #plt.pause(.1)
        if not plotting_on_given_ax:
            plt.show()

    def compute_local_grid_variables(self, grid):
        ''' Grid parameters w.r.t. the antenna element. '''
        
        if self.antenna.type != 'omni':
            method = 1
        else:
            method = 2

        # connecting vectors between the grid points and the antenna element
        if not grid.is_2D:
            self.x_3D = grid.x_3D - self.x
            self.y_3D = grid.y_3D - self.y
            self.z_3D = grid.z_3D - self.z

            # Slow method, but necessary if the antenna is not omnidirectional
            if method == 1:
                self.r_3D = np.sqrt(self.x_3D**2 + self.y_3D**2 + self.z_3D**2)
                self.r_3D[self.r_3D<2e-15] = 2e-15 # avoid division by zero errors

                # convert u to a (Nx.Ny.Nz, 3) array
                grid_shape = self.x_3D.shape
                x_flat = self.x_3D.flatten()
                y_flat = self.y_3D.flatten()
                z_flat = self.z_3D.flatten()
                r_flat = self.r_3D.flatten()
                u = np.array([x_flat, y_flat, z_flat]).T
                
                # rotate and convert to thetas and phis
                rotated_u = self.inverse_rotation_matrix.apply(u)
                self.theta_3D = np.arccos(np.clip(rotated_u[:, 2] / r_flat, -1, 1)) # due to floating point errors, argument can be slightly outside the range [-1, 1]
                self.phi_3D = np.arctan2(rotated_u[:, 1], rotated_u[:, 0])

                # reshape back to grid shape
                self.theta_3D = self.theta_3D.reshape(grid_shape)
                self.phi_3D = self.phi_3D.reshape(grid_shape)

                # use the unrotated u to compute the angles in the global coordinate system
                theta_global_3D = np.arccos(np.clip(u[:, 2] / r_flat, -1, 1)) # due to floating point errors, argument can be slightly outside the range [-1, 1]
                phi_global_3D = np.arctan2(u[:, 1], u[:, 0])

                # reshape back to grid shape
                theta_global_3D = theta_global_3D.reshape(grid_shape)
                phi_global_3D = phi_global_3D.reshape(grid_shape)

                # compute the unit vectors in the global unrotated coordinate system (but translated ofc)
                self.u_theta = np.zeros((3, grid_shape[0], grid_shape[1], grid_shape[2]))
                self.u_theta[0, :, :, :] = np.cos(theta_global_3D) * np.cos(phi_global_3D)
                self.u_theta[1, :, :, :] = np.cos(theta_global_3D) * np.sin(phi_global_3D)
                self.u_theta[2, :, :, :] = -np.sin(theta_global_3D)

                self.u_phi = np.zeros((3, grid_shape[0], grid_shape[1], grid_shape[2]))
                self.u_phi[0, :, :, :] = -np.sin(phi_global_3D)
                self.u_phi[1, :, :, :] = np.cos(phi_global_3D)

            # Fast method, only possible for omnidirectional antennas
            elif method == 2:
                # skip computing thetas and phis entirely (directivity is isotropic)
                # find u_theta and u_phi based on these formulas
                # in small tests this is 40% faster than the above method

                r2_XY = self.x_3D**2 + self.y_3D**2
                self.r_3D = np.sqrt(r2_XY + self.z_3D**2)
                self.r_3D[self.r_3D<2e-15] = 2e-15 # avoid division by zero errors
                ux_3D = self.x_3D / self.r_3D
                uy_3D = self.y_3D / self.r_3D
                uz_3D = self.z_3D / self.r_3D
                n = np.sqrt(r2_XY) / self.r_3D
                n[n<2e-15] = 2e-15 # avoid division by zero errors
                self.u_theta = np.zeros((3, *grid.shape))
                self.u_phi = np.zeros((3, *grid.shape))
                self.u_theta[0, ...] = ux_3D * uz_3D / n
                self.u_theta[1, ...] = uy_3D * uz_3D / n
                self.u_theta[2, ...] = -n
                self.u_phi[0, ...] = -uy_3D / n
                self.u_phi[1, ...] = ux_3D / n
        else:
            self.x_2D = grid.x_2D - self.x
            self.y_2D = grid.y_2D - self.y

            self.r_2D = np.sqrt(self.x_2D**2 + self.y_2D**2)
            self.r_2D[self.r_2D<2e-15] = 2e-15 
        
            self.theta_2D = np.arctan2(self.y_2D, self.x_2D) # angle to the global x axis or local y axis
            self.theta_2D = np.pi/2 - self.theta_2D # convert to the in-plane angle to the normal (global y, local z)
            self.angle_to_normal = np.pi/2 - self.orientation.get_phi()
            self.theta_2D = self.theta_2D - self.angle_to_normal # substraction because positive angle_to_normal should mean theta is lower
            self.phi_2D = np.zeros(self.theta_2D.shape) + np.deg2rad(0) 

    def compute_fields(self, simulation, grid = None):
        ''' Compute the electromagnetic fields of this antenna element. '''
        
        # Custom grids are sliced grids
        if grid is None:
            grid = simulation.grid
        else:
            assert simulation.use_sliced_grid
        
        # Pre-processing variables
        self.compute_local_grid_variables(grid)
        
        if not grid.is_2D:
            pw_factor = np.exp(1j * 2. * np.pi * simulation.frequency / csts.speed_of_light * (self.r_3D)) / self.r_3D
            #directivity_factor_theta = self.get_directivity_from_vecs(value='abs_theta') * np.exp(1j*self.get_directivity_from_vecs(value='phase_theta'))
            #directivity_factor_phi = self.get_directivity_from_vecs(value='abs_phi') * np.exp(1j*self.get_directivity_from_vecs(value='phase_phi'))
            if self.antenna.type == 'omni':
                directivity_factor_theta = 1
                directivity_factor_phi = 0
                if self.verbose:
                    print('Note: using a vertically polarized omnidirectional antenna.')
            else:
                directivity_factor_theta = self.get_directivity_from_vecs(value='phasor_theta')
                directivity_factor_phi = self.get_directivity_from_vecs(value='phasor_phi')
        else:
            pw_factor = np.exp(1j * 2. * np.pi * simulation.frequency / csts.speed_of_light * (self.r_2D)) / self.r_2D

            # Note the minus 
            directivity_factor_abs   = -self.antenna.get_directivity(self.theta_2D, self.phi_2D, value='abs_phi') 
            directivity_factor_phase = self.antenna.get_directivity(self.theta_2D, self.phi_2D, value='phase_phi')
            directivity_factor = directivity_factor_abs * np.exp(1j*directivity_factor_phase)

        if self.antenna.type == 'half_wave_dipole':
            current=np.sqrt(self.power_W/36.4)
        else:
            #raise NotImplementedError
            current = 1
            if self.verbose:
                print('Warning: current of SHAPE antennae not implemented.')
        power_factor = current*IMPEDANCE_FREE_SPACE/(2*np.pi)

        if not simulation.grid.is_2D:
            combined_factor = pw_factor*power_factor
            
            if simulation.use_sliced_grid:
                self.E_subgrid[grid.name] = combined_factor * (directivity_factor_theta * self.u_theta + directivity_factor_phi * self.u_phi)
                self.H_subgrid[grid.name] = 1/IMPEDANCE_FREE_SPACE * combined_factor * (directivity_factor_theta * self.u_phi - directivity_factor_phi * self.u_theta)
            else:
                self.E = combined_factor * (directivity_factor_theta * self.u_theta + directivity_factor_phi * self.u_phi)
                self.H = 1/IMPEDANCE_FREE_SPACE * combined_factor * (directivity_factor_theta * self.u_phi - directivity_factor_phi * self.u_theta)
        else:
            combined_factor = pw_factor*directivity_factor*power_factor

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

    def prune_near_field(self, simulation, grid=None):
        ''' Replace any electromagnetic fields of this antenna element that is within the near-field distance with NaN. '''

        # Custom grids are sliced grids
        if grid is None:
            grid = simulation.grid
        else:
            assert simulation.use_sliced_grid

        if not simulation.grid.contains(self):
            return

        self.far_field_distance = 2*self.antenna_size**2/simulation.wavelength
        
        # A circle around the receiver is set to nan
        subgrid = grid.get_subgrid(self, self.far_field_distance * 2) # diameter = 2 * radius
        if grid.is_2D:
            _, points_idx = subgrid.get_circle(center = self.pos, radius = self.far_field_distance)
        else:
            _, points_idx = subgrid.get_sphere(center = self.pos, radius = self.far_field_distance)
        for point_idx in points_idx:
            if not grid.is_2D:
                self.E[:, point_idx[0], point_idx[1], point_idx[2]] = np.nan*np.ones(3)
                self.H[:, point_idx[0], point_idx[1], point_idx[2]] = np.nan*np.ones(3)
            elif grid.is_2D:
                if simulation.polarization == 'TEz':
                    self.Ez[point_idx[0], point_idx[1]] = np.nan
                    self.Hx[point_idx[0], point_idx[1]] = np.nan
                    self.Hy[point_idx[0], point_idx[1]] = np.nan
                elif simulation.polarization == 'TMz':
                    self.Hz[point_idx[0], point_idx[1]] = np.nan
                    self.Ex[point_idx[0], point_idx[1]] = np.nan
                    self.Ey[point_idx[0], point_idx[1]] = np.nan
                elif simulation.polarization == 'Mixed':
                    raise NotImplementedError

        # Just a box
        '''
        p1 = Pos(self.x - self.far_field_distance, self.y - self.far_field_distance).discretize_on(grid)
        p2 = Pos(self.x + self.far_field_distance, self.y + self.far_field_distance).discretize_on(grid)
        for x_idx in grid.x_idx[p1.x_idx:p2.x_idx]:
            for y_idx in simulation.grid.y_idx[p1.y_idx:p2.y_idx]:
                if simulation.polarization == 'TEz':
                    self.Ez[x_idx, y_idx] = np.nan
                elif simulation.polarization == 'TMz':
                    self.Hz[x_idx, y_idx] = np.nan
                elif simulation.polarization == 'Mixed':
                    raise NotImplementedError
        '''

    def clear_unimportant_data(self, also_clear_fields=False):
        ''' Clear all intermediary data that is not needed for the simulation. '''

        if also_clear_fields:
            self.E = 'cleared'
            self.H = 'cleared'
            self.E_subgrid = 'cleared'
            self.H_subgrid = 'cleared'
        self.x_3D = 'cleared'
        self.y_3D = 'cleared'
        self.z_3D = 'cleared'
        self.r_3D = 'cleared'
        self.theta_3D = 'cleared'
        self.phi_3D = 'cleared'
        self.u_theta = 'cleared'
        self.u_phi = 'cleared'


