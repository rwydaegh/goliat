# -*- coding: utf-8 -*-

import numpy
import s4l_v1.document as document
import s4l_v1.materials.database as database
import s4l_v1.model as model
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.units as units
from s4l_v1 import Unit

# Creating the simulation
simulation = emfdtd.Simulation()
simulation.Name = "Loader simulation"

# Mapping the components and entities
component__plane_x = simulation.AllComponents["Plane X+"]
component__plane_x_1 = simulation.AllComponents["Plane X-"]
component__background = simulation.AllComponents["Background"]
component__plane_y = simulation.AllComponents["Plane Y+"]
component__plane_y_1 = simulation.AllComponents["Plane Y-"]
component__plane_z = simulation.AllComponents["Plane Z+"]
component__plane_z_1 = simulation.AllComponents["Plane Z-"]
component__overall_field = simulation.AllComponents["Overall Field"]
entity__point2 = model.AllEntities()["Point 2"]
entity__point6 = model.AllEntities()["Point 6"]
entity__point8 = model.AllEntities()["Point 8"]
entity__python_box = model.AllEntities()["Python_box"]
entity__point3 = model.AllEntities()["Point 3"]
entity__point1 = model.AllEntities()["Point 1"]
entity__point5 = model.AllEntities()["Point 5"]
entity__huygens_box = model.AllEntities()["Huygens_box"]
entity__point7 = model.AllEntities()["Point 7"]
entity__point4 = model.AllEntities()["Point 4"]

# Editing SetupSettings "Setup"
setup_settings = simulation.SetupSettings
setup_settings.SimulationTime = 1.0, units.Periods

# Parameters
freq = 28000000000.0
wavelength = 299792458.0 / freq
cpw = 15.0
maxstep_mm = wavelength / cpw * 1000

# Adding a new PlaneWaveSourceSettings
plane_wave_source_settings = emfdtd.PlaneWaveSourceSettings()
components = [entity__python_box]
plane_wave_source_settings.CenterFrequency = freq, units.Hz
simulation.Add(plane_wave_source_settings, components)

# Editing GlobalGridSettings "Grid (Empty)"
global_grid_settings = simulation.GlobalGridSettings
global_grid_settings.DiscretizationMode = global_grid_settings.DiscretizationMode.enum.Manual
global_grid_settings.MaxStep = numpy.array([maxstep_mm, maxstep_mm, maxstep_mm]), units.MilliMeters
global_grid_settings.Resolution = numpy.array([1.0, 1.0, 1.0]), units.MilliMeters
global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Manual
global_grid_settings.BottomPadding = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters
global_grid_settings.TopPadding = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters

# Removing AutomaticGridSettings Automatic
automatic_grid_settings = [x for x in simulation.AllSettings if isinstance(x, emfdtd.AutomaticGridSettings) and x.Name == "Automatic"][0]
simulation.RemoveSettings(automatic_grid_settings)

# Adding a new ManualGridSettings
manual_grid_settings = simulation.AddManualGridSettings([entity__huygens_box, entity__point1, entity__point2, entity__point3, entity__point4, entity__point5, entity__point6, entity__point7, entity__point8, entity__python_box])
manual_grid_settings.MaxStep = numpy.array([maxstep_mm, maxstep_mm, maxstep_mm]), units.MilliMeters
manual_grid_settings.Resolution = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters

# Editing AutomaticVoxelerSettings "Automatic Voxeler Settings"
automatic_voxeler_settings = [x for x in simulation.AllSettings if isinstance(x, emfdtd.AutomaticVoxelerSettings) and x.Name == "Automatic Voxeler Settings"][0]
components = [entity__huygens_box, entity__point1, entity__point2, entity__point3, entity__point4, entity__point5, entity__point6, entity__point7, entity__point8, entity__python_box]
simulation.Add(automatic_voxeler_settings, components)

# Editing SolverSettings "Solver"
solver_settings = simulation.SolverSettings
solver_settings.Kernel = solver_settings.Kernel.enum.Cuda

# Update the materials with the new frequency parameters
simulation.UpdateAllMaterials()

# Update the grid with the new parameters
simulation.UpdateGrid()

# Add the simulation to the UI
document.AllSimulations.Add( simulation )


####


# Creating the simulation
simulation = emfdtd.Simulation()

