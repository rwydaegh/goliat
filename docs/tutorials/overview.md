# GOLIAT tutorials

Interactive tutorials for learning GOLIAT through hands-on examples.

## Getting started

Each tutorial is a Jupyter notebook that you can run interactively. They use the bash helper from `scripts/notebook_helpers.py` to execute GOLIAT commands.

## Tutorial list

### 1. [Far-field basics](01_far_field_basics.ipynb)

**Start here.** Learn environmental exposure simulations with plane waves.

- Duration: 25-30 minutes
- Difficulty: Beginner
- Topics: Plane waves, directions, polarizations, config structure, running first study

### 2. [Configuration and caching](02_configuration_and_caching.ipynb)

Learn how configs extend each other and how GOLIAT avoids redundant work.

- Duration: 30-35 minutes
- Difficulty: Beginner to Intermediate
- Topics: Config inheritance, validation, config hashing, metadata, `--no-cache` flag

### 3. [Near-field basics](03_near_field_basics.ipynb)

Device exposure scenarios with antennas.

- Duration: 30-35 minutes
- Difficulty: Intermediate
- Topics: Antennas, placements, anatomical landmarks, localized SAR

### 4. [Gridding and phantom rotation](04_gridding_and_phantom_rotation.ipynb)

Computational grids and advanced near-field techniques.

- Duration: 35-40 minutes
- Difficulty: Intermediate to Advanced
- Topics: Automatic/manual gridding, subgridding, phantom rotation, scene alignment

### 5. [Parallel and cloud execution](05_parallel_and_cloud_execution.ipynb)

Running multiple simulations (local parallel and oSPARC).

- Duration: 30-35 minutes
- Difficulty: Intermediate to Advanced
- Topics: Config splitting, multiple GUIs, oSPARC setup, batch runs, job monitoring

## Contributing

Found an issue or want to improve a tutorial? See the [Technical Guide](../developer_guide/technical_guide.md) for developer information.

## See also

- [Quick start guide](../user_guide/quick_start.md) (get GOLIAT running in minutes)
- [User guide](../user_guide/user_guide.md) (comprehensive workflow explanations)
- [Configuration reference](../developer_guide/configuration.md) (full config parameter documentation)
- [Full List of Features](../reference/full_features_list.md) (everything GOLIAT can do)
