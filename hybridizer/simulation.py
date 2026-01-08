import numpy as np
import scipy.sparse as sp
from copy import deepcopy
from tqdm import tqdm
import matplotlib
import os
if os.name == 'nt':
    matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.colors import TwoSlopeNorm
#from matplotlib.colors import DivergingNorm #use DivergingNorm for older matplotlib
import scipy
import scipy.constants as csts
from scipy.signal import find_peaks, peak_widths, peak_prominences
import time
from pathlib import Path
import pickle
import h5py

IMPEDANCE_FREE_SPACE = np.sqrt(csts.mu_0/(csts.epsilon_0))
        
class DeterministicSimulation(object):
    ''' Composed of a Grid, a collection of radiating elements (base station AntennaCollection or scatterers ClusterCollection) and a receiver AntennaCollection. Computes the total field on the positions of the grid with beamforming. Plots the output. '''

    def __init__(self, grid, base_station, receivers, clusters = None, polarization = 'TEz', frequency=3.6e9, scene = 'tmp', verbose = True):
        self.grid = grid

        self.base_station = base_station
        if self.base_station is None:
            self.clusters = clusters
            self.radiating_collection = self.clusters
        else:
            self.radiating_collection = self.base_station
            
        self.receivers = receivers
        
        self.frequency = frequency
        self.wavelength = csts.speed_of_light / self.frequency
        self.polarization = polarization

        self.set_verbose(verbose)

        if not self.grid.is_2D:
            self.cpw = (self.wavelength/self.grid.dx, self.wavelength/self.grid.dy, self.wavelength/self.grid.dz)
        else:
            self.cpw = (self.wavelength/self.grid.dx, self.wavelength/self.grid.dy)
        self.cpw_min = min(self.cpw)
        if self.cpw_min < 1 and self.verbose:
            print('Warning: The grid is too rough for the given frequency because cpw = {:.2f} < 1.'.format(self.cpw_min))
        
        if self.verbose:
            if not self.grid.is_2D:
                print(f'dx = {self.grid.dx*100:.2f} cm, lambda = {self.wavelength*100:.2f} cm, CPW = ({self.cpw[0]:.2f}, {self.cpw[1]:.2f}, {self.cpw[2]:.2f}).')
            else:
                print(f'dx = {self.grid.dx*100:.2f} cm, lambda = {self.wavelength*100:.2f} cm, CPW = {self.cpw[0]:.2f}, {self.cpw[1]:.2f}.')

        self.use_sliced_grid = False
        if not self.grid.is_2D:
            self.E = np.zeros((3,)+self.grid.shape, dtype=np.csingle)
            self.H = np.zeros((3,)+self.grid.shape, dtype=np.csingle)
        else:
            if self.polarization == 'TEz':
                self.Ez = np.zeros(self.grid.shape, dtype=np.csingle)
                self.Hx = np.zeros(self.grid.shape, dtype=np.csingle)
                self.Hy = np.zeros(self.grid.shape, dtype=np.csingle)
            elif self.polarization == 'TMz':
                self.Hz = np.zeros(self.grid.shape, dtype=np.csingle)
                self.Ex = np.zeros(self.grid.shape, dtype=np.csingle)
                self.Ey = np.zeros(self.grid.shape, dtype=np.csingle)
            elif self.polarization == 'Mixed':
                raise NotImplementedError

        self.channel_matrix = None
        self.precoding_matrix = None

        self.set_verbose(True)
        self.use_existing_shown_value = False
        path_of_file = Path(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = path_of_file.parent / 'caches'
        self.scene = scene

    def set_verbose(self, verbose):
        self.verbose = verbose
        self.radiating_collection.set_verbose(verbose)
        self.receivers.set_verbose(verbose)

    def make_sliced_grid(self, thickness, distance_from_center = None, distance_from_sides = None, rx_size = None):
        ''' Adds a set of sliced grids to the simulation and a set of grids around each of the receivers. '''

        self.use_sliced_grid = True

        self.E_subgrid = {}
        self.H_subgrid = {}

        self.sliced_subgrids = self.grid.get_all_subgrid_slices(thickness, distance_from_center = distance_from_center, distance_from_sides = distance_from_sides)
        for name, subgrid in self.sliced_subgrids.items():
            self.E_subgrid[name] = np.zeros((3,)+subgrid.shape, dtype=np.csingle)
            self.H_subgrid[name] = np.zeros((3,)+subgrid.shape, dtype=np.csingle)
        
        self.rx_subgrids = {}
        for rx in self.receivers.antenna_elements:
            rx.discretize_on(self.grid)
            if rx_size is None:
                rx_size = self.grid.dx*2
            self.rx_subgrids[f'rx{rx.id}'] = self.grid.get_subgrid(rx, rx_size)
            self.rx_subgrids[f'rx{rx.id}'].name = f'rx{rx.id}'
        
        for name, subgrid in self.rx_subgrids.items():
            self.E_subgrid[name] = np.zeros((3,)+subgrid.shape, dtype=np.csingle)
            self.H_subgrid[name] = np.zeros((3,)+subgrid.shape, dtype=np.csingle)

    def compute_channel_matrix(self, scrambled = False, using_Ey=False):
        ''' Computes the channel matrix. Setting scrambled to True will randomize the phases of each element in the matrix. '''
         
        # avoid circular imports
        from .antenna import Pos
        
        assert self.radiating_collection.nbr_elements != 0, 'Add elements to base station first'
        assert self.receivers.nbr_elements != 0, 'Add elements to receivers first'
        self.channel_matrix = np.matrix(np.empty((self.receivers.nbr_elements, self.radiating_collection.nbr_elements), dtype=np.csingle))

        for tx in tqdm(self.radiating_collection.elements, disable=(not self.verbose)):
            # Compute the electric field of this antenna element radiating with equal power
            if self.use_sliced_grid:
                tx.E_subgrid = {}
                tx.H_subgrid = {}
                for subgrid in {**self.sliced_subgrids, **self.rx_subgrids}.values():
                    tx.compute_fields(self, grid=subgrid)
                    #tx.prune_near_field(self, grid=subgrid) #TODO
                    tx.clear_unimportant_data(also_clear_fields=False) # for memory efficiency
            else:
                tx.compute_fields(self)
                #tx.prune_near_field(self)

            # Measure the electric field at each of the receivers to construct the channel matrix
            for rx in self.receivers.antenna_elements:
                if not self.grid.is_2D:
                    if self.use_sliced_grid:
                        rx.discretize_on(self.rx_subgrids[f'rx{rx.id}'])
                        incoming_E_field = tx.E_subgrid[f'rx{rx.id}'][:,rx.x_idx, rx.y_idx, rx.z_idx]
                        rx.discretize_on(self.grid)
                    else:
                        rx.discretize_on(self.grid)
                        incoming_E_field = tx.E[:,rx.x_idx, rx.y_idx, rx.z_idx]
                    '''
                    u = Pos.from_vec(tx.vec_to(rx)).normalize()
                    F = rx.get_directivity_from_vec(u, value='abs_gain')
                    channel_coeff = np.dot(incoming_E_field, F)
                    '''
                    u = Pos.from_vec(rx.vec_to(tx)).normalize()
                    theta = u.get_theta()
                    phi = u.get_phi()
                    u_theta = np.array([np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)])
                    if not using_Ey:
                        channel_coeff = np.dot(incoming_E_field, u_theta)
                    else:
                        channel_coeff = np.dot(incoming_E_field, np.array([0., 1., 0.]))
                else:
                    rx.discretize_on(self.grid)
                    if self.polarization == 'TEz':
                        channel_coeff = tx.Ez[rx.x_idx, rx.y_idx]
                    elif self.polarization == 'TMz':
                        raise NotImplementedError
                        #incoming_Ez_field = tx.Ey[rx.x_idx, rx.y_idx, rx.z_idx]
                    elif self.polarization == 'Mixed':
                        raise NotImplementedError

                self.channel_matrix[rx.id, tx.id] = channel_coeff 

        # Scramble the phases of the channel matrix so the precoding effectively does not work 
        if scrambled:
            self.channel_matrix = np.matrix(np.array(self.channel_matrix) * np.exp(1j*2*np.pi*np.random.rand(*self.channel_matrix.shape)))

    def compute_precoding_matrix(self, scheme = 'MRT'):
        ''' Computes the precoding matrix with Frobenius norm. '''

        if scheme == 'MRT':
            self.precoding_matrix = self.channel_matrix.H 
        elif scheme == 'ZF':
            self.precoding_matrix = self.channel_matrix.H @ np.linalg.inv(self.channel_matrix @ self.channel_matrix.H) 
        self.precoding_matrix /= np.linalg.norm(self.precoding_matrix, 'fro')

    def focus(self, symbol=None, write_subgrid_data_to_grid=True):
        ''' Uses the precoding matrix to focus the fields onto the symbol. '''

        assert hasattr(self, 'precoding_matrix'), 'No precoding matrix yet. Run the simulation first before focusing.'
        #assert self.radiating_collection.collection_type == 'antenna_collection', 'Only base stations can focus.'
        
        # Default to focus on the first element
        if symbol is None:
            symbol = np.zeros(self.receivers.nbr_elements)
            symbol[0] = 1 
        # Check that the symbol consists of only zeros and just one 1
        if np.sum(symbol) == 1 and np.sum(symbol == 0) == len(symbol) - 1:
            # Single rx focus scenario
            self.focused_rx_nbr = np.argmax(symbol)
        symbol = np.matrix(symbol).T
        #self.base_station.weights = (self.precoding_matrix @ symbol).A1 
        self.radiating_collection.weights = (self.precoding_matrix @ symbol).A1 

        # Combine the fields with the approriate weights
        for tx, weight in zip(self.radiating_collection.elements, self.radiating_collection.weights):
            if not self.grid.is_2D:
                if self.use_sliced_grid:
                    for name, E_subgrid in tx.E_subgrid.items():
                        self.E_subgrid[name] += weight * E_subgrid
                    for name, H_subgrid in tx.H_subgrid.items():
                        self.H_subgrid[name] += weight * H_subgrid
                else:
                    self.E += weight * tx.E
                    self.H += weight * tx.H
            else:
                if self.polarization == 'TEz':
                    self.Ez += weight * tx.Ez 
                    self.Hx += weight * tx.Hx
                    self.Hy += weight * tx.Hy
                elif self.polarization == 'TMz':
                    self.Hz += weight * tx.Hz  
                    self.Ex += weight * tx.Ex
                    self.Ey += weight * tx.Ey
                elif self.polarization == 'Mixed':
                    raise NotImplementedError

        if self.use_sliced_grid and write_subgrid_data_to_grid:
            for name, subgrid in {**self.sliced_subgrids, **self.rx_subgrids}.items():
                # Do not add but set, because some pieces overlap
                self.E[:, subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice] = self.E_subgrid[name]
                self.H[:, subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice] = self.H_subgrid[name]

                # The subgrids are blocks of data in the global grid
                # The problem is that the full E and H grids take a lot of memory
                # We want to use scipy.sparse to store the data
                # But scipy.sparse does not support 4D matrices

    def custom_weighting(self, weights=None, all_ones=True):
        ''' Use a specific weighting for the base station elements. '''
        
        # An efficient check if fields are empty
        if not self.grid.is_2D:
            if self.E[0,0,0,0] != 0 or self.E[1,0,0,0] != 0 or self.E[2,0,0,0] != 0 or self.H[0,0,0,0] != 0 or self.H[1,0,0,0] != 0 or self.H[2,0,0,0] != 0:
                raise ValueError('The fields have already been computed. Reset the simulation first.')
        
        if all_ones:
            if weights is not None:
                if self.verbose:
                    print('WARNING: all_ones is True, so the weights are ignored.')
            self.radiating_collection.weights = np.ones((self.radiating_collection.nbr_elements))
        else:
            self.radiating_collection.weights = weights

        # Combine the fields with the approriate weights
        for tx, weight in zip(self.radiating_collection.elements, self.radiating_collection.weights):
            if self.use_sliced_grid:
                for name, E_subgrid in tx.E_subgrid.items():
                    self.E_subgrid[name] += weight * E_subgrid
                for name, H_subgrid in tx.H_subgrid.items():
                    self.H_subgrid[name] += weight * H_subgrid
            else:
                if not self.grid.is_2D:
                    self.E += weight * tx.E
                    self.H += weight * tx.H
                else:
                    if self.polarization == 'TEz':
                        self.Ez += weight * tx.Ez 
                        self.Hx += weight * tx.Hx
                        self.Hy += weight * tx.Hy
                    elif self.polarization == 'TMz':
                        self.Hz += weight * tx.Hz  
                        self.Ex += weight * tx.Ex
                        self.Ey += weight * tx.Ey
                    elif self.polarization == 'Mixed':
                        raise NotImplementedError

    def custom_channel_matrix(self, imposed_channel_matrix, use_cached_channel_matrix=False):
        ''' This function uses an already computed channel matrix to normalize the antenna element weights such that the desired channel matrix is obtained. '''

        if use_cached_channel_matrix:
            with open(f'{self.cache_dir}/channel_matrix.pkl', 'rb') as f:
                self.channel_matrix = pickle.load(f)

        # Some basic checks
        assert self.channel_matrix is not None, 'No channel matrix yet. Run the simulation first before focusing.'
        assert self.channel_matrix[0,0] != 0, 'The channel matrix is empty. Run the simulation first so the antenna elements can be normalized to the new channel matrix.'
        assert imposed_channel_matrix.shape == self.channel_matrix.shape, 'The imposed channel matrix has the wrong shape.'
        assert imposed_channel_matrix.shape[0] == 1, 'Only single rx focus scenario is implemented.' # TODO: implement multi rx, which is just asserting that the ratios of value between txs is the same between both matrices

        weights = np.array(imposed_channel_matrix[0,:])[0] / np.array(self.channel_matrix[0,:])[0]

        # Reset the fields
        if not self.grid.is_2D:
            self.E = 0 * self.E
            self.H = 0 * self.H
        else:
            if self.polarization == 'TEz':
                self.Ez = 0 * self.Ez
                self.Hx = 0 * self.Hx
                self.Hy = 0 * self.Hy
            elif self.polarization == 'TMz':
                self.Hz = 0 * self.Hz
                self.Ex = 0 * self.Ex
                self.Ey = 0 * self.Ey
            elif self.polarization == 'Mixed':
                raise NotImplementedError

        self.radiating_collection.weights = weights
        for tx, weight in zip(self.radiating_collection.elements, self.radiating_collection.weights):
            tx.E = weight * tx.E
            tx.H = weight * tx.H

        self.custom_weighting(all_ones=True)

    def efficient_cluster_addition(self):
        ''' Instead of computing a channel matrix which hold all the EMF data for each cluster, to then just add them with equal weights,
        this function will loop over the clusters and keep adding the fields to the grid. It is more memory efficient. '''

        # avoid circular imports
        from .antenna import Pos
        
        assert self.receivers.nbr_elements != 0, 'Add elements to receivers first'
        # An efficient check if fields are empty
        if not self.grid.is_2D:
            if self.E[0,0,0,0] != 0 or self.E[1,0,0,0] != 0 or self.E[2,0,0,0] != 0 or self.H[0,0,0,0] != 0 or self.H[1,0,0,0] != 0 or self.H[2,0,0,0] != 0:
                raise ValueError('The fields have already been computed. Reset the simulation first.')

        for tx in tqdm(self.radiating_collection.elements, disable=(not self.verbose)):
            # Compute the electric field of this antenna element radiating with equal power
            if self.use_sliced_grid:
                tx.E_subgrid = {}
                tx.H_subgrid = {}
                for subgrid in self.sliced_subgrids.values():
                    tx.compute_fields(self, grid=subgrid)
                    #tx.prune_near_field(self, grid=subgrid) #TODO
                for name, E_subgrid in tx.E_subgrid.items():
                    self.E_subgrid[name] += E_subgrid
                for name, H_subgrid in tx.H_subgrid.items():
                    self.H_subgrid[name] += H_subgrid
            else:
                tx.compute_fields(self)
                #tx.prune_near_field(self)

                if not self.grid.is_2D:
                    self.E += tx.E
                    self.H += tx.H
                else:
                    if self.polarization == 'TEz':
                        self.Ez += tx.Ez 
                        self.Hx += tx.Hx
                        self.Hy += tx.Hy
                    elif self.polarization == 'TMz':
                        self.Hz += tx.Hz  
                        self.Ex += tx.Ex
                        self.Ey += tx.Ey
                    elif self.polarization == 'Mixed':
                        raise NotImplementedError

            tx.clear_unimportant_data(also_clear_fields=True) # for memory efficiency

    def run(self, symbol = None, scrambled_channel = False, write_subgrid_data_to_grid = True):
        t0 = time.perf_counter()
        
        self.compute_channel_matrix(scrambled = scrambled_channel)
        self.compute_precoding_matrix()
        self.focus(symbol=symbol, write_subgrid_data_to_grid = write_subgrid_data_to_grid)
        
        t1=time.perf_counter()
        if self.verbose:
            print(f'Execution time of run was {t1-t0:.2f} seconds.')

    def cache_channel_matrix(self):
        ''' Cache the channel matrix to a pickle file. '''

        raise NotImplementedError('You also need to cache the electric and magnetic fields of each of the antenna elements')

        with open(f'{self.cache_dir}/channel_matrix.pkl', 'wb') as f:
            pickle.dump(self.channel_matrix, f)

    def export_incident_field(self, rx_nbr, grid_size=None):
        if self.verbose:
            print('Warning: export_incident_field is deprecated. Use export_incident_field_ascii instead.')
        self.export_incident_field_ascii(rx_nbr, grid_size=grid_size)

    def export_incident_field_ascii(self, rx_nbr, grid_size=None):
        ''' Export the EMFs in the simulation in a subgrid around the receiver to a .txt file that is read for the Huygen's box in Sim4Life. '''

        rx = self.receivers.antenna_elements[rx_nbr]

        if grid_size is None:
            margin_amount_of_cells = 3
            x_size = np.abs(self.grid.x[margin_amount_of_cells] - self.grid.x[-margin_amount_of_cells])
            y_size = np.abs(self.grid.y[margin_amount_of_cells] - self.grid.y[-margin_amount_of_cells])
            z_size = np.abs(self.grid.z[margin_amount_of_cells] - self.grid.z[-margin_amount_of_cells])
            grid_size = np.array([x_size, y_size, z_size])
            grid_size = np.array([0.22, 0.165, 0.235]) * 0.7
        subgrid = self.grid.get_subgrid(rx, grid_size)
        if not subgrid.is_2D:
            if self.polarization == 'TEz':
                E_field = self.E[:, subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice]
                H_field = self.H[:, subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice]
                field = [E_field, H_field]
            else:
                raise NotImplementedError
        else:
            if self.polarization == 'TEz':
                field = self.Ez[subgrid.x_2D_idx_global_slice, subgrid.y_2D_idx_global_slice]
            elif self.polarization == 'TMz':
                field = self.Hz[subgrid.x_2D_idx_global_slice, subgrid.y_2D_idx_global_slice]
            elif self.polarization == 'Mixed':
                raise NotImplementedError

        path_of_this_file = Path(os.path.dirname(os.path.abspath(__file__)))
        with open(path_of_this_file.parent + f'data/{self.scene}/python/current_exposure_field.txt', 'w') as f:
            f.write('<huygens>\n')
            
            f.write('<axes>\n')
            '''
            f.write(f'{subgrid.x[0] - subgrid.center.x} {subgrid.x.size} {subgrid.dx}\n')
            f.write(f'{subgrid.y[0] - subgrid.center.y} {subgrid.y.size} {subgrid.dy}\n')
            f.write(f'{subgrid.z[0] - subgrid.center.z} {subgrid.z.size} {subgrid.dz}\n')
            '''
            f.write(f'{self.grid.x[0] - self.grid.center.x} {self.grid.x.size} {self.grid.dx}\n')
            f.write(f'{self.grid.y[0] - self.grid.center.y} {self.grid.y.size} {self.grid.dy}\n')
            f.write(f'{self.grid.z[0] - self.grid.center.z} {self.grid.z.size} {self.grid.dz}\n')
            f.write('</axes>\n')
            
            f.write('<frequency>\n')
            f.write(str(self.frequency) + '\n')
            f.write('</frequency>\n')

            f.write('<incident-power>\n')
            f.write(str(1) + '\n')
            f.write('</incident-power>\n')

            lx = len(subgrid.x_idx_global)
            ly = len(subgrid.y_idx_global)
            lz = len(subgrid.z_idx_global)

            # We will only write the fields to the file that are in the neighborhood of the sides of the subgrid contained in the grid
            # This is because the Huygen's box will only compute the fields in the neighborhood of the sides of the subgrid contained in the grid
            margin_amount_of_cells = 1
            f.write('<e-field>\n')
            for ix, x_idx in tqdm(enumerate(self.grid.x_idx), disable=(not self.verbose)):
                #on_x_border = (ix == 0 or ix == 1 or ix == lx - 1 or ix == lx)
                # on_x_border should check if ix, the idx in the grid, is in the neighborhood of the sides of the subgrid contained in the grid, which is accessible through subgrid.x_idx_global
                # it should check if the distance between ix and the first element of subgrid.x_idx_global is within the margin_amount_of_cells
                on_x_border = (np.abs(ix - subgrid.x_idx_global[0]) <= margin_amount_of_cells or np.abs(ix - subgrid.x_idx_global[-1]) <= margin_amount_of_cells)

                for iy, y_idx in enumerate(self.grid.y_idx):
                    #on_y_border = (iy == 0 or iy == 1 or iy == ly - 1 or iy == ly)
                    on_y_border = (np.abs(iy - subgrid.y_idx_global[0]) <= margin_amount_of_cells or np.abs(iy - subgrid.y_idx_global[-1]) <= margin_amount_of_cells)

                    for iz, z_idx in enumerate(self.grid.z_idx):
                        #on_z_border = (iz == 0 or iz == 1 or iz == lz - 1 or iz == lz)
                        on_z_border = (np.abs(iz - subgrid.z_idx_global[0]) <= margin_amount_of_cells or np.abs(iz - subgrid.z_idx_global[-1]) <= margin_amount_of_cells)

                        if on_x_border or on_y_border or on_z_border or True:
                            #f.write(f'{np.real(self.E[0, x_idx, y_idx, z_idx])} {np.imag(self.E[0, x_idx, y_idx, z_idx])} {np.real(self.E[1, x_idx, y_idx, z_idx])} {np.imag(self.E[1, x_idx, y_idx, z_idx])} {np.real(self.E[2, x_idx, y_idx, z_idx])} {np.imag(self.E[2, x_idx, y_idx, z_idx])}\n')
                            f.write(f'{np.real(self.E[0, x_idx, y_idx, z_idx]):.3e} {np.imag(self.E[0, x_idx, y_idx, z_idx]):.3e} {np.real(self.E[1, x_idx, y_idx, z_idx]):.3e} {np.imag(self.E[1, x_idx, y_idx, z_idx]):.3e} {np.real(self.E[2, x_idx, y_idx, z_idx]):.3e} {np.imag(self.E[2, x_idx, y_idx, z_idx]):.3e}\n')
                        else:
                            f.write(f'0 0 0 0 0 0\n')
            f.write('</e-field>\n')

            f.write('<h-field>\n')
            for ix, x_idx in tqdm(enumerate(self.grid.x_idx), disable=(not self.verbose)):
                on_x_border = (np.abs(ix - subgrid.x_idx_global[0]) <= margin_amount_of_cells or np.abs(ix - subgrid.x_idx_global[-1]) <= margin_amount_of_cells)

                for iy, y_idx in enumerate(self.grid.y_idx):
                    on_y_border = (np.abs(iy - subgrid.y_idx_global[0]) <= margin_amount_of_cells or np.abs(iy - subgrid.y_idx_global[-1]) <= margin_amount_of_cells)
                    
                    for iz, z_idx in enumerate(self.grid.z_idx):
                        on_z_border = (np.abs(iz - subgrid.z_idx_global[0]) <= margin_amount_of_cells or np.abs(iz - subgrid.z_idx_global[-1]) <= margin_amount_of_cells)

                        if on_x_border or on_y_border or on_z_border or True:
                            #f.write(f'{np.real(self.H[0, x_idx, y_idx, z_idx])} {np.imag(self.H[0, x_idx, y_idx, z_idx])} {np.real(self.H[1, x_idx, y_idx, z_idx])} {np.imag(self.H[1, x_idx, y_idx, z_idx])} {np.real(self.H[2, x_idx, y_idx, z_idx])} {np.imag(self.H[2, x_idx, y_idx, z_idx])}\n')
                            f.write(f'{np.real(self.H[0, x_idx, y_idx, z_idx]):.3e} {np.imag(self.H[0, x_idx, y_idx, z_idx]):.3e} {np.real(self.H[1, x_idx, y_idx, z_idx]):.3e} {np.imag(self.H[1, x_idx, y_idx, z_idx]):.3e} {np.real(self.H[2, x_idx, y_idx, z_idx]):.3e} {np.imag(self.H[2, x_idx, y_idx, z_idx]):.3e}\n')
                        else:
                            f.write(f'0 0 0 0 0 0\n')
            f.write('</h-field>\n')
            
            f.write('</huygens>\n')

        return field
        
    def export_incident_field_h5(self, rx_nbr, exposure_simulation):

        h5_path = f'{exposure_simulation.S4L_document_results_path}\{exposure_simulation.S4L_executer_simulation_id}_Input.h5'
        #h5_path = f'{exposure_simulation.S4L_document_results_path}\{exposure_simulation.S4L_loader_simulation_id}_Output.h5'
        use_high_level_api = True
        skip_unnecessary_components = True
        use_yee_grid = True

        if use_yee_grid:
            if not self.use_sliced_grid:
                # The electric and magnetic fields are known on the vertices of Yee-cells
                # The electric field should be known on the center of the edges of the Yee-cells
                self.E[0, :-1, :, :] = 0.5 * (self.E[0, :-1, :, :] + self.E[0, 1:, :, :])
                self.E[1, :, :-1, :] = 0.5 * (self.E[1, :, :-1, :] + self.E[1, :, 1:, :])
                self.E[2, :, :, :-1] = 0.5 * (self.E[2, :, :, :-1] + self.E[2, :, :, 1:])

                # The magnetic field should be known on the center of the faces of the Yee-cells
                self.H[0, :, :-1, :-1] = 0.25 * (self.H[0, :, :-1, :-1] + self.H[0, :, 1:, :-1] + self.H[0, :, :-1, 1:] + self.H[0, :, 1:, 1:])
                self.H[1, :-1, :, :-1] = 0.25 * (self.H[1, :-1, :, :-1] + self.H[1, 1:, :, :-1] + self.H[1, :-1, :, 1:] + self.H[1, 1:, :, 1:])
                self.H[2, :-1, :-1, :] = 0.25 * (self.H[2, :-1, :-1, :] + self.H[2, 1:, :-1, :] + self.H[2, :-1, 1:, :] + self.H[2, 1:, 1:, :])
            else:
                for name, subgrid in self.sliced_subgrids.items():
                    self.E_subgrid[name][0, :-1, :, :] = 0.5 * (self.E_subgrid[name][0, :-1, :, :] + self.E_subgrid[name][0, 1:, :, :])
                    self.E_subgrid[name][1, :, :-1, :] = 0.5 * (self.E_subgrid[name][1, :, :-1, :] + self.E_subgrid[name][1, :, 1:, :])
                    self.E_subgrid[name][2, :, :, :-1] = 0.5 * (self.E_subgrid[name][2, :, :, :-1] + self.E_subgrid[name][2, :, :, 1:])

                    self.H_subgrid[name][0,:, :-1, :-1] = 0.25 * (self.H_subgrid[name][0, :, :-1, :-1] + self.H_subgrid[name][0, :, 1:, :-1] + self.H_subgrid[name][0, :, :-1, 1:] + self.H_subgrid[name][0, :, 1:, 1:])
                    self.H_subgrid[name][1,:-1, :, :-1] = 0.25 * (self.H_subgrid[name][1, :-1, :, :-1] + self.H_subgrid[name][1, 1:, :, :-1] + self.H_subgrid[name][1, :-1, :, 1:] + self.H_subgrid[name][1, 1:, :, 1:])
                    self.H_subgrid[name][2,:-1, :-1, :] = 0.25 * (self.H_subgrid[name][2, :-1, :-1, :] + self.H_subgrid[name][2, 1:, :-1, :] + self.H_subgrid[name][2, :-1, 1:, :] + self.H_subgrid[name][2, 1:, 1:, :])

        with h5py.File(h5_path, mode='r+') as h5_file:
            key = list(h5_file['FieldGroups'].keys())[0] #change if you are adding more sensors
            d = dict(h5_file[f'FieldGroups/{key}/_Object/'].attrs.items())
            assert d['name'].decode('ascii') == 'Incident Huygens Field'
            for field in ['EM E(x,y,z,f0)', 'EM H(x,y,z,f0)']:
                for dim, component in tqdm(enumerate(['comp0', 'comp1', 'comp2']), disable=(not self.verbose)):
                    if use_high_level_api:
                        val = h5_file['FieldGroups/%s/AllFields/%s/_Object/Snapshots/0/%s' % (key, field, component)]
                        if not self.use_sliced_grid:
                            if field == 'EM E(x,y,z,f0)':
                                val[:,:,:,0] = np.real(self.E[dim,:(-1 if dim == 0 else None),:(-1 if dim == 1 else None),:(-1 if dim == 2 else None)])
                                val[:,:,:,1] = np.imag(self.E[dim,:(-1 if dim == 0 else None),:(-1 if dim == 1 else None),:(-1 if dim == 2 else None)])

                                '''
                                if component == 'comp0':
                                    val[...] = self.E_yee_x
                                elif component == 'comp1':
                                    val[...] = self.E_yee_y
                                elif component == 'comp2':
                                    val[...] = self.E_yee_z
                                '''
                            elif field == 'EM H(x,y,z,f0)':
                                val[:,:,:,0] = np.real(self.H[dim,:(-1 if dim != 0 else None),:(-1 if dim != 1 else None),:(-1 if dim != 2 else None)])
                                val[:,:,:,1] = np.imag(self.H[dim,:(-1 if dim != 0 else None),:(-1 if dim != 1 else None),:(-1 if dim != 2 else None)])

                                '''
                                if component == 'comp0':
                                    val[...] = self.H_yee_x
                                elif component == 'comp1':
                                    val[...] = self.H_yee_y
                                elif component == 'comp2':
                                    val[...] = self.H_yee_z
                                '''
                        else:
                            val[...] = 0 * val[...] 

                            for name, subgrid in self.sliced_subgrids.items():
                                if skip_unnecessary_components:
                                    if ('x' in name and '0' in component) or ('y' in name and '1' in component) or ('z' in name and '2' in component):
                                        continue
                                
                                # Check if the subgrid is on the border of the global grid, if so, we need to cut the last cell, because Sim4Life's FDTD grid does not store that component
                                allow_x_cut = self.grid.x_idx[-1] in subgrid.x_idx_global
                                allow_y_cut = self.grid.y_idx[-1] in subgrid.y_idx_global
                                allow_z_cut = self.grid.z_idx[-1] in subgrid.z_idx_global

                                if field == 'EM E(x,y,z,f0)':
                                    val[subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice, 0] = np.real(self.E_subgrid[name][dim,:(-1 if (dim == 0 and allow_x_cut) else None),:(-1 if (dim == 1 and allow_y_cut) else None),:(-1 if (dim == 2 and allow_z_cut) else None)])
                                    val[subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice, 1] = np.imag(self.E_subgrid[name][dim,:(-1 if (dim == 0 and allow_x_cut) else None),:(-1 if (dim == 1 and allow_y_cut) else None),:(-1 if (dim == 2 and allow_z_cut) else None)])
                                elif field == 'EM H(x,y,z,f0)':
                                    val[subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice, 0] = np.real(self.H_subgrid[name][dim,:(-1 if (dim != 0 and allow_x_cut) else None),:(-1 if (dim != 1 and allow_y_cut) else None),:(-1 if (dim != 2 and allow_z_cut) else None)])
                                    val[subgrid.x_3D_idx_global_slice, subgrid.y_3D_idx_global_slice, subgrid.z_3D_idx_global_slice, 1] = np.imag(self.H_subgrid[name][dim,:(-1 if (dim != 0 and allow_x_cut) else None),:(-1 if (dim != 1 and allow_y_cut) else None),:(-1 if (dim != 2 and allow_z_cut) else None)])
                    else:
                        raise NotImplementedError()
                        val = h5_file['FieldGroups/%s/AllFields/%s/_Object/Snapshots/0/%s' % (key, field, component)]
                        
                        if not self.use_sliced_grid:
                            # TODO
                            if field == 'EM E(x,y,z,f0)':
                                ptr = val.id.get_vlen_memory(True)
                                ptr[0,:,:,:] = np.real(self.E[dim,:(-1 if dim == 0 else None),:(-1 if dim == 1 else None),:(-1 if dim == 2 else None)])
                                ptr[1,:,:,:] = np.imag(self.E[dim,:(-1 if dim == 0 else None),:(-1 if dim == 1 else None),:(-1 if dim == 2 else None)])
                            elif field == 'EM H(x,y,z,f0)':
                                ptr = val.id.get_vlen_memory(True)
                                ptr[0,:,:,:] = np.real(self.H[dim,:(-1 if dim != 0 else None),:(-1 if dim != 1 else None),:(-1 if dim != 2 else None)])
                                ptr[1,:,:,:] = np.imag(self.H[dim,:(-1 if dim != 0 else None),:(-1 if dim != 1 else None),:(-1 if dim != 2 else None)])
                        else:
                            raise NotImplementedError()
                    
    def reset(self):
        if self.radiating_collection.collection_type == 'antenna_array':
            self.__init__(grid = self.grid, base_station = self.base_station, receivers = self.receivers, frequency = self.frequency, polarization = self.polarization)
        elif self.radiating_collection.collection_type == 'cluster_collection':
            self.__init__(grid = self.grid, clusters = self.clusters, base_station = None, receivers = self.receivers, frequency = self.frequency, polarization = self.polarization)

    def clear_unimportant_data(self, also_clear_fields=True):
        ''' Clear all data that is not needed for post-processing. Keeps only the fields aggregated in the simulation.'''

        if not self.grid.is_2D:
            for element in self.radiating_collection.elements:
                element.clear_unimportant_data(also_clear_fields=also_clear_fields)
        else:
            raise NotImplementedError

    def clear_important_data(self, also_grid = True):
        ''' Clears the EMF and grid data. '''

        if self.use_sliced_grid:
            self.E_subgrid = {}
            self.H_subgrid = {}
        else:
            if not self.grid.is_2D:
                self.E = 'Cleared'
                self.H = 'Cleared'
            else:
                if self.polarization == 'TEz':
                    self.Ez = 'Cleared'
                    self.Hx = 'Cleared'
                    self.Hy = 'Cleared'
                elif self.polarization == 'TMz':
                    self.Hz = 'Cleared'
                    self.Ex = 'Cleared'
                    self.Ey = 'Cleared'
                elif self.polarization == 'Mixed':
                    raise NotImplementedError

        if also_grid:
            self.grid = 'Cleared'

    def get_value(self, value_type='abs', component_type='norm', field_type='E', scaling_type='linear', rms=False, z_pos = None, plane = None, xyz_pos = None, from_tx_element_nbr = None):

        # avoid circular import
        from .antenna import Pos
        
        # Get the field from either the simulation or an individual antenna element
        if from_tx_element_nbr is None:
            parent = self
        else:
            parent = self.radiating_collection.elements[from_tx_element_nbr]
        if not self.grid.is_2D:
            if field_type == 'E':
                vector_field = parent.E
                vector_field_name = 'E'
                name_alias = 'N/A'
            elif field_type == 'H':
                vector_field = parent.H
                vector_field_name = 'H'
                name_alias = 'N/A'
            # See https://en.wikipedia.org/wiki/Poynting_vector
            elif field_type == 'S':
                vector_field = np.cross(parent.E, parent.H, axis=0)
                vector_field_name = '(E x H)'
                name_alias = 'N/A'
            elif field_type == 'S_m':
                vector_field = 1/2*np.cross(parent.E, parent.H.conj(), axis=0)
                vector_field_name = '1/2*(E x H*)'
                name_alias = 'N/A'
            elif field_type == '<S>':
                assert rms is False
                assert value_type == 'real' or value_type == '', '<S> is defined as Re(1/2*(E x H*))'
                value_type = ''
                vector_field = np.real(1/2*np.cross(parent.E, parent.H.conj(), axis=0))
                vector_field_name = 'Re(1/2*(E x H*))'
                name_alias = '<S>'
            # See ICNIRP 2020 eq (16) and (18)
            elif field_type == 'Sinc_ICNIRP':
                assert rms is False
                assert component_type == 'norm' or component_type == '', 'Sinc is defined as |E x H*|'
                if value_type != '':
                    if self.verbose:
                        print('NOTE: it is useless to compute any value of a norm, just use the norm directly')
                    value_type = ''
                component_type = ''
                vector_field = np.linalg.norm(np.cross(parent.E, parent.H.conj(), axis=0), axis=0)
                vector_field_name = 'norm(E x H*)'
                name_alias = 'Sinc_ICNIRP'
            elif field_type == 'Sab_ICNIRP':
                assert rms is False
                assert value_type == 'real' or value_type == '', 'Sab is defined as surface integral over Re(E x H*) on an area A'
                value_type = ''
                vector_field = np.real(np.cross(parent.E, parent.H.conj(), axis=0))
                vector_field_name = 'Re(E x H*)'
                name_alias = 'Sab_ICNIRP'
            # See p. 321 of Sim4Life 6.2 User Manual
            elif field_type == 'Sinc_S4L':
                assert rms is False
                assert component_type == 'norm' or component_type == '', 'Sinc is defined as |E x H*|'
                if value_type != '':
                    if self.verbose:
                        print('NOTE: it is useless to compute any value of a norm, just use the norm directly')
                    value_type = ''
                component_type = ''
                vector_field = np.linalg.norm(1/2*np.cross(parent.E, parent.H.conj(), axis=0), axis=0)
                vector_field_name = 'norm(1/2*(E x H*))'
                name_alias = 'Sinc_S4L'
            elif field_type == 'Sab_S4L':
                assert rms is False
                assert value_type == 'real' or value_type == '', 'Sab is defined as surface integral over 1/2*Re(E x H*) on an area A'
                value_type = ''
                vector_field = np.real(1/2*np.cross(parent.E, parent.H.conj(), axis=0))
                vector_field_name = 'Re(1/2*(E x H*))'
                name_alias = 'Sab_S4L'

            if component_type=='':
                field = vector_field
                field_name = vector_field_name
                name_alias = name_alias
            elif component_type=='x':
                field = vector_field[0, ...]
                field_name = vector_field_name + 'x'
                name_alias += 'x'
            elif component_type=='y':
                field = vector_field[1, ...]
                field_name = vector_field_name + 'y'
                name_alias += 'y'
            elif component_type=='z':
                field = vector_field[2, ...]
                field_name = vector_field_name + 'z'
                name_alias += 'z'
            elif component_type=='norm':
                if value_type != '' and self.verbose:
                    print('NOTE: it is useless to compute any value of a norm, just use the norm directly')
                field = np.linalg.norm(vector_field, axis=0)
                field_name = f'norm({vector_field_name})'
                name_alias = f'norm({name_alias})'
            elif 'e_theta' in component_type:
                
                if 'to tx' in component_type:
                    tx_nbr = int(component_type.split(' ')[-1])
                    assert str(component_type.split(' ')[-2]) == 'tx'
                else:
                    if self.verbose:
                        print('WARNING: No transmitter specified for e_theta component, taking tx 0')
                    tx_nbr = 0
                    
                if 'from rx' in component_type:
                    rx_nbr = int(component_type.split(' ')[-4])
                    assert str(component_type.split(' ')[-5]) == 'rx'
                elif hasattr(self, 'focused_rx_nbr'):
                    rx_nbr = self.focused_rx_nbr
                else:
                    raise ValueError('No receiver specified for e_theta component')

                rx = self.receivers.antenna_elements[rx_nbr]
                tx = self.radiating_collection.elements[tx_nbr]
                u = Pos.from_vec(rx.vec_to(tx)).normalize()
                theta = u.get_theta()
                phi = u.get_phi()
                u_theta = np.array([np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), -np.sin(theta)])
                field = np.sum(vector_field * u_theta[:, np.newaxis, np.newaxis, np.newaxis], axis=0) # dot product

                field_name = f'{vector_field_name} . e_theta_{tx_nbr}_to_{rx_nbr}'
                name_alias = f'{name_alias} . e_theta_{tx_nbr}_to_{rx_nbr}'
            elif component_type == 'x normalized':
                field = vector_field[0, ...]/np.linalg.norm(vector_field, axis=0)
                field_name = f'{vector_field_name}x/norm({vector_field_name})'
                name_alias = f'{name_alias}x/norm({name_alias})'
            elif component_type == 'y normalized':
                field = vector_field[1, ...]/np.linalg.norm(vector_field, axis=0)
                field_name = f'{vector_field_name}y/norm({vector_field_name})'
                name_alias = f'{name_alias}y/norm({name_alias})'
            elif component_type == 'z normalized':
                field = vector_field[2, ...]/np.linalg.norm(vector_field, axis=0)
                field_name = f'{vector_field_name}z/norm({vector_field_name})'
                name_alias = f'{name_alias}z/norm({name_alias})'
        else:
            if self.polarization == 'TEz':
                field = parent.Ez
            elif self.polarization == 'TMz':
                field = parent.Hz
            elif self.polarization == 'Mixed':
                raise NotImplementedError

        # If 3D grid, extract the plane at z_pos or the point at xyz_pos
        if not self.grid.is_2D:
            if plane is not None and xyz_pos is not None:
                if plane == 'xy':
                    field = field[:, :, xyz_pos.z_idx]
                elif plane == 'xz':
                    field = field[:, xyz_pos.y_idx, :]
                elif plane == 'yz':
                    field = field[xyz_pos.x_idx, :, :]
            else:
                if z_pos is not None and xyz_pos is not None:
                    field = field[xyz_pos.x_idx, xyz_pos.y_idx, xyz_pos.z_idx] # TODO: optimize this function so that component_type is not calculated for each point, i.e., do this step earlier
                    field = np.squeeze(field)
                elif z_pos is not None and xyz_pos is None:
                    field = field[:, :, z_pos.z_idx]
                    field = np.squeeze(field)
                elif z_pos is None and xyz_pos is not None:
                    field = field[xyz_pos.x_idx, xyz_pos.y_idx, xyz_pos.z_idx]
                    field = np.squeeze(field)
                elif z_pos is None and xyz_pos is None:
                    pass # go on with 3D field

        # Calculate the value depending on the value_type and rms
        if rms:
            if 'S' in vector_field_name:
                rms_factor = 1/2
            else:
                rms_factor = np.sqrt(2)/2
        else:
            rms_factor = 1
        
        if value_type == '':
            assert 'norm' in field_name
            value = field*rms_factor
            value_units = 'V/m'
            value_name = field_name
            name_alias = name_alias
            always_positive = True
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'abs':
            value = np.abs(field*rms_factor)
            value_units = 'V/m'
            value_name = f'|{field_name}|'
            name_alias = f'|{name_alias}|'
            always_positive = True
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'phase':
            value = np.rad2deg(np.angle(field*rms_factor))
            value_units = 'deg'
            value_name = f'phase({field_name})'
            name_alias = f'phase({name_alias})'
            always_positive = False
            if 'dB' in scaling_type and self.verbose:
                print('Warning: you should not use db for phase values.')
        elif value_type == 'real':
            value = np.real(field*rms_factor)
            value_units = 'V/m'
            value_name = f'real({field_name})'
            name_alias = f'real({name_alias})'
            always_positive = False
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'real normalized':
            value = np.real(field*rms_factor)/np.abs(field*rms_factor)
            value_units = ''
            value_name = f'real({field_name})/abs({field_name})'
            name_alias = f'real({name_alias})/abs({name_alias})'
            always_positive = False
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'imag':
            value = np.imag(field*rms_factor)
            value_units = 'V/m'
            value_name = f'imag({field_name})'
            name_alias = f'imag({name_alias})'
            always_positive = False
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'imag normalized':
            value = np.imag(field*rms_factor)/np.abs(field*rms_factor)
            value_units = ''
            value_name = f'imag({field_name})/abs({field_name})'
            name_alias = f'imag({name_alias})/abs({name_alias})'
            always_positive = False
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'abs(real/imag)':
            value = np.abs(np.real(field*rms_factor)/np.imag(field*rms_factor))
            value_units = ''
            value_name = f'abs(real({field_name})/imag({field_name}))'
            name_alias = f'abs(real({name_alias})/imag({name_alias}))'
            always_positive = True
            if scaling_type == 'power_dB' and self.verbose:
                print('Warning: you should use amplitude_dB for field values, not power_dB.')
        elif value_type == 'power':
            if self.polarization == 'TEz':
                value = np.abs(field*rms_factor)**2/(2*IMPEDANCE_FREE_SPACE)
                value_name = f'power({field_name}) = |{field_name}|^2/2Z_0'
                name_alias = f'power({name_alias}) = |{name_alias}|^2/2Z_0'
                if self.verbose:
                    print('TODO, power should be E x H in current implementation')
            elif self.polarization == 'TMz':
                value = np.abs(field*rms_factor)**2*IMPEDANCE_FREE_SPACE/2
                value_name = f'power({field_name}) = |{field_name}|^2*Z_0/2'
                name_alias = f'power({name_alias}) = |{name_alias}|^2*Z_0/2'
            elif self.polarization == 'Mixed':
                raise NotImplementedError
            value_units = 'W/m^2'
            always_positive = True
            if scaling_type == 'amplitude_dB':
                if self.verbose:
                    print('Warning: you should use power_dB for power values, not amplitude_dB.')
        else:
            if isinstance(value_type, str):
                if hasattr(parent, value_type):
                    assert 'N/A' not in name_alias
                    value = getattr(parent, value_type)
                    value_units = '?'
                    if 'theta' in value_type or 'phi' in value_type:
                        if self.verbose:
                            print('Warning: converted radians to degrees.')
                        value = np.rad2deg(value)
                        value_units = '°'
                    value_name = value_type
                    always_positive = False
                else:
                    raise ValueError(f'Unknown or unassigned value_type: {value_type}')
            else:
                value = value_type
                value_units = '?'
                assert 'N/A' not in name_alias
                value_name = 'Other'
                always_positive = False

        if rms:
            value_name += ' (RMS)'
            name_alias += ' (RMS)'

        if 'dB' in scaling_type:
            assert always_positive == True, 'dB scaling is only possible for always_positive values'
            if scaling_type == 'amplitude_dB':
                value = 20*np.log10(value)
            elif scaling_type == 'power_dB':
                value = 10*np.log10(value)
            value_units += ' (dB)'
            always_positive = False

        if from_tx_element_nbr is not None:
            value_name += f'(el. # {from_tx_element_nbr})'
            name_alias += f'(el. # {from_tx_element_nbr})'

        if not self.grid.is_2D:
            if z_pos is not None and xyz_pos is not None:
                z_height = z_pos.z
            elif z_pos is not None and xyz_pos is None:
                z_height = z_pos.z
            elif z_pos is None and xyz_pos is not None:
                z_height = xyz_pos.z
            else:
                z_height = None
        else:
            z_height = None

        if 'N/A' not in name_alias:
            value_name = f'{name_alias} = {value_name}'
        value_info = {'name': value_name, 'units': value_units, 'always_positive': always_positive, 'z_height': z_height}

        return value, value_info

    def get_1D_slice(self, value = None, value_type = 'abs', component_type = 'norm', field_type='E', scaling_type='linear', rms = False, through_pos = None, axis = 'x', z_pos=None, from_tx_element_nbr=None):
        ''' Extracts a 1D slice of a value across the first position of the line of receivers. '''
        
        if value_type is not None and value is None:
            value, _ = self.get_value(value_type=value_type, component_type=component_type, field_type=field_type, scaling_type=scaling_type, z_pos=z_pos, from_tx_element_nbr=from_tx_element_nbr, rms=rms)
        assert value is not None, 'Provide value to slice.'
        
        if len(value.shape) == 2:
            if axis == 'x':
                return value[:,through_pos.y_idx]
            elif axis == 'y':
                return value[through_pos.x_idx,:]
        elif len(value.shape) == 3:
            if axis == 'x':
                return value[:,through_pos.y_idx,through_pos.z_idx]
            elif axis == 'y':
                return value[through_pos.x_idx,:,through_pos.z_idx]
            elif axis == 'z':
                return value[through_pos.x_idx,through_pos.y_idx,:]
        
    def get_hotspot_parameters(self, field_slice, print_result = False, field_units = '', axis='x'):
        ''' Extracts the height and FWHM of each detected peaks in the given slice. The hotspot is the peak with the largest height. '''
        
        peaks_idx, _ = find_peaks(field_slice)
        peaks = field_slice[peaks_idx]
        FWHMs, FWHM_heights, FWHM_left, FWHM_right = peak_widths(field_slice, peaks_idx, rel_height=0.5) 
        prominences = peak_prominences(field_slice, peaks_idx)[0]
        FWHM_left  = self.grid.float_index_to_position(FWHM_left, axis=axis)
        FWHM_right = self.grid.float_index_to_position(FWHM_right, axis=axis)
        FWHMs      = self.grid.float_index_to_position(FWHMs, axis=axis, relative_to_origin=True)
        all_peaks = {'peaks': peaks, 
                     'peaks_idx': peaks_idx, 
                     'FWMHs': FWHMs, 
                     'FWHM_heights': FWHM_heights, 
                     'FWHM_left': FWHM_left, 
                     'FWHM_right': FWHM_right}

        if peaks.size != 0:
            max_peak_idx = np.argmax(peaks)
            hotspot = {'peak': peaks[max_peak_idx], 
                       'FWHM': FWHMs[max_peak_idx],
                       'prominence': prominences[max_peak_idx]}
            if print_result and self.verbose:
                print(f"The maximum peak is {hotspot['peak']:.2e} {field_units}.")
                print(f"The FWHM of the hotspot is {hotspot['FWHM']*100:.2f} cm.")
                print(f"The prominence of the hotspot is {hotspot['prominence']:.2e} {field_units}.")
        else:
            if print_result and self.verbose:
                print(f"No hotspot found.")
            return 'No hotspot found', 'No peaks found'

        return hotspot, all_peaks

    def get_3D_hotspot_parameters(self, relative_hotspot_pos = None, rx = 0, print_result = False, **kwargs):
        ''' Extracts the height and FWHM of each detected peaks in the given slice. The hotspot is the peak with the largest height.'''

        # avoid circular import
        from .antenna import Pos

        assert self.grid.units == 'm', 'Grid must be in meters'
        assert len(self.E.shape) == 4, '3D grid required'

        hotspot = {}

        self.shown_value, self.shown_value_info = self.get_value(**kwargs) # 3D
        if relative_hotspot_pos is None:
            # find the location of maximum field value
            max_idx = np.unravel_index(np.argmax(self.shown_value, axis=None), self.shown_value.shape)
            hotspot_pos = Pos(self.grid.x[max_idx[0]], self.grid.y[max_idx[1]], self.grid.z[max_idx[2]]).discretize_on(self.grid)
            hotspot['Relative position'] = hotspot_pos - self.receivers.antenna_elements[rx]
        else:
            hotspot_pos = relative_hotspot_pos + self.receivers.antenna_elements[rx]
            hotspot_pos.discretize_on(self.grid)
            hotspot['Relative position'] = relative_hotspot_pos

        hotspot['Relative distance'] = hotspot['Relative position'].vec_size

        # find the hotspot along each axis
        for axis in ['x', 'y', 'z']:
            self.shown_slice = self.get_1D_slice(self.shown_value, **kwargs, through_pos = hotspot_pos, axis=axis)
            hotspot[axis], _ = self.get_hotspot_parameters(self.shown_slice, field_units = self.shown_value_info['units'], axis=axis)

        hotspot['Peak'] = 0
        hotspot_fwhm_mean = 0
        hotspot_prominence_mean = 0
        peaks_present = [False, False, False]
        if 'peak' in hotspot['x']:
            if print_result and self.verbose:
                print(f"The maximum peak is {hotspot['x']['peak']:.2e} {self.shown_value_info['units']} in x.")
                print(f"The FWHM of the hotspot is {hotspot['x']['FWHM']*100:.2f} cm in x.")
                print(f"The prominence of the hotspot is {hotspot['x']['prominence']:.2e} {self.shown_value_info['units']} in x.")
            hotspot_fwhm_mean += hotspot['x']['FWHM']
            hotspot_prominence_mean += hotspot['x']['prominence']
            peaks_present[0] = True
            hotspot['Peak'] = hotspot['x']['peak']
        else:
            if print_result and self.verbose:
                print(f"No hotspot found in x.")
        if 'peak' in hotspot['y']:
            if print_result and self.verbose:
                print(f"The maximum peak is {hotspot['y']['peak']:.2e} {self.shown_value_info['units']} in y.")
                print(f"The FWHM of the hotspot is {hotspot['y']['FWHM']*100:.2f} cm in y.")
                print(f"The prominence of the hotspot is {hotspot['y']['prominence']:.2e} {self.shown_value_info['units']} in y.")
            hotspot_fwhm_mean += hotspot['y']['FWHM']
            hotspot_prominence_mean += hotspot['y']['prominence']
            peaks_present[1] = True
            hotspot['Peak'] = hotspot['y']['peak']
        else:
            if print_result and self.verbose:
                print(f"No hotspot found in y.")
        if 'peak' in hotspot['z']:
            if print_result and self.verbose:
                print(f"The maximum peak is {hotspot['z']['peak']:.2e} {self.shown_value_info['units']} in z.")
                print(f"The FWHM of the hotspot is {hotspot['z']['FWHM']*100:.2f} cm in z.")
                print(f"The prominence of the hotspot is {hotspot['z']['prominence']:.2e} {self.shown_value_info['units']} in z.")
            hotspot_fwhm_mean += hotspot['z']['FWHM']
            hotspot_prominence_mean += hotspot['z']['prominence']
            peaks_present[2] = True
            hotspot['Peak'] = hotspot['z']['peak']
        else:
            if print_result and self.verbose:
                print(f"No hotspot found in z.")

        dimensionality = sum(peaks_present)
        if dimensionality != 0:
            hotspot_fwhm_mean /= dimensionality
            hotspot_prominence_mean /= dimensionality
        else:
            hotspot_fwhm_mean = 0
            hotspot_prominence_mean = 0
        hotspot['Average FWHM'] = hotspot_fwhm_mean
        hotspot['Average prominence'] = hotspot_prominence_mean
        hotspot['Dimensionality'] = dimensionality

        if print_result and self.verbose:
            print(f"The relative position of the hotspot to rx {rx} is [{hotspot['Relative position'].x*100:.2f}, {hotspot['Relative position'].y*100:.2f}, {hotspot['Relative position'].z*100:.2f}] cm.")
            print(f"The relative distance of the hotspot to rx {rx} is {hotspot['Relative distance']*100:.2f} cm.")
            print(f"The average FWHM of the hotspot is {hotspot_fwhm_mean*100:.2f} cm.")
            print(f"The average prominence of the hotspot is {hotspot_prominence_mean:.2e} {self.shown_value_info['units']}.")
            print(f"The dimensionality of the hotspot is {dimensionality}.")

        return hotspot
    
    def get_Sinc(self, which_Sinc_to_compute = 'max', in_db = False):
        ''' Gets the ICNIRP Sinc value at a specified location. '''

        Sinc, Sinc_info = self.get_value(value_type='', component_type='', field_type='Sinc_ICNIRP')
        if which_Sinc_to_compute == 'median':
            Sinc = np.median(Sinc)
        elif which_Sinc_to_compute == 'mean':
            Sinc = np.mean(Sinc)
        elif which_Sinc_to_compute == 'max':
            Sinc = np.max(Sinc)
        elif which_Sinc_to_compute == 'min':
            Sinc = np.min(Sinc)
        elif which_Sinc_to_compute == 'at_rx':
            self.receivers.antenna_elements[0].discretize_on(self.grid)
            Sinc = Sinc[self.receivers.antenna_elements[0].x_idx, self.receivers.antenna_elements[0].y_idx, self.receivers.antenna_elements[0].z_idx]

        if in_db:
            Sinc = 20*np.log10(Sinc)

        return Sinc

    def plot_2D_slice(self, *args, **kwargs):
        ''' Plots the specified value (e.g. fields) on the Grid in a first subplot as a 2D slice. In the second subplot, plot a 1D slice through the receivers. '''
        
        self.plot_2D_slice_initialize(*args, **kwargs)
        self.plot_2D_slice_draw(*args, **kwargs)

    def plot_2D_slice_initialize(self,
        value_type='abs', 
        component_type='norm', 
        field_type='E',
        scaling_type='linear',
        rms=False, 
        from_tx_element_nbr=None, 
        cut_off_high_data=False, 
        stochastic_identifier = None, 
        slice_through_rx = None,
        z_pos=None,
        slice_axis='x',
        plot_surface=False,

        # unneccessary
        show_figure=True
    ):
        matplotlib.rcParams['axes.formatter.limits'] = (-3, 3)

        # Z-position
        if z_pos is None:
            if slice_through_rx is None:
                try:
                    self.z_pos = self.receivers.line_pos_1
                except:
                    self.z_pos = self.receivers.antenna_elements[0]
            else:
                self.z_pos = self.receivers.antenna_elements[slice_through_rx]
        try:
            self.z_pos.discretize_on(self.grid)
        except:
            self.z_pos = z_pos
            self.z_pos.discretize_on(self.grid)
        
        # Fields
        if not self.use_existing_shown_value:
            # most common scenario
            self.shown_value, self.shown_value_info = self.get_value(value_type=value_type, component_type=component_type, field_type=field_type, scaling_type=scaling_type, z_pos=self.z_pos, from_tx_element_nbr=from_tx_element_nbr, rms=rms)
        else:
            # when shown_value is provided externally
            assert self.shown_value is not None and self.shown_value_info is not None, 'Provide shown_value and shown_value_info externally.'
        self.shown_slice = self.get_1D_slice(self.shown_value, value_type=value_type, component_type=component_type, field_type=field_type, rms=rms, through_pos = self.z_pos, axis=slice_axis)
        if cut_off_high_data:
            slice_max = np.nanmax(self.shown_slice)
            slice_min = np.nanmin(self.shown_slice)
            self.shown_value[self.shown_value>slice_max*2] = np.nan
            self.shown_value[self.shown_value<slice_min*2] = np.nan
        
        # Hotspot analysis
        self.shown_hotspot, self.shown_peaks = self.get_hotspot_parameters(self.shown_slice, print_result = True, field_units = self.shown_value_info['units'])

        # Figure
        if stochastic_identifier is None:
            figtitle = f"{self.shown_value_info['name']} [{self.shown_value_info['units']}]"
        else: 
            figtitle = f"{self.shown_value_info['name']} [{self.shown_value_info['units']}, {stochastic_identifier}]"

        try_to_write_on_existing_figure = False
        if try_to_write_on_existing_figure:
            try:
                if self.fig.number == self.fignumber:
                    for ax in self.fig.get_axes():
                        ax.cla()
            except AttributeError:
                if plot_surface:
                    #self.fig, self.axs = plt.subplots(1,2, num=figtitle, subplot_kw={"projection": "3d"})
                    self.fig = plt.figure(num=figtitle)
                    self.axs = [self.fig.add_subplot(1,2,1, projection='3d'), self.fig.add_subplot(1,2,2)]
                else:
                    self.fig, self.axs = plt.subplots(1,2, num=figtitle)
                self.fignumber = self.fig.number
        else:
            EUCAP_PAPER = False # CHANGE!
            if plot_surface:
                if EUCAP_PAPER:
                    self.fig = plt.figure(num=figtitle, figsize=(3.5, 3.5))
                    self.axs = [self.fig.add_subplot(1,1,1, projection='3d')]
                else:
                    #self.fig, self.axs = plt.subplots(1,2, num=figtitle, subplot_kw={"projection": "3d"})
                    self.fig = plt.figure(num=figtitle)
                    self.axs = [self.fig.add_subplot(1,2,1, projection='3d'), self.fig.add_subplot(1,2,2)]
            else:
                if EUCAP_PAPER:
                    self.fig = plt.figure(num=figtitle, figsize=(3.5, 3.5))
                    self.axs = [self.fig.add_subplot(1,1,1)]
                else:
                    self.fig, self.axs = plt.subplots(1,3, num=figtitle, gridspec_kw={'width_ratios': [1, 1, 0.1]})
                
            self.fignumber = self.fig.number

        # Left subplot: field data
        finite_value = self.shown_value[np.isfinite(self.shown_value)]
        if 'dB' not in self.shown_value_info['units']:
            if self.shown_value_info['always_positive']:
                self.cmap = 'jet'
                # you can make a choice here, usually the second only if there is a strong DC component to the values
                self.norm = Normalize(vmin=0.,  vmax=finite_value.max())
                #self.norm = Normalize(vmin=finite_value.min(),  vmax=finite_value.max())
            else:
                if finite_value.min() < 0 and 0 < finite_value.max():
                    self.cmap = 'bwr'
                    #self.norm = DivergingNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                    self.norm = TwoSlopeNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                else:
                    self.cmap = 'jet'
                    self.norm = None
        else:
            self.cmap = 'jet'
            self.norm = None

    def plot_2D_slice_draw(self,
        slice_through_rx = None,
        slice_axis='x',
        plot_surface=False,
        show_figure=True,

        # unneccessary
        value_type='abs', 
        z_pos=None,
        component_type='norm', 
        field_type='E',
        scaling_type='linear',
        rms=False, 
        from_tx_element_nbr=None, 
        cut_off_high_data=False, 
        stochastic_identifier = None,
        custom_shown_value=None,
        custom_shown_value_info=None
    ):

        # Left subplot: field data
        if not self.grid.is_2D:
            x, y, _ = self.grid.get_slice('all','z',self.z_pos.z_idx)
            if plot_surface:
                self.color_bar = self.axs[0].plot_surface(x, y, self.shown_value, cmap = self.cmap, norm = self.norm)
            else:
                self.color_bar = self.axs[0].contourf(x, y, self.shown_value, 500, cmap = self.cmap, norm = self.norm)
        else:
            if plot_surface:
                self.color_bar = self.axs[0].plot_surface(self.grid.x_2D, self.grid.y_2D, self.shown_value, cmap = self.cmap, norm = self.norm)
            else:
                self.color_bar = self.axs[0].contourf(self.grid.x_2D, self.grid.y_2D, self.shown_value, 500, cmap = self.cmap, norm = self.norm)

        # Colorbar axis 
        EUCAP_FIGURE = False # CHANGE!
        if EUCAP_FIGURE:
            self.cb = plt.colorbar(self.color_bar, orientation='vertical')
            self.axs[0].set_aspect('equal', adjustable='box')
            # Force the tick labels to be at -20 cm, -10 cm, 0 cm, 10 cm, 20 cm.
            # Note that the data is in meters
            # This for the x and y axis
            self.axs[0].set_xticks([-0.2, -0.1, 0, 0.1, 0.2])
            self.axs[0].set_yticks([-0.2, -0.1, 0, 0.1, 0.2])
            # Now get the tick labels
            xlabels = self.axs[0].get_xticks().tolist()
            ylabels = self.axs[0].get_yticks().tolist()
            # Set the tick labels to be the position
            self.axs[0].set_xticklabels([f'{float(x*100):.0f}' for x in xlabels])
            self.axs[0].set_yticklabels([f'{float(y*100):.0f}' for y in ylabels])
            self.axs[0].set_xlabel('$y$ [cm]')
            self.axs[0].set_ylabel('$z$ [cm]')      
            self.axs[0].set_title('$|E_y|$ [V/m]')
        else:
            #self.cb = self.fig.colorbar(self.color_bar, cax=self.fig.add_axes([0.95, 0.1, 0.02, 0.8]), orientation='vertical')
            self.cb = self.fig.colorbar(self.color_bar, cax=self.axs[2], orientation='vertical')
            self.axs[0].set_xlabel(f'x [{self.grid.units}]')
            self.axs[0].set_ylabel(f'y [{self.grid.units}]')
            self.axs[0].set_xlim(self.grid.pos_ll.x, self.grid.pos_ur.x)
            self.axs[0].set_ylim(self.grid.pos_ll.y, self.grid.pos_ur.y)
            if self.grid.units == 'm':
                self.axs[0].set_title(f"{self.shown_value_info['name']} (z = {100*self.shown_value_info['z_height']:.2f} cm)")
            elif self.grid.units == 'λ':
                self.axs[0].set_title(f"{self.shown_value_info['name']} (z = {self.shown_value_info['z_height']:.2f} {self.grid.units})")

        # Slice line
        if slice_through_rx is None:
            try:
                rx = self.receivers.line_pos_1
            except:
                rx = self.receivers.antenna_elements[0]
        else:
            rx = self.receivers.antenna_elements[slice_through_rx]

        if EUCAP_FIGURE:
            # make sure the colorbar starts at 0 and has a tick label at the end and beginning
            self.cb.set_ticks(np.linspace(self.shown_value.min(), self.shown_value.max(), 5))
            self.cb.set_ticklabels([f'{x:.3f}' for x in np.linspace(self.shown_value.min(), self.shown_value.max(), 5)])
        if EUCAP_FIGURE:
            margin = 0.0
        else:
            margin = 0.05
        if slice_axis == 'x':
            self.axs[0].plot([self.grid.pos_ll.x + -margin*self.grid.x_size, self.grid.pos_ll.x + (1+margin)*self.grid.x_size], [rx.y, rx.y], '--', c='black')
        elif slice_axis == 'y':
            self.axs[0].plot([rx.x, rx.x], [self.grid.pos_ll.y - margin*self.grid.y_size, self.grid.pos_ll.y + (1+margin)*self.grid.y_size], '--', c='black')

        #self.grid.plot(self.axs[0])
        for subgrid in self.grid.subgrids:
            subgrid.plot(self.axs[0], self.z_pos)
        
        if not EUCAP_FIGURE:
            for element in self.radiating_collection.elements:
                self.axs[0].scatter(element.x, element.y, s=20, color='red', marker='x') 
            
        for rx in self.receivers.antenna_elements:
            self.axs[0].scatter(rx.x, rx.y, s=20, color='black', marker='x')

        # Right subplot: slice data
        if not EUCAP_FIGURE:
            self.axs[1].plot(self.grid.x, self.shown_slice)
            self.axs[1].set_ylim(min(np.nanmin(self.shown_slice), 0), np.nanmax(self.shown_slice))
            if self.shown_peaks != 'No peaks found':
                self.axs[1].plot(self.grid.x[self.shown_peaks['peaks_idx']], self.shown_peaks['peaks'], 'x')
                self.axs[1].hlines(self.shown_peaks['FWHM_heights'], self.shown_peaks['FWHM_left'], self.shown_peaks['FWHM_right'], color='red')
            if slice_axis == 'x':
                self.axs[1].set_title(f'Slice through the x-axis at y = {rx.y:.2f} {self.grid.units}')
                self.axs[1].set_xlabel(f'x [{self.grid.units}]')
            if slice_axis == 'y':
                self.axs[1].set_title(f'Slice through the y-axis at x = {rx.x:.2f} {self.grid.units}')
                self.axs[1].set_xlabel(f'y [{self.grid.units}]')
            self.axs[1].set_ylabel(self.shown_value_info['name'])
        
        if EUCAP_FIGURE:
            path = r'C:\Users\rwydaegh\OneDrive - UGent\rwydaegh\EuCAP 2024\Figures'
            plt.savefig(path + r'\measurement_simulation.png', bbox_inches='tight', dpi=600)
            #plt.savefig(path + r'\measurement_measurement.png', bbox_inches='tight', dpi=600)

        plt.tight_layout()
        try:
            plt.pause(.1)
        except:
            pass
        if show_figure:
            plt.show()

    def plot_2D_slices(self, total_animation_time = 10, **kwargs):
        # avoid circular import
        from .antenna import Pos
        
        assert not self.grid.is_2D, 'Cannot plot 3D for 2D grid'

        nbr_of_slices = len(self.grid.z)
        pause_time = total_animation_time/nbr_of_slices
        
        plt.ion()
        for z_height in np.linspace(self.grid.pos_ll.z, self.grid.pos_ur.z, nbr_of_slices):
            if self.verbose:
                print('z_height = {:.2f} cm'.format(100*z_height))
            self.plot_2D_slice(z_pos = Pos(0,0,z_height), **kwargs) 
            try:
                plt.pause(pause_time)
            except:
                pass

    def plot_radial_probability_density_function(self, radial_resolution = 0, subgrid = None, in_wavelengths = True, only_return = False, **kwargs):
        ''' Plots the radial density function of the given value. '''
        
        matplotlib.rcParams['axes.formatter.limits'] = (-3, 3)  
        
        # Get value with the kwargs
        if not self.use_existing_shown_value:
            value, value_info = self.get_value(**kwargs)
        else:
            value, value_info = self.shown_value, self.shown_value_info

        if subgrid is not None:
            grid = self.grid.get_subgrid(subgrid[0], subgrid[1])

        # Get the radial density function
        point_distances = []
        fields = []
        if in_wavelengths:
            if self.grid.units == 'm':
                wavelength = self.wavelength
            elif self.grid.units == 'λ':
                wavelength = 1
        for x, x_idx in zip(grid.x, grid.x_idx_global):
            for y, y_idx in zip(grid.y, grid.y_idx_global):
                for z, z_idx in zip(grid.z, grid.z_idx_global):
                    r = np.sqrt(x**2 + y**2 + z**2)
                    if in_wavelengths:
                        r /= wavelength
                    point_distances.append(np.round(r, 6))
                    fields.append(value[x_idx, y_idx, z_idx])
        
        # Round each distance to the radial resolution so the data gets binned
        point_distances = np.array(point_distances)
        if radial_resolution != 0:
            point_distances = np.round(np.round(point_distances/radial_resolution)*radial_resolution, 6)

        # Sort the point_distances, keep indices
        sorted_indices = np.argsort(point_distances)
        sorted_point_distances = np.array(point_distances)[sorted_indices]
        sorted_fields = np.array(fields)[sorted_indices]

        # Unique distances and their indices
        unique_distances, indices = np.unique(sorted_point_distances, return_inverse=True)

        # Probability density
        field_distributions = [[] for _ in range(len(unique_distances))]
        for i, field in enumerate(sorted_fields):
            field_distributions[indices[i]].append(field)
        average_field_density = np.array([np.median(field_distribution) for field_distribution in field_distributions])
        percentile_25_field_density = np.array([np.percentile(field_distribution, 25) for field_distribution in field_distributions])
        percentile_75_field_density = np.array([np.percentile(field_distribution, 75) for field_distribution in field_distributions])

        # The maximum distance which fits a sphere in the grid
        smallest_dimension = min(grid.x_size, grid.y_size, grid.z_size)
        max_spherical_dist = smallest_dimension/2
        if in_wavelengths:
            max_spherical_dist /= self.wavelength

        if only_return:
            # Returning
            return unique_distances, average_field_density
        else:
            # Plotting
            plt.figure()
            if not in_wavelengths:
                unique_distances *= 100
                max_spherical_dist *= 100
            plt.scatter(unique_distances, average_field_density, label='Median', color = 'red', s = 1)
            plt.fill_between(unique_distances, percentile_25_field_density, percentile_75_field_density, alpha=0.2, label='25th to 75th percentile', color = 'blue')
            # vertical line at the maximum distance which fits a sphere in the grid
            plt.axvline(x=max_spherical_dist, color='black', linestyle='--', label='Maximum distance which fits a sphere in the grid')
            # a patch everywhere past this line to indicate that the data is not reliable
            plt.axvspan(max_spherical_dist, unique_distances[-1], alpha=0.05, color='red', label='Data past this line is less reliable')
            plt.xlim(0, unique_distances[-1])
            plt.ylim(0, 1.1*max( np.max(average_field_density), np.max(percentile_25_field_density), np.max(percentile_75_field_density) ))
            plt.xlabel(f"Distance [{('cm' if not in_wavelengths else 'λ')}]")
            plt.ylabel(value_info['name'] + f" [{value_info['units']}]")
            plt.legend(loc='upper right')
            plt.title('Radial Probability Density Function')
            plt.show()

    def plot_angular_probability_density_function(self, angular_resolution = 5, r_range = None, subgrid = None, divide_radial_part = False, in_wavelengths = True, **kwargs):
        ''' Plots the theta and phi density function of the given value. '''

        matplotlib.rcParams['axes.formatter.limits'] = (-3, 3)  

        # Get value with the kwargs
        if not self.use_existing_shown_value:
            value, value_info = self.get_value(**kwargs)
        else:
            value, value_info = self.shown_value, self.shown_value_info

        if subgrid is not None:
            grid = self.grid.get_subgrid(subgrid[0], subgrid[1])

        # Get the radial density function
        point_thetas = []
        point_phis = []
        point_r = []
        fields = []
        if in_wavelengths:
            if self.grid.units == 'm':
                wavelength = self.wavelength
            elif self.grid.units == 'λ':
                wavelength = 1
        for x, x_idx in zip(grid.x, grid.x_idx):
            for y, y_idx in zip(grid.y, grid.y_idx):
                for z, z_idx in zip(grid.z, grid.z_idx):
                    r = np.sqrt(x**2 + y**2 + z**2)
                    if in_wavelengths:
                        r /= self.wavelength
                    point_thetas.append(np.round(np.arccos(z/r), 6))
                    point_phis.append(np.round(np.arctan2(y,x), 6))
                    point_r.append(np.round(r, 6))
                    fields.append(value[x_idx, y_idx, z_idx])

        # Divide the fields by the median of the fields from the radial probability density function
        if divide_radial_part:
            radial_resolution = 0.5/1000
            unique_distances, average_field_density = self.plot_radial_probability_density_function(radial_resolution = radial_resolution, in_wavelengths = False, only_return = True, **kwargs)
            for r_angular, field_angular in zip(point_r, fields):
                r_angular = np.round(np.round(r_angular/radial_resolution)*radial_resolution, 6)
                field_angular /= average_field_density[np.where(unique_distances == r_angular)]

        # Consider only those in r_range
        if r_range is not None:
            for theta, phi, r, field in zip(point_thetas, point_phis, point_r, fields):
                if r < r_range[0] or r > r_range[1]:
                    point_thetas.remove(theta)
                    point_phis.remove(phi)
                    fields.remove(field)

        # Round each theta and phi to the angular resolution so the data gets binned
        point_thetas = np.array(point_thetas) * 180/np.pi
        point_phis = np.array(point_phis) * 180/np.pi
        point_thetas = np.round(point_thetas/angular_resolution)*angular_resolution
        point_phis = np.round(point_phis/angular_resolution)*angular_resolution
        point_thetas *= np.pi/180
        point_phis *= np.pi/180

        # Sort the point_thetas and point_phis, keep indices
        sorted_indices_theta = np.argsort(point_thetas)
        sorted_point_thetas = np.array(point_thetas)[sorted_indices_theta]
        sorted_fields_theta = np.array(fields)[sorted_indices_theta]

        sorted_indices_phi = np.argsort(point_phis)
        sorted_point_phis = np.array(point_phis)[sorted_indices_phi]
        sorted_fields_phi = np.array(fields)[sorted_indices_phi]

        # Unique distances and their indices
        unique_thetas, indices_thetas = np.unique(sorted_point_thetas, return_inverse=True)
        unique_phis, indices_phis = np.unique(sorted_point_phis, return_inverse=True)

        # Probability density
        field_distributions_theta = [[] for _ in range(len(unique_thetas))]
        field_distributions_phi = [[] for _ in range(len(unique_phis))]
        for i, field in enumerate(sorted_fields_theta):
            field_distributions_theta[indices_thetas[i]].append(field)
        for i, field in enumerate(sorted_fields_phi):
            field_distributions_phi[indices_phis[i]].append(field)
        average_field_density_theta = np.array([np.median(field_distribution) for field_distribution in field_distributions_theta])
        average_field_density_phis = np.array([np.median(field_distribution) for field_distribution in field_distributions_phi])

        percentile_25_field_density_theta = np.array([np.percentile(field_distribution, 25) for field_distribution in field_distributions_theta])
        percentile_75_field_density_theta = np.array([np.percentile(field_distribution, 75) for field_distribution in field_distributions_theta])
        percentile_25_field_density_phis = np.array([np.percentile(field_distribution, 25) for field_distribution in field_distributions_phi])
        percentile_75_field_density_phis = np.array([np.percentile(field_distribution, 75) for field_distribution in field_distributions_phi])

        # The maximum theta which fits a sphere in the grid
        smallest_dimension = min(grid.x_size, grid.y_size, grid.z_size)
        min_spherical_theta = np.arccos(smallest_dimension/2/grid.z_size)
        max_spherical_theta = np.pi - min_spherical_theta

        # Plotting
        fig = plt.figure()
        ax_theta = fig.add_subplot(121, projection='polar')
        ax_theta.set_theta_zero_location("N")
        ax_theta.set_theta_direction(-1)
        ax_theta.set_thetamax(180)
        ax_theta.set_title('Theta')
        ax_phi = fig.add_subplot(122, projection='polar')
        ax_phi.set_theta_zero_location("N")
        ax_phi.set_theta_direction(-1)
        ax_phi.set_title('Phi')

        ax_theta.scatter(unique_thetas, average_field_density_theta, label='Median', color = 'red', s = 1)
        ax_phi.scatter(unique_phis, average_field_density_phis, label='Median', color = 'red', s = 1)
        ax_theta.fill_between(unique_thetas, percentile_25_field_density_theta, percentile_75_field_density_theta, alpha=0.2, label='25th to 75th percentile', color = 'blue')
        ax_phi.fill_between(unique_phis, percentile_25_field_density_phis, percentile_75_field_density_phis, alpha=0.2, label='25th to 75th percentile', color = 'blue')
        ax_theta.axvline(x=min_spherical_theta, color='black', linestyle='--', label='Minimum theta which fits a sphere in the grid')
        ax_theta.axvline(x=max_spherical_theta, color='black', linestyle='--', label='Maximum theta which fits a sphere in the grid')
        ax_theta.axvspan(0, min_spherical_theta, alpha=0.05, color='red', label='Data is less reliable')
        ax_theta.axvspan(max_spherical_theta, np.pi, alpha=0.05, color='red', label='Data is less reliable')

        if r_range:
            fig.suptitle(f'Angular Probability Density Function (r = {r_range[0]:2f} to {r_range[1]:.2f} {("cm" if not in_wavelengths else "λ")})')
        else:
            fig.suptitle(f'Angular Probability Density Function')

        # make a legend for the whole figure
        handles, labels = ax_theta.get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center', ncol=3)
        
        plt.show()

    def plot_layout(self, value_type='abs', component_type='norm', field_type='E', scaling_type='linear', rms=False, z_pos=None, from_tx_element_nbr=None, slice_through_rx = None, plot_field_data=True, plot_base_station=True, plot_receivers=True):
        ''' Plot the layout of the base station and receivers. '''

        # Speed up rendering
        matplotlib.rcParams['path.simplify'] = True
        old_value = matplotlib.rcParams['path.simplify_threshold']
        matplotlib.rcParams['path.simplify_threshold'] = 1.0
        
        # Create figure
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        list_of_shown_objects = []

        # Plot grid
        self.grid.plot_wireframe(ax)
        list_of_shown_objects.append(self.grid.pos_ll)
        list_of_shown_objects.append(self.grid.pos_ur)

        # Set axis limits with a margin of 10%, and labels
        # This is necessary so the antenna pattern plots are well proportioned
        for element in self.radiating_collection.elements:
            list_of_shown_objects.append(element)
        x_min = min([obj.x for obj in list_of_shown_objects])
        x_max = max([obj.x for obj in list_of_shown_objects])
        y_min = min([obj.y for obj in list_of_shown_objects])
        y_max = max([obj.y for obj in list_of_shown_objects])
        z_min = min([obj.z for obj in list_of_shown_objects])
        z_max = max([obj.z for obj in list_of_shown_objects])
        x_margin = (x_max - x_min)*0.1
        y_margin = (y_max - y_min)*0.1
        z_margin = (z_max - z_min)*0.1
        ax.set_xlim(x_min - x_margin, x_max + x_margin)
        ax.set_ylim(y_min - y_margin, y_max + y_margin)
        ax.set_zlim(z_min - z_margin, z_max + z_margin)       
        ax.set_xlabel('x [m]')
        ax.set_ylabel('y [m]')
        ax.set_zlabel('z [m]')

        # Plot field data
        if plot_field_data:
            if z_pos is None:
                if slice_through_rx is None:
                    try:
                        z_pos = self.receivers.line_pos_1
                    except:
                        z_pos = self.receivers.antenna_elements[0]
                else:
                    z_pos = self.receivers.antenna_elements[slice_through_rx]
            z_pos.discretize_on(self.grid)
            self.shown_value, self.shown_value_info = self.get_value(value_type=value_type, component_type=component_type, field_type=field_type, scaling_type=scaling_type, rms=rms, z_pos=z_pos, from_tx_element_nbr=from_tx_element_nbr)
            if 'dB' not in self.shown_value_info['units']:
                if self.shown_value_info['always_positive']:
                    self.cmap = 'jet'
                    self.norm = None
                else:
                    finite_value = self.shown_value[np.isfinite(self.shown_value)]
                    if finite_value.min() < 0 and 0 < finite_value.max():
                        self.cmap = 'bwr'
                        #self.norm = DivergingNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                        self.norm = TwoSlopeNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                    else:
                        self.cmap = 'jet'
                        self.norm = None
            else:
                self.cmap = 'jet'
                self.norm = None
            x, y, _ = self.grid.get_slice('all', 'z', z_pos.z_idx)
            if not self.grid.is_2D:
                self.color_bar = ax.contourf(x, y, self.shown_value, 50, zdir='z', offset=z_pos.z, cmap = self.cmap, norm = self.norm)
                #self.color_bar = ax.plot_surface(x, y, self.shown_value, zdir='z', offset=z_pos.z, cmap = self.cmap, norm = self.norm)
            else:
                self.color_bar = ax.contourf(self.grid.x_2D, self.grid.y_2D, self.shown_value, 50, z_dir='z', offset=z_pos.z, cmap = self.cmap, norm = self.norm)
            # Colorbar axis 
            self.cb = fig.colorbar(self.color_bar, cax=fig.add_axes([0.92, 0.1, 0.02, 0.8]), orientation='vertical')
            ax.set_title(f"{self.shown_value_info['name']} (z = {100*self.shown_value_info['z_height']:.2f} cm)")

        # Plot base station
        if plot_base_station:
            for element in self.radiating_collection.elements:
                element.plot_pattern(ax=ax, normalized = 0.2, stride = 10, alpha = 0.5)
            ax.scatter(element.x, element.y, element.z, s=50, color='green')

        # Plot receivers
        if plot_receivers:
            for rx in self.receivers.antenna_elements:
                rx.plot_pattern(ax=ax, normalized = 0.2, stride = 10, alpha = 0.1)
                ax.scatter(rx.x, rx.y, rx.z, s=50, color='red')

        plt.show()

        matplotlib.rcParams['path.simplify'] = False
        matplotlib.rcParams['path.simplify_threshold'] = old_value

    @property
    def gram_matrix(self):
        return self.channel_matrix.H @ self.channel_matrix

    @property
    def gamma(self):
        gram_matrix_magn = np.square(np.abs(self.gram_matrix))
        return float(np.sum([gram_matrix_magn[i, i] for i in range(gram_matrix_magn.shape[0])])/np.sum(gram_matrix_magn, axis = (0, 1)))

    @property
    def kappa(self):
        singular_values = scipy.linalg.svd(self.channel_matrix, compute_uv = False)

        return singular_values[0]/singular_values[-1]

    def plot_channel(self, as_gram_matrix = True, print_results = True):
        shown_kappa, shown_gamma = self.kappa, self.gamma
        if print_results is False and self.verbose:
            print(f'Gamma = {shown_gamma:.2f}.')
            print(f'Kappa = {shown_kappa:.2f}.')
        
        if as_gram_matrix:
            title = 'Gram matrix'
        else:
            title = 'Channel matrix'
        plt.figure(title)
        
        if as_gram_matrix:
            plt.imshow(np.abs(self.gram_matrix))
            plt.title(f'$\gamma = {shown_gamma:.2f}, \kappa = {shown_kappa:.2f}$')
        else:
            plt.imshow(np.abs(self.channel_matrix))
        plt.colorbar()
        plt.xlabel('Tx')
        plt.ylabel('Rx')

        return shown_kappa, shown_gamma

