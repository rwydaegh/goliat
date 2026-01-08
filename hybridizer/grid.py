import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from matplotlib.collections import LineCollection
from copy import copy

class Grid(object):
    ''' A regular grid defined by its lower left (ll) and upper right (ur) Positions. The resolution defines how many points are on each axis. '''
    
    def __init__(self, pos_ll, pos_ur, resolution, is_2D = False, units = 'm', do_setup = True):
        self.is_2D = is_2D
        self.units = units
        
        if isinstance(resolution, int):
            self.x_resolution = resolution
            self.y_resolution = resolution
            if not self.is_2D:
                self.z_resolution = resolution
        elif isinstance(resolution, tuple) or isinstance(resolution, list) or isinstance(resolution, np.ndarray):
            self.x_resolution = resolution[0]
            self.y_resolution = resolution[1]
            if not self.is_2D:
                self.z_resolution = resolution[2]
        self.pos_ur = pos_ur
        self.pos_ll = pos_ll
        
        self.x = np.linspace(pos_ll.x, pos_ur.x, self.x_resolution + 1) # fenceposting
        self.y = np.linspace(pos_ll.y, pos_ur.y, self.y_resolution + 1)
        if not self.is_2D:
            self.z = np.linspace(pos_ll.z, pos_ur.z, self.z_resolution + 1)
        
        if do_setup:
            self.setup()
        
    def setup(self):
        ''' A continuation of the initialization. '''

        # Position
        if self.is_2D:
            self.x_2D, self.y_2D = np.meshgrid(self.x, self.y, indexing='ij')
        else:
            if len(self.x) * len(self.y) * len(self.z) < 350**3:
                self.x_3D, self.y_3D, self.z_3D = np.meshgrid(self.x, self.y, self.z, indexing='ij')
            else:
                print('WARNING: Grid is too large to be stored in memory.')
        
        assert len(self.x) > 1, 'Grid loses x dimension due to low resolution.'
        assert len(self.y) > 1, 'Grid loses y dimension due to low resolution.'
        if not self.is_2D:
            assert len(self.z) > 1, 'Grid loses z dimension due to low resolution.'
        self.dx = self.x[1] - self.x[0]
        self.dy = self.y[1] - self.y[0]
        if not self.is_2D:
            self.dz = self.z[1] - self.z[0]
            
        self.x_size = self.x[-1] - self.x[0]
        self.y_size = self.y[-1] - self.y[0]
        if not self.is_2D:
            self.z_size = self.z[-1] - self.z[0]
        
        # Indices
        self.x_idx = np.arange(self.x_resolution + 1) # fenceposting
        self.y_idx = np.arange(self.y_resolution + 1)
        if not self.is_2D:
            self.z_idx = np.arange(self.z_resolution + 1)
        if self.is_2D:
            self.x_2D_idx, self.y_2D_idx = np.meshgrid(self.x_idx, self.y_idx, indexing='ij')
        else:
            if len(self.x) * len(self.y) * len(self.z) < 350**3:
                self.x_3D_idx, self.y_3D_idx, self.z_3D_idx = np.meshgrid(self.x_idx, self.y_idx, self.z_idx, indexing='ij')
                
        if not self.is_2D:
            self.Nx = self.x_resolution + 1
            self.Ny = self.y_resolution + 1
            self.Nz = self.z_resolution + 1
            self.shape = (self.Nx, self.Ny, self.Nz)
        else:
            self.Nx = self.x_resolution + 1
            self.Ny = self.y_resolution + 1
            self.shape = (self.Nx, self.Ny)

        # Subgrids
        self.subgrids = []
        self.x_idx_global = self.x_idx
        self.y_idx_global = self.y_idx
        if not self.is_2D:
            self.z_idx_global = self.z_idx

    @classmethod
    def from_size(cls, point, grid_size, resolution, is_2D = False, units = 'm'):
        ''' Creates a Grid from a Point and a grid size. '''
        
        # avoid circular imports
        from .antenna import Pos
        
        if isinstance(grid_size, tuple):
            grid_size = np.asarray(grid_size)
        elif isinstance(grid_size, float) or isinstance(grid_size, int):
            grid_size = np.ones((3,))*grid_size

        pos_ll = Pos.from_vec(point.pos - grid_size/2)
        pos_ur = Pos.from_vec(point.pos + grid_size/2)

        return cls(pos_ll, pos_ur, resolution, is_2D=is_2D, units=units, do_setup=True)

    @classmethod
    def from_points(cls, x, y, z, is_2D = False, units = 'm'):
        ''' Creates a Grid from three 1D arrays of points. '''
        
        # avoid circular imports
        from .antenna import Pos
        
        pos_ll = Pos(x[0], y[0], z[0])
        pos_ur = Pos(x[-1], y[-1], z[-1])

        self = cls(pos_ll, pos_ur, (len(x)-1, len(y)-1, len(z)-1), is_2D=is_2D, units=units, do_setup=False)

        # Overwrite the uniform x, y, z arrays
        self.x = x
        self.y = y
        self.z = z

        self.setup()

        return self

    @property
    def center(self):
        ''' Returns the center Position of the grid. '''

        # avoid circular import
        from .antenna import Pos
        
        if self.is_2D:
            p = Pos(self.x[self.x.shape[0]//2], self.y[self.y.shape[0]//2], 0)
            p.discretize_on(self)
            return p
        else:
            p = Pos(self.x[self.x.shape[0]//2], self.y[self.y.shape[0]//2], self.z[self.z.shape[0]//2])
            p.discretize_on(self)
            return p

    def float_index_to_position(self, float_indices, axis, relative_to_origin=False):
        ''' Converts the float indices to positions as a numpy array. '''
        
        if axis == 'x':
            float_indices /= self.x_resolution # (0, N) --> (0, 1)
            float_indices *= (self.pos_ur.x - self.pos_ll.x) # (0, 1) --> (0, x_range)
            if not relative_to_origin:
                float_indices += self.pos_ll.x
        elif axis == 'y':
            float_indices /= self.y_resolution
            float_indices *= (self.pos_ur.y - self.pos_ll.y)
            if not relative_to_origin:
                float_indices += self.pos_ll.y 
        elif axis == 'z':
            assert not self.is_2D
            float_indices /= self.z_resolution
            float_indices *= (self.pos_ur.z - self.pos_ll.z)
            if not relative_to_origin:
                float_indices += self.pos_ll.z 

        return float_indices

    def get_subgrid(self, pos, size):
        ''' Returns a square SubGrid centred around a position. '''
        
        from .antenna import Pos # avoids circular imports
        
        if isinstance(size, int) or isinstance(size, float):
            ll = Pos(pos.x - size/2, pos.y - size/2, pos.z - size/2).discretize_on(self, also_change_position = True)
            ur = Pos(pos.x + size/2, pos.y + size/2, pos.z + size/2).discretize_on(self, also_change_position = True)
        elif isinstance(size, np.ndarray):
            ll = Pos(pos.x - size[0]/2, pos.y - size[1]/2, pos.z - size[2]/2).discretize_on(self, also_change_position = True)
            ur = Pos(pos.x + size[0]/2, pos.y + size[1]/2, pos.z + size[2]/2).discretize_on(self, also_change_position = True)

        size_x = self.x[ur.x_idx] - self.x[ll.x_idx]
        size_y = self.y[ur.y_idx] - self.y[ll.y_idx]
        if not self.is_2D:
            size_z = self.z[ur.z_idx] - self.z[ll.z_idx]
            resolution = (int(round(size_x/self.dx)), int(round(size_y/self.dy)), int(round(size_z/self.dz))) # floating-point precision and fence-posting
        else:
            resolution = (int(round(size_x/self.dx)), int(round(size_y/self.dy))) # floating-point precision and fence-posting
        
        subgrid = SubGrid(ll, ur, resolution, self.is_2D)
        self.subgrids.append(subgrid)
        return subgrid

    def get_subgrid_slice(self, pos, thickness, dimension):
        ''' Returns a SubGrid slice of the grid, which fully spans the grid in two dimensions but is one dimensional by a distance thickness. '''

        from .antenna import Pos

        if dimension == 'x':
            ll = Pos(pos.x - thickness/2, self.pos_ll.y, self.pos_ll.z).discretize_on(self, also_change_position = True)
            ur = Pos(pos.x + thickness/2, self.pos_ur.y, self.pos_ur.z).discretize_on(self, also_change_position = True)
            actual_thickness = ur.x - ll.x
            resolution = (int(round(actual_thickness/self.dx)), self.y_resolution, self.z_resolution)
        elif dimension == 'y':
            ll = Pos(self.pos_ll.x, pos.y - thickness/2, self.pos_ll.z).discretize_on(self, also_change_position = True)
            ur = Pos(self.pos_ur.x, pos.y + thickness/2, self.pos_ur.z).discretize_on(self, also_change_position = True)
            actual_thickness = ur.y - ll.y
            resolution = (self.x_resolution, int(round(actual_thickness/self.dy)), self.z_resolution)
        elif dimension == 'z':
            ll = Pos(self.pos_ll.x, self.pos_ll.y, pos.z - thickness/2).discretize_on(self, also_change_position = True)
            ur = Pos(self.pos_ur.x, self.pos_ur.y, pos.z + thickness/2).discretize_on(self, also_change_position = True)
            actual_thickness = ur.z - ll.z
            resolution = (self.x_resolution, self.y_resolution, int(round(actual_thickness/self.dz)))

        subgrid = SubGrid(ll, ur, resolution, is_2D = False)
        self.subgrids.append(subgrid)
        return subgrid

    def get_all_subgrid_slices(self, thickness, distance_from_center = None, distance_from_sides = None):
        ''' Returns a dictionary of SubGrid slices of the grid, one for each face of the grid. '''
        from .antenna import Pos

        # if thickness is a float, it is the same for all subgrids
        if isinstance(thickness, float) or isinstance(thickness, int):
            thickness_x = thickness
            thickness_y = thickness
            thickness_z = thickness
        elif isinstance(thickness, tuple) or isinstance(thickness, list) or isinstance(thickness, np.ndarray):
            if isinstance(thickness[0], float) or isinstance(thickness[1], float) or isinstance(thickness[2], float):
                thickness_x = thickness[0]
                thickness_y = thickness[1]
                thickness_z = thickness[2]
            else:
                raise NotImplementedError('Only absolute distances are supported for thicknesses subgrids.')

        # if distance_from_center is a float, it is the same for all subgrids
        if distance_from_center is not None:
            if isinstance(distance_from_center, float) or isinstance(distance_from_center, int):
                distance_from_center_x = distance_from_center
                distance_from_center_y = distance_from_center
                distance_from_center_z = distance_from_center
            elif isinstance(distance_from_center, tuple) or isinstance(distance_from_center, list) or isinstance(distance_from_center, np.ndarray):
                if isinstance(distance_from_center[0], float) or isinstance(distance_from_center[1], float) or isinstance(distance_from_center[2], float):
                    distance_from_center_x = distance_from_center[0]
                    distance_from_center_y = distance_from_center[1]
                    distance_from_center_z = distance_from_center[2]
                else:
                    raise NotImplementedError('Only absolute distances are supported for distance_from_center subgrids.')
        
        # if distance_from_sides is a float, it is the same for all subgrids
        if distance_from_sides is not None:
            if isinstance(distance_from_sides, float) or isinstance(distance_from_sides, int):
                distance_from_sides_x = distance_from_sides
                distance_from_sides_y = distance_from_sides
                distance_from_sides_z = distance_from_sides
            elif isinstance(distance_from_sides, tuple) or isinstance(distance_from_sides, list) or isinstance(distance_from_sides, np.ndarray):
                if isinstance(distance_from_sides[0], float) or isinstance(distance_from_sides[1], float) or isinstance(distance_from_sides[2], float):
                    distance_from_sides_x = distance_from_sides[0]
                    distance_from_sides_y = distance_from_sides[1]
                    distance_from_sides_z = distance_from_sides[2]
                else:
                    raise NotImplementedError('Only absolute distances are supported for distance_from_sides subgrids.')

        if distance_from_center is None and distance_from_sides is None:
            # in this case, the subgrids are the faces of the grid
            subgrids = {'x+': self.get_subgrid_slice(self.pos_ur, thickness_x, 'x'),
                        'x-': self.get_subgrid_slice(self.pos_ll, thickness_x, 'x'),
                        'y+': self.get_subgrid_slice(self.pos_ur, thickness_y, 'y'),
                        'y-': self.get_subgrid_slice(self.pos_ll, thickness_y, 'y'),
                        'z+': self.get_subgrid_slice(self.pos_ur, thickness_z, 'z'),
                        'z-': self.get_subgrid_slice(self.pos_ll, thickness_z, 'z')}

        if distance_from_center is not None:
            assert distance_from_sides is None, 'Cannot specify both distance_from_center and distance_from_sides.'
            subgrids = {'x+': self.get_subgrid_slice(self.center + Pos(distance_from_center_x, 0, 0), thickness_x, 'x'),
                        'x-': self.get_subgrid_slice(self.center - Pos(distance_from_center_x, 0, 0), thickness_x, 'x'),
                        'y+': self.get_subgrid_slice(self.center + Pos(0, distance_from_center_y, 0), thickness_y, 'y'),
                        'y-': self.get_subgrid_slice(self.center - Pos(0, distance_from_center_y, 0), thickness_y, 'y'),
                        'z+': self.get_subgrid_slice(self.center + Pos(0, 0, distance_from_center_z), thickness_z, 'z'),
                        'z-': self.get_subgrid_slice(self.center - Pos(0, 0, distance_from_center_z), thickness_z, 'z')}

        if distance_from_sides is not None:
            assert distance_from_center is None, 'Cannot specify both distance_from_center and distance_from_sides.'
            subgrids = {'x+': self.get_subgrid_slice(self.pos_ur - Pos(distance_from_sides_x, 0, 0), thickness_x, 'x'),
                        'x-': self.get_subgrid_slice(self.pos_ll + Pos(distance_from_sides_x, 0, 0), thickness_x, 'x'),
                        'y+': self.get_subgrid_slice(self.pos_ur - Pos(0, distance_from_sides_y, 0), thickness_y, 'y'),
                        'y-': self.get_subgrid_slice(self.pos_ll + Pos(0, distance_from_sides_y, 0), thickness_y, 'y'),
                        'z+': self.get_subgrid_slice(self.pos_ur - Pos(0, 0, distance_from_sides_z), thickness_z, 'z'),
                        'z-': self.get_subgrid_slice(self.pos_ll + Pos(0, 0, distance_from_sides_z), thickness_z, 'z')}

        subgrids['x+'].name = 'x+'
        subgrids['x-'].name = 'x-'
        subgrids['y+'].name = 'y+'
        subgrids['y-'].name = 'y-'
        subgrids['z+'].name = 'z+'
        subgrids['z-'].name = 'z-'

        return subgrids

    def plot(self, ax, z_pos = None):
        ''' Plots the grid as a matrix of dots on the given pyplot ax. The z_pos is only used for 3D grids on 2D contourplots. '''

        if not self.is_2D:
            # discretize z_pos on this (sub)grid
            assert z_pos is not None
            z_pos_this_grid = copy(z_pos).discretize_on(self, also_change_position = False)
            z_pos_this_grid.x = self.pos_ll.x
            z_pos_this_grid.y = self.pos_ll.y
            z_pos_this_grid.pos[:2] = self.pos_ll.pos[:2] 

            if self.contains(z_pos_this_grid):
                ax.scatter(self.x_3D[:,:,z_pos_this_grid.z_idx], self.y_3D[:,:,z_pos_this_grid.z_idx], s = np.sqrt(self.dx**2 + self.dy**2 + self.dz**2)*10)
            else:
                pass
        else:
            ax.scatter(self.x_2D, self.y_2D, s = 3*np.sqrt(self.dx**2 + self.dy**2)*10, c = 'black')

    def plot_wireframe(self, ax):
        ''' Plots the grid as a wireframe on the given pyplot ax which is 3D. '''

        if not self.is_2D:
            # Plot the wireframe of a cube that outlines the grid

            # Create the vertices
            x = np.array([self.pos_ll.x, self.pos_ur.x])
            y = np.array([self.pos_ll.y, self.pos_ur.y])
            z = np.array([self.pos_ll.z, self.pos_ur.z])
            X, Y, Z = np.meshgrid(x, y, z)

            # Create the faces
            verts = [[X[0,0,0], Y[0,0,0], Z[0,0,0]],
                     [X[0,0,1], Y[0,0,1], Z[0,0,1]],
                     [X[0,1,1], Y[0,1,1], Z[0,1,1]],
                     [X[0,1,0], Y[0,1,0], Z[0,1,0]],
                     [X[1,0,0], Y[1,0,0], Z[1,0,0]],
                     [X[1,0,1], Y[1,0,1], Z[1,0,1]],
                     [X[1,1,1], Y[1,1,1], Z[1,1,1]],
                     [X[1,1,0], Y[1,1,0], Z[1,1,0]]]
            
            # Create the lines
            lines = [[verts[0],verts[1]],
                     [verts[1],verts[2]],
                     [verts[2],verts[3]],
                     [verts[3],verts[0]],
                     [verts[4],verts[5]],
                     [verts[5],verts[6]],
                     [verts[6],verts[7]],
                     [verts[7],verts[4]],
                     [verts[0],verts[4]],
                     [verts[1],verts[5]],
                     [verts[2],verts[6]],
                     [verts[3],verts[7]]]

            # Create the line collection
            line_collection = Line3DCollection(lines, colors = 'k')

            # Add the line collection to the plot
            ax.add_collection3d(line_collection)
        else:
            # Create the vertices
            x = np.array([self.pos_ll.x, self.pos_ur.x])
            y = np.array([self.pos_ll.y, self.pos_ur.y])
            X, Y = np.meshgrid(x, y)

            # Create the faces
            verts = [[X[0,0], Y[0,0]],
                     [X[0,1], Y[0,1]],
                     [X[1,1], Y[1,1]],
                     [X[1,0], Y[1,0]]]
            
            # Create the lines
            lines = [[verts[0],verts[1]],
                     [verts[1],verts[2]],
                     [verts[2],verts[3]],
                     [verts[3],verts[0]]]

            # Create the line collection
            line_collection = LineCollection(lines, colors = 'k')

            # Add the line collection to the plot
            ax.add_collection(line_collection)
 
    def contains(self, pos):
        ''' Check if a point is inside the grid. '''
        
        if not self.is_2D:
            return (self.pos_ll.x <= pos.x <= self.pos_ur.x) and (self.pos_ll.y <= pos.y <= self.pos_ur.y) and (self.pos_ll.z <= pos.z <= self.pos_ur.z)
        else:
            return (self.pos_ll.x <= pos.x <= self.pos_ur.x) and (self.pos_ll.y <= pos.y <= self.pos_ur.y)

    def get_circle(self, center = None, radius = None, in_global = True):
        ''' Returns the positions and indices of points in a circle. By default this is the concentric circle. '''
        
        if center is None:
            center = self.pos_ll.pos + (self.pos_ur.pos - self.pos_ll.pos) / 2
        if radius is None:
            radius = (self.pos_ur.x - self.pos_ll.x) / 2

        points = []
        points_idx = []
        for x, x_idx in zip(self.x, self.x_idx):
            for y, y_idx in zip(self.y, self.y_idx):
                vec = np.array([x,y, center[2]]) - center
                r = np.linalg.norm(vec)
                if r < radius:
                    points.append(np.array([x,y]))
                    points_idx.append(np.array([x_idx, y_idx]))

        self.points_in_circle = np.array(points)
        self.points_idx_in_circle = np.array(points_idx)

        # generally this method is called for subgrids, so the indices are then returned in the global grid indices
        if in_global:
            self.points_idx_in_circle += np.array([self.pos_ll.x_idx, self.pos_ll.y_idx])

        return self.points_in_circle, self.points_idx_in_circle

    def get_sphere(self, center = None, radius = None, in_global = True):
        ''' Returns the positions and indices of points in a sphere. By default this is the concentric sphere. '''
        
        assert not self.is_2D
        
        if center is None:
            center = self.pos_ll.pos + (self.pos_ur.pos - self.pos_ll.pos) / 2
        if radius is None:
            radius = (self.pos_ur.x - self.pos_ll.x) / 2

        points = []
        points_idx = []
        for x, x_idx in zip(self.x, self.x_idx):
            for y, y_idx in zip(self.y, self.y_idx):
                for z, z_idx in zip(self.z, self.z_idx):
                    vec = np.array([x,y,z]) - center
                    r = np.linalg.norm(vec)
                    if r < radius:
                        points.append(np.array([x,y,z]))
                        points_idx.append(np.array([x_idx, y_idx, z_idx]))

        self.points_in_sphere = np.array(points)
        self.points_idx_in_sphere = np.array(points_idx)

        # generally this method is called for subgrids, so the indices are then returned in the global grid indices
        if in_global:
            self.points_idx_in_sphere += np.array([self.pos_ll.x_idx, self.pos_ll.y_idx, self.pos_ll.z_idx])

        return self.points_in_sphere, self.points_idx_in_sphere

    def get_slice(self, coordinates, dimension, index):
        ''' Returns a slice of the 3D meshgrid. This getter does not use self.x_3D, self.y_3D, self.z_3D, but instead uses self.x, self.y, self.z to avoid memory issues. '''

        assert not self.is_2D

        if dimension == 'x':
            x, y, z = np.meshgrid(self.x[index], self.y, self.z, indexing='ij')
        elif dimension == 'y':
            x, y, z = np.meshgrid(self.x, self.y[index], self.z, indexing='ij')
        elif dimension == 'z':
            x, y, z = np.meshgrid(self.x, self.y, self.z[index], indexing='ij')
        
        x = x.squeeze()
        y = y.squeeze()
        z = z.squeeze()
        
        if coordinates == 'x':
            return x
        elif coordinates == 'y':
            return y
        elif coordinates == 'z':
            return z
        elif coordinates == 'all':
            return x, y, z

class SubGrid(Grid):
    ''' A subgrid is a Grid embedded in a larger Grid. Positions are w.r.t. the larger Grid. '''

    def __init__(self, pos_ll, pos_ur, resolution, is_2D, name = None):
        super().__init__(pos_ll, pos_ur, resolution, is_2D)
        self.name = name
        
        # Global indices in the parent grid
        self.x_idx_global = self.x_idx + self.pos_ll.x_idx
        self.y_idx_global = self.y_idx + self.pos_ll.y_idx
        if not self.is_2D:
            self.z_idx_global = self.z_idx + self.pos_ll.z_idx

        deprecated = True
        if self.is_2D:
            if deprecated:
                self.x_2D_idx_global, self.y_2D_idx_global = np.meshgrid(self.x_idx_global, self.y_idx_global, indexing='ij') 
        else:
            if deprecated:
                if len(self.x) * len(self.y) * len(self.z) < 350**3:
                    self.x_3D_idx_global, self.y_3D_idx_global, self.z_3D_idx_global = np.meshgrid(self.x_idx_global, self.y_idx_global, self.z_idx_global, indexing='ij')
                else:
                    print('WARNING: Subgrid is too large to be stored in memory')
            
            # Just plain faster
            self.x_3D_idx_global_slice = slice(self.x_idx_global[0], self.x_idx_global[-1]+1) 
            self.y_3D_idx_global_slice = slice(self.y_idx_global[0], self.y_idx_global[-1]+1)
            self.z_3D_idx_global_slice = slice(self.z_idx_global[0], self.z_idx_global[-1]+1)