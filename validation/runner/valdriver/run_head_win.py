"""Windows wrapper for run_head.py (Windows VM, local Sim4Life 9.2 + network licence).
Sets the env the oSPARC runner provided and replaces POSIX symlinks with junctions/hardlinks."""

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("GOLIATVAL_SRC", r"C:\Users\Admin\goliat")
os.environ.setdefault("INPUT_FOLDER", r"C:\Users\Admin\goliat\data\phantoms")
spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(r"C:\goliatval\out") / spec["name"]
out.mkdir(parents=True, exist_ok=True)
os.environ["GOLIATVAL_OUT"] = str(out)


def _link(src, dst, target_is_directory=False):
    if os.path.isdir(src):
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(dst), str(src)], stdout=subprocess.DEVNULL)
    else:
        os.link(src, dst)


os.symlink = _link
sys.argv = [str(HERE / "run_head.py"), sys.argv[1]]
runpy.run_path(str(HERE / "run_head.py"), run_name="__main__")
