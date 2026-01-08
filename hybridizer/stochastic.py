import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from tqdm import tqdm

class SensitvityAnalysis:

    def __init__(self, initialize_simulation = None, run_simulation = None, post_process_simulation = None):
        self.initialize_simulation = initialize_simulation
        self.run_simulation = run_simulation
        self.post_process_simulation = post_process_simulation

        self.simulations = []
        self.results = []

class OneDimensionalAnalysis(SensitvityAnalysis):
    
    def __init__(self, parameter_space, initialize_simulation = None, run_simulation = None, post_process_simulation = None):
        super().__init__(initialize_simulation=initialize_simulation, run_simulation=run_simulation, post_process_simulation=post_process_simulation)
        
        self.parameter_space = parameter_space

        self.x_axis = 'Parameter'
        self.y_axis = 'Result'

        self.stochastic = False
        self.verbose = True

    def set_stochastic(self, nbr_of_repeats):
        self.stochastic = True
        self.nbr_of_repeats = nbr_of_repeats

    def run(self):
        assert self.initialize_simulation is not None
        assert self.run_simulation is not None
        assert self.post_process_simulation is not None
        
        for parameter in tqdm(self.parameter_space, disable=(not self.verbose)):
            if self.stochastic:
                set_of_results = []
                set_of_simulations = []

                for _ in range(self.nbr_of_repeats):
                    self.initialize_simulation(parameter)
                    #set_of_simulations.append(self.current_simulation)
                    self.run_simulation()
                    result = self.post_process_simulation()
                    
                    set_of_results.append(result)
                    
                #self.simulations.append(set_of_simulations)
                self.results.append(set_of_results)
            else:
                self.initialize_simulation(parameter)
                self.simulations.append(self.current_simulation)
                self.run_simulation()
                result = self.post_process_simulation()
            
                self.results.append(result)

        return self.results

    def field_plot_each(self):
        for simulation, parameter in zip(self.simulations, self.parameter_space):
            simulation.plot(stochastic_identifier = f'{parameter:.2e}')

    def plot_result_mean_and_range(self):
        raise NotImplementedError
        plt.figure('Results of 1D sensitivity analysis: boxplot plot')
        plt.boxplot(self.results, labels=[str(p) for p in self.parameter_space])
        plt.xlabel(self.x_axis)
        plt.ylabel(self.y_axis)
        plt.show()

    def plot_result_boxplot(self):
        plt.figure('Results of 1D sensitivity analysis: boxplot plot')
        plt.boxplot(self.results, labels=[str(p) for p in self.parameter_space])
        plt.ylim([0, np.nanmax(self.results)*1.1])
        plt.xlabel(self.x_axis)
        plt.ylabel(self.y_axis)
        plt.show()

    def plot_result_scatter(self):
        self.results = np.array(self.results)
        self.parameters = np.stack([self.parameter_space for _ in range(self.nbr_of_repeats)], axis=1)

        plt.figure('Results of 1D sensitivity analysis: scatter plot')
        plt.scatter(self.parameters, self.results)
        plt.ylim([0, np.nanmax(self.results)*1.1])
        plt.xlabel(self.x_axis)
        plt.ylabel(self.y_axis)
        plt.show()

    def plot_result(self):
        plt.figure('Results of 1D sensitivity analysis')
        plt.plot(self.parameter_space, self.results)
        plt.ylim([0, np.nanmax(self.results)*1.1])
        plt.xlabel(self.x_axis)
        plt.ylabel(self.y_axis)
        plt.show()

class TwoDimensionalAnalysis(SensitvityAnalysis):
    def __init__(self, parameter_1_space, parameter_2_space, initialize_simulation = None, run_simulation = None, post_process_simulation = None):
        super().__init__(initialize_simulation=initialize_simulation, run_simulation=run_simulation, post_process_simulation=post_process_simulation)

        self.parameter_1_space = parameter_1_space
        self.parameter_2_space = parameter_2_space

        self.x_1_axis = 'First parameter'
        self.x_2_axis = 'Second parameter'
        self.y_axis = 'Result'

    def run(self):
        raise NotImplementedError
        
        assert self.initialize_simulation is not None
        assert self.run_simulation is not None
        assert self.post_process_simulation is not None
        
        for parameter in self.parameter_space:
            self.initialize_simulation(parameter)
            self.simulations.append(self.current_simulation)
            self.run_simulation()
            result = self.post_process_simulation()
            
            self.results.append(result)

        return self.results

    def plot(self):
        raise NotImplementedError
        
        for simulation, parameter in zip(self.simulations, self.parameter_space):
            simulation.plot(stochastic_identifier = f'{parameter:.2e}')
