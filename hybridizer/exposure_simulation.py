from pathlib import Path
import os, time, h5py, subprocess, socket, shutil
import numpy as np
from scipy.constants import speed_of_light as c0

from s4l_v1._api.application import get_app_safe, run_application

from .antenna import Pos
from .grid import Grid

class ExposureSimulation(object):

    def __init__(self, S4L_file_name):

        self.S4L_file_name = S4L_file_name
        _, self.frequency_band = self.S4L_file_name.split(' ')
        if 'low' in self.frequency_band:
            self.frequency = 0.7e9
            self.cpw = 80
        elif 'mid' in self.frequency_band:
            self.frequency = 3.5e9
            self.cpw = 15
        elif 'high' in self.frequency_band:
            self.frequency = 26e9
            self.cpw = 8 # lower to make it feasible to run
            print('CPW is a bit low', 'Warning')
        elif 'e+' in self.frequency_band:
            self.frequency = float(self.frequency_band.split('-')[0])
            self.cpw = 10
        else:
            raise ValueError('Frequency band not recognized.')
        
        self.scene = 'tmp'
        self.has_overall_field_extractor = False
        self.skin_model_name = 'MIDA_mmWave_smoothed' # or 'skin_coarse'

        self.lmbd_mm = c0 / self.frequency * 10.**3
        self.max_step_mm = self.lmbd_mm/self.cpw

        self.verbose = True

    def assign_scene(self, scene):
        self.scene = scene

        # copy the S4L file in the exposure_simulation_list to the scene folder in the working directory
        exposure_simulation_list = Path(os.path.dirname(os.path.abspath(__file__))).parent / f'data/exposure_simulation_list'
        origin = exposure_simulation_list / f'{self.S4L_file_name}.smash'
        if not os.path.exists(exposure_simulation_list):
            os.makedirs(exposure_simulation_list)
        if not os.path.exists(origin):
            raise ValueError(f'The exposure simulation file {self.S4L_file_name} does not exist in data/exposure_simulation_list/.')

        destination = self.wrk_dir / f'{self.S4L_file_name}.smash'
        if not os.path.exists(self.wrk_dir):
            os.makedirs(self.wrk_dir)
        if not os.path.exists(destination.parent):
            os.makedirs(destination.parent)
        if not os.path.exists(destination):
            shutil.copy(origin, destination)

        results_dir = self.wrk_dir / f'{self.S4L_file_name}.smash_Results'
        if not os.path.exists(results_dir):
            # copy the results folder from the exposure_simulation_list to the scene folder in the working directory
            origin_results_dir = exposure_simulation_list / f'{self.S4L_file_name}.smash_Results'
            if os.path.exists(origin_results_dir):
                shutil.copytree(origin_results_dir, results_dir)
            else:
                if self.verbose:
                    print('WARNING: The Sim4Life results folder does not exist in data/exposure_simulation_list/. The loader and executer simulations will be run.')

    @property
    def wrk_dir(self):
        path_of_file = Path(os.path.dirname(os.path.abspath(__file__))).parent
        return path_of_file / f'data/{self.scene}/sim4life'

    def prepare(self, run_placeholder_simulations = True):
        import s4l_v1.document as document
        import s4l_v1.model as model
        import s4l_v1.simulation as simulation
        import s4l_v1.analysis as analysis
        import s4l_v1.units as units
        self.S4L_document_module = document
        self.S4L_model_module = model
        self.S4L_simulation_module = simulation
        self.S4L_analysis_module = analysis

        if get_app_safe() is None:
            self.app = run_application()
            
        self.S4L_document_path = str(self.wrk_dir / (self.S4L_file_name + '.smash'))
        self.S4L_document_results_path = self.S4L_document_path + '_Results'
        self.S4L_document_module.Open(self.S4L_document_path)
        self.S4L_document = self.S4L_document_module

        self.S4L_loader_simulation = self.S4L_document_module.AllSimulations['Loader simulation']
        self.S4L_executer_simulation = self.S4L_document_module.AllSimulations['EM']

        self.set_submit_server('localhost')
        self.kernel_type = 'Software'
        if not self.S4L_loader_simulation.HasResults() and run_placeholder_simulations:
            if self.verbose:
                print('Running the loader simulation...')
            self.S4L_loader_simulation.RunSimulation(wait=True, server_id=self.submit_server_id)
        if not self.S4L_executer_simulation.HasResults() and run_placeholder_simulations:
            if self.verbose:
                print('Running the executer simulation...')
            self.S4L_executer_simulation.RunSimulation(wait=True, server_id=self.submit_server_id)

        self.S4L_loader_simulation_id = self.S4L_loader_simulation.InputFilename.split('/')[-1].split('_')[0]
        self.S4L_executer_simulation_id = self.S4L_executer_simulation.InputFilename.split('/')[-1].split('_')[0]

        self.bounding_box_model = self.S4L_model_module.AllEntities()[f'Bounding_box']
        self.huygens_box_model = self.S4L_model_module.AllEntities()[f'Huygens_box']
        self.python_box_model = self.S4L_model_module.AllEntities()[f'Python_box']

        self.plane_wave_source = self.S4L_executer_simulation.AllSettings['Plane Wave Settings']
        self.huygens_box_source = self.S4L_executer_simulation.AllSettings['Huygens Box Settings']

        '''
        self.S4L_executer_simulation.SetupSettings.GlobalAutoTermination = self.S4L_executer_simulation.SetupSettings.GlobalAutoTermination.enum.GlobalAutoTerminationMedium
        quasi_infinite_simulation_time = True
        if quasi_infinite_simulation_time:
            self.S4L_executer_simulation.SetupSettings.SimulationTime = 1000, units.Periods # periods, just as an quasi-infinite maximum. The auto convergence should then allow it to stop earlier
        else:
            self.S4L_executer_simulation.SetupSettings.SimulationTime = 30, units.Periods
        '''

        self.device_name = socket.gethostname().upper()
        if 'WICASIM' in self.device_name or 'FANG-WKST' in self.device_name:
            self.set_submit_server('localhost')
            self.kernel_type = 'CUDA'
        elif self.device_name == 'UG-GYST2J3':
            if self.frequency < 10e9:
                self.set_submit_server('localhost')
                self.kernel_type = 'Software'
            else:
                if self.verbose:
                    print('Running this simulation on WICASIM4 because it will take too long on this device.')
                self.set_submit_server('WICASIM4')
                self.kernel_type = 'CUDA'
        else:
            # search for cached response in the working directory
            cached_response_path = self.wrk_dir / 'has_GPU.txt'
            if os.path.exists(cached_response_path):
                with open(cached_response_path, 'r') as f:
                    response = f.read()
            else:
                response = input('Unknown device. Do you have a GPU to run the S4L simulation(s) on? (y/n): ').rstrip("\r")
                with open(cached_response_path, 'w') as f:
                    f.write(response)
            if response == 'y':
                self.set_submit_server('localhost')
                self.kernel_type = 'CUDA'
            elif response == 'n':
                if self.frequency < 10e9:
                    self.set_submit_server('localhost')
                    self.kernel_type = 'Software'
                else:
                    if self.verbose:
                        print('Running this simulation on WICASIM4 because it will take too long on this device.')
                    self.set_submit_server('WICASIM4')
                    self.kernel_type = 'CUDA'

    def set_huygens_box(self, nbr_of_cells_around_bounding_box=3):
        
        self.cell_size = self.lmbd_mm/self.cpw
        self.cell_size /= 1000 # to meters

        bounding_box_size = self.get_box_size(self.bounding_box_model)
        bounding_box_translation = self.get_box_translation(self.bounding_box_model)

        huygens_box_size = [bounding_box_size[0] + 2*nbr_of_cells_around_bounding_box*self.cell_size, bounding_box_size[1] + 2*nbr_of_cells_around_bounding_box*self.cell_size, bounding_box_size[2] + 2*nbr_of_cells_around_bounding_box*self.cell_size]
        #huygens_box_translation = [bounding_box_translation[0] - 3*self.cell_size, bounding_box_translation[1] - 3*self.cell_size, bounding_box_translation[2] - 3*self.cell_size]

        #self.set_box_translation(self.huygens_box_model, huygens_box_translation)
        self.set_box_size(self.huygens_box_model, huygens_box_size)

        # Save
        self.S4L_document.Save()

    def set_python_box(self, nbr_of_cells_around_huygens_box=3):

        self.cell_size = self.lmbd_mm/self.cpw
        self.cell_size /= 1000 # to meters

        huygens_box_size = self.get_box_size(self.huygens_box_model)
        huygens_box_translation = self.get_box_translation(self.huygens_box_model)

        python_box_size = [huygens_box_size[0] + 2*nbr_of_cells_around_huygens_box*self.cell_size, huygens_box_size[1] + 2*nbr_of_cells_around_huygens_box*self.cell_size, huygens_box_size[2] + 2*nbr_of_cells_around_huygens_box*self.cell_size]
        #python_box_translation = [huygens_box_translation[0] - 3*self.cell_size, huygens_box_translation[1] - 3*self.cell_size, huygens_box_translation[2] - 3*self.cell_size]

        #self.set_box_translation(self.python_box_model, python_box_translation)
        self.set_box_size(self.python_box_model, python_box_size)

        # Save
        self.S4L_document.Save()

    def create_grid(self):

        assert self.S4L_loader_simulation.HasResults(), 'The S4L loader simulation needs results first to access grid parameters.'

        overall_field_sensor = self.S4L_loader_simulation.Results()[ 'Overall Field' ]
        field = overall_field_sensor['EM E(x,y,z,f0)']
        grid = field.Data.Grid
        Nx, Ny, Nz = len(grid.XAxis) - 1, len(grid.YAxis) - 1, len(grid.ZAxis) - 1 
        ll_x, ll_y, ll_z = grid.XAxis[0], grid.YAxis[0], grid.ZAxis[0]
        ur_x, ur_y, ur_z = grid.XAxis[-1], grid.YAxis[-1], grid.ZAxis[-1]

        return Grid(Pos(ll_x, ll_y, ll_z), Pos(ur_x, ur_y, ur_z), resolution=(Nx, Ny, Nz))

    def run(self, run_isolve_directly = True):
        self.S4L_executer_simulation.ClearResults()
        if self.verbose:
            print('Starting FDTD simulation...')
        t0 = time.time()
        # dont try this, it will reset the input file from the loader simulation
        #self.S4L_executer_simulation.RunSimulation(wait=True, server_id=self.submit_server_id, run_isolve_directly=run_isolve_directly)
        if run_isolve_directly:
            # start a subprocess
            isolve_path = self.S4L_executer_simulation._GetISolvePath()
            input_file_path = self.S4L_executer_simulation.InputFilename
            iSolve_cmd = [isolve_path, "-i", input_file_path]
            subprocess.run(iSolve_cmd)

        if self.verbose:
            print(f'Done in {time.time()-t0:.2f} seconds')
        
        assert self.S4L_executer_simulation.HasResults(), 'Something went wrong with the S4L simulation.'

    def set_submit_server(self, server):
        ''' Server string to id. '''

        servers=self.S4L_simulation_module.GetAvailableServers()
        try:
            self.submit_server_id=servers.get(server)
        except:
            raise ValueError(f'{server} server is not available.')

    def get_box_size(self, box):
        ''' Extracts the bounding box of the head in the S4L file. '''

        for property in [box.Parameters[i] for i in range(0,4)]:
                if property.Name == 'SizeX':
                    SizeX=property.Value
                elif property.Name == 'SizeY':
                    SizeY=property.Value
                elif property.Name == 'SizeZ':
                    SizeZ=property.Value 
        return np.array([SizeX, SizeY, SizeZ])/1000 # to meters

    def set_box_size(self, box, size):
        ''' Sets the bounding box of the head in the S4L file. '''

        #input(f'Please set the size to {size} manually for {box.Name}.')
        for property in [box.Parameters[i] for i in range(0,4)]:
                if property.Name == 'SizeX':
                    property.Value = size[0]*1000 # to mm
                elif property.Name == 'SizeY':
                    property.Value = size[1]*1000
                elif property.Name == 'SizeZ':
                    property.Value = size[2]*1000

        box.EvaluateParameters()

    def get_box_translation(self, box):
        ''' Extracts the translation of the bounding box of the head in the S4L file. '''

        return np.array(box.Transform.Translation)/1000 # to meters

    def set_box_translation(self, box, translation):
        ''' Sets the translation of the bounding box of the head in the S4L file. '''

        from XCoreModeling import Vec3, Transform

        box.ApplyTransform(box.Transform.Inverse())
        box.ApplyTransform(Transform(Vec3(1.0,1.0,1.0),Vec3(0.0,0.0,0.0),Vec3(translation[0]*1000,translation[1]*1000,translation[2]*1000)))

    def get_huygens_grid(self, uniform = False):
        ''' Returns a Python Grid object corresponding to the Huygens box in the S4L executer simulation. 
        Uniform: based on the resolution and ll/ur positions
        Non-uniform: based on the x, y, z coordinates '''

        h5_path = f'{self.S4L_document_results_path}\{self.S4L_executer_simulation_id}_Input.h5'
        with h5py.File(h5_path, mode='r+') as h5_file:
            mesh_keys = list(h5_file['Meshes'].keys())
            meshes = [h5_file[f'Meshes/{mesh_key}/'] for mesh_key in mesh_keys]
            mesh_attributes = [dict(h5_file[f'Meshes/{mesh_key}/_Object'].attrs.items()) for mesh_key in mesh_keys]
            mesh_names = [mesh_attr['mesh_name'].decode('ascii') for mesh_attr in mesh_attributes]
            huygens_box_found = False
            for mesh, mesh_name in zip(meshes, mesh_names):
                if 'Mesh Huygens_box' in mesh_name:
                    huygens_box_found = True
                    break
            assert huygens_box_found, 'Huygens box not found in the S4L loader simulation.'
            if uniform:
                grid_resolution = len(mesh['axis_x']) - 1, len(mesh['axis_y']) - 1, len(mesh['axis_z']) - 1 # fenceposting
                pos_ll = Pos(mesh['axis_x'][0], mesh['axis_y'][0], mesh['axis_z'][0])
                pos_ur = Pos(mesh['axis_x'][-1], mesh['axis_y'][-1], mesh['axis_z'][-1])
                grid = Grid(pos_ll, pos_ur, resolution=grid_resolution)
            else:
                x, y, z = mesh['axis_x'][:], mesh['axis_y'][:], mesh['axis_z'][:]
                grid = Grid.from_points(x, y, z)

        return grid

    def get_python_grid(self, uniform = False):
        ''' Returns a Python Grid object corresponding to the Python box in the S4L loader simulation.
        Uniform: based on the resolution and ll/ur positions
        Non-uniform: based on the x, y, z coordinates '''

        h5_path = f'{self.S4L_document_results_path}\{self.S4L_loader_simulation_id}_Input.h5'
        with h5py.File(h5_path, mode='r+') as h5_file:
            mesh_keys = list(h5_file['Meshes'].keys())
            meshes = [h5_file[f'Meshes/{mesh_key}/'] for mesh_key in mesh_keys]
            mesh_attributes = [dict(h5_file[f'Meshes/{mesh_key}/_Object'].attrs.items()) for mesh_key in mesh_keys]
            mesh_names = [mesh_attr['mesh_name'].decode('ascii') for mesh_attr in mesh_attributes]
            overall_axis_found = False
            for mesh, mesh_name in zip(meshes, mesh_names):
                if 'Overall Axes' in mesh_name:
                    overall_axis_found = True
                    break
            assert overall_axis_found, 'Overall axes not found in the S4L loader simulation.'
            if uniform:
                grid_resolution = len(mesh['axis_x']) - 1, len(mesh['axis_y']) - 1, len(mesh['axis_z']) - 1 # fenceposting
                pos_ll = Pos(mesh['axis_x'][0], mesh['axis_y'][0], mesh['axis_z'][0])
                pos_ur = Pos(mesh['axis_x'][-1], mesh['axis_y'][-1], mesh['axis_z'][-1])
                grid = Grid(pos_ll, pos_ur, resolution=grid_resolution)
            else:
                x, y, z = mesh['axis_x'][:], mesh['axis_y'][:], mesh['axis_z'][:]
                grid = Grid.from_points(x, y, z)

        return grid

    def add_overall_field_extractor(self):
        ''' Adds an overall field extractor to the analysis pipeline. Other functions 
        require has_overall_field_extractor to be True to proceed. '''
        
        import s4l_v1.units as units

        assert self.S4L_executer_simulation.HasResults(), 'Simulation does not have results. Consider dummy running the simulation first.'
        simulation_extractor = self.S4L_executer_simulation.Results()

        self.em_sensor_extractor = simulation_extractor["Overall Field"]
        self.em_sensor_extractor.FrequencySettings.ExtractedFrequency = u"All"
        self.em_sensor_extractor.SurfaceCurrent.SurfaceResolution = 0.001, units.Meters
        self.S4L_document.AllAlgorithms.Add(self.em_sensor_extractor)
        self.has_overall_field_extractor = True

    def get_max_Sab(self, first_time = False):
        ''' Extracts the maximum Sab from the S4L simulation. If first_time is true, updates the existing algorithm. '''

        if not first_time:
            '''
            algorithms = [i for i in self.S4L_document_module.AllAlgorithms]

            PDE_alg = None
            for alg in algorithms:
                if alg.Name == 'Power Density Evaluator':
                    PDE_alg = alg

            if PDE_alg is None:
                if self.verbose:
                    print('Warning: did not find the power density evaluator, so making it again.')
                first_time = False
            else:
               '''
            if self.verbose:
                print('Updating the post-processing algorithm...')
            t0=time.time()
            self.sapd_report_output.Update()
            data = self.sapd_report_output.Data
            data_json = data.DataSimpleDataCollection

            self.max_Sab_results = {}
            for key in ['PeakPower', 'PeakSAPDPosition']:
                snapshot_index = 0
                try:
                    value = data_json.FieldValue(key, snapshot_index)
                    description = data_json.FieldDescription(key) #description for 'PeakPower' is 'Peak Spatial-Avg. Power Density', not 'Peak Power'
                except Exception as e:
                    if self.verbose:
                        print(e)
                        print("Failed to find max Sab")
                    value = -10000
                    description = 'Peak Spatial-Avg. Power Density'
                self.max_Sab_results[description] = value

            if self.verbose:
                print(f'Done in {time.time()-t0:.2f} seconds')

            return

        if self.verbose:
            print('Creating the post-processing step...')
        t0 =time.time()
        import s4l_v1.units as units

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()

        inputs = []
        model_to_grid_filter = self.S4L_analysis_module.core.ModelToGridFilter(inputs=inputs)
        model_to_grid_filter.Name = self.skin_model_name
        model_to_grid_filter.Entity = self.S4L_model_module.AllEntities()[self.skin_model_name]
        model_to_grid_filter.UpdateAttributes()
        self.S4L_document_module.AllAlgorithms.Add(model_to_grid_filter)

        # Adding a new GenericSAPDEvaluator
        inputs = [self.em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]
        generic_sapd_evaluator = self.S4L_analysis_module.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
        generic_sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
        generic_sapd_evaluator.Threshold = 0.01, units.Meters # 10 mm
        generic_sapd_evaluator.UpdateAttributes()
        self.S4L_document_module.AllAlgorithms.Add(generic_sapd_evaluator)

        # Evaluator to json to dictionary
        self.sapd_report_output = generic_sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
        self.sapd_report_output.Update()
        data = self.sapd_report_output.Data
        data_json = data.DataSimpleDataCollection

        self.max_Sab_results = {}
        for key in ['PeakPower', 'PeakSAPDPosition']:
            snapshot_index = 0
            try:
                value = data_json.FieldValue(key, snapshot_index)
                description = data_json.FieldDescription(key) #description for 'PeakPower' is 'Peak Spatial-Avg. Power Density', not 'Peak Power'
            except Exception as e:
                if self.verbose:
                    print(e)
                    print("Failed to find max Sab")
                value = -10000
                description = 'Peak Spatial-Avg. Power Density'
            self.max_Sab_results[description] = value

        self.S4L_document.Save()

        if self.verbose:
            print(f'Done in {time.time()-t0:.2f} seconds')