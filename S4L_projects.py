## IMPORTS

# Scripting
import os, shutil, pickle, gc, h5py
from re import A
from pathlib import Path

# Back-ends
import numpy as np
import pandas as pd
from scipy.constants import speed_of_light as c0

# Ease-of-life 
import time, IPython

# Other code in the project. Reload is necessary as it isn't practical to relaunch S4L and its Python Kernel every time you change something.
import Code
from importlib import reload
allow_reloads = False #isinstance could fail https://stackoverflow.com/questions/50478661/python-isinstance-not-working-as-id-expect
if allow_reloads:
    try:
        reload(Code.projects)
        reload(Code.wi_to_s4l) 
        reload(Code.rays) 
    except:
        pass
from Code.projects import Project, S4L_Project, Headless_Study
from Code.wi_to_s4l import combine_ico, replace_results
from Code.rays import Rays #note: changes the matplotlib GUI backend

## Classes

class Deterministic(S4L_Project):
    ''' A type of S4L_Project that analyses one S4L file with the incoming rays of one WI file. 
    This is a concrete class that implements full runs for one or all receivers, from making the library to exposure results. 
    Can also be constructed by composition of a Stochastic object. '''

    def __init__(self, rx_list, WI_name, S4L_name, frequency_band, parent = None, precoding='MRT', nbr_tesselation_points=12, verbose=True, headless_S4L=False, ignore_exposure_cache=False):
        if isinstance(parent, Stochastic):
            self.parent = parent # self.parent.x can call methods of Stochastic and it's parents
        elif parent is None:
            self.parent = self # self.parent.x calls x on dedicated new S4L project due to inheritance. 
        super().__init__(S4L_name, frequency_band, nbr_tesselation_points, verbose=verbose, headless_S4L=headless_S4L)
        self.clear_my_prints() #because standalone constructor here

        self.rx_list = rx_list
        self.WI_name=WI_name  
        self.dedicated_WI_path = 'Default'      
        self.has_overall_field_extractor = False
        self.ignore_exposure_cache = ignore_exposure_cache
        self.keep_combined_pw_result = False #definitely do not uncomment line below when doing a large Study. The hard disk write speed will become a limiting factor. It can be useful as some kind of cache
        self.rays_in_memory = None
        self.precoding = precoding

    @classmethod
    def from_stochastic_S4L_project(cls, stochastic_S4L_project, WI_name):
        foo =  cls(
            stochastic_S4L_project.rx_list,
            WI_name,
            stochastic_S4L_project.S4L_name,
            stochastic_S4L_project.frequency_band,
            parent = stochastic_S4L_project,
            precoding = stochastic_S4L_project.precoding,
            nbr_tesselation_points = stochastic_S4L_project.nbr_tesselation_points,
            verbose=stochastic_S4L_project.verbose,
            headless_S4L = stochastic_S4L_project.headless_S4L,
            ignore_exposure_cache = stochastic_S4L_project.ignore_exposure_cache
            )
        foo.do_not_assert = stochastic_S4L_project.do_not_assert #TODO
        return foo

    def all_rx_run(self, notes='', overwrite_pw_lib=False, overwrite_ez_pat=False, remove_after=True):
        ''' Wraps single_rx_run. Can throw away the combined PW result file, because this is a large data file. 
        The exposure result is kept. '''
        
        for rx in self.rx_list:
            self.single_rx_run(rx, notes=notes, overwrite_pw_lib=overwrite_pw_lib, overwrite_ez_pat=overwrite_ez_pat)
            if self.keep_combined_pw_result and remove_after:
                try:
                    os.remove(self.combined_pw_result_path)
                except:
                    pass
        del self.rays_in_memory

    def single_rx_run(self, rx, notes='', overwrite_pw_lib=False, overwrite_sf_pts=False, overwrite_sf_lib=False, overwrite_ez_pat=False):
        ''' Find the exposure for one receiver id rx. This includes making the libary, 
        the electric field pattern around the UE, the combination of the plane waves, computing
        the exposure result and exporting. '''

        self.rx=rx
        self.assertion(self.rx>=0, 'Invalid rx.', 'Error')
        self.assertion(self.rx in self.rx_list, 'Rx id not in rx id list of the Deterministic object.', 'Error')
        if 'Phase test' in str(self.WI_name):
            self.assertion(self.rx==0, 'There is only one rx with id 0 in the phase test of this Phase test RT simulation.', 'Error')

        if not self.parent.get_run_with_S4L:
            self.assertion(False, 'Setting project to run with S4L.', 'Warning')
            self.parent.set_to_run_with_S4L(True)

        t_start=time.time()
        self.current_run['name'] = f'Deterministic'
        if notes != '' and notes[:2] != ', ':
            self.current_run['name'] += ', ' + notes
        self.current_run['start time'] = t_start
        self.current_run['timestamp'] = time.ctime(t_start)
        self.current_run['params'] = self.get_string_parameters()
        
        if not self.parent.has_pw_library:
            self.parent.make_pw_lib(overwrite=overwrite_pw_lib)
        else:
            self.assertion(False, 'Already has PW library, skipping this step.', 'Warning')

        if self.parent.use_surface_fields:
            if not self.parent.has_sf_pts:
                self.parent.make_sf_pts(overwrite=overwrite_sf_pts)
            else:
                self.assertion(False, 'Already has surface points, skipping this step', 'Warning')

            if not self.parent.has_sf_library:
                self.parent.make_sf_lib(overwrite=overwrite_sf_lib)
            else:
                self.assertion(False, 'Already has surface field library, skipping this step', 'Warning')

        if not self.parent.has_ez_pattern:
            self.parent.make_ez_pat(overwrite=overwrite_ez_pat)
        else:
            self.assertion(False, 'Already has ez pattern, skipping this step.', 'Warning')

        if not self.has_max_exposure_result(self.rx):
            if self.parent.get_lib_in_memory() is None:
                self.parent.set_lib_in_memory()
            else:
                self.assertion(False, 'Already has PW library loaded to memory, skipping this step.', 'Warning')

            if self.rays_in_memory is None:
                self.put_rays_in_memory()
            else:
                self.assertion(False, 'Already has rays loaded to memory, skipping this step.', 'Warning')

            if not self.has_combined_pw_result:
                self.combine_pws()
                self.replace_results()
                del self.combine_pws_result #for memory
            else:
                self.assertion(False, 'Already has combined PW results, skipping this step.', 'Warning')

            if 'Empty' in self.parent.S4L_document_name:
                self.export_max_Sinc()
            else:
                if self.parent.frequency_band == 'mid':
                    self.export_psSAR10g()
                elif self.parent.frequency_band == 'high':
                    self.export_max_Sab()
        else:
            self.assertion(False, 'Already has an exposure result, skipping PW combination and maximum export.', 'Warning')

        self.write_current_run_log() 

    def write_current_run_log(self):
        path = self.current_run_path / f"Rx #{self.rx}, run #{self.nbr_of_runs+1} log.txt"
        with open(str(path), 'w', encoding="utf-8") as f:
            f.writelines(self.get_current_run_log())
        return path

    @property
    def print_file_path(self):
        if isinstance(self.parent, Stochastic):
            return self.parent.print_file_path
        elif isinstance(self.parent, Deterministic):
            return super().print_file_path
        
    def plot(self, notes='', exclude_first=False, scatter_plot=False, with_legend=True):
        ''' Plots the exposure type as a function of distance, from the rx id, in mW and normalized to the 320 W base station. '''

        raise NotImplemented

    @property
    def current_run_path(self):
        if isinstance(self.parent, Stochastic):
            path = self.parent.current_run_path / self.current_run['name']
            if not path.exists():
                os.mkdir(path)
            return path
        else:
            return super().current_run_path

    def has_max_exposure_result(self, rx=None):
        ''' Exposure result don't exist when never computed, or not cached.
        Boolean when attribute exposure_result exists, or it's rx'th element. '''

        if rx is not None:
            return bool((f'rx_{rx}' in self.exposure_result) or (str(rx) in self.exposure_result))
        else:
            return bool(self.exposure_result)

    @property
    def exposure_result_cache_path(self):
        return self.current_run_path / f'{self.parent.exposure_result_type}_{self.rx}.pickle'

    def cache_exposure_result(self):
        if self.assertion(self.has_max_exposure_result(), 'Can not cache exposure result if it does not exist.', 'Deterrent'):            
            notes = self.exposure_result
            with open(self.exposure_result_cache_path, 'wb') as f:
                pickle.dump(notes, f)

    @property
    def exposure_result(self):
        ''' Returns the specific exposure result assigned after a computation, depending on self.exposure_result_type. '''

        if self.exposure_result_cache_path.exists() and not self.ignore_exposure_cache:
            self.assertion(False, 'Reading exposure result from cache.', 'Warning')
            with open(self.exposure_result_cache_path, 'rb') as f:
                return pickle.load(f)
        else:
            try:
                exp_type = self.parent.exposure_result_type
                if exp_type=='max_Sinc':
                    return self.max_Sinc_results
                elif exp_type=='psSAR10g':
                    return self.psSAR10g_results
                elif exp_type=='max_Sab':
                    return self.max_Sab_results
            except AttributeError:
                return []

    @property
    def full_exposure_result(self):
        ''' Compiles the exposure result caches of all receiver runs. '''

        full_results = {}
        for rx in self.rx_list:
            with open(self.current_run_path / f'{self.parent.exposure_result_type}_{rx}.pickle', 'rb') as file:
                data = pickle.load(file)
                try:
                    full_results[f'rx_{rx}'] = data[f'rx_{rx}']
                except:
                    full_results[f'rx_{rx}'] = data[str(rx)]
        return full_results

    @property
    def WI_path(self):
        if self.dedicated_WI_path == 'Default':
            return self.wrk_dir / 'WI' / self.WI_name
        else:
            return self.dedicated_WI_path / self.WI_name

    def set_dedicated_WI_path(self, new_path):
        ''' Overrides the default location of the WI path to a new place. Reading and writing will
        always go to the new path henceforth. You may want this when you have a separate data hard drive or folder. '''

        new_path = Path(new_path)
        self.assertion(new_path.exists(), 'New plane wave library path does not exist.', 'Error')
        old_path = self.WI_path
        self.dedicated_WI_path = new_path
        self.my_print(f'The Wireless InSite ray tracing results from {new_path} is now used instead of {old_path}', show=True)

    @property
    def has_RT_cache_files(self):
        ''' The Rays object produces these caches, as well as the self.rays pickling in combine_pws. '''

        path = self.WI_path / 'Interface'
        if path.exists():
            if set(['d.npy', 'h.npy', 'ico', 'rays.pkl']).issubset(set(os.listdir(path))):
                return True
        return False

    @property
    def has_RT_raw_files(self):
        ''' Required files for the Rays class, which converts them to faster/smaller cache files. '''

        path = self.WI_path / 'Interface'
        if path.exists():
            if set(['rays.sqlite' , 'cfg.xml']).issubset(set(os.listdir(path))):
                return True
        return False

    @property
    def has_RT_files(self):
        if self.has_RT_cache_files:
            self.assertion(False, 'Using cached RT files. Changes in the RT simulation will not have any effect.', 'Warning') #TODO: figure out a way to know this through the creation date of the files
            return True
        else:
            return self.assertion(self.has_RT_raw_files, 'Cannot find the raw RT raytracing files rays.sqlite and/or cfg.xml. There are also no cached files found of these.', 'Error')

    @Project.heavy_job(job_name='Load the rays to memory')
    def put_rays_in_memory(self):
        ''' The rays object gets reused often in a Determinstic, Stochastic or Study run, as the 
        WI environment is sometimes the same. This function fills up self.rays with some GB's of data 
        so it gets reused in self.combine_pws() '''

        self.assertion(self.rays_in_memory is None, 'There are already rays loaded to memory. Continuing will overwrite.', 'Deterrent')
        self.assertion(self.has_RT_files, 'No ray tracing files are found to combine PWs.', 'Error')
        # TODO: implement this for consistency, although it should be okay most of the time
        #self.assertion(self.enough_memory_for_rays, 'There is not enough memory available to put the rays in memory', 'Deterrent')

        project = 'Interface'
        try:
            self.rays_in_memory = Rays.from_pickle(project=project, projects_dir=self.WI_path, sample=None)
        except FileNotFoundError:
            if 'Phase test' in str(self.WI_name):
                self.rays_in_memory = Rays.from_x3d_results_phase_test(project=project, projects_dir=self.WI_path, sample=None)
            else:
                self.rays_in_memory = Rays.from_x3d_results(project=project, projects_dir=self.WI_path, sample=None)
            self.rays_in_memory.pickle_self()

    @property
    def combined_pw_result_path(self):
        return self.current_run_path / f'combined_pw_result_rx_{self.rx}.h5'

    @property
    def has_combined_pw_result(self):
        if self.combined_pw_result_path.exists():
            return True
        return False

    @Project.heavy_job(job_name='Combine the plane waves')
    def combine_pws(self):
        ''' Combines the plane waves from the library with the correct weights according to the precoding. 
        After this is done the resulting h5 file loaded up in S4L (which can be viewed in the analysis section),
        but also under the run directory. '''

        #TODO: get rid of this chain of functions on wi_to_s4l and interact only with rays in these classes (i.e. copy paste)
        #note that you could make result below an attribute of self, but that would increase memory footprint.
        self.combine_pws_result = combine_ico(
            self.rays_in_memory, 
            self.nbr_tesselation_points, 
            self.parent.pw_library_path, 
            lib_in_memory=self.parent.get_lib_in_memory(),
            sim_name=self.parent.simulation_name, 
            scheme=self.precoding, 
            rx_id=self.rx, 
            pat_dir=self.parent.ez_pattern_path, 
            loc=self.parent.UE_point[self.parent.axis_idx])

    def combine_pws_no_run(self, rx):
        return combine_ico(
            self.rays_in_memory, 
            self.nbr_tesselation_points, 
            self.parent.pw_library_path, 
            lib_in_memory={},
            sim_name=self.parent.simulation_name, 
            scheme=self.precoding, 
            rx_id=rx,
            pat_dir=self.parent.ez_pattern_path, 
            loc=self.parent.UE_point[self.parent.axis_idx],
            dont_actually_run=True)

    @Project.heavy_job(job_name='Replace results in S4L')
    def replace_results(self):
        sim = self.parent.S4L_simulation
        if not sim.HasResults():
            self.my_print('Dummy running the simulation to get a result file, only so this can later be replaced with other results')
            sim.RunSimulation(wait=True, server_id=self.parent.submit_server_id)

        if self.parent.use_surface_fields:
            with open(self.sf_pts_path, 'rb') as f:
                self.surface_points = pickle.load(f)
            
        h5_path = Path(sim.OutputFilename)
        with h5py.File(h5_path, mode='r+') as h5_file:
            gr1 = list(h5_file['FieldGroups'].keys())[1] #change if you are adding more sensors
            for field in ['EM E(x,y,z,f0)', 'EM H(x,y,z,f0)']:
                for component in ['comp0', 'comp1', 'comp2']:
                    val = h5_file['FieldGroups/%s/AllFields/%s/_Object/Snapshots/0/%s' % (gr1, field, component)]
                    if self.parent.use_surface_fields:
                        new_val = np.zeros(val.shape, dtype=val.dtype)
                        for surface_point, field_value in zip(self.surface_points, self.combine_pws_result[field][component]):
                            new_val[surface_point[0],surface_point[1],surface_point[2]] = field_value
                        val[:] = new_val
                    else:
                        new_val = self.combine_pws_result[field][component]
                    try:
                        val[:] = new_val
                    except:
                        Exception(f'Problem probably related to corrupted file or two processes writing to same file {h5_path}.')
        if self.keep_combined_pw_result:
            shutil.copy(self.parent.S4L_simulation.OutputFilename, self.combined_pw_result_path)

    @Project.heavy_job(job_name='Export the maximum Sab')
    def export_max_Sab(self):
        ''' Adds S4L algorithms that output only results about the maximum SAPD.
        If an overall field extractor already exists it will continue on that one. '''

        import s4l_v1.units as units

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()
        #else:
            #self.assertion(False, 'There is already an overall field sensor, so re-using it. This may cause problems if the results changed in between!')

        inputs = []
        model_to_grid_filter = self.parent.S4L_analysis_module.core.ModelToGridFilter(inputs=inputs)
        model_to_grid_filter.Name = "Whole_skin_mida_coarse_medium"
        #model_to_grid_filter.Entity = self.parent.S4L_model_module.AllEntities()["Whole_skin_mida_coarse_medium"]
        model_to_grid_filter.Entity = self.parent.S4L_model_module.AllEntities()["Whole_skin"]
        model_to_grid_filter.UpdateAttributes()
        self.parent.S4L_document_module.AllAlgorithms.Add(model_to_grid_filter)

        # Adding a new GenericSAPDEvaluator
        inputs = [self.em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]
        generic_sapd_evaluator = self.parent.S4L_analysis_module.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
        generic_sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
        generic_sapd_evaluator.Threshold = 0.01, units.Meters # 10 mm
        generic_sapd_evaluator.UpdateAttributes()
        self.parent.S4L_document_module.AllAlgorithms.Add(generic_sapd_evaluator)

        # Evaluator to json to dictionary
        sapd_report_output = generic_sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
        sapd_report_output.Update()
        data = sapd_report_output.Data
        data_json = data.DataSimpleDataCollection

        if not self.has_max_exposure_result():
            self.max_Sab_results = {}
        self.max_Sab_results[str(self.rx)] = {}
        for key in ['PeakPower', 'PeakSAPDPosition']:
            snapshot_index = 0
            try:
                value = data_json.FieldValue(key, snapshot_index)
                description = data_json.FieldDescription(key) #description for 'PeakPower' is 'Peak Spatial-Avg. Power Density', not 'Peak Power'
            except:
                value = -10000
                description = 'PeakPower'
                self.assertion(False, "Failed to find max Sab", "Warning")
            self.max_Sab_results[str(self.rx)][description] = value
        self.cache_exposure_result()

    @Project.heavy_job(job_name='Export the psSAR10g')
    def export_psSAR10g(self):
        ''' Adds S4L algorithms that output only results about the maximum psSAR10g.
        If an overall field extractor already exists it will continue on that one. '''

        import s4l_v1.units as units
        from s4l_v1 import Unit

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()

        # Adding a new AverageSarFieldEvaluator
        inputs = [self.em_sensor_extractor.Outputs["SAR(x,y,z,f0)"]]
        average_sar_field_evaluator = self.parent.S4L_analysis_module.em_evaluators.AverageSarFieldEvaluator(inputs=inputs)
        average_sar_field_evaluator.TargetMass = 10.0, Unit("g")
        average_sar_field_evaluator.UpdateAttributes()
        self.parent.S4L_document_module.AllAlgorithms.Add(average_sar_field_evaluator)

        # Evaluator to json to dictionary
        psSAR_output = average_sar_field_evaluator.Outputs["Peak Spatial SAR (psSAR) Results"]
        psSAR_output.Update()
        data = psSAR_output.Data
        data_json = data.DataSimpleDataCollection

        if not self.has_max_exposure_result():
            self.psSAR10g_results = {}
        self.psSAR10g_results[str(self.rx)] = {}
        for key in ['PeakValue', 'PeakLocation', 'PeakCubeSideLength']:
            snapshot_index = 0
            try:
                value = data_json.FieldValue(key, snapshot_index)
                description = data_json.FieldDescription(key) #description for PeakValue is 'psSAR', not 'Peak Value'
            except:
                value = -10000
                description = 'psSAR'
                self.assertion(False, "Failed to find psSAR10g", "Warning")
            self.psSAR10g_results[str(self.rx)][description] = value
        self.cache_exposure_result()

    @Project.heavy_job(job_name='Export the maximum Sinc')
    def export_max_Sinc(self):
        ''' Adds S4L algorithms that output only results about the maximum Sinc.
        If an overall field extractor already exists it will continue on that one. '''

        import s4l_v1.units as units

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()

        # Adding a new StatisticsEvaluator
        inputs = [self.em_sensor_extractor.Outputs["S(x,y,z,f0)"]]
        statistics_evaluator = self.parent.S4L_analysis_module.core.StatisticsEvaluator(inputs=inputs)
        ## NOTE: this neatly gives the time-averaged pontying vector! See also 'On the definition of Sinc.txt'
        statistics_evaluator.Mode = u"Real" 
        statistics_evaluator.Component = u"Vector"
        statistics_evaluator.UpdateAttributes()
        self.parent.S4L_document_module.AllAlgorithms.Add(statistics_evaluator)

        # Evaluator to json to dictionary
        Sinc_output = statistics_evaluator.Outputs['S Statistics']
        Sinc_output.Update()
        data = Sinc_output.Data
        data_json = data.DataSimpleDataCollection

        if not self.has_max_exposure_result():
            self.max_Sinc_results = {}
        self.max_Sinc_results[str(self.rx)] = {}
        for key in ['Max', 'MaxCenter']:
            snapshot_index = 0
            try:
                value = data_json.FieldValue(key, snapshot_index)
                description = data_json.FieldDescription(key)
            except:
                value = -10000
                description = 'Peak Value'
                self.assertion(False, "Failed to find max Sinc", "Warning")
            self.max_Sinc_results[str(self.rx)][description] = value
        self.cache_exposure_result()
        
    def add_overall_field_extractor(self):
        ''' Adds an overall field extractor to the analysis pipeline. Other functions 
        require has_overall_field_extractor to be True to proceed. '''
        
        import s4l_v1.units as units

        self.assertion(self.parent.S4L_simulation.HasResults(), 'Simulation does not have results. Consider dummy running the simulation first.', 'Error')
        simulation_extractor = self.parent.S4L_simulation.Results()

        self.em_sensor_extractor = simulation_extractor["Overall Field"]
        self.em_sensor_extractor.FrequencySettings.ExtractedFrequency = u"All"
        self.em_sensor_extractor.SurfaceCurrent.SurfaceResolution = 0.001, units.Meters
        self.parent.S4L_document.AllAlgorithms.Add(self.em_sensor_extractor)
        self.has_overall_field_extractor = True

    def export_full_avgSAR10g(self):
        ''' Adds an exporter to the analysis pipeline that outputs the full averaged SAR10g to a .mat MATLAB file. '''
        #TODO: only save the maximum and location out, maybe as a separate function

        from s4l_v1 import Unit

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()
        
        # Adding a new AverageSarFieldEvaluator
        inputs = [self.em_sensor_extractor.Outputs["SAR(x,y,z,f0)"]]
        self.average_sar_field_evaluator = self.parent.S4L_analysis_module.em_evaluators.AverageSarFieldEvaluator(inputs=inputs)
        self.average_sar_field_evaluator.TargetMass = 10.0, Unit("g")
        self.average_sar_field_evaluator.UpdateAttributes()
        self.parent.S4L_document.AllAlgorithms.Add(self.average_sar_field_evaluator)

        # Adding a new MatlabExporter
        inputs = [self.average_sar_field_evaluator.Outputs["IEEE/IEC62704-1 Avg.SAR(x,y,z,f0)"]]
        matlab_exporter = self.parent.S4L_analysis_module.exporters.MatlabExporter(inputs=inputs)
        matlab_exporter.UpdateAttributes()
        path = Path(self.parent.S4L_document.FilePath).parent / 'ExportedData_SAR10g.mat'
        try:
            os.remove(path)
            self.assertion(False, f'Deleted a result at {path} to replace it!', 'Warning')
        except:
            pass
        matlab_exporter.ExportTo(path)
        self.parent.S4L_document.AllAlgorithms.Add(matlab_exporter)

    def export_full_power_density(self):
        ''' Adds an exporter to the analysis pipeline that outputs the full power density to a .mat MATLAB file. '''
        #TODO: only save the maximum and location out, maybe as a separate function

        # Necessary to proceed
        if not self.has_overall_field_extractor:
            self.add_overall_field_extractor()

        # Adding a new MatlabExporter
        inputs = [self.em_sensor_extractor.Outputs["S(x,y,z,f0)"]]
        matlab_exporter = self.parent.S4L_analysis_module.exporters.MatlabExporter(inputs=inputs)
        matlab_exporter.UpdateAttributes()
        path= Path(self.parent.S4L_document.FilePath).parent / 'ExportedData_S.mat'
        try:
            os.remove(path)
            self.assertion(False, f'Deleted a result at {path} to replace it!', 'Warning')
        except:
            pass
        matlab_exporter.ExportTo(path)
        self.parent.S4L_document.AllAlgorithms.Add(matlab_exporter)

