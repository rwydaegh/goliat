import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.optimize import fminbound

from .antenna import Pos, AntennaElement
from .cluster import Cluster

class RadiatingCollection(object):
    ''' Umbrella class for AntennaCollection and ClusterCollection. '''

    def __init__(self):
        self.collection_type = None
        self.verbose = True

    def set_verbose(self, verbose):
        ''' Sets the verbose attribute for all AntennaElements. '''
        
        for elem in self.elements:
            elem.set_verbose(verbose)

    @property
    def elements(self):
        if self.collection_type == 'antenna_collection':
            return self.antenna_elements
        elif self.collection_type == 'cluster_collection':
            return self.clusters

    @property
    def nbr_elements(self):
        if self.collection_type == 'antenna_collection':
            return self.nbr_antenna_elements
        elif self.collection_type == 'cluster_collection':
            return self.nbr_clusters

class AntennaCollection(RadiatingCollection):
    ''' Composed of AntennaElements. Has a power value. ''' 
    
    def __init__(self, power_dBm = 10):
        self.collection_type = 'antenna_collection'
        
        self.antenna_elements = []
        self.antenna_element_sizes = 0.05 # in meters
        self.antenna_element_types = 'SHAPE_antenna'
        self.nbr_antenna_elements = 0

        self.Ptot_dBm = power_dBm

    @property
    def Ptot_W(self):
        ''' Converts the dBm power value to watts. '''
        
        return 10**(self.Ptot_dBm/10)/1000
            
    def add_antenna_element(self, args):
        ''' Adds an AntennaElement to the AntennaCollection. '''
        
        if args[3] is None:
            args[3] = self.antenna_element_types
        if args[4] is None:
            args[4] = self.antenna_element_sizes

        ae = AntennaElement(*args, id = len(self.antenna_elements))
        
        self.antenna_elements.append(ae)
        self.nbr_antenna_elements += 1

        return ae

    def add_line_of_antenna_elements(self, pos_1, pos_2, N, antenna_type = None, antenna_size = None, orientation = None):
        ''' Adds a collection of N AntennaElements with position on a straight line defined by the two Positions. '''
        
        if antenna_type is None:
            antenna_type = self.antenna_element_types
        if antenna_size is None:
            antenna_size = self.antenna_element_sizes
        
        self.line_pos_1 = pos_1
        self.line_pos_2 = pos_2
        positions_x = np.linspace(pos_1.x, pos_2.x, N)
        positions_y = np.linspace(pos_1.y, pos_2.y, N)
        positions_z = np.linspace(pos_1.z, pos_2.z, N)
        parallel_vector = pos_1.vec_to(pos_2)
        for x, y, z in zip(positions_x, positions_y, positions_z):
            ae = self.add_antenna_element([x, y, z, antenna_type, antenna_size])
            if orientation is None:
                assert parallel_vector[2] == 0, 'AntennaElements on a line must be in the xy-plane. Alternatively, specify an orientation.' #TODO
                if parallel_vector[2] == 0:
                    normal_vector = Pos(-parallel_vector[1], parallel_vector[0], 0)
                    ae.set_orientation(normal_vector)
            else:
                ae.set_orientation(orientation)

    def add_parabola_of_antenna_elements(self, pos_1, pos_2, focus, N, antenna_type = None, antenna_size = None):
        ''' Adds a collection of N AntennaElements with position on a parabolic line.
        The parabola is defined by it's directrix, defined by two points, and a focus point. 
        Points outside of these two are not considered, making it a finite parabola.'''
        
        if antenna_type is None:
            antenna_type = self.antenna_element_types
        if antenna_size is None:
            antenna_size = self.antenna_element_sizes
        
        assert N%2==1, 'N must be uneven.'
        assert N>=5, 'N must be at least 5' #TODO: implement even numbers
        
        # directrix definition
        directrix_positions_x = np.linspace(pos_1.x, pos_2.x, N)
        directrix_positions_y = np.linspace(pos_1.y, pos_2.y, N)
        directrix_dist = np.sqrt(np.square(directrix_positions_x - directrix_positions_x[0]) + np.square(directrix_positions_y - directrix_positions_y[0]))
        
        # directrix properties
        parallel_vector = pos_1.vec_to(pos_2)
        normal_vector = Pos(-parallel_vector[1], parallel_vector[0]).normalize()
        midpoint_idx = N//2
        midpoint = Pos(directrix_positions_x[midpoint_idx], directrix_positions_y[midpoint_idx])
        focus_to_midpoint = midpoint.dist_to(focus)
        factor = 5 # to make sure long enough orthogonal lines are considered, should be high.

        ae_positions = []
        for x, y in zip(directrix_positions_x, directrix_positions_y):
            orthogonal_line_x = np.linspace(x, x + normal_vector.x * focus_to_midpoint * factor, 1000) # 1000 should just be a high number that increases accuracy of the locations
            orthogonal_line_y = np.linspace(y, y + normal_vector.y * focus_to_midpoint * factor, 1000)
            
            diffs = []
            for orth_x, orth_y in zip(orthogonal_line_x, orthogonal_line_y):
                
                point_on_line = Pos(x, y)
                point_on_orth_line = Pos(orth_x, orth_y)
                
                d1 = point_on_orth_line.dist_to(point_on_line)
                d2 = point_on_orth_line.dist_to(focus)
                
                diffs.append(np.abs(d2 - d1))
                
            min_idx = np.argmin(np.array(diffs))
            ae_positions.append(Pos(orthogonal_line_x[min_idx], orthogonal_line_y[min_idx]))

        normal_vectors = []
        for ae_pos, ae_pos_next in zip(ae_positions[:-1], ae_positions[1:]):
            connecting_vector = ae_pos.vec_to(ae_pos_next)
            normal_vectors.append(Pos(-connecting_vector[1], connecting_vector[0]).normalize())

        avg_normal_vectors = []
        for n, n_next in zip(normal_vectors[:-1], normal_vectors[1:]):
            avg_normal_vectors.append(Pos((n.x + n_next.x)/2, (n.y + n_next.y)/2))

        fx = interp1d(directrix_dist[1:-1], [n.x for n in avg_normal_vectors], fill_value='extrapolate')
        fy = interp1d(directrix_dist[1:-1], [n.y for n in avg_normal_vectors], fill_value='extrapolate')
        avg_normal_vectors.insert(0, Pos(fx(directrix_dist[0]), fy(directrix_dist[0])))
        avg_normal_vectors.insert(len(avg_normal_vectors), Pos(fx(directrix_dist[len(avg_normal_vectors)]), fy(directrix_dist[len(avg_normal_vectors)])))
        
        for ae_pos, n in zip(ae_positions, avg_normal_vectors):
            ae = self.add_antenna_element([ae_pos.x, ae_pos.y, antenna_type, antenna_size])
            ae.set_orientation(n)

    def add_random_extra_angles(self, range): 
        ''' For each AntennaElement, add a random additional angle to its orientation, which is sampled from a uniform distribution in the range, given in radians. '''
        
        for ae in self.antenna_elements:
            random_extra_angle = range * (np.random.random() - 0.5)
            ae.set_orientation(ae.orientation.rotate(random_extra_angle))

    def divide_power(self):
        ''' Divides the total power Ptot allocated to the AntennaCollection equally among its AntennaElement's Ptot. '''
        
        self.power_per_antenna_element = self.Ptot_W / self.nbr_antenna_elements
        for ae in self.antenna_elements:
            ae.power_W = self.power_per_antenna_element

    def print_info(self, data):
        ''' Prints multiple series of data associated to each AntennaElement nicely, along with each AntennaElement's id. '''

        self.antenna_element_ids = np.array([ae.id for ae in self.antenna_elements])
        data_with_ids = {}; data_with_ids['Tx id'] = self.antenna_element_ids; data_with_ids.update(data) # so 'Tx id' is the first key
        df = pd.DataFrame(data_with_ids)
        df.set_index('Tx id')
        print(df.to_string(index=False))

