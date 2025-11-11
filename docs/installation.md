# Installation

GOLIAT supports two installation methods. Use PyPI if you just want to run simulations. Use editable install if you need to modify code or access repository tools.

## PyPI installation

Install from PyPI and run from any directory. No repository cloning needed.

You need Sim4Life 8.2.0 with valid license, Sim4Life Python interpreter, and Windows.

Create a virtual environment with Sim4Life Python:

```bash
C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe -m venv venv --system-site-packages
source venv/Scripts/activate
```

The `--system-site-packages` flag allows the venv to access Sim4Life's packages (like `s4l_v1`).

Install GOLIAT:

```bash
python -m pip install goliat
```

Navigate to your project directory and initialize:

```bash
cd /path/to/your/project
goliat init
```

Creates `configs/` and `data/` directories and downloads required models. Then run simulations:

```bash
goliat study near_field_config
```

Works from any directory. Upgrade with `python -m pip install --upgrade goliat`. You can't modify source code or access repository scripts.

## Editable installation

Clone repository and install in editable mode. Required for development, testing, or contributing.

You need Git, Sim4Life 8.2.0 with valid license, and Sim4Life Python interpreter.

Clone repository:

```bash
git clone https://github.com/rwydaegh/goliat.git
cd goliat
```

Set up Sim4Life Python environment:

```bash
source .bashrc
```

Adds Sim4Life Python to PATH. GOLIAT prompts to copy `.bashrc` to home directory.

Install in editable mode (or in a venv):

```bash
python -m pip install -e .
```

Code changes are immediately available without reinstalling.

Initialize:

```bash
goliat init
```

Downloads models and sets up directories in repository root.

Gives you full repository access (scripts, tests, docs) and better IDE support. Use this if you're modifying code, running tests, or contributing.

## Post-installation

Both methods require running `goliat init` once. It verifies Sim4Life Python interpreter, downloads phantom and antenna models, and creates `configs/` and `data/` directories.

Takes 5-10 minutes depending on internet speed. If you delete parts of the setup, `goliat init` repairs incomplete installations.

## Choosing between options

Use PyPI if you just want to run simulations and don't need to modify code. Use editable install if you're developing, modifying code, running tests, or contributing.

For installation issues, see [troubleshooting guide](troubleshooting.md).