class Stochastic(S4L_Project):
    ''' A type of S4L_Project that analyses one S4L file with the incoming rays of multiple WI files for one sphere tesselation. '''

    def __init__(self, rx_list, channel_list, S4L_name, frequency_band, channel_case, precoding='MRT', nbr_tesselation_points=12, verbose=False):
        super().__init__(S4L_name, frequency_band, nbr_tesselation_points, verbose=verbose)
        self.parent = super()
        self.clear_my_prints()

        self.rx_list = rx_list
        self.channel_list = channel_list
        self.channel_case = channel_case
        self.precoding = precoding
        self.name = f'Stochastic {self.channel_case} {self.frequency_band}-band {self.phantom} {self.precoding}'

        self.ignore_exposure_cache = False
        self.det_projects = []
        self.process_number = 'main'

        self.BS_power = 320
        self.power_units = 'mW'

    def make_deterministic_projects(self):
        self.det_projects = []
        for channel in self.channel_list:
            self.channel = channel
            WI_name=f'{self.channel_case} {self.channel} {self.frequency_band}-band'
        
            det_project = Deterministic.from_stochastic_S4L_project(self, WI_name)
            #det_project.set_to_run_with_S4L(True)
            self.det_projects.append(det_project)
            #det_project.set_dedicated_WI_path(Path('D:/users/rwydaegh/Simulation files/WI'))

    def set_dedicated_WI_path(self, path):
        self.assertion(self.det_projects, 'No Deterministic projects made yet. Setting a dedicated WI path before their creation is not implemented.', 'Error')

        for det_project in self.det_projects:
            det_project.set_dedicated_WI_path(path)

    def run(self, notes='', flush=True, print_channels=False):
        ''' Full stochastic run, looping over all channels. '''
        if not self.get_run_with_S4L:
            self.assertion(False, 'Setting stochastic project to run with S4L.', 'Warning')
            self.set_to_run_with_S4L(True)

        if not self.assertion(self.det_projects, 'Make the Deterministic projects first before running the stochastic project.', 'Warning'):
            return
        
        t_start=time.time()
        self.current_run['name'] = self.name 
        if notes != '' and notes[:2] != ', ':
            self.current_run['name'] += ', ' + notes
        self.current_run['start time'] = t_start
        self.current_run['timestamp'] = time.ctime(t_start)
        self.current_run['params'] = self.get_string_parameters()

        if notes != '' and notes[:2] != ', ':
            notes = ', ' + notes
        self.exposure_results = {}

        if self.process_number is not None:
            with open(self.wrk_dir / 'Runs' / 'Process prints' / 'processes metadata.txt', 'a') as f:
                f.write(f'PROCESS_NUM_TO_PID {self.process_number} {os.getpid()}\n')
                
        i=0
        for det_project, channel in zip(self.det_projects, self.channel_list):
            self.channel = channel
            if print_channels:
                self.my_print(f'{self.name}: {self.channel} in range {self.channel_list[0]} to {self.channel_list[-1]}')
            #det_project.all_rx_run(notes=f'Channel {self.channel}')

            '''
            if self.process_number is not None:
                with open(self.wrk_dir / 'Runs' / 'Process prints' / 'processes metadata.txt', 'r+') as f:
                    for line in f.readlines():
                        if 'NUM' not in line:
                            _, num, pid = line.split(' ')
                            num=int(num)
                            if num==self.process_number:
                                f.write(f'PROCESS_NUM_TO_PID {self.process_number} {os.getpid()}\n')
            '''
            
            det_project.all_rx_run(notes=f'Scenario {self.channel}')
            self.exposure_results[f'channel_{channel}'] = det_project.full_exposure_result
            self.write_current_run_log()
            if flush:
                self.my_print('------ FLUSHING -----')
                t0=time.perf_counter()     
                self.det_projects = None
                gc.collect()
                self.S4L_analysis_module.ResetAnalysis()
                self.S4L_document_module.Open(self.S4L_document_module.FilePath)
                self.my_print(f'flush took {time.perf_counter()-t0} seconds')   
                parent = self.parent
                doc = self.S4L_document_module
                d = self.S4L_document
                s= self.S4L_simulation
                mod = self.S4L_model_module
                sim = self.S4L_simulation_module
                ana = self.S4L_analysis_module
                id = self.submit_server_id
                del self.parent, self.S4L_document_module, self.S4L_document, self.submit_server_id, self.S4L_simulation, self.S4L_model_module, self.S4L_simulation_module, self.S4L_analysis_module   
                with open(self.S4L_path / f'data_{self.process_number}.pickle', 'wb') as f:
                        pickle.dump(self, f)
                '''
                for k, v in self.get_parameters()[::-1]:
                    print('---')
                    print(k)
                    with open(self.S4L_path / f'{k}_{self.process_number}.pickle', 'wb') as f:
                        pickle.dump(v, f)
                '''
                self.parent = parent
                self.S4L_document_module = doc
                self.S4L_document = d
                self.submit_server_id = id
                self.S4L_simulation = s
                self.S4L_model_module = mod
                self.S4L_simulation_module = sim
                self.S4L_analysis_module = ana
                i+=1
        self.save_exposure_results(notes=notes)

        self.write_current_run_log()

    def write_current_run_log(self):
        path = self.current_run_path / f"Channel #{self.channel}, run #{self.nbr_of_runs+1} log.txt"
        with open(str(path), 'w', encoding="utf-8") as f:
            f.writelines(self.get_current_run_log())
        return path 

    @property
    def print_file_path(self):
        if isinstance(self.parent, Headless_Study):
            if isinstance(self.process_number, int):
                path = self.wrk_dir / 'Runs' / 'Process prints' / f'process_{self.process_number}.txt'
                if not os.path.exists(path):
                    with open(path, 'w') as f:
                        pass
            elif isinstance(self.process_number, str):
                if self.process_number=='main':
                    path = self.wrk_dir / 'Runs' / f'process_{self.process_number}.txt'
            return path
        else:
            return super().print_file_path

    @property
    def current_run_path(self):
        if isinstance(self.parent, Headless_Study):
            path = self.parent.current_run_path / self.current_run['name']
            if not path.exists():
                os.mkdir(path)
            return path
        else:
            return super().current_run_path

    def convert_shared_lib(self, lib_of_references):
        lib_of_data = {}
        for path in os.listdir(self.pw_library_path):
            path = Path(self.pw_library_path / path)
            file_name = path.name
            lib_of_data[file_name] = {}
            if '.h5' in file_name:
                for field in ['EM E(x,y,z,f0)', 'EM H(x,y,z,f0)']:
                    lib_of_data[file_name][field] = {}
                    for component in ['comp0', 'comp1', 'comp2']:
                        struct = lib_of_references[file_name][field][component]
                        lib_of_data[file_name][field][component] = np.frombuffer(struct[0]).reshape((struct[1].value,
                                                                                                     struct[2].value,
                                                                                                     struct[3].value,
                                                                                                     struct[4].value))
        return lib_of_data  
        
    def get_lib_in_memory(self):
        if isinstance(self.parent, Headless_Study):
            if self.parent.shared_memory:
                return self.convert_shared_lib(self.parent.get_lib_in_memory(self))
            else:
                return self.parent.get_lib_in_memory(self)
        else:
            return super().get_lib_in_memory()

    def set_lib_in_memory(self):
        if isinstance(self.parent, Headless_Study):
            self.parent.set_lib_in_memory(self)
        else:
            super().set_lib_in_memory()
        
    @property
    def power_units_conversion_factor(self):
        if self.power_units == 'mW':
            return 1000
        elif self.power_units =='$\mu$W':
            return 1000000
        
    def get_shown_result(self, notes='', normalized_to_power=False):
        shown_result = self.get_only_max_results(notes=notes, normalized_to_power=normalized_to_power)
        if shown_result is None:
            return
        if normalized_to_power:
            self.power_units = '$\mu$W'
        shown_result = shown_result / self.BS_power * self.power_units_conversion_factor #normalize to base station power of 1 W, and put in correct units (typically mW)

        return shown_result
        
    def plot(self, notes='', exclude_first=False, scatter_plot=False, with_legend=True):
        ''' Plots the exposure type as a function of distance, from the rx id, in mW and normalized to the 320 W base station. '''

        import matplotlib
        import matplotlib.pyplot as plt
        matplotlib.use('Qt5Agg')

        self.shown_result = self.get_only_max_results(notes=notes)
        if self.shown_result is None:
            return

        self.rx_x = 6 + (np.array(self.rx_list)-1)*0.5
        plt.figure(self.name)
        plt.title(self.name + ', \n normalized to 1 W transmitted power')
        if exclude_first:
            self.rx_x = self.rx_x[:-1]
            self.shown_result = self.shown_result[1:]
        for channel in range(len(self.channel_list)):
            if scatter_plot:
                plt.scatter(self.rx_x, np.array(self.shown_result)[:,channel] / 320 * 1000, label=f'channel {channel}')
            else:
                plt.plot(self.rx_x, np.array(self.shown_result)[:,channel] / 320 * 1000, label=f'channel {channel}')
        if with_legend:
            plt.legend()
        plt.xlabel('Rx distance [m]')
        exp_type = self.exposure_result_type
        if exp_type == 'max_Sab':
            plt.ylabel('Maximum SAPD [mW/m2]')
        elif exp_type == 'psSAR10g':
            plt.ylabel('Maximum psSAR10g [mW/kg]')
        elif exp_type == 'max_Sinc':
            plt.ylabel('Maximum Sinc [mW/m2]')
        plt.ylim(ymin=0)

    def plot_histograms(self, notes='', combine_all_rx=False, subplot_pos = None, stats_type='cdf', normalized_to_power=False, cache_name='', zero_based=False):
        import matplotlib
        import matplotlib.pyplot as plt
        matplotlib.use('Qt5Agg')

        if cache_name!='':
            if 'read' in cache_name:
                cache_name = cache_name[5:]
                self.shown_result = self.read_shown_results_cache(name=cache_name)
            elif 'write' in cache_name:
                self.shown_result = self.get_shown_result(notes=notes, normalized_to_power=normalized_to_power)
                cache_name = cache_name[6:]
                self.cache_shown_results(name=cache_name)
            else:
                self.assertion(False, 'Read or write not specified in cache name. Will write.', 'Deterrent')
                self.shown_result = self.get_shown_result(notes=notes, normalized_to_power=normalized_to_power)
                self.cache_shown_results(name=cache_name)
        else:
            #self.assertion(False, 'No cache name specified', 'Warning')
            self.shown_result = self.get_shown_result(notes=notes, normalized_to_power=normalized_to_power)

        #plt.figure(self.name)
        if subplot_pos is not None:
            ax = plt.subplot(subplot_pos)
        plt.title(self.name + ', normalized 1 W')
        channels = []
        for channel_str in self.shown_result.keys():
            channel = int(channel_str.split('_')[1])
            channels.append(channel)
        if not combine_all_rx:
            for rx in self.rx_list:
                #plt.subplot(int('31'+str(rx+1)))
                data = list(np.array(self.shown_result)[rx, :])
                count, bins = np.histogram(data, bins=len(data))
                pdf = count / sum(count)
                cdf = np.cumsum(pdf)
                if zero_based:
                    rx_idx_shown = rx
                else:
                    self.assertion(False, 'Showing non-zero based Rx indices', 'Warning')
                    rx_idx_shown = rx + 1
                if stats_type=='cdf':
                    plt.ylabel('CDF')
                    plt.step(bins[1:], cdf, label=f'Rx {rx_idx_shown}')
                elif stats_type=='pdf':
                    plt.ylabel('PDF')
                    plt.step(bins[1:], pdf, label=f'Rx {rx_idx_shown}')
                elif stats_type=='raw':
                    plt.scatter(channels, data, s=5, marker='.', label=f'Rx {rx_idx_shown}')
        data = []
        for rx in self.rx_list:
            for i in list(np.array(self.shown_result)[rx, :]):
                data.append(i)
        count, bins = np.histogram(data, bins=len(data))
        pdf = count / sum(count)
        cdf = np.cumsum(pdf)
        if stats_type=='cdf':
            plt.ylabel('CDF')
            plt.step(bins[1:], cdf, label=f'All rx', color='black')
            plt.axvline(x=bins[np.searchsorted(cdf, 0.95)], label='95% mark (for all)', color='black')
        elif stats_type=='pdf':
            plt.ylabel('PDF')
            plt.step(bins[1:], pdf, label=f'All rx', color='black')
        elif stats_type=='raw':
            pass #TODO

        if stats_type!='raw':
            exp_type = self.exposure_result_type
            if exp_type == 'max_Sab':
                plt.xlabel(r'$\mathrm{max}\,S_\mathrm{ab}(\mathbf{r})$ (1 W) ['+self.power_units+'/m$^2$]') #Scalar real field
            elif exp_type == 'psSAR10g':
                plt.xlabel(r'psSAR$_\mathrm{10g}$ (1 W) ['+self.power_units+'/kg]')
            elif exp_type == 'max_Sinc':
                plt.xlabel(r'$\mathrm{max}\,|\mathrm{Re}(S_\mathrm{inc}(\mathbf{r}))|$ (1 W) ['+self.power_units+'/m$^2$]')
        else:
            plt.xlabel('Channel number')
        plt.legend()

        try:
            ax
            return ax
        except:
            pass

    def cache_shown_results(self, name=''):
        with open(self.current_run_path / f'{name}_cache.pickle', 'wb') as f:
            pickle.dump(self.shown_result, f)

    def read_shown_results_cache(self, name=''):
        with open(self.current_run_path / f'{name}_cache.pickle', 'rb') as f:
            shown_result = pickle.load(f)
        return shown_result

    def get_only_max_results(self, notes='', normalized_to_power=False):
        ''' Extracts only the maxima from the leaves of the cached exposure_result nested dictionary. '''

        if notes != '' and notes[:2] != ', ':
            notes = ', ' + notes
        run_name = self.name + notes
        self.current_run['name'] = run_name
        p = self.current_run_path / f'{run_name}.pickle' #CORRECT, please uncomment in future
        #p = self.current_run_path / f'{self.S4L_name} {self.channel_case}.pickle' #INCORRECT, provisional because bad files, please comment in future
        if self.assertion(p.exists(), 'No stochastic results to plot.', 'Warning'):
            results = self.read_exposure_result(notes=notes)
        else:
            return None

        if normalized_to_power:
            return results['normalized_results']
        
        only_max_results = {}
        for channel in self.channel_list:
            try:
                results[f'channel_{channel}']
                channel_key = f'channel_{channel}'
            except:
                self.assertion(False, f'Channel {channel} of {self.name} is missing', 'Warning')
                continue
            channel_result = results[channel_key]
            only_max_results[channel_key] = {}
            for rx in self.rx_list:
                try:
                    channel_result[f'rx_{rx}']
                    rx_key = f'rx_{rx}'
                except:
                    self.assertion(False, f'Rx {rx} of {self.name} in channel {channel} is missing', 'Warning')
                    continue
                rx_result = channel_result[rx_key]
                only_max_results[channel_key][rx_key] = {}
                exp_type = self.exposure_result_type
                if exp_type=='max_Sinc':
                    only_max_results[channel_key][rx_key] = rx_result['Max']
                elif exp_type=='psSAR10g':
                    only_max_results[channel_key][rx_key] = rx_result['psSAR']
                elif exp_type=='max_Sab':
                    only_max_results[channel_key][rx_key] = rx_result['Peak Spatial-Avg. Power Density']

        return pd.DataFrame(only_max_results)

    def get_only_pos_results(self, notes=''):
        ''' Extracts only the maxima from the leaves of the cached exposure_result nested dictionary. '''

        if notes != '' and notes[:2] != ', ':
            notes = ', ' + notes
        run_name = self.name + notes
        self.current_run['name'] = run_name
        p = self.current_run_path / f'{run_name}.pickle' #CORRECT, please uncomment in future
        #p = self.current_run_path / f'{self.S4L_name} {self.channel_case}.pickle' #INCORRECT, provisional because bad files, please comment in future
        if self.assertion(p.exists(), 'No stochastic results to plot.', 'Warning'):
            results = self.read_exposure_result(notes=notes)
        else:
            return None
        
        only_pos_results = {}
        for channel in self.channel_list:
            try:
                results[f'channel_{channel}']
                channel_key = f'channel_{channel}'
            except:
                self.assertion(False, f'Channel {channel} of {self.name} is missing', 'Warning')
                continue
            channel_result = results[channel_key]
            only_pos_results[channel_key] = {}
            for rx in self.rx_list:
                try:
                    channel_result[f'rx_{rx}']
                    rx_key = f'rx_{rx}'
                except:
                    self.assertion(False, f'Rx {rx} of {self.name} in channel {channel} is missing', 'Warning')
                    continue
                rx_result = channel_result[rx_key]
                only_pos_results[channel_key][rx_key] = {}
                exp_type = self.exposure_result_type
                if exp_type=='max_Sinc':
                    only_pos_results[channel_key][rx_key] = np.linalg.norm(np.array(rx_result['Max Center']))
                elif exp_type=='psSAR10g':
                    only_pos_results[channel_key][rx_key] = np.linalg.norm(np.array(rx_result['Peak Location']))
                elif exp_type=='max_Sab':
                    only_pos_results[channel_key][rx_key] = np.linalg.norm(np.array(rx_result['Peak Location']))

        return pd.DataFrame(only_pos_results)

    def save_exposure_results(self, notes=''):
        ''' Saves self.exposure_results. '''

        if notes != '' and notes[:2] != ', ':
            notes = ', ' + notes
        run_name = self.name + notes
        with open(self.current_run_path / f'{run_name}.pickle', 'wb') as f:
            pickle.dump(self.exposure_results, f)

    def read_exposure_result(self, notes=''):
        ''' Reads self.exposure_results from pickle. '''

        if notes != '' and notes[:2] != ', ':
            notes = ', ' + notes
        run_name = self.name + notes
        p = self.current_run_path / f'{run_name}.pickle' #CORRECT, please uncomment in future
        #p = self.current_run_path / f'{self.S4L_name} {self.channel_case}.pickle' #INCORRECT, provisional because bad files, please comment in future
        with open(p, 'rb') as f:
            return pickle.load(f)
