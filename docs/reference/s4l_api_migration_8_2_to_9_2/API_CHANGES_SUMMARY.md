# Sim4Life Python API Changes: Version 8.2 → 9.2

## Executive Summary

This document provides a comprehensive analysis of the changes between the Sim4Life Python API versions 8.2 and 9.2. The update represents a **major modernization effort** with significant improvements to type safety, API consistency, and feature additions. However, it also introduces **breaking changes** that will require code modifications for existing scripts.

### Quick Statistics

| Metric | Count |
|--------|-------|
| New API Modules | 9 |
| Removed API Modules | 3 |
| Modified API Modules | 104 |
| Total Files Changed | ~154 MB of documentation |

---

## Table of Contents

1. [Breaking Changes](#1-breaking-changes)
2. [Type System Improvements](#2-type-system-improvements)
3. [New Modules](#3-new-modules)
4. [Removed Modules](#4-removed-modules)
5. [Module-by-Module Changes](#5-module-by-module-changes)
6. [Migration Guide](#6-migration-guide)
7. [New Features by Category](#7-new-features-by-category)

---

## 1. Breaking Changes

### 1.1 Enum System Overhaul ⚠️ CRITICAL

The most significant breaking change is the complete replacement of the enum system.

**Before (8.2):**
```python
from Boost.Python import enum
# Enums were custom Boost.Python types
class eCompression:
    __slots__ = ()
    kHigh
    kLossless
    kMedium
    kNone
    names  # Dictionary of names
    values  # Dictionary of values
```

**After (9.2):**
```python
import enum
# Enums are now standard Python IntEnum
class eCompression(enum.IntEnum):
    __members__: mappingproxy
    __name__ = 'eCompression'
    kHigh: Extractors.eCompression
    kLossless: Extractors.eCompression
    kMedium: Extractors.eCompression
    kNoCompression: Extractors.eCompression  # Note: kNone → kNoCompression
```

**Impact:**
- Code using `.names` or `.values` will break
- Use `list(EnumClass)` or `EnumClass.__members__` instead
- Some enum values have been renamed (e.g., `kNone` → `kNoCompression`)
- Enum values now have proper type annotations

### 1.2 Argument Name Standardization

Function argument indices have been re-indexed from 1-based to 0-based.

**Before (8.2):**
```python
def SomeFunction(arg1: Any, arg2: Any, arg3: Any) -> None
```

**After (9.2):**
```python
def SomeFunction(arg0: Type1, arg1: Type2, arg2: Type3) -> None
```

**Affected Modules:** Nearly all modules with positional arguments.

### 1.3 Vector Type Standardization

Vector types have been consolidated.

**Before (8.2):**
```python
XCoreModeling.Vec3
XCoreMath.Vec3
```

**After (9.2):**
```python
QTech.Vec3  # Primary vector type
XCoreMath.Vec3  # Still available for transforms
```

**Examples of affected functions:**
- `Compose(arg2: XCoreMath.Vec3, ...)` → `Compose(arg0: QTech.Vec3, ...)`
- `Transform(vec3: Vec3)` → `Transform(vec3: QTech.Vec3)`

### 1.4 Return Type Changes

Many functions now return `list` instead of `tuple`.

**Before (8.2):**
```python
def GetNeuronEntities() -> tuple[XCoreModeling.Entity]
def GetSectionNames(...) -> tuple[str]
def FindEntities(filter) -> tuple
```

**After (9.2):**
```python
def GetNeuronEntities() -> list[XCoreModeling.Entity]
def GetSectionNames(...) -> list[str]
def FindEntities(filter: Callable[[Entity], bool]) -> list[Entity]
```

---

## 2. Type System Improvements

### 2.1 Replacement of `Any` with Specific Types

The most pervasive change is the replacement of generic `Any` types with precise Python types.

#### Numeric Types

| Before (8.2) | After (9.2) |
|--------------|-------------|
| `Any` | `SupportsFloat` |
| `Any` | `SupportsInt` |
| `Any` | `float` |
| `Any` | `int` |
| `Any` | `bool` |
| `Any` | `complex` |

#### Collection Types

| Before (8.2) | After (9.2) |
|--------------|-------------|
| `Any` | `collections.abc.Sequence[T]` |
| `Any` | `list[T]` |
| `Any` | `dict[K, V]` |
| `Any` | `set[T]` |
| `tuple` | `list[T]` (in many cases) |

#### Callable Types

| Before (8.2) | After (9.2) |
|--------------|-------------|
| `Any` | `collections.abc.Callable[[Args], ReturnType]` |
| `Any` | `collections.abc.typing.Callable[[str], bool]` |

#### NumPy Types

| Before (8.2) | After (9.2) |
|--------------|-------------|
| `Any` | `numpy.ndarray` |
| `Any` | `numpy.typing.NDArray[numpy.float64]` |
| `Any` | `Annotated[numpy.typing.ArrayLike, numpy.float32]` |

### 2.2 Path Type Improvements

File path parameters now accept multiple types:

**Before (8.2):**
```python
def ImportImage(file_path: str) -> Image
```

**After (9.2):**
```python
def ImportImage(file_path: os.PathLike | str | bytes) -> Image
```

### 2.3 Optional Type Annotations

Proper use of `None` types and union types:

**Before (8.2):**
```python
def Update(output_index: int = 0, iteration_indices: list[int] = ...) -> bool
```

**After (9.2):**
```python
def Update(output_index: int | str | None = None, iteration_indices: list[int] | None = None) -> bool
```

---

## 3. New Modules

### 3.1 ChromiumUI
Replaces the deprecated `Chromium` module for browser-based UI components.

### 3.2 HelpUI
New module for help system integration within the UI.

### 3.3 JosuaControllerInterface
Interface for JOSUA (presumably a simulation controller or optimizer).

### 3.4 LazySocks
Lazy socket implementation for deferred connections.

### 3.5 s4l_v1._api.pybindutils
Internal utilities for pybind11 bindings.

### 3.6 SysSimAppBase
Base application class for system simulations.

### 3.7 TestKit_Spok
Testing utilities for Spok framework.

### 3.8 ToolkitFUS
Focused Ultrasound (FUS) toolkit - new simulation capabilities.

### 3.9 XOsparcApiClient
Client for o²S²PARC platform integration (cloud computing).

---

## 4. Removed Modules

### 4.1 Chromium
**Replacement:** `ChromiumUI`

### 4.2 ImagePostPro
**Status:** Deprecated/merged into other modules

### 4.3 XNdArray
**Status:** Functionality absorbed into NumPy integration

---

## 5. Module-by-Module Changes

### 5.1 Core Framework (XCore)

#### New Classes
- `FileFilter` - File type filtering for dialogs
- `Exception` - Custom exception handling
- `AlignmentEnum` - UI alignment constants

#### New Methods
- `AddRow()` - Table row operations
- `GetCell(row, col)` - Cell access
- `GetRowAsJson(row)` - JSON serialization
- `GetTable()` - Full table retrieval
- `GetColumnDefinitions()` - Schema access
- `GetDataAsVariantMap()` - Data export

#### Signal Improvements
All signals now have proper callable type hints:
```python
# Before
Connect(slot: Any) -> Connection

# After
Connect(slot: collections.abc.Callable[[DataIndex], None]) -> Connection
Connect(slot: collections.abc.Callable[[Property, PropertyModificationTypeEnum], None]) -> Connection
Connect(slot: collections.abc.Callable[[SupportsFloat], None]) -> Connection
# ... and many more specific signatures
```

#### Unit Constants
Now properly typed as `ClassVar[Unit]`:
```python
Ampere: ClassVar[Unit]
Celsius: ClassVar[Unit]
CentiMeter: ClassVar[Unit]
# etc.
```

### 5.2 Modeling (XCoreModeling)

#### New Functions
| Function | Description |
|----------|-------------|
| `CreateDBSElectrode()` | Create Deep Brain Stimulation electrodes |
| `CreatePaddleElectrode()` | Create paddle-style electrodes |
| `GeodesicIsolinePatches()` | Geodesic isoline computation |
| `GeodesicVoronoiDiagram()` | Voronoi diagrams on surfaces |
| `IdentifyInterface()` | Interface identification between regions |
| `AttachLocalCoordinateSystem()` | Attach coordinate systems to vertices |
| `DeleteTriangleMeshPatches()` | Batch patch deletion |

#### New Classes
- `DBSElectrodeParameters` - DBS electrode configuration
- `ePaddleElectrodeContactShape` - Paddle electrode shapes (Circular, etc.)

#### Removed/Consolidated
- `CreateTrianglePatch` → Use `NewPatch` instead
- `DeleteTrianglePatch` → Use `DeletePatch` instead
- `NewTrianglePatch*` methods consolidated

#### Type Improvements
```python
# Before
def FindEntities(filter: Any) -> tuple

# After
def FindEntities(filter: collections.abc.Callable[[Entity], bool]) -> list[Entity]
```

### 5.3 Image Processing (ImageModeling / s4l_v1.model.image)

#### New Functions
| Function | Description |
|----------|-------------|
| `BodyModelGeneration(image, modality)` | Generate body models from images |
| `Predict1010SystemLandmarks(image)` | Predict 10-10 EEG system landmarks |

#### Enhanced Functions
```python
# HeadModelGeneration - Simplified signature
# Before (8.2)
def HeadModelGeneration(images: Any, bias_correction: Any = True,
                        closing_radius: Any = 30, ...) -> LabelField

# After (9.2)
def HeadModelGeneration(images: collections.abc.Sequence[XCoreModeling.Image]) -> LabelField
```

#### New Enum Values
- `kCC` - Cross-correlation metric
- `kMI` - Mutual information metric
- `kNoInit` - No initialization option

### 5.4 Post-Processing (Analysis)

#### New Algorithm
**`ScalarProductFieldEvaluator`**
- Computes scalar (dot) product between two vector fields
- Useful for: E·J calculations, power density, projection analysis

#### New Methods Across All Analysis Modules
```python
UpdateAll() -> bool  # Update all outputs at once
```

#### Update Method Enhancement
```python
# Before
def Update(output_index: int = 0, iteration_indices: list[int] = ...) -> bool

# After
def Update(output_index: int | str | None = None,
           iteration_indices: list[int] | None = None) -> bool
def Update(key: str) -> bool  # New overload
```

#### Viewer Enhancements
New properties:
- `Center` - Center point property
- `Point1`, `Point2` - Line/probe endpoints
- `Resolution` - Output resolution

Enhanced functions:
```python
# ExportIsoSurfaceToModel now accepts name parameter
def ExportIsoSurfaceToModel(name: str = 'Iso-Surface')
```

### 5.5 Electromagnetic Simulations

#### EM FDTD (s4l_v1.simulation.emfdtd)

New properties:
| Property | Description |
|----------|-------------|
| `AnalyticMethod` | Analytical method selection |
| `CongruentVoxeling` | Congruent voxelization option |
| `ConvergenceLevel` | Convergence criteria |
| `GlobalAutoTermination` | Auto-termination settings |
| `GlobalBoundaryType` | Global boundary configuration |
| `TimeStepFactor` | Time step control |
| `VoxelEngine` | Voxelization engine selection |

#### EM LF (s4l_v1.simulation.emlf)

New properties:
| Property | Description |
|----------|-------------|
| `AbsoluteSolverTolerance` | Absolute solver tolerance |
| `AbsoluteTolerance` | General absolute tolerance |
| `RelativeSolverTolerance` | Relative solver tolerance |
| `RelativeTolerance` | General relative tolerance |
| `DivergenceSolverTolerance` | Divergence solver tolerance |
| `MaxLinearIterations` | Maximum linear iterations |
| `PredefinedTolerances` | Predefined tolerance presets |
| `EnforceCoulombGaugingOfVectorPotential` | Coulomb gauge enforcement |

#### Shared EM Properties
All EM simulations now have:
- `SimulationUuid` - Unique simulation identifier
- `SimulationNotes` - User notes field
- `JobPriority` / `JobPriorityEnum` - Job scheduling priority
- `NumberOfGpus`, `NumberOfProcesses`, `NumberOfThreads` - Parallelization
- `Parallelization` - Parallelization mode
- `MaxFraction` - Maximum fraction setting
- `VoxelEngine` - Voxelization engine

### 5.6 Thermal Simulations

#### New Functionality
```python
CloneAsTIncrease() -> ThermalSimulator.ThermalSimulation
```
Clone simulation configured for temperature increase studies.

#### New Properties
| Property | Description |
|----------|-------------|
| `BloodVolume` | Blood volume for bio-heat |
| `Duration` | Simulation duration |
| `InitTime` | Initialization time |
| `LastSnapshot` | Last snapshot option |
| `MassDensity` | Mass density setting |
| `SpecificHeatCapacity` | Heat capacity |
| `ThermalConductivity` | Thermal conductivity |
| `UseBodyCoreHeating` | Body core heating model |
| `OverallTemperature` | Overall temperature sensor |
| `ThermalUnstructuredModel` | Unstructured mesh model |

### 5.7 Acoustic Simulations

#### New Properties
| Property | Description |
|----------|-------------|
| `CongruentVoxeling` | Congruent voxelization |
| `Frequency` | Operating frequency |
| `Harmonics` | Harmonic analysis settings |
| `Periods` | Number of periods |
| `ModelType` | Acoustic model type |
| `SolverType` | Solver selection |

### 5.8 Neuron Simulations

#### Return Type Updates
```python
# Before
def GetNeuronEntities() -> tuple[XCoreModeling.Entity]
def GetSectionNames(...) -> tuple[str]

# After
def GetNeuronEntities() -> list[XCoreModeling.Entity]
def GetSectionNames(...) -> list[str]
```

### 5.9 Posing/Deformation (XPoser)

#### Major Restructuring

**Removed:**
- `BoneEnvelope` class
- `BoneMeshControl` class
- `CreateBone()` function
- `IsBone()` function
- Individual bone control methods (`AddMeshes`, `RemoveMeshes`, `Start`, `Stop`, etc.)

**New Functions:**
| Function | Description |
|----------|-------------|
| `ApplyMorphing(bone_system, posture, displacements_file)` | Apply morphing with displacement field |
| `ConcatenateDeformation(input1, input2, output, scale)` | Concatenate deformation fields |
| `InterpolateDeformation(input, target, output)` | Interpolate deformation to new mesh |
| `InvertDeformation(input, output)` | Invert deformation field |
| `UntangleDeformation(input, output, ...)` | Fix tangled/inverted elements |
| `FixSkinThickness(old_skin, new_skin, max_thickness)` | Fix skin thickness issues |
| `SubdivideFemMesh(bone_mesh, max_edge_length)` | Subdivide FEM mesh |
| `MakePosable(mesh, bone_links, regions)` | Make mesh posable |
| `RemoveDomain0(input, output, domain_array)` | Remove domain 0 |
| `SaveProblemRegionVertexIds(...)` | Save problematic regions |

**New Class: `MaterialRegion`**
```python
class MaterialRegion:
    CommaSeparatedSettings: str
    Names: list[str]
    PoissonRatio: float
    VolumeGrowth: float
    YoungsModulus: float
```

### 5.10 Rendering (XRenderer/XRendererUI)

#### New Functions
```python
def RenderToImage(width: int = 1024, height: int = 1024,
                  output_file: str = '', use_alpha: bool = False) -> None

def UpdateRenderer() -> None

def DebugQueueFrameCapture(path: str) -> bool
```

#### API Improvements
```python
# SetViewDirection - Enhanced signature
# Before
def SetViewDirection(arg1: QTech.Vec3) -> None

# After
def SetViewDirection(look: QTech.Vec3, right: QTech.Vec3 = Vec3(0, 0, 0)) -> None
```

#### Property Type Fixes
All `Any` properties replaced with specific types:
```python
# Before
property Distance: Any
property PerspectiveMode: Any
property ViewDirection: Any
property Viewpoint: Any

# After
property Distance: float
property PerspectiveMode: bool
property ViewDirection: list[float]
property Viewpoint: QTech.Vec3
```

### 5.11 Simulation Framework (XSimulator)

#### New Class
```python
class DiscretizationSimulation:
    # Specialized simulation for discretization studies
```

#### New Function
```python
def ScanNetwork(ip_start: str, ip_end: str, ports: str,
                wait_for_resources: int) -> list[tuple[XCore.Uuid, dict[str, str]]]
```
Scan network for available compute resources.

#### Type Improvements
```python
# Before
def CollectAllComponents() -> Any
def CollectSettingsIf(concept: ConceptInfo) -> Any

# After
def CollectAllComponents() -> list[Component]
def CollectSettingsIf(concept: ConceptInfo) -> list[ConceptSettings]
```

### 5.12 Plotting (XPlotLib)

#### Major Cleanup

All enum constants consolidated to `ClassVar` pattern:
```python
# Before - Separate entries
Axis0Left
Axis0Left
Axis0Right
Axis0Right
# ... repeated for all axes

# After - ClassVar type hints
Axis0Left: ClassVar[PlottingAxis]
Axis0Right: ClassVar[PlottingAxis]
```

#### Type Improvements for Plot Data
```python
# Before
def AddPlot(x_data: Any, y_data: Any, plot_legend: str) -> PlotSettings

# After
def AddPlot(x_data: Annotated[numpy.typing.ArrayLike, numpy.float32],
            y_data: Annotated[numpy.typing.ArrayLike, numpy.float32],
            plot_legend: str) -> PlotSettings
def AddPlot(x_data: collections.abc.Sequence[SupportsFloat],
            y_data: collections.abc.Sequence[SupportsFloat],
            plot_legend: str) -> PlotSettings
```

### 5.13 Virtual Population (ViP)

#### New Functions
| Function | Description |
|----------|-------------|
| `Dilate(radius)` | Morphological dilation |
| `Erode(radius)` | Morphological erosion |
| `SmoothPolylines(entity_list, angle, iterations, refine)` | Smooth multiple polylines |
| `Save(file_path)` | Save to file |

#### Removed
- `CreateProjectionMask` - Removed entirely
- `RenderLines` - Removed entirely

#### Type Improvements
Extensive replacement of `Any` with proper types:
```python
# Before
def BatchExtractSelectedTissues(input_file: str, output_dir: str,
                                 list_tissue_list: Any) -> None

# After
def BatchExtractSelectedTissues(input_file: str, output_dir: str,
                                 list_tissue_list: collections.abc.Sequence[str]) -> None
```

### 5.14 Materials Database (XMaterials)

#### Property Additions
```python
Active: bool  # New property
Description: str  # New property
Type: LinearDispersionPole  # New type annotation
```

#### Type Improvements
```python
# Before
def FindMaterial(pattern: str, aliases: Any) -> Any
def Evaluate(frequencies: Any) -> Any

# After
def FindMaterial(pattern: str, aliases: bool) -> list[Material]
def Evaluate(frequencies: collections.abc.Sequence[SupportsFloat]) -> list[complex]
```

---

## 6. Migration Guide

### 6.1 Updating Enum Usage

```python
# OLD CODE (8.2)
from SomeModule import SomeEnum
value = SomeEnum.kSomeValue
all_values = SomeEnum.values
all_names = SomeEnum.names

# NEW CODE (9.2)
from SomeModule import SomeEnum
value = SomeEnum.kSomeValue  # Still works
all_values = list(SomeEnum)  # Use list() instead
all_names = SomeEnum.__members__  # Use __members__ instead
```

### 6.2 Updating Function Calls with Renamed Arguments

```python
# OLD CODE (8.2) - Positional arguments work
result = SomeFunction(arg1, arg2, arg3)

# NEW CODE (9.2) - Still works positionally, but named args changed
result = SomeFunction(arg0, arg1, arg2)

# If using keyword arguments, update names:
# OLD: result = SomeFunction(arg1=val1, arg2=val2)
# NEW: result = SomeFunction(arg0=val1, arg1=val2)
```

### 6.3 Updating Vector Types

```python
# OLD CODE (8.2)
from XCoreModeling import Vec3
point = Vec3(1.0, 2.0, 3.0)

# NEW CODE (9.2)
from QTech import Vec3
point = Vec3(1.0, 2.0, 3.0)
```

### 6.4 Updating Return Type Handling

```python
# OLD CODE (8.2)
entities = simulation.GetNeuronEntities()  # Returns tuple
first = entities[0]  # Works

# NEW CODE (9.2)
entities = simulation.GetNeuronEntities()  # Returns list
first = entities[0]  # Still works - lists are indexable too
# But if you were type checking for tuple, update to list
```

### 6.5 Using New Update Methods

```python
# OLD CODE (8.2)
algorithm.Update(0, [])  # Update output 0

# NEW CODE (9.2) - Multiple options
algorithm.Update()  # Update default
algorithm.Update("output_name")  # Update by name
algorithm.Update(0, None)  # Update with explicit None
algorithm.UpdateAll()  # NEW: Update all outputs
```

### 6.6 Path Parameters

```python
# OLD CODE (8.2)
image = ImportImage("/path/to/image.png")

# NEW CODE (9.2) - All these work
from pathlib import Path
image = ImportImage("/path/to/image.png")  # str still works
image = ImportImage(Path("/path/to/image.png"))  # pathlib works
image = ImportImage(b"/path/to/image.png")  # bytes works
```

---

## 7. New Features by Category

### 7.1 Medical Device Modeling
- **DBS Electrode Creation** - `CreateDBSElectrode()`, `DBSElectrodeParameters`
- **Paddle Electrode Creation** - `CreatePaddleElectrode()`, `ePaddleElectrodeContactShape`
- **10-10 System Landmarks** - `Predict1010SystemLandmarks()`

### 7.2 Mesh Processing
- **Geodesic Tools** - `GeodesicIsolinePatches()`, `GeodesicVoronoiDiagram()`, `GeodesicPath()`
- **Interface Identification** - `IdentifyInterface()`
- **Local Coordinate Systems** - `AttachLocalCoordinateSystem()`

### 7.3 Deformation/Morphing (XPoser)
- **Deformation Operations** - Concatenate, Interpolate, Invert, Untangle
- **Morphing Application** - `ApplyMorphing()`
- **Mesh Quality** - `FixSkinThickness()`, `SubdivideFemMesh()`
- **Material Regions** - New `MaterialRegion` class

### 7.4 Simulation Enhancements
- **Thermal** - Temperature increase cloning, body core heating
- **EM LF** - Enhanced solver tolerances and options
- **EM FDTD** - Auto-termination, analytical methods
- **Acoustic** - Harmonic analysis, model types

### 7.5 Cloud/Distributed Computing
- **o²S²PARC Integration** - `XOsparcApiClient` module
- **Network Scanning** - `ScanNetwork()` for compute resources
- **Job Priority** - `JobPriority` and `JobPriorityEnum` across simulations

### 7.6 Post-Processing
- **Scalar Product Evaluation** - `ScalarProductFieldEvaluator`
- **Batch Updates** - `UpdateAll()` method
- **ISO Surface Export** - Named exports with `ExportIsoSurfaceToModel(name)`

### 7.7 Rendering
- **Direct Image Render** - `RenderToImage()`
- **Renderer Updates** - `UpdateRenderer()`
- **Debug Capture** - `DebugQueueFrameCapture()`

### 7.8 Image Processing
- **Body Model Generation** - `BodyModelGeneration()`
- **Landmark Prediction** - `Predict1010SystemLandmarks()`
- **New Metrics** - Cross-correlation (kCC), Mutual Information (kMI)

---

## Appendix A: Complete List of Renamed Enum Values

| Module | Old Name | New Name |
|--------|----------|----------|
| Extractors | `kNone` | `kNoCompression` |
| Various | `Axis4ight` | `Axis4Right` (typo fix) |

## Appendix B: Removed Properties/Methods

| Module | Removed Item | Replacement |
|--------|--------------|-------------|
| XCoreModeling | `AsVtkImage()` | Use numpy integration |
| XCoreModeling | `AsVtkMesh()` | Use numpy integration |
| XCoreModeling | `DeleteTrianglePatch()` | `DeletePatch()` |
| XCoreModeling | `NewTrianglePatch()` | `NewPatch()` |
| XCoreModeling | `NewTrianglePatchFromRest()` | `NewPatchFromRest()` |
| XPoser | `BoneEnvelope` | Removed (new deformation API) |
| XPoser | `BoneMeshControl` | Removed (new deformation API) |
| XPoser | `CreateBone()` | Removed |
| XPoser | `IsBone()` | Removed |
| ViP | `CreateProjectionMask` | Removed |
| ViP | `RenderLines` | Removed |
| SysSimPrePro | Many UI properties | Simplified API |

## Appendix C: Files for Further Reference

- `PythonAPIReference_DIFF_8_2_to_9_2/DIFF_MANIFEST.txt` - List of all changed files
- `PythonAPIReference_DIFF_8_2_to_9_2/CONTENT_DIFF.md` - Detailed line-by-line diff
- `PythonAPIReference_8_2/` - Original 8.2 documentation
- `PythonAPIReference_9_2/` - New 9.2 documentation

---

*Document generated: 2026-01-13*
*Based on comparison of Sim4Life Python API Reference documentation versions 8.2 and 9.2*