class ClusterCollection(RadiatingCollection):
    ''' Composed of Clusters. '''

    def __init__(self):
        self.collection_type = 'cluster_collection'
        
        self.clusters = []
        self.nbr_clusters = 0

    def add_cluster(self, cluster_args, receiver):
        ''' Add a cluster. '''

        cluster = Cluster(*cluster_args, id = len(self.clusters))
        cluster.set_receiver(receiver)

        self.clusters.append(cluster)
        self.nbr_clusters += 1

        return cluster

    def add_cluster_list(self, cluster_positions, receiver):
        ''' Add a list of clusters all pointing to a specified receiver. '''

        for cluster_position in cluster_positions:
            cluster_args = [cluster_position[0], cluster_position[1], cluster_position[2]]
            self.add_cluster(cluster_args, receiver)

    def prune_clusters(self, target_unaccounted_field):
        ''' Remove clusters that have low power, making sure the removed clusters' combined field is below the ratio target_unaccounted_field of the total field. '''

        # make an array of each cluster's field_at_receiver
        abs_field = np.abs(np.array([cluster.field_at_receiver for cluster in self.clusters]))

        # sort the array
        sorted_idx = np.argsort(abs_field)[::-1]
        sorted_abs_field = abs_field[sorted_idx]
        sorted_clusters = [self.clusters[i] for i in sorted_idx]


        # we want to find the minimum of this function, which is continually decreasing, over the natural numbers
        # f(nbr_of_clusters) = np.sum(sorted_abs_field[nbr_of_clusters:])/total_abs_field - target_unaccounted_field
        total_abs_field = np.sum(sorted_abs_field)
        cluster_optimizer = lambda nbr_of_clusters: np.abs(np.sum(sorted_abs_field[int(round(nbr_of_clusters))+1:])/total_abs_field - target_unaccounted_field)
        nbr_clusters = int(round(fminbound(cluster_optimizer, 0, len(self.clusters), xtol=1)))

        self.clusters = sorted_clusters[:nbr_clusters]
        self.nbr_clusters = nbr_clusters