# Mapping the components and entities
component__plane_x = simulation.AllComponents["Plane X+"]
component__plane_x_1 = simulation.AllComponents["Plane X-"]
component__background = simulation.AllComponents["Background"]
component__plane_y = simulation.AllComponents["Plane Y+"]
component__plane_y_1 = simulation.AllComponents["Plane Y-"]
component__plane_z = simulation.AllComponents["Plane Z+"]
component__plane_z_1 = simulation.AllComponents["Plane Z-"]
component__overall_field = simulation.AllComponents["Overall Field"]
entity__point2 = model.AllEntities()["Point 2"]
entity__point6 = model.AllEntities()["Point 6"]
entity__point8 = model.AllEntities()["Point 8"]
entity_mida_mm_wave_smoothed = model.AllEntities()["MIDA_mmWave_smoothed"]
entity__point3 = model.AllEntities()["Point 3"]
entity__point1 = model.AllEntities()["Point 1"]
entity__point5 = model.AllEntities()["Point 5"]
entity__huygens_box = model.AllEntities()["Huygens_box"]
entity__point7 = model.AllEntities()["Point 7"]
entity__point4 = model.AllEntities()["Point 4"]

# Simulation links
link__overall_field = document.AllSimulations["Loader simulation"].AllComponents["Overall Field"]

# Editing SetupSettings "Setup"
setup_settings = simulation.SetupSettings
setup_settings.SimulationTime = 1000.0, units.Periods

# Adding a new MaterialSettings
material_settings = emfdtd.MaterialSettings()
components = [entity_mida_mm_wave_smoothed]
material_settings.Name = "mmWaveHand"
print('Please add the mmWaveHand material to the simulation.')
#material_settings.ElectricProps.MaterialModel = None
simulation.Add(material_settings, components)

# Adding a new HuygensSourceSettings
huygens_source_settings = simulation.AddHuygensSourceSettings([entity__huygens_box, link__overall_field])
huygens_source_settings.CenterFrequency = 28000000000.0, units.Hz

# Adding a new PointSensorSettings
point_sensor_settings = emfdtd.PointSensorSettings()
components = [entity__point1, entity__point2, entity__point3, entity__point4, entity__point5, entity__point6, entity__point7, entity__point8]
simulation.Add(point_sensor_settings, components)

# Editing GlobalGridSettings "Grid (Empty)"
global_grid_settings = simulation.GlobalGridSettings
global_grid_settings.DiscretizationMode = global_grid_settings.DiscretizationMode.enum.Manual
global_grid_settings.MaxStep = numpy.array([maxstep_mm, maxstep_mm, maxstep_mm]), units.MilliMeters
global_grid_settings.Resolution = numpy.array([1e-06, 1e-06, 1e-06]), units.MilliMeters
global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Manual
global_grid_settings.BottomPadding = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters
global_grid_settings.TopPadding = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters

# Removing AutomaticGridSettings Automatic
automatic_grid_settings = [x for x in simulation.AllSettings if isinstance(x, emfdtd.AutomaticGridSettings) and x.Name == "Automatic"][0]
simulation.RemoveSettings(automatic_grid_settings)

# Adding a new ManualGridSettings
manual_grid_settings = simulation.AddManualGridSettings([entity__huygens_box, entity__point1, entity__point2, entity__point3, entity__point4, entity__point5, entity__point6, entity__point7, entity__point8])
manual_grid_settings.MaxStep = numpy.array([maxstep_mm, maxstep_mm, maxstep_mm]), units.MilliMeters
manual_grid_settings.Resolution = numpy.array([0.0, 0.0, 0.0]), units.MilliMeters

# Editing AutomaticVoxelerSettings "Automatic Voxeler Settings"
automatic_voxeler_settings = [x for x in simulation.AllSettings if isinstance(x, emfdtd.AutomaticVoxelerSettings) and x.Name == "Automatic Voxeler Settings"][0]
components = [entity__huygens_box, entity__point1, entity__point2, entity__point3, entity__point4, entity__point5, entity__point6, entity__point7, entity__point8, entity_mida_mm_wave_smoothed]
simulation.Add(automatic_voxeler_settings, components)

# Editing SolverSettings "Solver"
solver_settings = simulation.SolverSettings
solver_settings.Kernel = solver_settings.Kernel.enum.Cuda

# Update the materials with the new frequency parameters
simulation.UpdateAllMaterials()

# Update the grid with the new parameters
simulation.UpdateGrid()

# Add the simulation to the UI
document.AllSimulations.Add( simulation )
