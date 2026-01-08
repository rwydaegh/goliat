import os, shutil
import matplotlib
if os.name == 'nt':
    matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
from tqdm import tqdm
import traceback
import scipy.io as sio
import numpy as np
import pickle
import time
from pathlib import Path

from .simulation import DeterministicSimulation
from .collection import ClusterCollection, AntennaCollection
from .antenna import Pos
from .grid import Grid, SubGrid

class TimeDomainSimulation(object):
    ''' This class uses a series of DeterministicSimulations which correspond to different time steps to simulate the time domain response of the system. 
    The simulation has a number of Grids around each position of the receivers that move in time.
    The AntennaCollection (base station) is assumed to be fixed in time. 
    The ClusterCollection can move in time.
    '''

    def __init__(self):
        ''' Initialize the TimeDomainSimulation. '''

        self.polarization = 'TEz'
        self.default_pickle_save_name = 'max_Sab_results'
        self.scenario_list = []
        self.hotspots = []

        self.use_full_quadriga_channel = True # False case was previous implementation, backwards compatibility needs to be checked
        self.assume_mmMAGIC = True
        self.rx = 0
        self.cache_dir = 'tmp'
        self.scene = 'tmp'

        self.cluster_radiation_as_almost_plane_wave = True

        self.set_verbose(True)

    def set_verbose(self, verbose):
        ''' Set the verbosity of the TimeDomainSimulation. '''

        self.verbose = verbose
        if hasattr(self, 'simulations'):
            for simulation in self.simulations:
                simulation.set_verbose(verbose) # sets verbosity of collections and their clusters too

    ## Paths and directories of data

    @property
    def scene_dir(self):
        ''' Return the path of the scene directory. '''

        path_of_this_file = Path(os.path.dirname(os.path.abspath(__file__)))
        return path_of_this_file.parent / f'data/{self.scene}'

    @property
    def python_dir(self):
        ''' Return the path of the python directory. '''

        python_dir = self.scene_dir / 'python'
        if not os.path.exists(python_dir):
            os.makedirs(python_dir)
        return python_dir

    @property
    def cache_path(self):
        ''' Return the path of the cache directory. '''

        cache_path = self.python_dir / self.cache_dir
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        return cache_path
    
    @property
    def quadriga_dir(self):
        ''' Return the path of the quadriga directory. '''

        quadriga_dir = self.scene_dir / 'quadriga'
        if not os.path.exists(quadriga_dir):
            os.makedirs(quadriga_dir)
        return quadriga_dir

    ## Read data

    def read_ray_tracing_data(self, file_name):

        raise NotImplementedError

        # sqlite file from Wireless InSite

        # use rays.py

        # make sure you define tx_positions, rx_positions, lbs_positions etc. Like in read_quadriga_data

    def read_quadriga_data(self, file_name, channel_type):
        ''' Read the quadriga data from the .mat file. '''
        
        self.quadriga_file_name = file_name
        data = sio.loadmat(str(self.quadriga_dir / f'{self.quadriga_file_name}.mat'))['data']

        if self.use_full_quadriga_channel:
            if channel_type == 'precoded':
                self.channel = data['precoded_channel'][0][0]
            elif channel_type == 'unprecoded':
                self.channel = data['unprecoded_channel'][0][0]
            elif channel_type == '':
                self.channel = data['channel'][0][0]
            else:
                raise ValueError('channel_type should be either "precoded", "unprecoded" or "".')
            self.N_snapshots = self.channel.shape[-1]
            self.snapshots = np.arange(self.N_snapshots)
        else:
            if channel_type == 'precoded':
                self.receive_vector = data['precoded_vector'][0][0]
            elif channel_type == 'unprecoded':
                self.receive_vector = data['unprecoded_vector'][0][0]
            elif channel_type == '':
                self.receive_vector = data['vector'][0][0]
            else:
                raise ValueError('channel_type should be either "precoded", "unprecoded" or "".')
            self.N_snapshots = self.receive_vector.shape[-1]
            self.snapshots = np.arange(self.N_snapshots)

        self.rx_positions = data['rx_positions'][0][0] # moves along the path of the user
        self.lbs_positions = data['lbs_position'][0][0] # infinitely far, but correct angle (for Ray-Tracing)
        self.num_sub_paths = data['num_sub_paths'][0][0] # number of rays for each rx position
        self.frequency = data['center_frequency'][0][0][0][0] 

        try:
            scenario_list = data['scenario_list'][0][0][0].split(' ')
            self.scenario_list = np.reshape(np.array(scenario_list),[self.rx_positions.shape[1],2])
        except:
            pass

    def read_new_channel(self, file_name, channel_type):
        ''' Assumes data (e.g. tx, rx, lbs, ... positions) has already been read.
        Also 
         except that this function changes self.channel to a new channel. '''

        self.quadriga_file_name = file_name
        data = sio.loadmat(str(self.quadriga_dir / f'{self.quadriga_file_name}.mat'))['data']

        if self.use_full_quadriga_channel:
            if channel_type == 'precoded':
                self.channel = data['precoded_channel'][0][0]
            elif channel_type == 'unprecoded':
                self.channel = data['unprecoded_channel'][0][0]
            elif channel_type == '':
                self.channel = data['channel'][0][0]
            else:
                raise ValueError('channel_type should be either "precoded", "unprecoded" or "".')
        else:
            if channel_type == 'precoded':
                self.receive_vector = data['precoded_vector'][0][0]
            elif channel_type == 'unprecoded':
                self.receive_vector = data['unprecoded_vector'][0][0]
            elif channel_type == '':
                self.receive_vector = data['vector'][0][0]
            else:
                raise ValueError('channel_type should be either "precoded", "unprecoded" or "".')

        if hasattr(self, 'snapshot_numbers_in_input_data'):
            snapshots = self.snapshot_numbers_in_input_data[self.snapshots]
            if self.use_full_quadriga_channel:
                self.channel = self.channel[:,:,:,:,snapshots]
            else:
                self.receive_vector = self.receive_vector[:,:,:,snapshots]

        for clusters in self.clusters:
            for cluster in clusters.clusters:
                if self.use_full_quadriga_channel:
                    cluster.field_at_receiver = np.sum(self.channel[self.rx, :, cluster.i_big_cluster, cluster.i_sub_cluster, cluster.i_snapshot])
                else:
                    cluster.field_at_receiver  = self.receive_vector[self.rx, cluster.i_big_cluster, cluster.i_sub_cluster, cluster.i_snapshot]

    ## Process data

    def sample_input_data(self, max_num_samples=1000):
        ''' Sample the input data only every x number of samples such that the total length is max_num_samples. '''

        if self.use_full_quadriga_channel:
            nbr_of_snap = self.channel.shape[-1]
        else:
            nbr_of_snap = self.receive_vector.shape[-1]
        assert max_num_samples <= nbr_of_snap, 'max_num_samples is larger than the number of snapshots in the input data.'
        every_N = int(nbr_of_snap/max_num_samples)

        if self.use_full_quadriga_channel:
            self.channel = self.channel[:,:,:,:,::every_N]
            self.rx_positions = self.rx_positions[:,:,::every_N]
            self.lbs_positions = self.lbs_positions[:,:,:,:,::every_N]
        else:
            self.receive_vector = self.receive_vector[:,:,:,::every_N]
            self.rx_positions = self.rx_positions[:,::every_N]
            self.lbs_positions = self.lbs_positions[:,:,::every_N]
            self.num_sub_paths = self.num_sub_paths[:,::every_N]
            if self.scenario_list:
                self.scenario_list = self.scenario_list[::every_N,:]
        self.snapshot_numbers_in_input_data = np.arange(self.N_snapshots)[::every_N]

        if self.use_full_quadriga_channel:
            self.N_snapshots = self.channel.shape[-1]
        else:
            self.N_snapshots = self.receive_vector.shape[-1]
        self.snapshots = np.arange(self.N_snapshots)

    def cut_input_data(self, min_num_snapshots=None, max_num_snapshots=None):
        ''' Cut off the input data between two specified values. '''

        if self.use_full_quadriga_channel:
            nbr_of_snap = self.channel.shape[-1]
        else:
            nbr_of_snap = self.receive_vector.shape[-1]
        if min_num_snapshots is None:
            min_num_snapshots = 0
        if max_num_snapshots is None:
            max_num_snapshots = nbr_of_snap
        assert min_num_snapshots >= 0, 'min_num_snapshots is smaller than 0.'
        assert max_num_snapshots <= nbr_of_snap, 'max_num_snapshots is larger than the number of snapshots in the input data.'

        if self.use_full_quadriga_channel:
            self.channel = self.channel[:,:,:,:,min_num_snapshots:max_num_snapshots]
            self.rx_positions = self.rx_positions[:,:,min_num_snapshots:max_num_snapshots]
            self.lbs_positions = self.lbs_positions[:,:,:,:,min_num_snapshots:max_num_snapshots]
        else:
            self.receive_vector = self.receive_vector[:,:,:,min_num_snapshots:max_num_snapshots]
            self.rx_positions = self.rx_positions[:,min_num_snapshots:max_num_snapshots]
            self.lbs_positions = self.lbs_positions[:,:,min_num_snapshots:max_num_snapshots]
            self.num_sub_paths = self.num_sub_paths[:,min_num_snapshots:max_num_snapshots]
            if len(self.scenario_list)==0:
                self.scenario_list = self.scenario_list[min_num_snapshots:max_num_snapshots,:]
        self.snapshot_numbers_in_input_data = np.arange(self.N_snapshots)[min_num_snapshots:max_num_snapshots]

        if self.use_full_quadriga_channel:
            self.N_snapshots = self.channel.shape[-1]
        else:
            self.N_snapshots = self.receive_vector.shape[-1]
        self.snapshots = np.arange(self.N_snapshots)

    def get_chunk_delimiters(self, num_chunks, with_cluster_weights=True):
        ''' Get a list of tuples containing 1. the index of the chunk, 2. the start snapshot of the chunk, 3. the end snapshot of the chunk. 
        Sometimes the final chunk is smaller than the others, we have to account for that. '''

        if with_cluster_weights:
            total_load = sum(self.num_clusters)
            target_load_per_chunk = total_load / num_chunks

            chunk_delimiters = []
            current_load = 0
            start_index = 0

            for i, clusters in enumerate(self.num_clusters):
                current_load += clusters
                if current_load >= target_load_per_chunk or i == len(self.num_clusters) - 1:
                    # When the current load meets or exceeds the target, or we're at the last snapshot,
                    # finalize the current chunk and reset for the next.
                    chunk_delimiters.append((len(chunk_delimiters), start_index, i + 1))
                    start_index = i + 1
                    current_load = 0

                    # Adjust the target load per chunk if necessary to account for rounding issues.
                    remaining_chunks = num_chunks - len(chunk_delimiters)
                    if remaining_chunks > 0:
                        remaining_load = total_load - sum([cluster for _, start, end in chunk_delimiters for cluster in self.num_clusters[start:end]])
                        target_load_per_chunk = remaining_load / remaining_chunks

            return chunk_delimiters
        else:
            chunk_delimiters = []
            for i in range(num_chunks):
                start = int(i * self.N_snapshots / num_chunks)
                if i == num_chunks - 1:
                    end = self.N_snapshots
                else:
                    end = int((i + 1) * self.N_snapshots / num_chunks)
                chunk_delimiters.append((i, start, end))

            return chunk_delimiters
    
    ## Make components

    def make_grids_from_size(self, rx, grid_size, resolution=50):
        ''' Make the grids around the receivers. '''

        self.grids = []
        for rx_pos in self.rx_positions[:,rx,:].T:
            rx_pos = Pos.from_vec(rx_pos)
            grid = Grid.from_size(rx_pos, grid_size, resolution, is_2D = False)
            self.grids.append(grid)

    def make_grids_from_points(self, rx, x, y, z):
        ''' Make the grids around the receivers based on a a reference exposure grid. '''

        # Make copies of the x, y, z arrays, because you might modify the exposure grid from where the function is called
        x = np.copy(x)
        y = np.copy(y)
        z = np.copy(z)

        self.grids = []
        for rx_pos in self.rx_positions[:,rx,:].T:
            rx_pos = Pos.from_vec(rx_pos)
            x_center = (x[0] + x[-1])/2
            y_center = (y[0] + y[-1])/2
            z_center = (z[0] + z[-1])/2
            x_center_idx = np.argmin(np.abs(x - x_center))
            y_center_idx = np.argmin(np.abs(y - y_center))
            z_center_idx = np.argmin(np.abs(z - z_center))
            x_center = x[x_center_idx]
            y_center = y[y_center_idx]
            z_center = z[z_center_idx]
            translation = Pos(x_center, y_center, z_center) - rx_pos
            x = x - translation.x
            y = y - translation.y
            z = z - translation.z
            grid = Grid.from_points(x, y, z)
            self.grids.append(grid)

    def add_base_station(self, base_station):
        ''' Add the base station. '''

        self.base_station = base_station

    def make_receivers(self):
        ''' Make the receivers. '''
        
        self.receivers = []
        for rx_pos in self.rx_positions[:,self.rx,:].T:
            receiver_collection = AntennaCollection()
            receiver_collection.set_verbose(self.verbose)
            receiver_collection.add_antenna_element([rx_pos[0], rx_pos[1], rx_pos[2], 'omni', None])
            self.receivers.append(receiver_collection)

    def make_clusters_old(self, max_num_clusters=None, max_num_sub_clusters=None):
        ''' Make the cluster collections for each snapshot consisting of 'big' clusters with subclusters in them.'''

        assert not self.use_full_quadriga_channel, 'Old implementation with just the receiving vector and most important clusters'

        self.clusters = []
        # Loop through the snapshots
        for i_snapshot, num_sub_paths, lbs_pos, receiver_coll in tqdm(zip(self.snapshots, self.num_sub_paths.T, self.lbs_positions.T, self.receivers), disable=(not self.verbose)):
            cluster_collection = ClusterCollection()
            cluster_collection.set_verbose(self.verbose)

            cluster_idx = 0 # index that follows the flattened array with all subclusters of all big clusters

            # How many big clusters are there?
            stop_point = np.argmin(num_sub_paths) # if no big cluster, this is marked in Quadriga as having no subclusters
            if stop_point != 0:
                num_sub_paths = num_sub_paths[:stop_point]
            N_big_clusters = num_sub_paths.shape[0]

            # If specified, only add big clusters up to a maximum number
            if max_num_clusters is not None:
                N_big_clusters = min(max_num_clusters, N_big_clusters)

            # Loop through those "big clusters", aka just clusters in Quadriga
            for i_big_cluster in range(N_big_clusters):
                
                # For this big cluster, how many subclusters are there?
                N_sub_clusters = num_sub_paths[i_big_cluster]

                # If specified, only add subclusters up to a maximum number
                if max_num_sub_clusters is not None:
                    N_sub_clusters = min(max_num_sub_clusters, N_sub_clusters)

                # Loop through those subclusters
                for i_sub_cluster in range(N_sub_clusters):
                    cluster_pos = lbs_pos[cluster_idx,:]
                    cluster = cluster_collection.add_cluster(cluster_pos, receiver_coll.antenna_elements[0])                    
                    cluster.field_at_receiver = self.receive_vector[self.rx,i_big_cluster,i_sub_cluster,i_snapshot]

                    cluster.i_big_cluster = i_big_cluster
                    cluster.i_sub_cluster = i_sub_cluster
                    cluster.i_snapshot = i_snapshot # this is not the same as the snapshot number in the input data

                    cluster_idx += 1
            
            # Finally add the cluster collection, i.e., the collection of all clusters in this snapshot 
            self.clusters.append(cluster_collection)

    def make_clusters(self, prune_percentage):
        ''' Simpler and newer implementation that just uses the full channel matrix. '''

        assert self.use_full_quadriga_channel
        assert self.assume_mmMAGIC

        GENERAL_BIAS = 1e8
        if self.verbose:
            print('WARNING: using a general bias of 1e8 to deal with floating point errors in the Quadriga data. Fix this!')

        self.clusters = []
        for i_snapshot, rx_pos, receiver_coll in tqdm(zip(self.snapshots, self.rx_positions[:,self.rx,:].T, self.receivers), disable=(not self.verbose)):
            cluster_collection = ClusterCollection()
            cluster_collection.set_verbose(self.verbose)

            # Loop through the transmitters
            for i_tx in range(self.channel.shape[1]):
                # Loop through the big clusters
                i_lbs = 0
                for i_big_cluster in range(self.channel.shape[2]):
                    field = self.channel[self.rx, i_tx, i_big_cluster, 0, i_snapshot]

                    # IMPORTANT: for floating point errors
                    # DEAL WITH THIS LATER
                    field *= GENERAL_BIAS

                    if field == 0:
                        # note that we dont add to i_lbs
                        continue
                    if i_lbs >= self.lbs_positions.shape[3]:
                        # happens in these merges
                        continue
                    cluster_pos = self.lbs_positions[:, self.rx, i_tx, i_lbs, i_snapshot]
                    cluster_pos_dist = np.linalg.norm(cluster_pos)
                    if cluster_pos_dist == 0 or cluster_pos_dist > 10_000:
                        cluster_pos = self.lbs_positions[:, self.rx, i_tx, i_lbs, i_snapshot-1]
                        cluster_pos_dist = np.linalg.norm(cluster_pos)
                        if cluster_pos_dist > 10_000:
                            try:
                                # pick the next one
                                cluster_pos = self.lbs_positions[:,self.rx, i_tx, i_lbs, i_snapshot+1]
                                cluster_pos_dist = np.linalg.norm(cluster_pos)
                                # it could be that after this it is still not okay because it is rapidly shifting between scenario's, which we will accept now
                            except:
                                # usually happens when there is no next i_snapshot, especially when the snapshots are cut in small chunks
                                pass # use previous one

                    cluster = cluster_collection.add_cluster(cluster_pos, receiver_coll.antenna_elements[self.rx])
                    cluster.radiation_as_almost_plane_wave = self.cluster_radiation_as_almost_plane_wave
                    cluster.field_at_receiver = field

                    cluster.i_big_cluster = i_big_cluster
                    cluster.i_sub_cluster = 0
                    cluster.i_snapshot = i_snapshot

                    i_lbs += 1

            cluster_collection.prune_clusters(prune_percentage / 100)
            self.clusters.append(cluster_collection)

    @property
    def num_clusters(self):
        ''' Return the number of clusters across all snapshots. '''

        return np.array([np.sum(self.channel[self.rx, 0, :, 0, i] == 0) for i in range(self.channel.shape[-1])])

    def make_simulations(self, **kwargs):
        ''' Make the simulations. '''

        if hasattr(self, 'base_station'):
            self.make_base_station_simulations(**kwargs)
        elif hasattr(self, 'clusters'):
            self.make_cluster_simulations(**kwargs)

    def make_cluster_simulations(self, max_num_simulations=None):
        ''' Make the simulations, one for each cluster collection. '''
        
        self.simulations = []
        i = 0
        for grid, receiver, cluster_collection in zip(self.grids, self.receivers, self.clusters):
            if max_num_simulations is not None:
                if i>max_num_simulations:
                    break
            simulation =  DeterministicSimulation(grid, base_station=None, clusters=cluster_collection, receivers=receiver, polarization=self.polarization, frequency=self.frequency, scene=self.scene, verbose=self.verbose)
            self.simulations.append(simulation)

    def make_sliced_grids(self, thickness, distance_from_center=None, distance_from_sides=None):
        ''' Make the grids sliced. '''

        for simulation in self.simulations:
            simulation.make_sliced_grid(thickness = thickness, distance_from_center=distance_from_center, distance_from_sides=distance_from_sides)

    def make_base_station_simulations(self, only_sides_with_thickness=None, max_num_simulations=None):
        ''' Make the simulations, one for each base station. '''
        
        self.simulations = []
        i = 0
        for grid, receiver in zip(self.grids, self.receivers):
            if max_num_simulations is not None:
                if i>max_num_simulations:
                    break
            simulation = DeterministicSimulation(grid, base_station = self.base_station, receivers = receiver, polarization= self.polarization, frequency= self.frequency, scene = self.scene, verbose=self.verbose)
            simulation.set_verbose(self.verbose)
            if only_sides_with_thickness is not None:
                simulation.make_sliced_grid(thickness = only_sides_with_thickness)
            self.simulations.append(simulation)

    ## Run simulations

    def reset_simulations(self):
        ''' Reset the simulations. '''

        for simulation in self.simulations:
            simulation.reset()

    def radiate_elements_one_simulation(simulation):
        ''' # old way, comprenshive using a full channel
        simulation.compute_channel_matrix()
        simulation.custom_weighting(all_ones=True)
        simulation.clear_unimportant_data()
        '''
        simulation.efficient_cluster_addition()

    def radiate_elements(self, snapshots = None, only_keep_hotspot_data = False, method = 'anywhere', **kwargs):
        ''' Compute the channel matrices and let each Tx radiate equally for each simulation across time. '''

        if self.verbose:
            print('Radiating elements...')

        if snapshots is None:
            snapshots = self.snapshots

        for it in tqdm(range(len(snapshots)), disable=(not self.verbose)):
            snapshot = snapshots[it]
            simulation = self.simulations[snapshot]
            ''' # old way, comprenshive using a full channel
            simulation.compute_channel_matrix()
            simulation.custom_weighting(all_ones=True)
            simulation.clear_unimportant_data()
            '''
            simulation.efficient_cluster_addition()

            if only_keep_hotspot_data:
                if method == 'central':
                    hotspot = simulation.get_3D_hotspot_parameters(relative_hotspot_pos=Pos(0,0,0), **kwargs)
                elif method == 'anywhere':
                    hotspot = simulation.get_3D_hotspot_parameters(**kwargs)
                hotspot['snapshot'] = snapshot
                self.hotspots.append(hotspot)

                simulation.clear_important_data()

    def radiate_elements_multiple_hotspot_analyses(self, kwargs_list, snapshots = None):
        ''' Compute the channel matrices and let each Tx radiate equally for each simulation across time. '''

        if self.verbose:
            print('Radiating elements...')

        if snapshots is None:
            snapshots = self.snapshots

        self.hotspot_analysis_list = [[] for _ in range(len(kwargs_list))]
        for it in tqdm(range(len(snapshots)), disable = (not self.verbose)):
            try:
                snapshot = snapshots[it]
                simulation = self.simulations[snapshot]
                ''' # old way, comprenshive using a full channel
                simulation.compute_channel_matrix()
                simulation.custom_weighting(all_ones=True)
                simulation.clear_unimportant_data()
                '''

                simulation.efficient_cluster_addition()
            
                for i, kwargs in enumerate(kwargs_list):
                        method = kwargs['method']
                        # make a deep copy of the kwargs
                        kwargs_copy = kwargs.copy()
                        kwargs_copy.pop('method')
                        if method == 'central':
                            hotspot = simulation.get_3D_hotspot_parameters(relative_hotspot_pos=Pos(0,0,0), **kwargs_copy)
                        elif method == 'anywhere':
                            hotspot = simulation.get_3D_hotspot_parameters(**kwargs_copy)
                        hotspot['snapshot'] = snapshot
                        self.hotspot_analysis_list[i].append(hotspot)
                
                simulation.clear_important_data()
            except Exception as e:
                print('FAILED AT SNAPSHOT', it)
                print('Exception: ' + str(e))
                traceback.print_exc()

    def run_exposure_simulations(self, simulation_name, metric = 'Sab', snapshots = None, parallel = False, which_Sinc_to_compute = ['median', 'max', 'min', 'at_rx']):
        ''' Delegates to Sinc and Sab methods. '''

        if metric == 'Sab':
            assert simulation_name != '', 'simulation_name should be specified for Sab method.'
            self.run_exposure_simulations_Sab(simulation_name, snapshots = snapshots, parallel = parallel)
        elif metric == 'Sinc':
            self.run_exposure_simulations_Sinc(snapshots = snapshots, parallel = parallel, which_Sinc_to_compute = which_Sinc_to_compute)
        else:
            raise ValueError('metric should be either "Sab" or "Sinc".')

    def run_exposure_simulations_Sab(self, simulation_name, snapshots = None, parallel = False):
        ''' Run the exposure simulations with evaluation of Sab afterwards. 
        This requires an FDTD simulation. '''
        
        try:
            ExposureSimulation
        except:
            from .exposure_simulation import ExposureSimulation

        if snapshots is None:
            snapshots = self.snapshots

        self.max_Sab_results = np.zeros(len(self.snapshots))
        first_time = True
        for it in tqdm(range(len(snapshots)), disable=(not self.verbose)):
            exposure_simulation = ExposureSimulation(simulation_name)
            exposure_simulation.verbose = self.verbose
            exposure_simulation.assign_scene(self.scene)
            exposure_simulation.prepare()
            
            snapshot = self.snapshots[snapshots[it]]
            simulation = self.simulations[snapshot]
            # the idea here is that the S4L file just has the regular bounding box around the head, and this export makes it a bit bigger, such that no custom boxes need to be made in S4L
            simulation.export_incident_field_h5(0, exposure_simulation)
            
            exposure_simulation.run()
            exposure_simulation.get_max_Sab(first_time = first_time)
            self.max_Sab_results[snapshot] = exposure_simulation.max_Sab_results['Peak Spatial-Avg. Power Density']

            first_time = False

        # save this to a pickle file in the working directory
        with open(self.cache_path / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'wb') as f:
            pickle.dump(self.max_Sab_results, f)

    def run_exposure_simulations_Sinc(self, snapshots = None, parallel = False, which_Sinc_to_compute = ['median', 'max', 'min', 'at_rx']):
        ''' Run the exposure simulations with evaluation of Sinc afterwards. 
        This does not require an FDTD simulation. '''
    
        if snapshots is None:
            snapshots = self.snapshots

        self.max_Sinc_results = {}
        for which_Sinc in which_Sinc_to_compute:
            self.max_Sinc_results[which_Sinc] = np.zeros(len(self.snapshots))

        t0 = time.time()
        if parallel and False:
            import multiprocessing
            

            num_processes = multiprocessing.cpu_count()
            num_processes = 8
            # transfer the which_Sinc_to_compute to the simulations
            for simulation in self.simulations:
                simulation.which_Sinc_to_compute = which_Sinc_to_compute
            pool = multiprocessing.Pool(processes=num_processes)
            max_Sinc_results = pool.map(self.parallel_process_simulation, snapshots)
            pool.close()
            pool.join()

            for snapshot, max_Sinc_result in zip(snapshots, max_Sinc_results):
                for which_Sinc in which_Sinc_to_compute:
                    self.max_Sinc_results[which_Sinc][snapshot] = max_Sinc_result[which_Sinc]
        else:
            for it in tqdm(range(len(snapshots)), disable=(not self.verbose)):
                snapshot = self.snapshots[snapshots[it]]
                simulation = self.simulations[snapshot]

                simulation.efficient_cluster_addition()

                for which_Sinc in which_Sinc_to_compute:
                    Sinc = simulation.get_Sinc(which_Sinc_to_compute = which_Sinc)
                    self.max_Sinc_results[which_Sinc][snapshot] = Sinc         

                simulation.clear_important_data()
        if self.verbose:
            print(f'Finished the Sinc calculations in {time.time()-t0:.2f} seconds.')

        # save this to a pickle file in the working directory
        with open(self.cache_path / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'wb') as f:
            pickle.dump(self.max_Sinc_results, f)

    def parallel_process_simulation(self, snapshots):
        ''' Parallel processing of the simulation. '''

        max_Sinc_results = {}
        for which_Sinc in which_Sinc_to_compute:
            max_Sinc_results[which_Sinc] = np.zeros(len(snapshots))

        for it in range(len(snapshots)):
            snapshot = self.snapshots[snapshots[it]]
            simulation = self.simulations[snapshot]

            simulation.efficient_cluster_addition()

            for which_Sinc in which_Sinc_to_compute:
                Sinc = simulation.get_Sinc(which_Sinc_to_compute = which_Sinc)
                max_Sinc_results[which_Sinc][snapshot] = Sinc

            simulation.clear_important_data()

        return max_Sinc_results

    def radiate_and_run_exposure_simulations(self, simulation_name, snapshots = None, also_clear_fields = True):
        ''' Radiate the elements and run the exposure simulations. '''

        try:
            ExposureSimulation
        except:
            from .exposure_simulation import ExposureSimulation

        if snapshots is None:
            snapshots = self.snapshots

        self.max_Sab_results = np.zeros(len(self.snapshots))
        exposure_simulation = ExposureSimulation(simulation_name)
        exposure_simulation.verbose = self.verbose
        exposure_simulation.assign_scene(self.scene)
        exposure_simulation.prepare()
        first_time = True
        for it in tqdm(range(len(snapshots)), disable=(not self.verbose)):
            try:
                snapshot = snapshots[it]
                simulation = self.simulations[snapshot]
                if self.verbose:
                    if hasattr(self, 'snapshot_numbers_in_input_data'):
                        print('SNAPSHOT NUMBER ', self.snapshot_numbers_in_input_data[snapshot])
                    else:
                        print('SNAPSHOT NUMBER ', snapshot)
                ''' # old way, comprenshive using a full channel
                simulation.compute_channel_matrix()
                simulation.custom_weighting(all_ones=True)
                simulation.clear_unimportant_data()
                '''
                # new way, replaces above lines
                #simulation.use_sliced_grid = False
                simulation.efficient_cluster_addition() 
                #simulation.plot_2D_slice(value_type='real', component_type='z', field_type='E')

                # the idea here is that the S4L file just has the regular bounding box around the head, and this export makes it a bit bigger, such that no custom boxes need to be made in S4L
                simulation.export_incident_field_h5(0, exposure_simulation) 
                 
                exposure_simulation.run()
                exposure_simulation.get_max_Sab(first_time=first_time)
                self.max_Sab_results[snapshot] = exposure_simulation.max_Sab_results['Peak Spatial-Avg. Power Density']

                with open(self.cache_path / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'wb') as f:
                    pickle.dump(self.max_Sab_results, f)

                if also_clear_fields:
                    simulation.E = None
                    simulation.H = None
            except Exception as e:
                print(f'FAILED AT SNAPSHOT {it}')
                print(e)

                self.max_Sab_results[snapshot] = -1

                with open(self.cache_path / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'wb') as f:
                    pickle.dump(self.max_Sab_results, f)

            first_time = False

    ## Post-process simulations

    def read_exposure_results(self, name = None):
        ''' Reads the correct pickle file containing the exposure results. '''

        if name is not None:
            with open(self.cache_path + f'{self.default_pickle_save_name}_{name}.pickle', 'rb') as f:
                self.max_Sab_results = pickle.load(f)
        else:
            with open(self.cache_path + f'{self.default_pickle_save_name}.pickle', 'rb') as f:
                self.max_Sab_results = pickle.load(f)

    def read_chunked_exposure_results(self, chunk_delimiters):
        ''' Reads all pickle files found in the chunk directories under the cache path. '''
    
        # initialize
        with open(self.cache_path / f'chunk_{chunk_delimiters[0][0]}' / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'rb') as f:
            max_Sinc_results = pickle.load(f)
        self.max_Sinc_results = {}
        for which_Sinc in max_Sinc_results.keys():
            self.max_Sinc_results[which_Sinc] = np.zeros(len(self.snapshots))

        # fill in 
        for chunk_delimiter in chunk_delimiters:
            with open(self.cache_path / f'chunk_{chunk_delimiter[0]}' / f'{self.default_pickle_save_name}_{self.quadriga_file_name}.pickle', 'rb') as f:
                max_Sinc_results = pickle.load(f)
                for which_Sinc in self.max_Sinc_results.keys():
                    self.max_Sinc_results[which_Sinc][chunk_delimiter[1]:chunk_delimiter[2]] = max_Sinc_results[which_Sinc]

    def clear_chunked_exposure_results(self):
        ''' Clears all directories under cache_path that contain the word chunk.'''

        # list all directories
        all_files = os.listdir(self.cache_path)
        for file in all_files:
            if 'chunk' in file:
                shutil.rmtree(self.cache_path / file, ignore_errors=True)

    def get_average_all_fields_across_time(self, snapshots = None, in_wavelengths = True):
        ''' Returns a mean of all fields averaged across the snapshots in the form of an empty plotting simulation around 0,0,0.
        Also known as `propagation-wise' averaging. '''

        if snapshots is None:
            snapshots = self.snapshots

        # the plotting simulation has no transmitter, only a custom relative grid around 0,0,0 and a single receiver at 0,0,0
        grid_size = np.array([self.simulations[0].grid.x_size, self.simulations[0].grid.y_size, self.simulations[0].grid.z_size])
        if in_wavelengths:
            # transform to units of wavelength
            grid_size /= self.simulations[0].wavelength
        grid_resolution = np.array([self.simulations[0].grid.x_resolution, self.simulations[0].grid.y_resolution, self.simulations[0].grid.z_resolution])
        if in_wavelengths:
            plotting_grid = Grid.from_size(Pos(0,0,0), grid_size, grid_resolution, units = 'λ')
        else:
            plotting_grid = Grid.from_size(Pos(0,0,0), grid_size, grid_resolution, units = 'm')
        receiver_collection = AntennaCollection()
        receiver_collection.set_verbose(self.verbose)
        receiver_collection.add_antenna_element([0, 0, 0, 'omni', None])
        cluster_collection = ClusterCollection()
        cluster_collection.set_verbose(self.verbose)
        plotting_simulation = DeterministicSimulation(plotting_grid, base_station = None, clusters = cluster_collection, receivers=receiver_collection, frequency=self.frequency, scene = self.scene)
        plotting_simulation.use_existing_shown_value = False

        for i_snapshot in snapshots:
            simulation = self.simulations[i_snapshot]
            plotting_simulation.E += simulation.E / len(snapshots)
            plotting_simulation.H += simulation.H / len(snapshots)

        return plotting_simulation

    def get_value_averaged_across_time(self, snapshots = None, in_wavelengths = True, **kwargs):
            ''' Returns a mean of get_value averaged across the snapshots in the form of an empty plotting simulation around 0,0,0.
            Also known as `exposure-wise' averaging, when the value is an exposure metric. '''

            if snapshots is None:
                snapshots = self.snapshots

            first_iteration = True
            for i_snapshot in snapshots:
                simulation = self.simulations[i_snapshot]
                simulation.receivers.antenna_elements[0].discretize_on(simulation.grid)
                if first_iteration:
                    first_iteration = False
                    value, value_info = simulation.get_value(**kwargs, z_pos = simulation.receivers.antenna_elements[0])
                else:
                    new_value, value_info = simulation.get_value(**kwargs, z_pos = simulation.receivers.antenna_elements[0])
                    value += new_value

            value /= len(snapshots)
            value_info['z_height'] = 0
            
            # the plotting simulation has no transmitter, a custom relative grid around 0,0,0 and a single receiver at 0,0,0
            grid_size = np.array([self.simulations[0].grid.x_size, self.simulations[0].grid.y_size, self.simulations[0].grid.z_size])
            if in_wavelengths:
                # transform to units of wavelength
                grid_size /= self.simulations[0].wavelength
            grid_resolution = np.array([self.simulations[0].grid.x_resolution, self.simulations[0].grid.y_resolution, self.simulations[0].grid.z_resolution])
            if in_wavelengths:
                plotting_grid = Grid.from_size(Pos(0,0,0), grid_size, grid_resolution, units = 'λ')
            else:
                plotting_grid = Grid.from_size(Pos(0,0,0), grid_size, grid_resolution, units = 'm')
            receiver_collection = AntennaCollection()
            receiver_collection.set_verbose(self.verbose)
            receiver_collection.add_antenna_element([0, 0, 0, 'omni', None])
            cluster_collection = ClusterCollection()
            cluster_collection.set_verbose(self.verbose)
            plotting_simulation = DeterministicSimulation(plotting_grid, base_station = None, clusters = cluster_collection, receivers=receiver_collection, frequency=self.frequency, scene=self.scene, verbose=self.verbose)
            plotting_simulation.shown_value = value
            plotting_simulation.shown_value_info = value_info
            plotting_simulation.use_existing_shown_value = True

            return plotting_simulation

    ## Plot simulations

    def plot_layout(self, snapshots = None, value_type='abs', component_type='norm', field_type='E', z_pos=None, from_tx_element_nbr=None, slice_through_rx = None, plot_field_data=True, plot_patterns=True):
        ''' Plot the layout of the base station and receivers for each simulation. '''

        # Which snapshots are shown
        if snapshots is None:
            #snapshots = slice(0, self.N_snapshots)
            snapshots = self.snapshots

        # Speed up rendering
        matplotlib.rcParams['path.simplify'] = True
        old_value = matplotlib.rcParams['path.simplify_threshold']
        matplotlib.rcParams['path.simplify_threshold'] = 1.0
        
        # Create figure
        fig = plt.figure('Layout')
        ax = fig.add_subplot(111, projection='3d')
        list_of_shown_objects = []

        grids = [self.grids[i] for i in snapshots]
        receivers = [self.receivers[i] for i in snapshots]
        clusters = [self.clusters[i] for i in snapshots]
        simulations = [self.simulations[i] for i in snapshots]
        if plot_field_data:
            self.shown_values = []
            self.shown_value_infos = []

        for grid, receiver, simulation in zip(grids, receivers, simulations):
            # Plot grid
            grid.plot_wireframe(ax)
            list_of_shown_objects.append(grid.pos_ll)
            list_of_shown_objects.append(grid.pos_ur)

            # Plot field data
            if plot_field_data:
                if z_pos is None:
                    if slice_through_rx is None:
                        try:
                            z_pos = receiver.line_pos_1
                        except:
                            z_pos = receiver.antenna_elements[0]
                    else:
                        z_pos = receiver.antenna_elements[slice_through_rx]
                z_pos.discretize_on(grid)

                shown_value, shown_value_info = simulation.get_value(value_type=value_type, component_type=component_type, field_type=field_type, z_pos=z_pos, from_tx_element_nbr=from_tx_element_nbr)
                self.shown_values.append(shown_value)
                self.shown_value_infos.append(shown_value_info)
                if shown_value_info['always_positive']:
                    cmap = 'jet'
                    norm = None
                else:
                    finite_value = shown_value[np.isfinite(shown_value)]
                    if finite_value.min() < 0 and 0 < finite_value.max():
                        cmap = 'bwr'
                        #norm = DivergingNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                        norm = TwoSlopeNorm(vmin=finite_value.min(), vcenter = 0., vmax=finite_value.max())
                    else:
                        cmap = 'jet'
                        norm = None
                if not grid.is_2D:
                    self.color_bar = ax.contourf(grid.x_3D[:,:,z_pos.z_idx], grid.y_3D[:,:,z_pos.z_idx], shown_value, 50, zdir='z', offset=z_pos.z, cmap = cmap, norm = norm)
                else:
                    self.color_bar = ax.contourf(grid.x_2D, grid.y_2D, shown_value, 50, z_dir='z', offset=z_pos.z, cmap = cmap, norm = norm)
                # Colorbar axis 
                self.cb = fig.colorbar(self.color_bar, cax=fig.add_axes([0.92, 0.1, 0.02, 0.8]), orientation='vertical')
                ax.set_title(f"{shown_value_info['name']} (z = {100*shown_value_info['z_height']:.2f} cm)")

        # Get axis limits with a margin of 10%
        '''
        for antenna_element in self.base_station.antenna_elements:
            list_of_shown_objects.append(antenna_element)
        '''
        for cluster_collection in [self.clusters[i] for i in snapshots]:
            for cluster in cluster_collection.clusters:
                if cluster.vec_size < 1e4:
                    list_of_shown_objects.append(cluster)
                
        x_min = min([obj.x for obj in list_of_shown_objects])
        x_max = max([obj.x for obj in list_of_shown_objects])
        y_min = min([obj.y for obj in list_of_shown_objects])
        y_max = max([obj.y for obj in list_of_shown_objects])
        z_min = min([obj.z for obj in list_of_shown_objects])
        z_max = max([obj.z for obj in list_of_shown_objects])
        x_margin = (x_max - x_min)*0.1
        y_margin = (y_max - y_min)*0.1
        z_margin = (z_max - z_min)*0.1
        #general_size = ((x_max - x_min)**2 + (y_max - y_min)**2 + (z_max - z_min)**2)/50000
        ax.set_xlim(x_min - x_margin, x_max + x_margin)
        ax.set_ylim(y_min - y_margin, y_max + y_margin)
        ax.set_zlim(z_min - z_margin, z_max + z_margin)       

        '''
        # Plot base station
        for antenna_element in self.base_station.antenna_elements:
            antenna_element.plot_pattern(ax=ax, normalized = 0.2, stride = 10, alpha = 0.5)
            ax.scatter(antenna_element.x, antenna_element.y, antenna_element.z, s=50, color='red')
        '''

        # Plot clusters
        for cluster_collection in clusters:
            for cluster in cluster_collection.clusters:
                if cluster.vec_size < 1e4:
                    cluster.plot_pattern(ax=ax, normalized = 0.025, stride = 10, alpha = 0.5, only_orientation = (not plot_patterns))
                    #ax.scatter(cluster.x, cluster.y, cluster.z, s=50*general_size, color='blue')
                    ax.scatter(cluster.x, cluster.y, cluster.z, s=5, color='blue')
        
        # Plot receivers
        for receiver in receivers:
            for antenna_element in receiver.antenna_elements:
                antenna_element.plot_pattern(ax=ax, normalized = 0.025, stride = 10, alpha = 0.1, only_orientation = (not plot_patterns))
                #ax.scatter(antenna_element.x, antenna_element.y, antenna_element.z, s=50*general_size, color='black')
                ax.scatter(antenna_element.x, antenna_element.y, antenna_element.z, s=5, color='black')

        ax.set_xlabel('x [m]')
        ax.set_ylabel('y [m]')
        ax.set_zlabel('z [m]')

        plt.show()

        matplotlib.rcParams['path.simplify'] = False
        matplotlib.rcParams['path.simplify_threshold'] = old_value

    def plot_layout_all_snapshots(self, **kwargs):
        list_of_shown_objects = []
        
        receiver_list = [self.receivers[i].antenna_elements[0] for i in range(0,self.N_snapshots)]
        receiver_coord_list = [rx.x for rx in receiver_list], [rx.y for rx in receiver_list], [rx.z for rx in receiver_list]

        list_of_shown_objects.extend(receiver_list)
        for cluster_collection in self.clusters:
            for cluster in cluster_collection.clusters:
                if cluster.vec_size < 1e4:
                    list_of_shown_objects.append(cluster)
        for receiver in self.receivers:
            for antenna_element in receiver.antenna_elements:
                list_of_shown_objects.append(antenna_element)
        
        x_min = min([rx.x for rx in receiver_list])
        x_max = max([rx.x for rx in receiver_list])
        y_min = min([rx.y for rx in receiver_list])
        y_max = max([rx.y for rx in receiver_list])
        z_min = min([obj.z for obj in list_of_shown_objects])
        z_max = max([obj.z for obj in list_of_shown_objects])
        x_margin = (x_max - x_min)*0.1
        y_margin = (y_max - y_min)*0.1
        z_margin = (z_max - z_min)*0.1

        plt.figure('Layout')
        plt.ion()
        for i in tqdm(range(0,self.N_snapshots), disable=(not self.verbose)):
            plt.clf()

            # Plot the layout for the current snapshot
            self.plot_layout(snapshots=[i], **kwargs)

            # Make a plot line that connects all the receiver positions across snapshots
            if kwargs['plot_field_data']:
                axes = plt.gcf().axes
                for axx in axes:
                    if axx.get_title() != '':
                        ax = axx
                        break
            else:
                ax = plt.gca()
            ax.scatter(*receiver_coord_list,c='red',s=1)

            ax.set_xlim(x_min - x_margin, x_max + x_margin)
            ax.set_ylim(y_min - y_margin, y_max + y_margin)
            ax.set_zlim(z_min - z_margin, z_max + z_margin)
            
            plt.show()
            try:
                plt.pause(.1)
            except:
                pass

    def plot_rx_point_across_time(self, snapshots = None, relative_distance = None, rx_nbr = 0, show_plot = True, annotation = '',  **kwargs):
        ''' Plots the field at the point of a certain receiver specified by rx_nbr, for each specified snapshot. '''

        if snapshots is None:
            snapshots = self.snapshots

        if relative_distance is not None:
            translation_text = f' + translation [{relative_distance.x*100:.2f}, {relative_distance.y*100:.2f}, {relative_distance.z*100:.2f}] cm'
        else:
            translation_text = ''
        
        # Acquire the data using get_value and xyz_pos
        field_values = np.zeros(len(snapshots))
        for i_snapshot in snapshots:
            kwargs['xyz_pos'] = self.receivers[i_snapshot].antenna_elements[rx_nbr]
            if relative_distance is not None:
                kwargs['xyz_pos'] = kwargs['xyz_pos'] + relative_distance
            kwargs['xyz_pos'].discretize_on(self.simulations[i_snapshot].grid)
            value, value_info = self.simulations[i_snapshot].get_value(**kwargs)
            field_values[i_snapshot] = value

            # OR

            #self.simulations[i_snapshot].get_hotspot_parameters()
            #np.max(self.simulations[i_snapshot].get_value())

        # Plot the data
        title = f"{value_info['name']} at rx number {rx_nbr}"
        if translation_text:
            title += f" {translation_text}"
        if annotation:
            title += f" ({annotation})"
        plt.figure(title)
        plt.title(title)
        if hasattr(self, 'snapshot_numbers_in_input_data'):
            snapshots = self.snapshot_numbers_in_input_data[snapshots]
        plt.plot(snapshots, field_values, label=f"{self.quadriga_file_name}, rx {rx_nbr}")
        plt.xlabel('Snapshot')
        plt.ylabel(f"{value_info['name']} [{value_info['units']}]")

        if show_plot:
            plt.show()

        return field_values
    
    def get_Sinc_across_time(self, which_Sinc_to_compute='median', snapshots = None, in_db = False):
        ''' Goes through the snapshots and computes the Sinc at the receiver position for each snapshot. '''

        if snapshots is None:
            snapshots = self.snapshots

        Sinc_values = np.zeros(len(snapshots))
        for i_snapshot in snapshots:
            simulation = self.simulations[i_snapshot]
            Sinc = simulation.get_Sinc(which_Sinc_to_compute = which_Sinc_to_compute, in_db = in_db)
            Sinc_values[i_snapshot] = Sinc

        with open(self.cache_path / f'max_Sinc_results_{self.quadriga_file_name}_{which_Sinc_to_compute}.pickle', 'wb') as f:
            pickle.dump(Sinc_values, f)
        
        return Sinc_values

    def plot_exposure_result_across_time(self, snapshots = None, rx_nbr = 0, in_db = False, show = True):

        if not hasattr(self,'max_Sab_results'):
            self.read_exposure_results(name=self.quadriga_file_name)

        if snapshots is None:
            snapshots = self.snapshots

        plt.figure(f'Sab at rx point {rx_nbr}')
        if hasattr(self, 'snapshot_numbers_in_input_data'):
            snapshots = self.snapshot_numbers_in_input_data[snapshots]
        if in_db:
            plt.plot(snapshots, 10*np.log10(self.max_Sab_results), label=f"{self.quadriga_file_name}, rx {rx_nbr}")
        else:
            plt.plot(snapshots, self.max_Sab_results, label=f"{self.quadriga_file_name}, rx {rx_nbr}")
        plt.xlabel('Snapshot')
        plt.ylabel('Max S_ab [W/m^2]')
        plt.title('Exposure results across time')
        if show:
            plt.show()

    def hotspot_full_analysis(self, method = 'anywhere', plot = True, verbose = True, **kwargs):
        self.hotspot_location_analysis(method = method, plot = plot, verbose = verbose, **kwargs)
        self.hotspot_peak_analysis(method = method, plot = plot, verbose = verbose, **kwargs)

    def hotspot_location_analysis(self, method = 'anywhere', plot = True, verbose = True, **kwargs):
        ''' Plots information about the hotspot locations across time. '''
        
        if self.verbose:
            if method == 'central':
                print('WARNING: these plots are not very informative as the hotspot is always at the center of the grid.')

        if self.hotspots == []:
            for simulation in tqdm(self.simulations, disable = (not self.verbose)):
                if method == 'central':
                    hotspot = simulation.get_3D_hotspot_parameters(relative_hotspot_pos=Pos(0,0,0), **kwargs)
                elif method == 'anywhere':
                    hotspot = simulation.get_3D_hotspot_parameters(**kwargs)
                self.hotspots.append(hotspot)
        else:
            if self.verbose:
                if kwargs:
                    print('Using already computed hotspots. Ignoring kwargs and plotting stage.')

        hotspot_peaks = np.array([hotspot['Peak'] for hotspot in self.hotspots])
        hotspot_distances = np.array([hotspot['Relative distance'] for hotspot in self.hotspots])
        hotspot_prominences = np.array([hotspot['Average prominence'] for hotspot in self.hotspots])
        hotspot_prominence_to_peak_ratios = []
        for peak, prominence in zip(hotspot_peaks, hotspot_prominences):
            if peak == 0:
                hotspot_prominence_to_peak_ratios.append(0)
            elif prominence == 0:
                hotspot_prominence_to_peak_ratios.append(0)
            elif prominence > peak:
                hotspot_prominence_to_peak_ratios.append(1) # happens when the signal takes negative values
            else:
                hotspot_prominence_to_peak_ratios.append(prominence/peak)
        hotspot_prominence_to_peak_ratios = np.array(hotspot_prominence_to_peak_ratios)
        hotspot_relative_positions = np.array([hotspot['Relative position'].pos for hotspot in self.hotspots])
        hotspot_relative_x = hotspot_relative_positions[:,0]
        hotspot_relative_y = hotspot_relative_positions[:,1]
        hotspot_relative_z = hotspot_relative_positions[:,2]
        if plot:
            plt.figure('Hotspot locations')
            ax = plt.axes(projection='3d')
            scatter = ax.scatter3D(hotspot_relative_x, hotspot_relative_y, hotspot_relative_z,
                        s = hotspot_prominence_to_peak_ratios**3*100, c = hotspot_prominence_to_peak_ratios, cmap='viridis')
            plt.colorbar(scatter)
            ax.set_xlabel('x')
            ax.set_ylabel('y')
            ax.set_zlabel('z')

            plt.figure('Hotspot locations per dimension')
            plt.subplot(1,3,1)
            plt.hist(hotspot_relative_x*100, bins=10)
            plt.xlabel('x position of hotspot [cm]')
            plt.ylabel('Number of occurences')
            plt.title(f'Avg. rel. x pos: {np.mean(hotspot_relative_x)*100:.2f} cm \n Std. dev.: {np.std(hotspot_relative_x)*100:.2f} cm')
            plt.subplot(1,3,2)
            plt.hist(hotspot_relative_y*100, bins=10)
            plt.xlabel('y position of hotspot [cm]')
            plt.ylabel('Number of occurences')
            plt.title(f'Avg. rel. y pos: {np.mean(hotspot_relative_y)*100:.2f} cm \n Std. dev.: {np.std(hotspot_relative_y)*100:.2f} cm')
            plt.subplot(1,3,3)
            plt.hist(hotspot_relative_z*100, bins=10)
            plt.xlabel('z position of hotspot [cm]')
            plt.ylabel('Number of occurences')
            plt.title(f'Avg. rel. z pos: {np.mean(hotspot_relative_z)*100:.2f} cm \n Std. dev.: {np.std(hotspot_relative_z)*100:.2f} cm')

            plt.figure('Hotspot distances')
            plt.plot(list(range(len(hotspot_distances))), hotspot_distances*100)
            plt.xlabel('Time snapshots')
            plt.ylabel('Hotspot distance [cm]')
            plt.figure()
            plt.hist(hotspot_distances*100, bins=50)
            plt.xlabel('Hotspot distance [cm]')
            plt.ylabel('Number of occurences')
        if verbose and self.verbose:
            print(f'Average relative distance: {np.mean(hotspot_distances)*100:.2f} cm')
            print(f'Standard deviation: {np.std(hotspot_distances)*100:.2f} cm')

        grid = self.simulations[0].grid
        if grid == 'Cleared' and self.verbose:
            print('Skipping hotspot density analysis as the grid is cleared.')
        else:
            grid_sizes_x = np.linspace(0.1/100, grid.x_size, 15)
            grid_sizes_y = np.linspace(0.1/100, grid.y_size, 15)
            grid_sizes_z = np.linspace(0.1/100, grid.z_size, 15)
            sizes = []
            average_distances = []
            number_of_hotspots = []
            for x_size, y_size, z_size in zip(grid_sizes_x, grid_sizes_y, grid_sizes_z):
                avg_size = (x_size + y_size + z_size)/3
                sizes.append(avg_size)
                # make a subgrid
                try:
                    subgrid = grid.get_subgrid(grid.center, np.array([x_size, y_size, z_size]))
                    considered_hotspots = []
                    for hotspot in self.hotspots:
                        if subgrid.contains(grid.center + hotspot['Relative position']):
                            considered_hotspots.append(hotspot)
                    
                    considered_hotspots_relative_distances = np.array([hotspot['Relative distance'] for hotspot in considered_hotspots])
                    number_of_hotspots.append(len(considered_hotspots))
                    average_distances.append(np.mean(considered_hotspots_relative_distances))
                except:
                    number_of_hotspots.append(np.nan)
                    average_distances.append(np.nan)
                    continue

            sizes = np.array(sizes)*100
            average_distances = np.array(average_distances)*100
            volumes = np.array(sizes)**3
            hotspot_density = np.array(number_of_hotspots)/volumes

            if plot:
                plt.figure('Hotspot density as a function of considered volumes')
                plt.plot(sizes, hotspot_density)
                plt.xlabel('Considered box size [cm]')
                plt.ylabel('Hotspot density [1/cm^3]')

                plt.figure('Hotspot procentual relative distances as a function of considered distances')
                plt.plot(sizes, average_distances/sizes*np.sqrt(3)/2*100)
                plt.xlabel('Considered distance [cm]')
                plt.ylabel('Procentual ratio to max box length [%]')

                plt.show()

    def hotspot_peak_analysis(self, method = 'anywhere', plot = True, verbose = True, **kwargs):
        ''' Plots information about the hotspot peaks across time.'''

        if self.hotspots == []:
            self.hotspots = []
            for simulation in tqdm(self.simulations, disable = (not self.verbose)):
                if method == 'central':
                    hotspot = simulation.get_3D_hotspot_parameters(relative_hotspot_pos=Pos(0,0,0), **kwargs)
                elif method == 'anywhere':
                    hotspot = simulation.get_3D_hotspot_parameters(**kwargs)
                self.hotspots.append(hotspot)
        else:
            if kwargs and self.verbose:
                print('Using already computed hotspots. Ignoring kwargs and plotting stage.')
        
        hotspot_peaks = np.array([hotspot['Peak'] for hotspot in self.hotspots])
        hotspot_FWHM = np.array([hotspot['Average FWHM'] for hotspot in self.hotspots])
        hotspot_prominences = np.array([hotspot['Average prominence'] for hotspot in self.hotspots])
        hotspot_prominence_to_peak_ratios = []
        for peak, prominence in zip(hotspot_peaks, hotspot_prominences):
            if peak == 0:
                hotspot_prominence_to_peak_ratios.append(0)
            elif prominence == 0:
                hotspot_prominence_to_peak_ratios.append(0)
            elif prominence > peak:
                hotspot_prominence_to_peak_ratios.append(1) # happens when the signal takes negative values
            else:
                hotspot_prominence_to_peak_ratios.append(prominence/peak)
        hotspot_prominence_to_peak_ratios = np.array(hotspot_prominence_to_peak_ratios)
        hotspot_dimensionality = np.array([hotspot['Dimensionality'] for hotspot in self.hotspots])

        # Go through the arrays and check if there are nan or inf values (nonfinite) and zero values. If yes, throw a warning and get them out of there.
        non_finite_data = ~np.isfinite(hotspot_peaks)
        zero_data = (hotspot_peaks == 0)
        if np.sum(non_finite_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        if np.sum(zero_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        hotspot_peaks = hotspot_peaks[~np.logical_or(non_finite_data, zero_data)]

        non_finite_data = ~np.isfinite(hotspot_FWHM)
        zero_data = (hotspot_FWHM == 0)
        if np.sum(non_finite_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        if np.sum(zero_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        hotspot_FWHM = hotspot_FWHM[~np.logical_or(non_finite_data, zero_data)]

        non_finite_data = ~np.isfinite(hotspot_prominences)
        zero_data = (hotspot_prominences == 0)
        if np.sum(non_finite_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        if np.sum(zero_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        hotspot_prominences = hotspot_prominences[~np.logical_or(non_finite_data, zero_data)]

        non_finite_data = ~np.isfinite(hotspot_prominence_to_peak_ratios)
        zero_data = (hotspot_prominence_to_peak_ratios == 0)
        if np.sum(non_finite_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        if np.sum(zero_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        hotspot_prominence_to_peak_ratios = hotspot_prominence_to_peak_ratios[~np.logical_or(non_finite_data, zero_data)]

        non_finite_data = ~np.isfinite(hotspot_dimensionality)
        zero_data = (hotspot_dimensionality == 0)
        if np.sum(non_finite_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        if np.sum(zero_data) > 0 and self.verbose:
            print('WARNING, non finite data found!')
        hotspot_dimensionality = hotspot_dimensionality[~np.logical_or(non_finite_data, zero_data)]

        if verbose and self.verbose:
            print(f'Average peak: {np.mean(hotspot_peaks):.2e}')
            print(f'Standard deviation: {np.std(hotspot_peaks):.2e}')
            print(f'25th percentile: {np.percentile(hotspot_peaks, 25):.2e}')
            print(f'50th percentile: {np.percentile(hotspot_peaks, 50):.2e}')
            print(f'75th percentile: {np.percentile(hotspot_peaks, 75):.2e}')
            print(f'90th percentile: {np.percentile(hotspot_peaks, 90):.2e}')
            print(f'99th percentile: {np.percentile(hotspot_peaks, 99):.2e}')

            print(f'Average peak from dB (10-scale):', np.mean(10*np.log10(hotspot_peaks)))
            print(f'Standard deviation from dB (10-scale):', np.std(10*np.log10(hotspot_peaks)))
            print(f'25th percentile from dB (10-scale):', np.percentile(10*np.log10(hotspot_peaks), 25))
            print(f'50th percentile from dB (10-scale):', np.percentile(10*np.log10(hotspot_peaks), 50))
            print(f'75th percentile from dB (10-scale):', np.percentile(10*np.log10(hotspot_peaks), 75))
            print(f'90th percentile from dB (10-scale):', np.percentile(10*np.log10(hotspot_peaks), 90))
            print(f'99th percentile from dB (10-scale):', np.percentile(10*np.log10(hotspot_peaks), 99))

            print(f'Average FWHM: {np.mean(hotspot_FWHM)*100:.2f} cm')
            print(f'Standard deviation: {np.std(hotspot_FWHM)*100:.2f} cm')
            print(f'25th percentile: {np.percentile(hotspot_FWHM*100, 25):.2f} cm')
            print(f'50th percentile: {np.percentile(hotspot_FWHM*100, 50):.2f} cm')
            print(f'75th percentile: {np.percentile(hotspot_FWHM*100, 75):.2f} cm')
            print(f'90th percentile: {np.percentile(hotspot_FWHM*100, 90):.2f} cm')
            print(f'99th percentile: {np.percentile(hotspot_FWHM*100, 99):.2f} cm')

            print(f'Average prominence-to-peak ratio: {np.mean(hotspot_prominence_to_peak_ratios):.2f}')
            print(f'Standard deviation: {np.std(hotspot_prominence_to_peak_ratios):.2f}')
            print(f'25th percentile: {np.percentile(hotspot_prominence_to_peak_ratios, 25):.2f}')
            print(f'50th percentile: {np.percentile(hotspot_prominence_to_peak_ratios, 50):.2f}')
            print(f'75th percentile: {np.percentile(hotspot_prominence_to_peak_ratios, 75):.2f}')
            print(f'90th percentile: {np.percentile(hotspot_prominence_to_peak_ratios, 90):.2f}')
            print(f'99th percentile: {np.percentile(hotspot_prominence_to_peak_ratios, 99):.2f}')

            print(f'Percentage 3D balls: {np.sum(hotspot_dimensionality == 3)/len(hotspot_dimensionality)*100:.2f}%')
            print(f'Percentage 2D cylinders: {np.sum(hotspot_dimensionality == 2)/len(hotspot_dimensionality)*100:.2f}%')
            print(f'Percentage 1D sheets: {np.sum(hotspot_dimensionality == 1)/len(hotspot_dimensionality)*100:.2f}%')
            print(f'Average dimensionality: {np.mean(hotspot_dimensionality):.2f}')
            print(f'Standard deviation: {np.std(hotspot_dimensionality):.2f}')

        if plot:
            plt.figure('Hotspot FWHM as function of time')
            plt.plot(list(range(len(hotspot_FWHM))), hotspot_FWHM*100)
            plt.xlabel('Time snapshots')
            plt.ylabel('Average FWHM [cm]')
            plt.figure('Hotspot FWHM histogram')
            plt.hist(hotspot_FWHM*100, bins=50)
            plt.xlabel('FWHM of hotspot [cm]')
            plt.ylabel('Number of occurences')
            
            plt.figure('Hotspot prominence-to-peak as function of time')
            plt.plot(list(range(len(hotspot_prominence_to_peak_ratios))), hotspot_prominence_to_peak_ratios)
            plt.xlabel('Time snapshots')
            plt.ylabel('Prominence-to-peak ratio')
            plt.figure('Hotspot peak-to-prominence histogram')
            plt.hist(hotspot_prominence_to_peak_ratios, bins=50)
            plt.xlabel('Prominence-to-peak ratio of hotspot')
            plt.ylabel('Number of occurences')

            plt.figure('Hotspot dimensionality as function of time')
            plt.plot(list(range(len(hotspot_dimensionality))), hotspot_dimensionality)
            plt.xlabel('Time snapshots')
            plt.ylabel('Dimensionality of hotspot')
            plt.figure('Hotspot dimensionality histogram')
            plt.bar(np.arange(4), [np.sum(hotspot_dimensionality == i) for i in range(4)], tick_label=['0D nothing', '1D sheet', '2D cylinder', '3D ball'], align='center', width=0.5)
            plt.xticks(np.arange(4))
            plt.xlabel('Dimensionality of hotspot')
            plt.ylabel('Number of occurences')

            plt.show()

    def plot_2D_slice_across_time(self, snapshots = None, ion=False, **kwargs):
        ''' Plots a 2D slice of the fields for each specified snapshot.'''
        
        if snapshots is None:
            snapshots = self.snapshots
        
        plt.figure('2D slice')
        if ion:
            plt.ion()
        for i_snapshot in snapshots:
            if self.verbose:
                print('Plotting snapshot ' + str(i_snapshot) + ' of ' + str(self.N_snapshots))
            
            plt.clf()

            # Plot the 2D slice for the current snapshot
            self.simulations[i_snapshot].use_existing_shown_value = False
            self.simulations[i_snapshot].grid.units = 'm'
            self.simulations[i_snapshot].plot_2D_slice(**kwargs)

            plt.show()
            if ion:
                try:
                    plt.pause(.1)
                except:
                    pass
        if ion:
            plt.ioff()
 
    def plot_2D_slices_across_time(self, snapshots = None, ion=False, **kwargs):
        ''' Plots 2D slices of the fields for each specified snapshot.'''
        
        if snapshots is None:
            snapshots = self.snapshots
        
        plt.figure('2D slices')
        if ion:
            plt.ion()
        for i_snapshot in snapshots:
            if self.verbose:
                print('Plotting snapshot ' + str(i_snapshot) + ' of ' + str(self.N_snapshots))
            
            plt.clf()

            # Plot the 2D slices for the current snapshot
            self.simulations[i_snapshot].plot_2D_slices(**kwargs)

            plt.show()
            if ion:
                try:
                    plt.pause(.1)
                except:
                    pass
        if ion:
            plt.ioff()

    def Helsinki_figure_A1(self):

        # OPTIONS
        use_latex = True
        in_db = True
        snapshots = self.snapshots
        linewidth = 1
        xaxis_type = 'distance'
        max_distance = 273
        speed = 1.4
        color_LOS = 'g'
        color_NLOS = 'r'
        hue_urban = 0.30
        hue_suburban = 0.15
        BS_power = 320 # in W
        C0 = 'k'
        C1 = 'r'
        C2 = 'g'
        C3 = 'b'
        LS0 = 'solid'
        LS1 = 'dotted'
        LS2 = 'solid'
        LS3 = 'dotted'
        lw0 = 1.25
        lw1 = 0.75
        lw2 = 0.75
        lw3 = 1.25
        common_axis_on_snapshots = False

        if use_latex:
            plt.rcParams['text.usetex'] = True
        else:
            plt.rcParams['text.usetex'] = False

        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Times New Roman"]})
        plt.rcParams.update({
            "font.family": "serif"
        })


        # The figure should be composed of 2 subplots for plotting and 1 for the legend
        # To do this, we create a figure with 3 subplots, but make the third one much smaller in the vertical direction
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, gridspec_kw={'height_ratios': [1, 1, 0.1]}, num = 'BioEM figure 3')
        fig.set_size_inches(7.1, 7.1)
        '''
        fig = plt.figure('BioEM figure 3', figsize=(7.1, 7.1))
        gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 0.1])
        ax2 = fig.add_subplot(gs[1])
        ax1 = fig.add_subplot(gs[0], sharex=ax2)
        ax3 = fig.add_subplot(gs[2])
        '''


        # The text should be printed in 9 points
        font_size = 9
        plt.rcParams.update({'font.size': font_size})
        
        # We want this font size to be for all text, so in the labels, in the title and in the legend
        plt.rcParams.update({'axes.labelsize': font_size})
        plt.rcParams.update({'axes.titlesize': font_size})
        plt.rcParams.update({'legend.fontsize': font_size})
        plt.rcParams.update({'xtick.labelsize': font_size})
        plt.rcParams.update({'ytick.labelsize': font_size})


        # Set global linewidth
        plt.rcParams.update({'lines.linewidth': linewidth})
        
        if hasattr(self, 'snapshot_numbers_in_input_data'):
            snapshots = self.snapshot_numbers_in_input_data[snapshots]

        data = {
        'Sinc': {'Distributed': {'Precoded' : None, 'Unprecoded' : None}, 
                 'Collocated':  {'Precoded' : None, 'Unprecoded' : None}},
        'Sab':  {'Distributed': {'Precoded' : None, 'Unprecoded' : None}, 
                 'Collocated':  {'Precoded' : None, 'Unprecoded' : None}},
         }

        root = Path(r'C:\Users\rwydaegh\OneDrive - UGent\rwydaegh\SHAPE\src\legacy_code\papers_archive\bioem_paper_archive')
        with open(root/'plot_data/Sinc_distributed_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Distributed']['Precoded'] = foo
        with open(root/'plot_data/Sinc_distributed_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Distributed']['Unprecoded'] = foo
        with open(root/'plot_data/Sinc_collocated_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Collocated']['Precoded'] = foo
        with open(root/'plot_data/Sinc_collocated_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Collocated']['Unprecoded'] = foo
        with open(root/'plot_data/Sab_distributed_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Distributed']['Precoded'] = foo
        with open(root/'plot_data/Sab_distributed_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Distributed']['Unprecoded'] = foo
        with open(root/'plot_data/Sab_collocated_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Collocated']['Precoded'] = foo
        with open(root/'plot_data/Sab_collocated_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Collocated']['Unprecoded'] = foo
            
        if in_db:
            for key1 in data.keys():
                for key2 in data[key1].keys():
                    for key3 in data[key1][key2].keys():
                        dBm_to_dBW = 10*np.log10(1000)

                        precoding_gain = 11
                        if key2 == 'Collocated':
                            per_AE_to_per_BS = 10*np.log10(1/64)

                            if key3 == 'Precoded':
                                precoding_gain = 17

                        elif key2 == 'Distributed':
                            per_AE_to_per_BS = 10*np.log10(1/335)
                        
                        data[key1][key2][key3] = 10*np.log10(data[key1][key2][key3]) + dBm_to_dBW + per_AE_to_per_BS + precoding_gain

        # Plot the data
        if common_axis_on_snapshots:
            if xaxis_type == 'time':
                xaxis = snapshots/np.max(snapshots)*max_distance/speed
            elif xaxis_type == 'distance':
                xaxis = snapshots/np.max(snapshots)*max_distance
            elif xaxis_type == 'snapshot':
                xaxis = snapshots
                
            ax1.plot(xaxis, data['Sinc']['Distributed']['Unprecoded'], c=C1, linestyle=LS1, linewidth=linewidth*lw1)
            ax1.plot(xaxis, data['Sinc']['Distributed']['Precoded'], c=C0, linestyle=LS0, linewidth=linewidth*lw0)
            ax1.plot(xaxis, data['Sinc']['Collocated']['Precoded'], c=C2, linestyle=LS2, linewidth=linewidth*lw2)
            ax1.plot(xaxis, data['Sinc']['Collocated']['Unprecoded'], c=C3, linestyle=LS3, linewidth=linewidth*lw3)

            ax2.plot(xaxis, data['Sab']['Distributed']['Unprecoded'], c=C1, linestyle=LS1, linewidth=linewidth*lw1)
            ax2.plot(xaxis, data['Sab']['Distributed']['Precoded'], c=C0, linestyle=LS0, linewidth=linewidth*lw0)
            ax2.plot(xaxis, data['Sab']['Collocated']['Precoded'], c=C2, linestyle=LS2, linewidth=linewidth*lw2)
            ax2.plot(xaxis, data['Sab']['Collocated']['Unprecoded'], c=C3, linestyle=LS3, linewidth=linewidth*lw3)

            # set direction to inside of ticks
            ax1.tick_params(direction='in')
            ax2.tick_params(direction='in')
        else:
            datas = [
                data['Sinc']['Distributed']['Precoded'],
                data['Sinc']['Distributed']['Unprecoded'],
                data['Sinc']['Collocated']['Precoded'],
                data['Sinc']['Collocated']['Unprecoded'],
                data['Sab']['Distributed']['Precoded'],
                data['Sab']['Distributed']['Unprecoded'],
                data['Sab']['Collocated']['Precoded'],
                data['Sab']['Collocated']['Unprecoded']
            ]
            for i, d in enumerate(datas):
                # xaxis that adjusts to the size of the ydata
                xaxis = np.arange(0, len(d))
                # normalize
                xaxis = xaxis/np.max(xaxis)
                # scale to the max distance
                if xaxis_type == 'time':
                    xaxis = xaxis*max_distance/speed
                elif xaxis_type == 'distance':
                    xaxis = xaxis*max_distance
                elif xaxis_type == 'snapshot':
                    xaxis = xaxis*np.max(snapshots)
                
                if i%4==0:
                    lww = lw0
                    cc = C0
                    lss = LS0
                elif i%4==1:
                    lww = lw1
                    cc = C1
                    lss = LS1
                elif i%4==2:
                    lww = lw2
                    cc = C2
                    lss = LS2
                elif i%4==3:
                    lww = lw3
                    cc = C3
                    lss = LS3
                
                if i < 4:
                    ax = ax1
                else:
                    ax = ax2
                
                ax.plot(xaxis, d, c=cc, linestyle=lss, linewidth=linewidth*lww)
                    
        # Get min and max values of the plotted data in the subplot
        # Get the minimum of data['Sinc']['Distributed']['Precoded'], but ignore -inf values
        # for this we can use np.nanmin which ignores nan and inf values

        min_subfig1 = np.nanmin([np.nanmin(data['Sinc']['Distributed']['Precoded']),
                                np.nanmin(data['Sinc']['Distributed']['Unprecoded']),
                                np.nanmin(data['Sinc']['Collocated']['Precoded']),
                                np.nanmin(data['Sinc']['Collocated']['Unprecoded'])])
        max_subfig1 = np.nanmax([np.nanmax(data['Sinc']['Distributed']['Precoded']),
                                np.nanmax(data['Sinc']['Distributed']['Unprecoded']),
                                np.nanmax(data['Sinc']['Collocated']['Precoded']),
                                np.nanmax(data['Sinc']['Collocated']['Unprecoded'])])
        min_subfig2 = np.nanmin([np.nanmin(data['Sab']['Distributed']['Precoded']),
                                np.nanmin(data['Sab']['Distributed']['Unprecoded']),
                                np.nanmin(data['Sab']['Collocated']['Precoded']),
                                np.nanmin(data['Sab']['Collocated']['Unprecoded'])])
        max_subfig2 = np.nanmax([np.nanmax(data['Sab']['Distributed']['Precoded']),
                                np.nanmax(data['Sab']['Distributed']['Unprecoded']),
                                np.nanmax(data['Sab']['Collocated']['Precoded']),
                                np.nanmax(data['Sab']['Collocated']['Unprecoded'])])
                                        
        ax1.set_xlim([np.min(xaxis), np.max(xaxis)])
        ax2.set_xlim([np.min(xaxis), np.max(xaxis)])

        ax1.set_ylim([min_subfig1, max_subfig1])
        ax2.set_ylim([min_subfig2, max_subfig2])

        if xaxis_type == 'time':
            ax1.set_xlabel('Time [sec]')
            ax2.set_xlabel('Time [sec]')
        elif xaxis_type == 'distance':
            #ax1.set_xlabel('Distance [m]')
            ax2.set_xlabel('Distance [m]')
        elif xaxis_type == 'snapshot':
            ax1.set_xlabel('Snapshot [ ]')
            ax2.set_xlabel('Snapshot [ ]')

        if in_db:
            power_units_ax1 = 'dBW'
            power_units_ax2 = 'dBW'
        else:
            power_units_ax1 = 'W'
            power_units_ax2 = 'W'
        ax1.set_ylabel('$\mathrm{max}\,|\mathrm{Re}(S_\mathrm{inc}(\mathbf{r}))|$ (1 W) ['+power_units_ax1+'/m$^2$]', fontsize = font_size)
        ax2.set_ylabel('$\mathrm{max}\,S_\mathrm{ab}(\mathbf{r})$ (1 W) ['+power_units_ax2+'/m$^2$]', fontsize = font_size)

        # There should another axis on the right side of the plot
        ax1right = ax1.twinx()
        ax2right = ax2.twinx()

        ax1_ylim = ax1.get_ylim()
        ax2_ylim = ax2.get_ylim()

        reference_level = 10 # W/m2
        basic_restriction = 20 # W/m2

        # power units
        if power_units_ax1 != 'W' and power_units_ax1 != 'dBW':
            raise NotImplementedError('ref and basic levels should be changed to correct units')

        if in_db:
            reference_level_db = 10*np.log10(reference_level)
            basic_restriction_db = 10*np.log10(basic_restriction)
            BS_power_dB = 10*np.log10(BS_power)

            ax1right.set_ylim([ax1_ylim[0] - reference_level_db + BS_power_dB, ax2_ylim[1] - reference_level_db + BS_power_dB])
            ax2right.set_ylim([ax2_ylim[0] - basic_restriction_db + BS_power_dB, ax2_ylim[1] - basic_restriction_db + BS_power_dB])

            ax1right.set_ylabel(f'Ratio to reference level ({BS_power} W) [dB]')
            ax2right.set_ylabel(f'Ratio to basic restriction ({BS_power} W) [dB]')
        else: 
            ax1right.set_ylim([100*BS_power*ax1_ylim[0]/reference_level, 100*BS_power*ax2_ylim[1]/reference_level])
            ax2right.set_ylim([100*BS_power*ax2_ylim[0]/basic_restriction, 100*BS_power*ax2_ylim[1]/basic_restriction])

            ax1right.set_ylabel(f'Ratio to reference level ({BS_power} W) [' + r'$\%$' + ']')
            ax2right.set_ylabel(f'Ratio to basic restriction ({BS_power} W) [' + r'$\%$' + ']')

        #ax1.set_title(r'\uppercase{\textbf{Reference quantity}}')
        #ax2.set_title(r'\uppercase{\textbf{Basic quantity}}')

        '''
        LOS_urban_regions = [
                       (100, 200),
                       (700, 800)]
        LOS_suburban_regions = [
                       (200, 300),
                       (450, 600)]
        NLOS_urban_regions = [
                       (0, 100),
                       (800, 1000)]
        NLOS_suburban_regions = [
                       (300, 450),
                       (600, 700)]
        '''

        with open(root / 'plot_data/path_changes.pickle', 'rb') as f:
            path_changes = pickle.load(f)
        
        LOS_urban_regions = path_changes['Urban_LOS']
        LOS_suburban_regions = path_changes['Suburban_LOS']
        NLOS_urban_regions = path_changes['Urban_NLOS']
        NLOS_suburban_regions = path_changes['Suburban_NLOS']

        # Example for LOS_urban
        for region in LOS_urban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_urban)
            ax2.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_urban)

        # Now repeat for LOS_suburban, NLOS_urban and NLOS_suburban
        for region in LOS_suburban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_suburban)
            ax2.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_suburban)

        for region in NLOS_urban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_urban)
            ax2.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_urban)

        for region in NLOS_suburban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_suburban)
            ax2.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_suburban)

        # There should be one legend for the whole figure and not for each subplot
        labels = ['Cell-free precoded (user)', 'Cell-free unprecoded (non-user)', 'Collocated precoded (user)', 'Collocated unprecoded (non-user)']
        handles = [Line2D([0], [0], color=C0, lw=linewidth*lw0*2, linestyle=LS0),
                   Line2D([0], [0], color=C1, lw=linewidth*lw1*2, linestyle=LS1),
                   Line2D([0], [0], color=C2, lw=linewidth*lw2*2, linestyle=LS2),
                   Line2D([0], [0], color=C3, lw=linewidth*lw3*2, linestyle=LS3)]
        # Now we add a label and handle for the LOS region
        '''
        labels.insert(2, 'LOS (collocated), suburban')
        handles.insert(2, Rectangle((0, 0), 1, 1, facecolor=color_LOS, alpha=hue_suburban))
        labels.insert(2, 'LOS (collocated), urban')
        handles.insert(2, Rectangle((0, 0), 1, 1, facecolor=color_LOS, alpha=hue_urban))
        labels.append('NLOS (collocated), urban')
        handles.append(Rectangle((0, 0), 1, 1, facecolor=color_NLOS, alpha=hue_urban))
        labels.append('NLOS (collocated), suburban')
        handles.append(Rectangle((0, 0), 1, 1, facecolor=color_NLOS, alpha=hue_suburban))
        '''

        # Add the legend to the third axis, it should take up the whole width and height of the axis
        ax3.legend(handles, labels, loc='center', bbox_to_anchor=(0.5, 0.5), ncol=2, columnspacing=3)
        ax3.get_legend().get_frame().set_linewidth(linewidth)
        ax3.get_legend().get_frame().set_edgecolor('black')
        ax3.get_legend().get_frame().set_boxstyle('square')

        
        # set direction to inside of ticks
        ax1.tick_params(direction='in')
        ax2.tick_params(direction='in')
        ax1right.tick_params(direction='in')
        ax2right.tick_params(direction='in')

        ax1.set_xticklabels([])

        # Now the whole third axis should be made invisible
        ax3.set_axis_off()
        
        plt.tight_layout(h_pad=2)
        path_of_this_file = Path(__file__).parent.parent
        plt.savefig(path_of_this_file / 'Figure_2_reconstructed', bbox_inches='tight') #used to be Figure 3 under root/Figures
        plt.show()


        # Let's compute the correlation matrix between the precoded and unprecoded Sincs
        # We take the literal graphed data, so the one in db etc
        precoded_sinc_collocated = data['Sinc']['Collocated']['Precoded'] 
        unprecoded_sinc_collocated = data['Sinc']['Collocated']['Unprecoded']
        precoded_sinc_distributed = data['Sinc']['Distributed']['Precoded']
        unprecoded_sinc_distributed = data['Sinc']['Distributed']['Unprecoded']
        precoded_sab_collocated = data['Sab']['Collocated']['Precoded'] 
        unprecoded_sab_collocated = data['Sab']['Collocated']['Unprecoded']
        precoded_sab_distributed = data['Sab']['Distributed']['Precoded']
        unprecoded_sab_distributed = data['Sab']['Distributed']['Unprecoded']

        # Remove nan values
        precoded_sinc_collocated = precoded_sinc_collocated[~np.isnan(precoded_sinc_collocated)]
        unprecoded_sinc_collocated = unprecoded_sinc_collocated[~np.isnan(unprecoded_sinc_collocated)]
        precoded_sinc_distributed = precoded_sinc_distributed[~np.isnan(precoded_sinc_distributed)]
        unprecoded_sinc_distributed = unprecoded_sinc_distributed[~np.isnan(unprecoded_sinc_distributed)]
        precoded_sab_collocated = precoded_sab_collocated[~np.isnan(precoded_sab_collocated)]
        unprecoded_sab_collocated = unprecoded_sab_collocated[~np.isnan(unprecoded_sab_collocated)]
        precoded_sab_distributed = precoded_sab_distributed[~np.isnan(precoded_sab_distributed)]
        unprecoded_sab_distributed = unprecoded_sab_distributed[~np.isnan(unprecoded_sab_distributed)]

        # the Sab values only have 101 values, while the Sinc values have much more
        # so we need to sample the Sinc values to the same length as the Sab values
        # we can do this by taking the mean of every 101 values
        precoded_sinc_collocated = np.mean(precoded_sinc_collocated[:len(precoded_sinc_collocated) // 101 * 101].reshape(-1, 101), axis=1)[:101]
        unprecoded_sinc_collocated = np.mean(unprecoded_sinc_collocated[:len(unprecoded_sinc_collocated) // 101 * 101].reshape(-1, 101), axis=1)[:101]
        precoded_sinc_distributed = np.mean(precoded_sinc_distributed[:len(precoded_sinc_distributed) // 101 * 101].reshape(-1, 101), axis=1)[:101]
        unprecoded_sinc_distributed = np.mean(unprecoded_sinc_distributed[:len(unprecoded_sinc_distributed) // 101 * 101].reshape(-1, 101), axis=1)[:101]

        # Compute the correlation matrix
        correlation_matrix = np.corrcoef([precoded_sinc_collocated, unprecoded_sinc_collocated, precoded_sinc_distributed, unprecoded_sinc_distributed,
                                          precoded_sab_collocated, unprecoded_sab_collocated, precoded_sab_distributed, unprecoded_sab_distributed])
        print('Correlation matrix:')
        print(correlation_matrix)

        # Plot the correlation matrix with colors and labels
        fig, ax = plt.subplots()
        fig.set_size_inches(3.5, 3.5)

        # set font size
        plt.rcParams.update({'font.size': font_size})
        cax = ax.matshow(correlation_matrix, cmap='viridis')

        # Add color bar
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        divider = make_axes_locatable(ax)
        cax_cb = divider.append_axes("right", size="5%", pad=0.1)  # Adjust pad to move the colorbar outside
        cbar = fig.colorbar(cax, cax=cax_cb)
        cbar.set_label('Correlation coefficient', rotation=90)

        # Set axis labels
        labels = [r'$S^{d,p}_\mathrm{inc}$', r'$S^{d,u}_\mathrm{inc}$', r'$S^{c,p}_\mathrm{inc}$', r'$S^{c,u}_\mathrm{inc}$', r'$S^{d,p}_\mathrm{ab}$', r'$S^{d,u}_\mathrm{ab}$', r'$S^{c,p}_\mathrm{ab}$', r'$S^{c,u}_\mathrm{ab}$']
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_yticklabels(labels)

        # Remove ticks
        ax.tick_params(axis='both', which='both', length=0)

        # Save the figure as correlations.pdf
        plt.tight_layout()
        path_of_this_file = Path(r"C:\Users\rwydaegh\OneDrive - UGent\rwydaegh\New A1 paper\Figures")
        plt.savefig(path_of_this_file / 'correlations.pdf', bbox_inches='tight')

        plt.show()
    
    def BioEM_figure_3(self):
        ''' Plots figure 3 from the BioEM paper. '''
        '''' Lightly adapted to work with figure_2_bioem22_reconstructed.py'''

        # OPTIONS
        use_latex = True
        in_db = True
        rx_nbr = 0
        snapshots = self.snapshots
        dist = 20
        linewidth = 1
        xaxis_type = 'distance'
        max_distance = 273
        speed = 1.4
        color_LOS = 'g'
        color_NLOS = 'r'
        hue_urban = 0.30
        hue_suburban = 0.15
        BS_power = 320 # in W
        C0 = 'k'
        C1 = 'r'
        C2 = 'g'
        C3 = 'b'
        LS0 = 'solid'
        LS1 = 'dotted'
        LS2 = 'solid'
        LS3 = 'dotted'
        lw0 = 0.75
        lw1 = 1.25
        lw2 = 0.75
        lw3 = 1.25
        common_axis_on_snapshots = False

        if use_latex:
            plt.rcParams['text.usetex'] = True
        else:
            plt.rcParams['text.usetex'] = False

        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Times New Roman"]})
        plt.rcParams.update({
            "font.family": "serif"
        })

        # The figure should be composed of 2 subplots for plotting and 1 for the legend
        # To do this, we create a figure with 3 subplots, but make the third one much smaller in the vertical direction
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, gridspec_kw={'height_ratios': [1, 1, 0.1]}, num = 'BioEM figure 3')
        
        # Set the figure to be 8x8 inches, later we set the dpi to 300.
        fig.set_size_inches(8, 8)

        # The text should be printed in 11 points
        plt.rcParams.update({'font.size': 11})
        
        # We want this font size to be for all text, so in the labels, in the title and in the legend
        plt.rcParams.update({'axes.labelsize': 11})
        plt.rcParams.update({'axes.titlesize': 11})
        plt.rcParams.update({'legend.fontsize': 11})
        plt.rcParams.update({'xtick.labelsize': 11})
        plt.rcParams.update({'ytick.labelsize': 11})

        # Set global linewidth
        plt.rcParams.update({'lines.linewidth': linewidth})
        
        if hasattr(self, 'snapshot_numbers_in_input_data'):
            snapshots = self.snapshot_numbers_in_input_data[snapshots]

        data = {
        'Sinc': {'Distributed': {'Precoded' : None, 'Unprecoded' : None}, 
                 'Collocated':  {'Precoded' : None, 'Unprecoded' : None}},
        'Sab':  {'Distributed': {'Precoded' : None, 'Unprecoded' : None}, 
                 'Collocated':  {'Precoded' : None, 'Unprecoded' : None}},
         }

        root = Path(r'C:\Users\rwydaegh\OneDrive - UGent\rwydaegh\SHAPE\src\legacy_code\papers_archive\bioem_paper_archive')
        with open(root/'plot_data/Sinc_distributed_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Distributed']['Precoded'] = foo
        with open(root/'plot_data/Sinc_distributed_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Distributed']['Unprecoded'] = foo
        with open(root/'plot_data/Sinc_collocated_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Collocated']['Precoded'] = foo
        with open(root/'plot_data/Sinc_collocated_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sinc']['Collocated']['Unprecoded'] = foo
        with open(root/'plot_data/Sab_distributed_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Distributed']['Precoded'] = foo
        with open(root/'plot_data/Sab_distributed_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Distributed']['Unprecoded'] = foo
        with open(root/'plot_data/Sab_collocated_precoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Collocated']['Precoded'] = foo
        with open(root/'plot_data/Sab_collocated_unprecoded.pickle', 'rb') as f:
            foo = pickle.load(f)
            data['Sab']['Collocated']['Unprecoded'] = foo
            
        if in_db:
            for key1 in data.keys():
                for key2 in data[key1].keys():
                    for key3 in data[key1][key2].keys():
                        dBm_to_dBW = 10*np.log10(1000)

                        precoding_gain = 11
                        if key2 == 'Collocated':
                            per_AE_to_per_BS = 10*np.log10(1/64)

                            if key3 == 'Precoded':
                                precoding_gain = 17

                        elif key2 == 'Distributed':
                            per_AE_to_per_BS = 10*np.log10(1/335)
                        
                        data[key1][key2][key3] = 10*np.log10(data[key1][key2][key3]) + dBm_to_dBW + per_AE_to_per_BS + precoding_gain

        # Plot the data
        if common_axis_on_snapshots:
            if xaxis_type == 'time':
                xaxis = snapshots/np.max(snapshots)*max_distance/speed
            elif xaxis_type == 'distance':
                xaxis = snapshots/np.max(snapshots)*max_distance
            elif xaxis_type == 'snapshot':
                xaxis = snapshots
                
            ax1.plot(xaxis, data['Sinc']['Distributed']['Precoded'], c=C0, linestyle=LS0, linewidth=linewidth*lw0)
            ax1.plot(xaxis, data['Sinc']['Distributed']['Unprecoded'], c=C1, linestyle=LS1, linewidth=linewidth*lw1)
            ax1.plot(xaxis, data['Sinc']['Collocated']['Precoded'], c=C2, linestyle=LS2, linewidth=linewidth*lw2)
            ax1.plot(xaxis, data['Sinc']['Collocated']['Unprecoded'], c=C3, linestyle=LS3, linewidth=linewidth*lw3)

            ax2.plot(xaxis, data['Sab']['Distributed']['Precoded'], c=C0, linestyle=LS0, linewidth=linewidth*lw0)
            ax2.plot(xaxis, data['Sab']['Distributed']['Unprecoded'], c=C1, linestyle=LS1, linewidth=linewidth*lw1)
            ax2.plot(xaxis, data['Sab']['Collocated']['Precoded'], c=C2, linestyle=LS2, linewidth=linewidth*lw2)
            ax2.plot(xaxis, data['Sab']['Collocated']['Unprecoded'], c=C3, linestyle=LS3, linewidth=linewidth*lw3)
        else:
            datas = [
                data['Sinc']['Distributed']['Precoded'],
                data['Sinc']['Distributed']['Unprecoded'],
                data['Sinc']['Collocated']['Precoded'],
                data['Sinc']['Collocated']['Unprecoded'],
                data['Sab']['Distributed']['Precoded'],
                data['Sab']['Distributed']['Unprecoded'],
                data['Sab']['Collocated']['Precoded'],
                data['Sab']['Collocated']['Unprecoded']
            ]
            for i, d in enumerate(datas):
                # xaxis that adjusts to the size of the ydata
                xaxis = np.arange(0, len(d))
                # normalize
                xaxis = xaxis/np.max(xaxis)
                # scale to the max distance
                if xaxis_type == 'time':
                    xaxis = xaxis*max_distance/speed
                elif xaxis_type == 'distance':
                    xaxis = xaxis*max_distance
                elif xaxis_type == 'snapshot':
                    xaxis = xaxis*np.max(snapshots)
                
                if i%4==0:
                    lww = lw0
                    cc = C0
                    lss = LS0
                elif i%4==1:
                    lww = lw1
                    cc = C1
                    lss = LS1
                elif i%4==2:
                    lww = lw2
                    cc = C2
                    lss = LS2
                elif i%4==3:
                    lww = lw3
                    cc = C3
                    lss = LS3
                
                if i < 4:
                    ax = ax1
                else:
                    ax = ax2
                
                ax.plot(xaxis, d, c=cc, linestyle=lss, linewidth=linewidth*lww)
                    
        # Get min and max values of the plotted data in the subplot
        # Get the minimum of data['Sinc']['Distributed']['Precoded'], but ignore -inf values
        # for this we can use np.nanmin which ignores nan and inf values

        min_subfig1 = np.nanmin([np.nanmin(data['Sinc']['Distributed']['Precoded']),
                                np.nanmin(data['Sinc']['Distributed']['Unprecoded']),
                                np.nanmin(data['Sinc']['Collocated']['Precoded']),
                                np.nanmin(data['Sinc']['Collocated']['Unprecoded'])])
        max_subfig1 = np.nanmax([np.nanmax(data['Sinc']['Distributed']['Precoded']),
                                np.nanmax(data['Sinc']['Distributed']['Unprecoded']),
                                np.nanmax(data['Sinc']['Collocated']['Precoded']),
                                np.nanmax(data['Sinc']['Collocated']['Unprecoded'])])
        min_subfig2 = np.nanmin([np.nanmin(data['Sab']['Distributed']['Precoded']),
                                np.nanmin(data['Sab']['Distributed']['Unprecoded']),
                                np.nanmin(data['Sab']['Collocated']['Precoded']),
                                np.nanmin(data['Sab']['Collocated']['Unprecoded'])])
        max_subfig2 = np.nanmax([np.nanmax(data['Sab']['Distributed']['Precoded']),
                                np.nanmax(data['Sab']['Distributed']['Unprecoded']),
                                np.nanmax(data['Sab']['Collocated']['Precoded']),
                                np.nanmax(data['Sab']['Collocated']['Unprecoded'])])
                                        
        ax1.set_xlim([np.min(xaxis), np.max(xaxis)])
        ax2.set_xlim([np.min(xaxis), np.max(xaxis)])

        ax1.set_ylim([min_subfig1, max_subfig1])
        ax2.set_ylim([min_subfig2, max_subfig2])

        if xaxis_type == 'time':
            ax1.set_xlabel('Time [sec]')
            ax2.set_xlabel('Time [sec]')
        elif xaxis_type == 'distance':
            ax1.set_xlabel('Distance [m]')
            ax2.set_xlabel('Distance [m]')
        elif xaxis_type == 'snapshot':
            ax1.set_xlabel('Snapshot [ ]')
            ax2.set_xlabel('Snapshot [ ]')

        if in_db:
            power_units_ax1 = 'dBW'
            power_units_ax2 = 'dBW'
        else:
            power_units_ax1 = 'W'
            power_units_ax2 = 'W'
        ax1.set_ylabel('$\mathrm{max}\,|\mathrm{Re}(S_\mathrm{inc}(\mathbf{r}))|$ (1 W) ['+power_units_ax1+'/m$^2$]', fontsize = 11)
        ax2.set_ylabel('$\mathrm{max}\,S_\mathrm{ab}(\mathbf{r})$ (1 W) ['+power_units_ax2+'/m$^2$]')

        # There should another axis on the right side of the plot
        ax1right = ax1.twinx()
        ax2right = ax2.twinx()

        ax1_ylim = ax1.get_ylim()
        ax2_ylim = ax2.get_ylim()

        reference_level = 10 # W/m2
        basic_restriction = 20 # W/m2

        # power units
        if power_units_ax1 != 'W' and power_units_ax1 != 'dBW':
            raise NotImplementedError('ref and basic levels should be changed to correct units')

        if in_db:
            reference_level_db = 10*np.log10(reference_level)
            basic_restriction_db = 10*np.log10(basic_restriction)
            BS_power_dB = 10*np.log10(BS_power)

            ax1right.set_ylim([ax1_ylim[0] - reference_level_db + BS_power_dB, ax2_ylim[1] - reference_level_db + BS_power_dB])
            ax2right.set_ylim([ax2_ylim[0] - basic_restriction_db + BS_power_dB, ax2_ylim[1] - basic_restriction_db + BS_power_dB])

            ax1right.set_ylabel(f'Ratio to reference level ({BS_power} W) [dB]')
            ax2right.set_ylabel(f'Ratio to basic restriction ({BS_power} W) [dB]')
        else: 
            ax1right.set_ylim([100*BS_power*ax1_ylim[0]/reference_level, 100*BS_power*ax2_ylim[1]/reference_level])
            ax2right.set_ylim([100*BS_power*ax2_ylim[0]/basic_restriction, 100*BS_power*ax2_ylim[1]/basic_restriction])

            ax1right.set_ylabel(f'Ratio to reference level ({BS_power} W) [' + r'$\%$' + ']')
            ax2right.set_ylabel(f'Ratio to basic restriction ({BS_power} W) [' + r'$\%$' + ']')

        ax1.set_title(r'\uppercase{\textbf{Reference quantity}}')
        ax2.set_title(r'\uppercase{\textbf{Basic quantity}}')

        '''
        LOS_urban_regions = [
                       (100, 200),
                       (700, 800)]
        LOS_suburban_regions = [
                       (200, 300),
                       (450, 600)]
        NLOS_urban_regions = [
                       (0, 100),
                       (800, 1000)]
        NLOS_suburban_regions = [
                       (300, 450),
                       (600, 700)]
        '''

        with open(root / 'plot_data/path_changes.pickle', 'rb') as f:
            path_changes = pickle.load(f)
        
        LOS_urban_regions = path_changes['Urban_LOS']
        LOS_suburban_regions = path_changes['Suburban_LOS']
        NLOS_urban_regions = path_changes['Urban_NLOS']
        NLOS_suburban_regions = path_changes['Suburban_NLOS']

        # Example for LOS_urban
        for region in LOS_urban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_urban)
            ax2.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_urban)

        # Now repeat for LOS_suburban, NLOS_urban and NLOS_suburban
        for region in LOS_suburban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_suburban)
            ax2.axvspan(region[0], region[1], facecolor=color_LOS, alpha=hue_suburban)

        for region in NLOS_urban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_urban)
            ax2.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_urban)

        for region in NLOS_suburban_regions:
            if xaxis_type == 'time':
                region = (region[0]*max_distance/speed, region[1]*max_distance/speed)
            elif xaxis_type == 'distance':
                region = (region[0]*max_distance, region[1]*max_distance)
            elif xaxis_type == 'snapshot':
                pass
            ax1.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_suburban)
            ax2.axvspan(region[0], region[1], facecolor=color_NLOS, alpha=hue_suburban)

        # There should be one legend for the whole figure and not for each subplot
        labels = ['Cell-free precoded (user)', 'Cell-free unprecoded (non-user)', 'Collocated precoded (user)', 'Collocated unprecoded (non-user)']
        handles = [Line2D([0], [0], color=C0, lw=linewidth*lw0*2, linestyle=LS0),
                   Line2D([0], [0], color=C1, lw=linewidth*lw1*2, linestyle=LS1),
                   Line2D([0], [0], color=C2, lw=linewidth*lw2*2, linestyle=LS2),
                   Line2D([0], [0], color=C3, lw=linewidth*lw3*2, linestyle=LS3)]
        # Now we add a label and handle for the LOS region
        labels.insert(2, 'LOS (collocated), suburban')
        handles.insert(2, Rectangle((0, 0), 1, 1, facecolor=color_LOS, alpha=hue_suburban))
        labels.insert(2, 'LOS (collocated), urban')
        handles.insert(2, Rectangle((0, 0), 1, 1, facecolor=color_LOS, alpha=hue_urban))
        labels.append('NLOS (collocated), urban')
        handles.append(Rectangle((0, 0), 1, 1, facecolor=color_NLOS, alpha=hue_urban))
        labels.append('NLOS (collocated), suburban')
        handles.append(Rectangle((0, 0), 1, 1, facecolor=color_NLOS, alpha=hue_suburban))

        # Add the legend to the third axis, it should take up the whole width and height of the axis
        ax3.legend(handles, labels, loc='center', bbox_to_anchor=(0.5, 0.5), ncol=2, columnspacing=3)
        ax3.get_legend().get_frame().set_linewidth(linewidth)
        ax3.get_legend().get_frame().set_edgecolor('black')
        ax3.get_legend().get_frame().set_boxstyle('square')

        # Now the whole third axis should be made invisible
        ax3.set_axis_off()
        
        plt.tight_layout()
        path_of_this_file = Path(__file__).parent.parent
        plt.savefig(path_of_this_file / 'Figure_2_reconstructed', bbox_inches='tight', dpi=300) #used to be Figure 3 under root/Figures
        plt.show()
        
def process_simulation(simulation):
    ''' Heart of the parallelism, where it forks off. Needs to be a separate function to be picklable.'''

    max_Sinc_results = {}

    simulation.efficient_cluster_addition()
    for which_Sinc in simulation.which_Sinc_to_compute:
        Sinc = simulation.get_Sinc(which_Sinc_to_compute = which_Sinc)
        max_Sinc_results[which_Sinc] = Sinc         

    simulation.clear_important_data()

    return max_Sinc_results