class FourierTransformSimulation(object):

    def __init__(self, subgrid, simulation):
        self.subgrid = subgrid
        self.field_simulation = simulation
        self.basis_function_simulation = deepcopy(simulation)
        from hybridizer.collection import ClusterCollection
        self.basis_function_simulation.clusters = ClusterCollection()

    def compute_fourier_transform(self, n_theta = 9, n_phi = 18):
        self.n_theta = n_theta + 1
        self.n_phi = n_phi + 1
        self.thetas = np.linspace(0, np.pi, self.n_theta)
        self.phis = np.linspace(0, 2*np.pi, self.n_phi)

        from hybridizer.antenna import Pos
        cluster_pos_array = []
        for theta in self.thetas:
            for phi in self.phis:
                relative_pos = Pos(
                    np.sin(theta) * np.cos(phi),
                    np.sin(theta) * np.sin(phi),
                    np.cos(theta)
                )
                pos = (relative_pos + self.subgrid.center).pos
                cluster_pos_array.append(pos)
        cluster_pos_array = np.array(cluster_pos_array)

        self.basis_function_simulation.reset()
        self.basis_function_simulation.grid = self.subgrid
        self.basis_function_simulation.clusters.add_cluster_list(cluster_pos_array, self.subgrid.center)
        for cluster in self.basis_function_simulation.clusters.clusters:
            cluster.radiation_as_plane_wave = False
            cluster.field_at_receiver = 1.0

        E_field = self.field_simulation.E
        
        E_fft = np.zeros((3, self.n_theta, self.n_phi), dtype=np.complex128)
        self.basis_function_simulation.compute_channel_matrix(using_Ey=True)
        cluster_idx = 0
        for theta_idx in range(self.n_theta):
            for phi_idx in range(self.n_phi):
                E_fft[:, theta_idx, phi_idx] += np.sum(
                    E_field[:, self.subgrid.x_3D_idx_global_slice, self.subgrid.y_3D_idx_global_slice, self.subgrid.z_3D_idx_global_slice]
                    * np.conj(self.basis_function_simulation.clusters.clusters[cluster_idx].E), 
                    axis=(1, 2, 3)
                )
                cluster_idx += 1

        return E_fft

