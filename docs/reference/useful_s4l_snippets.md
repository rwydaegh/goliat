# Useful Sim4Life API snippets

Practical code examples for common Sim4Life Python API tasks, extracted from real-world usage. Organized by functionality.

## Dictionary-like access patterns

Many Sim4Life API objects behave like dictionaries and can be accessed directly by name or key, not just iterated. For example:

```python
# Direct access by name
entity = s4l_v1.model.AllEntities()["Entity Name"]
simulation = s4l_v1.document.AllSimulations["Simulation Name"]
output = algorithm.Outputs["Output Name"]
extractor = simulation_extractor["Overall Field"]

# Instead of always iterating
for entity in s4l_v1.model.AllEntities():
    if entity.Name == "Entity Name":
        # found it
        break
```

Common dictionary-like collections: `AllEntities()`, `AllSimulations`, `AllSettings`, `AllAlgorithms`, `Outputs`, and result extractors. Use direct access when you know the name/key.

## Table of Contents

1. [Application control](#1-application-control)
2. [Project management](#2-project-management)
3. [Model and geometry](#3-model-and-geometry)
4. [Materials](#4-materials)
5. [Simulation setup](#5-simulation-setup)
6. [Simulation execution](#6-simulation-execution)
7. [Results extraction](#7-results-extraction)
8. [Data and downloads](#8-data-and-downloads)
9. [Analysis algorithms](#9-analysis-algorithms)
10. [Rendering and UI](#10-rendering-and-ui)

---

## 1. Application control

### How can I start the Sim4Life application programmatically?

```python
from s4l_v1._api import application

if application.get_app_safe() is None:
    application.run_application(disable_ui_plugins=True)
```

Use `disable_ui_plugins=True` for headless execution. Check if the app is already running before starting it.

Used in: `goliat/utils/core.py` (ensure_s4l_running)

### How can I suppress Sim4Life logging output?

```python
import XCore

old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Error)
# ... perform operations ...
XCore.SetLogLevel(old_log_level)
```

Save the old log level to restore it later. Use `XCore.eLogCategory.Error` to suppress most output.

Used in: `goliat/setups/base_setup.py` (_finalize_setup)

---

## 2. Project management

### How can I create a new Sim4Life project?

```python
import s4l_v1.document

s4l_v1.document.New()
```

Creates an unsaved project in memory. Automatically closes any existing document before creating a new one.

Used in: `goliat/project_manager.py`, `goliat/utils/core.py`

### How can I open an existing Sim4Life project file?

```python
import s4l_v1.document

project_path = "path/to/project.smash"
s4l_v1.document.Open(project_path)
```

Raises an exception if the file doesn't exist or is corrupted.

Used in: `goliat/project_manager.py`, `goliat/utils/core.py`, `goliat/simulation_runner.py`

### How can I save a Sim4Life project?

```python
import s4l_v1.document

project_path = "path/to/project.smash"
s4l_v1.document.SaveAs(project_path)
```

Use `SaveAs` even for existing projects (it overwrites). You may want to add retry logic if save operations occasionally fail.

Used in: `goliat/project_manager.py`, `goliat/simulation_runner.py`

### How can I close a Sim4Life project?

```python
import s4l_v1.document

if s4l_v1.document.IsOpen():
    s4l_v1.document.Close()
```

Check `IsOpen()` before closing to avoid errors. Closing releases file locks on .smash files.

Used in: `goliat/project_manager.py`, `goliat/simulation_runner.py`

### How can I get the current project file path?

```python
import s4l_v1.document

project_path = s4l_v1.document.FilePath
```

Returns empty string if the project hasn't been saved yet.

Used in: `goliat/project_manager.py`

### How can I access all simulations in a project?

```python
import s4l_v1.document

all_simulations = s4l_v1.document.AllSimulations

# Find simulation by name
simulation = next(
    (s for s in all_simulations if s.Name == "simulation_name"),
    None
)

# Remove all simulations
for sim in list(all_simulations):
    all_simulations.Remove(sim)
```

Use `list()` when iterating and modifying to avoid iterator issues.

Used in: `goliat/project_manager.py`

---

## 3. Model and geometry

### How can I get all entities in the model?

```python
import s4l_v1.model
import XCoreModeling

all_entities = s4l_v1.model.AllEntities()

# Filter entities by type
phantom_parts = [e for e in all_entities if isinstance(e, XCoreModeling.TriangleMesh)]

# Find entity by name
entity = next(
    (e for e in all_entities if hasattr(e, "Name") and e.Name == "entity_name"),
    None
)
```

Returns an iterable collection of entity objects. Filter by type or name as needed.

Used in: `goliat/setups/base_setup.py`, `goliat/setups/near_field_setup.py`, `goliat/setups/material_setup.py`

### How can I get the bounding box of entities?

```python
import s4l_v1.model

entities = [entity1, entity2]
bbox_min, bbox_max = s4l_v1.model.GetBoundingBox(entities)

# With transform
from XCoreMath import Transform
transform = Transform(...)
bbox_min, bbox_max = s4l_v1.model.GetBoundingBox(entities, transform=transform)

# Control tightness (exact=True is slower but tighter, exact=False is faster but looser)
bbox_min, bbox_max = s4l_v1.model.GetBoundingBox(entities, exact=True)
```

Returns two Vec3 objects: minimum and maximum corners. Can pass a single entity or a list. The `exact` parameter controls tightness: `exact=True` computes a tighter box but takes longer, `exact=False` is faster but may be looser.

Used in: `goliat/setups/base_setup.py`, `goliat/setups/near_field_setup.py`, `goliat/setups/gridding_setup.py`

### How can I create geometric entities?

```python
import s4l_v1.model
import XCoreModeling

# Create a point
point_pos = s4l_v1.model.Vec3(10.0, 20.0, 30.0)
point_entity = s4l_v1.model.CreatePoint(point_pos)
point_entity.Name = "Point Sensor 1"

# Create a solid block
min_corner = s4l_v1.model.Vec3(0, 0, 0)
max_corner = s4l_v1.model.Vec3(100, 100, 100)
solid_block = s4l_v1.model.CreateSolidBlock(min_corner, max_corner)

# Create a wire block (bounding box)
wire_block = XCoreModeling.CreateWireBlock(min_corner, max_corner)
wire_block.Name = "simulation_bbox"
```

Points are used for point sensors. Wire blocks are typically used for simulation bounding boxes.

Used in: `goliat/setups/base_setup.py` (CreatePoint)

### How can I import models from files?

```python
import s4l_v1.model
import XCoreModeling

sab_path = "path/to/model.sab"
imported_entities = list(s4l_v1.model.Import(sab_path))

# Or using XCoreModeling
imported_entities = list(XCoreModeling.Import(sab_path))

# Find specific imported entity
entity = next(
    (e for e in imported_entities if "Antenna" in e.Name),
    None
)
```

Returns an iterable of imported entities. Convert to list if you need to iterate multiple times.

Used in: `goliat/setups/phantom_setup.py`, `goliat/scripts/prepare_antennas.py`

### How can I export entities to files?

```python
import s4l_v1.model

entities_to_export = [entity1, entity2]
export_path = "path/to/export.sab"
s4l_v1.model.Export(entities_to_export, export_path)
```

Can export single entity or list of entities. Common format: .sab.

Used in: `goliat/scripts/prepare_antennas.py`

### How can I transform entities (translate, rotate, scale)?

```python
from XCoreMath import Transform, Rotation, Translation, Vec3
import numpy as np

# Create a rotation around Z-axis
rotation = Rotation(Vec3(0, 0, 1), np.deg2rad(90))

# Create a translation
translation = Translation(Vec3(10, 20, 30))

# Compose transforms (order matters)
final_transform = Transform()
final_transform = rotation * final_transform
final_transform = translation * final_transform

# Apply transform to entity
entity.ApplyTransform(final_transform)
```

Transform multiplication order matters (right-to-left application). Use `np.deg2rad()` to convert degrees to radians.

Used in: `goliat/setups/placement_setup.py`

### How can I calculate distance between entities?

```python
import XCoreModeling

distance_result, _ = XCoreModeling.GetEntityEntityDistance(entity1, entity2)
min_distance = distance_result.Distance  # Distance in mm
```

Returns a distance result object with `.Distance` property. Distance is typically in millimeters.

Used in: `goliat/setups/placement_setup.py`

### How can I delete entities?

```python
# Delete a single entity
entity.Delete()

# Delete multiple entities
entities_to_delete = [e for e in all_entities if e.Name in ["old_bbox", "temp_entity"]]
for entity in entities_to_delete:
    entity.Delete()
```

Deletion is immediate and permanent. Make sure entities exist before deleting.

Used in: Various setup modules

### How can I create Vec3 vectors?

```python
import s4l_v1.model
from XCoreMath import Vec3
from QTech import Vec3 as QTechVec3

# Using s4l_v1.model
vec = s4l_v1.model.Vec3(10.0, 20.0, 30.0)

# Using XCoreMath
vec = Vec3(10.0, 20.0, 30.0)

# Using QTech (for view directions)
view_dir = QTechVec3(1, 0, 0)
```

Different modules have their own Vec3 classes. Use the appropriate one for the API you're calling.

Used in: `goliat/setups/base_setup.py`, `goliat/setups/placement_setup.py`

### How can I identify and work with entity groups?

```python
import s4l_v1.model

all_entities = s4l_v1.model.AllEntities()

# Find entity groups
all_groups = [e for e in all_entities if isinstance(e, s4l_v1.model.EntityGroup)]

# Find specific group by name
antenna_group = next((g for g in all_groups if g.Name == "Antenna"), None)

# Access entities in a group
if antenna_group:
    for entity in antenna_group.Entities:
        # Work with child entity
        pass

# Apply transform to entire group
transform = s4l_v1.model.Transform(...)
antenna_group.ApplyTransform(transform)

# Set group name
antenna_group.Name = "Antenna 700 MHz"
```

Groups contain multiple entities. Use `isinstance(e, s4l_v1.model.EntityGroup)` to identify them. Groups can be transformed and renamed like other entities.

Used in: `goliat/scripts/prepare_antennas.py`

### How can I access child entities in a group?

```python
# Access entities in a group
group = next((e for e in all_entities if e.Name.startswith("Group ")), None)
if group and hasattr(group, "Entities"):
    for entity in group.Entities:
        if hasattr(entity, "History") and "Union" in entity.History:
            # Get children of union operations
            children = entity.GetChildren()
        else:
            # Direct child
            pass
```

`Entities` property is for entity groups. `GetChildren()` is for entities created by boolean operations (Union, etc.).

Used in: `goliat/scripts/prepare_antennas.py`

### How can I decompose a transform into rotation and translation?

```python
from XCoreMath import Transform

# Get transform from entity
transform = entity.Transform

# Decompose into rotation and translation
rotation = transform.DecomposeRotation  # Returns Vec3 of Euler angles
translation = transform.Translation      # Returns Vec3 of translation

# Modify components
rotation[2] = np.deg2rad(-90)  # Modify Z rotation
translation[1] = 0              # Modify Y translation

# Create new transform
new_transform = Transform(Vec3(1, 1, 1), rotation, translation)
```

Rotation is Euler angles [rx, ry, rz] in radians. Translation is [tx, ty, tz] in model units.

Used in: `goliat/setups/placement_setup.py`

---

## 4. Materials

### How can I access the material database?

```python
import s4l_v1.materials.database

database = s4l_v1.materials.database
material = database["IT'IS 4.2"]["Brain"]
```

Common database: "IT'IS 4.2" for tissue properties. Materials are accessed by name as strings. Raises KeyError if material not found.

Used in: `goliat/setups/material_setup.py`

### How can I link a material from the database to a simulation?

```python
import s4l_v1.materials.database
import s4l_v1.simulation.emfdtd as emfdtd

database = s4l_v1.materials.database
material_settings = emfdtd.MaterialSettings()

# Link material from database (Option 1: Material object)
db_material = database["IT'IS 4.2"]["Brain"]
simulation.LinkMaterialWithDatabase(material_settings, db_material)

# Link material from database (Option 2: string name)
simulation.LinkMaterialWithDatabase(material_settings, "Brain")

# Assign to entities
simulation.Add(material_settings, [entity1, entity2])
```

The `material` parameter can be either a Material object from the database or a string name. Material settings must be linked before adding to simulation. Material properties are frequency-dependent (set simulation frequency first).

Used in: `goliat/setups/material_setup.py`

### How can I access material properties?

```python
import s4l_v1.simulation.emfdtd as emfdtd

for settings in simulation.AllSettings:
    if isinstance(settings, emfdtd.MaterialSettings):
        name = settings.Name
        permittivity = settings.ElectricProps.RelativePermittivity
        conductivity = settings.ElectricProps.Conductivity
        density = settings.MassDensity
```

Properties are frequency-dependent (based on simulation frequency). Access via `simulation.AllSettings` to iterate all material settings.

Used in: `goliat/setups/material_setup.py`

### How can I update material properties after frequency changes?

```python
import XCore

# Suppress logging during update
old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Error)
simulation.UpdateAllMaterials()
XCore.SetLogLevel(old_log_level)
```

Must be called after changing simulation frequency. Should be called before voxelization.

Used in: `goliat/setups/base_setup.py` (_finalize_setup)

---

## 5. Simulation setup

### How can I create an EM-FDTD simulation?

```python
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.document

simulation = emfdtd.Simulation()
simulation.Name = "EM_FDTD_simulation"
simulation.Frequency = 700, s4l_v1.units.MHz

# Add to document
document = s4l_v1.document
document.AllSimulations.Add(simulation)
```

Set frequency before assigning materials (affects material properties). Simulation must be added to document to be saved.

Used in: `goliat/setups/near_field_setup.py`, `goliat/setups/far_field_setup.py`

### How can I configure solver settings (kernel, etc.)?

```python
import s4l_v1.simulation.emfdtd as emfdtd

solver = simulation.SolverSettings

# Set kernel type
kernel_type = "cuda"  # or "acceleware" or "software"
if kernel_type == "acceleware":
    solver.Kernel = solver.Kernel.enum.AXware
elif kernel_type == "cuda":
    solver.Kernel = solver.Kernel.enum.Cuda
else:
    solver.Kernel = solver.Kernel.enum.Software
```

Kernel enum values: `AXware`, `Cuda`, `Software`. GPU kernels require compatible hardware.

Used in: `goliat/setups/base_setup.py` (_setup_solver_settings)

### How can I set simulation time and termination criteria?

```python
import s4l_v1.units

# Set simulation time (in periods of the simulation frequency)
sim_time_periods = 100  # Number of periods
simulation.SetupSettings.SimulationTime = (
    sim_time_periods,
    s4l_v1.units.Periods,
)

# Set termination criteria
term_level = "GlobalAutoTerminationWeak"  # or "GlobalAutoTerminationUserDefined"
term_options = simulation.SetupSettings.GlobalAutoTermination.enum
simulation.SetupSettings.GlobalAutoTermination = getattr(term_options, term_level)

# If user-defined, set convergence level
if term_level == "GlobalAutoTerminationUserDefined":
    convergence_db = -30
    simulation.SetupSettings.ConvergenceLevel = convergence_db
```

Time is typically set in periods (cycles) of the simulation frequency. Calculate the required number of periods based on your simulation domain size and frequency. Termination options: `GlobalAutoTerminationWeak`, `GlobalAutoTerminationMedium`, `GlobalAutoTerminationStrong`, `GlobalAutoTerminationUserDefined`.

Used in: `goliat/setups/base_setup.py` (_apply_simulation_time_and_termination)

### How can I add an edge source (antenna excitation)?

```python
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.units

edge_source_settings = emfdtd.EdgeSourceSettings()
excitation_enum = edge_source_settings.ExcitationType.enum

# For harmonic (single frequency)
edge_source_settings.ExcitationType = excitation_enum.Harmonic
edge_source_settings.Frequency = frequency_mhz, s4l_v1.units.MHz
edge_source_settings.CenterFrequency = frequency_mhz, s4l_v1.units.MHz

# For Gaussian (frequency sweep)
edge_source_settings.ExcitationType = excitation_enum.Gaussian
edge_source_settings.CenterFrequency = frequency_mhz, s4l_v1.units.MHz
edge_source_settings.Bandwidth = bandwidth_mhz, s4l_v1.units.MHz  # Set appropriate bandwidth

# Add to simulation
source_entity = antenna_line_entity
simulation.Add(edge_source_settings, [source_entity])
```

Harmonic for single-frequency simulations. Gaussian for frequency sweeps. Source entity is typically a line/edge in the antenna CAD model.

Used in: `goliat/setups/source_setup.py`

### How can I add a plane wave source (far-field)?

```python
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.units

plane_wave_source = emfdtd.PlaneWaveSourceSettings()
plane_wave_source.CenterFrequency = frequency_mhz, s4l_v1.units.MHz

# Set direction (theta, phi in degrees)
plane_wave_source.Theta = 90  # Elevation angle
plane_wave_source.Phi = 0      # Azimuth angle

# Set polarization (psi angle)
plane_wave_source.Psi = 0   # Theta polarization
# or
plane_wave_source.Psi = 90  # Phi polarization

# Add to simulation bounding box
simulation.Add(plane_wave_source, [bbox_entity])
```

Theta/Phi define wave propagation direction. Psi=0 for theta polarization, Psi=90 for phi polarization. Applied to simulation bounding box entity.

Used in: `goliat/setups/source_setup.py`

### How can I add sensors (edge, point, far-field)?

```python
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.units

# Edge sensor (for power monitoring)
edge_sensor_settings = emfdtd.EdgeSensorSettings()
simulation.Add(edge_sensor_settings, [source_entity])

# Point sensor (for E-field monitoring at specific locations)
point_entity = model.CreatePoint(model.Vec3(x, y, z))
point_sensor = emfdtd.PointSensorSettings()
point_sensor.Name = "Point Sensor 1"
simulation.Add(point_sensor, [point_entity])

# Far-field sensor (for radiation patterns)
far_field_sensor_settings = simulation.AddFarFieldSensorSettings()

# Configure extracted frequencies for Gaussian source
if excitation_type == "gaussian":
    center_freq_hz = frequency_mhz * 1e6
    bandwidth_hz = bandwidth_mhz * 1e6  # Set appropriate bandwidth
    start_freq_hz = center_freq_hz - (bandwidth_hz / 2)
    end_freq_hz = center_freq_hz + (bandwidth_hz / 2)
    num_samples = 21  # Choose number of frequency samples
    extracted_frequencies_hz = [
        start_freq_hz + i * (bandwidth_hz / (num_samples - 1))
        for i in range(num_samples)
    ]
    far_field_sensor_settings.ExtractedFrequencies = (
        extracted_frequencies_hz,
        s4l_v1.units.Hz,
    )
```

Edge sensors monitor power at source edges. Point sensors monitor E-field at specific 3D locations. Far-field sensors extract radiation patterns. Note that far-field sensors use `ExtractedFrequencies` (plural) while sensor extractors use `ExtractedFrequency` (singular).

Used in: `goliat/setups/base_setup.py` (_add_point_sensors), `goliat/setups/source_setup.py`

### How can I configure automatic gridding?

```python
import s4l_v1.simulation.emfdtd as emfdtd

# Set global gridding mode
simulation.GlobalGridSettings.DiscretizationMode = "Automatic"
simulation.GlobalGridSettings.BoundingBox = model.GetBoundingBox([sim_bbox_entity])

# Add automatic grid for simulation bounding box
added_grid_settings = simulation.AddAutomaticGridSettings([sim_bbox_entity])

# Set refinement level
refinement_mapping = {
    "Very Fine": "AutoRefinementVeryFine",
    "Fine": "AutoRefinementFine",
    "Default": "AutoRefinementDefault",
    "Coarse": "AutoRefinementCoarse",
    "Very Coarse": "AutoRefinementVeryCoarse",
}
s4l_refinement = refinement_mapping["Default"]

simulation.GlobalGridSettings.AutoRefinement = s4l_refinement
added_grid_settings.AutoRefinement = s4l_refinement
```

Refinement levels: `AutoRefinementVeryFine`, `AutoRefinementFine`, `AutoRefinementDefault`, `AutoRefinementCoarse`, `AutoRefinementVeryCoarse`. Must set both global and added grid settings.

Used in: `goliat/setups/gridding_setup.py`

### How can I configure manual gridding?

```python
import s4l_v1.simulation.emfdtd as emfdtd
import s4l_v1.units
import numpy as np

# Set global gridding mode
simulation.GlobalGridSettings.DiscretizationMode = "Manual"
simulation.GlobalGridSettings.BoundingBox = model.GetBoundingBox([sim_bbox_entity])

# Add manual grid for simulation bounding box
added_manual_grid = simulation.AddManualGridSettings([sim_bbox_entity])

# Set maximum step size (in mm)
max_step_mm = 2.0
max_step_setting = (
    np.array([max_step_mm] * 3),  # Same for x, y, z
    s4l_v1.units.MilliMeters,
)

simulation.GlobalGridSettings.MaxStep = max_step_setting
added_manual_grid.MaxStep = max_step_setting
```

MaxStep is a 3-element array [x, y, z] in millimeters. Can use different sizes per axis if needed. Must set both global and added grid settings.

Used in: `goliat/setups/gridding_setup.py`

### How can I configure subgridding?

```python
import s4l_v1.simulation.emfdtd as emfdtd

# Find the automatic grid settings
automatic_grid_settings = next(
    (x for x in simulation.AllSettings
     if isinstance(x, emfdtd.AutomaticGridSettings) and x.Name == "Automatic"),
    None
)

if automatic_grid_settings:
    # Add automatic grid to components that need subgridding
    simulation.Add(automatic_grid_settings, components_to_subgrid)
    
    # Configure subgridding parameters
    automatic_grid_settings.SubGridMode = automatic_grid_settings.SubGridMode.enum.Box
    automatic_grid_settings.SubGridLevel = automatic_grid_settings.SubGridLevel.enum.x9
    automatic_grid_settings.AutoRefinement = automatic_grid_settings.AutoRefinement.enum.AutoRefinementVeryFine
    
    # When converting strings to enums, use getattr() for flexibility
    subgrid_mode = "Box"
    automatic_grid_settings.SubGridMode = getattr(automatic_grid_settings.SubGridMode.enum, subgrid_mode)
```

Subgridding overrides manual gridding for specified components. Common levels: `x9`, `x3` (9x or 3x finer than base grid). When converting strings to enum values, `getattr(enum_class, string_value)` is more flexible than direct enum access.

Used in: `goliat/setups/gridding_setup.py`

### How can I configure grid padding?

```python
import s4l_v1.units
import numpy as np

global_grid_settings = simulation.GlobalGridSettings

# Automatic padding
global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Automatic

# Manual padding
global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Manual
bottom_padding = np.array([10, 10, 10])  # mm
top_padding = np.array([10, 10, 10])     # mm
global_grid_settings.BottomPadding = bottom_padding, s4l_v1.units.MilliMeters
global_grid_settings.TopPadding = top_padding, s4l_v1.units.MilliMeters
```

Padding is specified per axis [x, y, z] in millimeters. Automatic padding is usually sufficient.

Used in: `goliat/setups/gridding_setup.py`

### How can I configure boundary conditions (PML)?

```python
import s4l_v1.simulation.emfdtd as emfdtd

# Set global boundary type
global_boundaries = simulation.GlobalBoundarySettings
bc_enum = global_boundaries.GlobalBoundaryType.enum
global_boundaries.GlobalBoundaryType = bc_enum.UpmlCpml

# Set PML strength
# Boundary settings are created automatically when simulation is added
boundary_settings_list = [
    x for x in simulation.AllSettings
    if isinstance(x, emfdtd.BoundarySettings)
]
if boundary_settings_list:
    boundary_settings = boundary_settings_list[0]
    strength_enum = boundary_settings.PmlStrength.enum
    boundary_settings.PmlStrength = strength_enum.Medium  # or Weak, Strong
```

Boundary types: `UpmlCpml` (most common), although there are others available. PML strength: `Weak`, `Medium`, `Strong`. Boundary settings are created automatically when the simulation is added to the document, so you can access them via `simulation.AllSettings`.

Used in: `goliat/setups/boundary_setup.py`

### How can I add voxeler settings and create voxels?

```python
import s4l_v1.simulation.emfdtd as emfdtd

# Add automatic voxeler to all simulation parts
voxeler_settings = emfdtd.AutomaticVoxelerSettings()
all_simulation_parts = [phantom_entities, antenna_parts, bbox_entity]
simulation.Add(voxeler_settings, all_simulation_parts)

# Update materials (frequency-dependent properties)
simulation.UpdateAllMaterials()

# Update grid
simulation.UpdateGrid()

# Create voxels
simulation.CreateVoxels()
```

Must update materials and grid before creating voxels. Voxelization is computationally expensive.

Used in: `goliat/setups/base_setup.py` (_finalize_setup)

---

## 6. Simulation execution

### How can I write the solver input file?

```python
if hasattr(simulation, "WriteInputFile"):
    simulation.WriteInputFile()
    # Save project to flush files
    document.SaveAs(project_path)
```

Input file is written to project directory. File name can be retrieved with `simulation.GetInputFileName()`. Save project after writing to ensure file is flushed.

Used in: `goliat/simulation_runner.py` (run)

### How can I run a simulation locally?

```python
import s4l_v1.simulation

# Run on localhost (default)
simulation.RunSimulation(wait=True)

# Run on specific server
server_name = "MyLargeGPUMachine"
available_servers = s4l_v1.simulation.GetAvailableServers()
server_id = next(
    (s for s in available_servers if server_name.lower() in s.lower()),
    None
)
if server_id:
    simulation.RunSimulation(wait=True, server_id=server_id)
```

`wait=True` blocks until simulation completes. Server ID can be partial name (searches available servers).

Used in: `goliat/simulation_runner.py` (run)

### How can I run iSolve.exe manually?

```python
import os
import subprocess
import sys

# Find iSolve.exe relative to Python executable
python_path = sys.executable
s4l_root = os.path.dirname(os.path.dirname(python_path))
isolve_path = os.path.join(s4l_root, "Solvers", "iSolve.exe")

# Get input file path
input_file_path = os.path.join(project_dir, simulation.GetInputFileName())

# Run iSolve
command = [isolve_path, "-i", input_file_path]
process = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

# Wait for completion
return_code = process.wait()
if return_code != 0:
    raise RuntimeError(f"iSolve.exe failed with return code {return_code}")

# Reload project to load results
document.Close()
document.Open(project_path)
```

iSolve.exe is typically in `{Sim4Life}/Solvers/iSolve.exe`. Must reload project after completion to see results.

Used in: `goliat/simulation_runner.py` (_run_isolve_manual)

### How can I submit a simulation to oSPARC cloud?

```python
import XOsparcApiClient
import time

# Initialize client
client = XOsparcApiClient.OsparcApiClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    api_server="https://osparc.io",
    api_version="v0",
)

# Prepare job submission
input_file_path = os.path.join(project_dir, simulation.GetInputFileName())
job_data = XOsparcApiClient.JobSubmissionData()
job_data.InputFilePath = input_file_path
job_data.ResourceName = "osparc-1"
job_data.SolverKey = "sim4life-isolve"
job_data.SolverVersion = ""

# Create and start job
create_response = client.CreateJob(job_data)
job_id = create_response.Content.get("id")

start_response = client.StartJob(job_data, job_id)

# Poll for completion
while True:
    status_response = client.GetJobStatus(
        job_data.SolverKey,
        job_data.SolverVersion,
        job_id
    )
    status = status_response.Content.get("state")
    if status in ["SUCCESS", "FAILED", "ABORTED"]:
        break
    time.sleep(30)

# Reload project after completion
document.Close()
document.Open(project_path)
```

Requires Sim4Life 8.2.0+ for XOsparcApiClient module. Job states: PENDING, RUNNING, SUCCESS, FAILED, ABORTED. Must poll status until completion. You can also use the [osparc PyPI package](https://pypi.org/project/osparc/) or see the [osparc-simcore-clients repository](https://github.com/ITISFoundation/osparc-simcore-clients) for more information and alternative client implementations.

Used in: `goliat/simulation_runner.py` (_run_osparc_direct)

### How can I get the input file name from a simulation?

```python
# Get relative path from simulation
relative_path = simulation.GetInputFileName()

# Construct full path
project_dir = os.path.dirname(project_path)
input_file_path = os.path.join(project_dir, relative_path)
```

Returns relative path (e.g., "EM_FDTD_..._Input.h5"). Must combine with project directory for full path.

Used in: `goliat/simulation_runner.py`

---

## 7. Results extraction

### How can I access simulation results?

```python
simulation_extractor = simulation.Results()

# Access specific result
overall_field = simulation_extractor["Overall Field"]
input_power = simulation_extractor["Input Power"]
point_sensor = simulation_extractor["Point Sensor Entity 1"]
```

Result names depend on what was configured (sources, sensors, etc.). Common names: "Overall Field", "Input Power", "Point Sensor Entity N".

Used in: `goliat/results_extractor.py` (extract)

### How can I use E-field data as input to analysis algorithms?

```python
import s4l_v1.document
import s4l_v1.analysis

# Get E-field extractor
em_sensor_extractor = simulation_extractor["Overall Field"]
em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"

# Add to document algorithms and update
document = s4l_v1.document
document.AllAlgorithms.Add(em_sensor_extractor)
em_sensor_extractor.Update()

# Use E-field output as input to analysis algorithms (e.g., SAR evaluator)
e_field_output = em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]
inputs = [e_field_output]
sar_evaluator = s4l_v1.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
# ... configure and use evaluator ...

# Clean up
document.AllAlgorithms.Remove(em_sensor_extractor)
```

E-field data is typically used as input to analysis algorithms like SAR evaluators. Must add extractor to document before updating. Remove extractor when done to free memory.

Used in: `goliat/extraction/sar_extractor.py`

### How can I extract SAR statistics?

```python
import s4l_v1.analysis
import s4l_v1.document
import s4l_v1.units as units

# Get E-field data
em_sensor_extractor = simulation_extractor["Overall Field"]
em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
document.AllAlgorithms.Add(em_sensor_extractor)
em_sensor_extractor.Update()

# Create SAR statistics evaluator
inputs = [em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]]
sar_stats_evaluator = s4l_v1.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
sar_stats_evaluator.PeakSpatialAverageSAR = True
sar_stats_evaluator.PeakSAR.TargetMass = 10.0, units.Unit("g")
sar_stats_evaluator.UpdateAttributes()

# Compute SAR statistics
document.AllAlgorithms.Add(sar_stats_evaluator)
sar_stats_evaluator.Update()

# Access results (check if results exist first)
stats_output = sar_stats_evaluator.Outputs
if len(stats_output) > 0 and hasattr(stats_output.item_at(0), "Data"):
    results = stats_output.item_at(0).Data
    columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]
    data = [
        [results.RowCaptions[i]] + [results.Value(i, j) for j in range(results.NumberOfColumns())]
        for i in range(results.NumberOfRows())
    ]

# Clean up
document.AllAlgorithms.Remove(sar_stats_evaluator)
```

TargetMass typically 10g for IEEE/IEC compliance. Results are in table format with tissues as rows.

Used in: `goliat/extraction/sar_extractor.py` (extract_sar_statistics)

### How can I extract peak SAR location details?

```python
import s4l_v1.document
import s4l_v1.analysis
import s4l_v1.units as units

# First, set up and update the overall field extractor
em_sensor_extractor = simulation_extractor["Overall Field"]
em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
document.AllAlgorithms.Add(em_sensor_extractor)
em_sensor_extractor.Update()

# Use SAR output as input to average SAR field evaluator
inputs = [em_sensor_extractor.Outputs["SAR(x,y,z,f0)"]]

# Create average SAR field evaluator
average_sar_field_evaluator = s4l_v1.analysis.em_evaluators.AverageSarFieldEvaluator(inputs=inputs)
average_sar_field_evaluator.TargetMass = 10.0, units.Unit("g")
average_sar_field_evaluator.UpdateAttributes()

document.AllAlgorithms.Add(average_sar_field_evaluator)
average_sar_field_evaluator.Update()

# Get peak SAR details
peak_sar_output = average_sar_field_evaluator.Outputs["Peak Spatial SAR (psSAR) Results"]
peak_sar_output.Update()

data_collection = peak_sar_output.Data.DataSimpleDataCollection
peak_sar_details = {
    key: data_collection.FieldValue(key, 0)
    for key in data_collection.Keys()
}

# Clean up
document.AllAlgorithms.Remove(average_sar_field_evaluator)
document.AllAlgorithms.Remove(em_sensor_extractor)
```

Provides 3D coordinates, tissue name, mass, etc. for peak SAR. The extractor must be updated first to compute SAR field data. Data collection contains various metadata fields.

Used in: `goliat/extraction/sar_extractor.py` (extract_peak_sar_location)

### How can I extract input power?

```python
import s4l_v1.document

# Get input power extractor
input_power_extractor = simulation_extractor["Input Power"]
document.AllAlgorithms.Add(input_power_extractor)
input_power_extractor.Update()

# Method 1: Use GetPower() if available
if hasattr(input_power_extractor, "GetPower"):
    power_w, _ = input_power_extractor.GetPower(0)

# Method 2: Extract from harmonic data
else:
    input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
    input_power_output.Update()
    
    if hasattr(input_power_output, "GetHarmonicData"):
        power_complex = input_power_output.GetHarmonicData(0)
        power_w = abs(power_complex)
    else:
        power_data = input_power_output.Data.GetComponent(0)
        power_w = power_data.item()  # Single value

document.AllAlgorithms.Remove(input_power_extractor)
```

GetPower() is preferred but not always available. Harmonic data extraction is fallback method.

Used in: `goliat/extraction/power_extractor.py` (extract_input_power)

### How can I extract power balance?

```python
import s4l_v1.document

# Get overall field extractor
em_sensor_extractor = simulation_extractor["Overall Field"]

# Access power balance output
power_balance_extractor = em_sensor_extractor.Outputs["Power Balance"]
power_balance_extractor.Update()

# Extract power balance data
data_collection = power_balance_extractor.Data.DataSimpleDataCollection
power_balance_data = {
    key: data_collection.FieldValue(key, 0)
    for key in data_collection.Keys()
    if key != "Balance"
}

# Calculate balance percentage
pin = power_balance_data.get("Pin", 0.0)
p_out = power_balance_data.get("DielLoss", 0.0) + power_balance_data.get("RadPower", 0.0)
balance = 100 * (p_out / pin) if pin > 1e-9 else float("nan")
```

Balance should be close to 100% for good energy conservation. Keys: "Pin", "DielLoss", "RadPower", "Balance".

Used in: `goliat/extraction/power_extractor.py` (extract_power_balance)

### How can I extract point sensor data?

```python
import s4l_v1.document
import numpy as np

sensor_name = "Point Sensor Entity 1"
em_sensor_extractor = simulation_extractor[sensor_name]

document.AllAlgorithms.Add(em_sensor_extractor)

# Access E-field time data
em_output = em_sensor_extractor.Outputs["EM E(t)"]
em_output.Update()

# Extract time axis and E-field components
time_axis = em_output.Data.Axis
ex = em_output.Data.GetComponent(0)  # E_x component
ey = em_output.Data.GetComponent(1)  # E_y component
ez = em_output.Data.GetComponent(2)  # E_z component

# Calculate magnitude
e_mag = np.sqrt(ex**2 + ey**2 + ez**2)

document.AllAlgorithms.Remove(em_sensor_extractor)
```

Sensor name format: "Point Sensor Entity N". Time axis is in seconds. E-field components are in V/m.

Used in: `goliat/extraction/sensor_extractor.py`

---

## 8. Data and downloads

### How can I get available model downloads?

```python
import s4l_v1.data

available_downloads = s4l_v1.data.GetAvailableDownloads()

# Find specific phantom
phantom_name = "thelonious"
phantom_to_download = next(
    (item for item in available_downloads
     if phantom_name.lower() in item.Name.lower()),
    None
)
```

Returns iterable of download items. Each item has `.Name` property.

Used in: `goliat/setups/phantom_setup.py`

### How can I download a model?

```python
import s4l_v1.data
import os

download_email = "user@example.com"
download_directory = os.path.join(base_dir, "data", "phantoms")

s4l_v1.data.DownloadModel(
    phantom_to_download,
    email=download_email,
    directory=download_directory,
)
```

Email may be required for licensing. Downloads to specified directory. File is saved as .sab format.

Used in: `goliat/setups/phantom_setup.py`

---

## 9. Analysis algorithms

### How can I add an algorithm to the document?

```python
import s4l_v1.document

document = s4l_v1.document
document.AllAlgorithms.Add(algorithm)
algorithm.Update()
```

Algorithms must be added before updating. Add to document to persist and manage lifecycle.

Used in: `goliat/extraction/sar_extractor.py`, `goliat/extraction/power_extractor.py`

### How can I remove an algorithm from the document?

```python
import s4l_v1.document

document = s4l_v1.document
document.AllAlgorithms.Remove(algorithm)
```

Always remove algorithms when done to free memory. Should be done in finally blocks for error handling.

Used in: `goliat/extraction/sar_extractor.py`, `goliat/extraction/power_extractor.py`

### How can I access algorithm outputs?

```python
# Update algorithm first
algorithm.Update()

# Access outputs dictionary
outputs = algorithm.Outputs

# Get specific output (example: SAR evaluator output)
output = outputs["Peak Spatial SAR (psSAR) Results"]
output.Update()  # May need to update output

# Access data
data = output.Data
# Or for data collections:
data_collection = output.Data.DataSimpleDataCollection
value = data_collection.FieldValue("key", 0)

# For table data (SAR statistics):
results = outputs.item_at(0).Data
columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]
data = [
    [results.RowCaptions[i]] + [results.Value(i, j) for j in range(results.NumberOfColumns())]
    for i in range(results.NumberOfRows())
]
```

Output names depend on algorithm type. Common examples: "Peak Spatial SAR (psSAR) Results", "EM E(x,y,z,f0)", "Power Balance". Some outputs need Update() before accessing data. Table data has rows/columns structure. Data collections are key-value structures.

Used in: `goliat/extraction/sar_extractor.py`, `goliat/extraction/power_extractor.py`

### How can I access all simulation settings?

```python
import s4l_v1.simulation.emfdtd as emfdtd

# Iterate all settings
for settings in simulation.AllSettings:
    if isinstance(settings, emfdtd.MaterialSettings):
        name = settings.Name
        permittivity = settings.ElectricProps.RelativePermittivity
    
    elif isinstance(settings, emfdtd.AutomaticGridSettings):
        if settings.Name == "Automatic":
            # Found the automatic grid
            pass
    
    elif isinstance(settings, emfdtd.BoundarySettings):
        strength = settings.PmlStrength
```

Contains materials, grids, boundaries, sources, sensors, etc. Filter by type using `isinstance()`.

Used in: `goliat/setups/gridding_setup.py`, `goliat/setups/boundary_setup.py`

### How can I set frequency extraction settings?

```python
# Set to extract all frequencies
extractor.FrequencySettings.ExtractedFrequency = "All"

# Or extract specific frequency
extractor.FrequencySettings.ExtractedFrequency = frequency_hz, units.Hz
```

Important distinction: sensor extractors use `ExtractedFrequency` (singular), while far-field sensor settings use `ExtractedFrequencies` (plural). Must be set before calling `Update()`. "All" extracts all computed frequencies.

Used in: `goliat/extraction/sar_extractor.py`

---

## 10. Rendering and UI

### How can I set the view direction?

```python
import s4l_v1.renderer
from QTech import Vec3

# Set view direction vectors
views = {
    "x_pos": Vec3(1, 0, 0),
    "x_neg": Vec3(-1, 0, 0),
    "y_pos": Vec3(0, 1, 0),
    "y_neg": Vec3(0, -1, 0),
    "z_pos": Vec3(0, 0, 1),
    "z_neg": Vec3(0, 0, -1),
}

s4l_v1.renderer.SetViewDirection(views["x_pos"])
```

Direction is a unit vector (Vec3). Use QTech.Vec3 for renderer API.

Used in: `goliat/analysis/screenshot_analysis/get_screenshot.py`

### How can I zoom to an entity?

```python
import s4l_v1.renderer

s4l_v1.renderer.ZoomToEntity(entity)
```

Entity must be visible in the model.

Used in: `goliat/analysis/screenshot_analysis/get_screenshot.py`

### How can I capture a screenshot?

```python
import s4l_v1.renderer
import s4l_v1.model
import XCoreUI
import os
import time

# Hide grid if needed
grid_entity = s4l_v1.model.AllEntities()["Grid"]
grid_entity.Visible = False

# Force UI update
ui_app = XCoreUI.GetUIApp()
if ui_app and ui_app.MainFrame:
    ui_app.MainFrame.UpdateView()

# Wait for rendering to complete
time.sleep(1)

# Capture screenshot
folder = os.path.dirname(file_path)
filename_prefix = os.path.splitext(os.path.basename(file_path))[0]
s4l_v1.renderer.SaveScreenCapture(
    output_folder=folder,
    output_prefix=filename_prefix
)
```

Takes separate folder and prefix (not full path). Saves as PNG format. Force a UI update before capture and optionally hide the grid for cleaner screenshots. A short sleep after the UI update ensures rendering completes.

Used in: `goliat/analysis/screenshot_analysis/get_screenshot.py`

### How can I change the current UI mode?

```python
import s4l_v1.ui

s4l_v1.ui.ChangeCurrentMode("Simulation")
```

Mode names: "Simulation", "Modeling", etc. May need to force UI update after mode change.

Used in: `goliat/analysis/screenshot_analysis/get_screenshot.py`

### How can I control entity visibility?

```python
# Hide grid
grid_entity = s4l_v1.model.AllEntities()["Grid"]
grid_entity.Visible = False

# Force UI update
import XCoreUI
ui_app = XCoreUI.GetUIApp()
if ui_app and ui_app.MainFrame:
    ui_app.MainFrame.UpdateView()
```

Visibility changes may require UI update to take effect.

Used in: `goliat/analysis/screenshot_analysis/get_screenshot.py`
