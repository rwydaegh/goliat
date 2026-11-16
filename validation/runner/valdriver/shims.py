"""Generic shim shared with run_one.py: Sim4Life 9.6 raises on assignment of unknown attributes
where older SDKs ignored it (GOLIAT sets Simulation.Frequency and GlobalGridSettings.BoundingBox,
neither of which exists in the 8.2 API). Restores no-op semantics and records every hit."""

import inspect
import sys

PERMISSIVE = []


def install_permissive_setattr(report):
    import s4l_v1  # noqa: F401
    import s4l_v1.model  # noqa: F401
    import s4l_v1.simulation.emfdtd  # noqa: F401

    patched = []
    for n, mod in list(sys.modules.items()):
        if not n.startswith("s4l_v1") or mod is None:
            continue
        for cname, cls in list(vars(mod).items()):
            if not inspect.isclass(cls) or "__setattr__" not in cls.__dict__ or getattr(cls, "_goliatval_patched", False):
                continue
            orig = cls.__dict__["__setattr__"]

            def make(orig, cname):
                def __setattr__(self, k, v):
                    try:
                        orig(self, k, v)
                    except AttributeError as e:
                        if "unknown attribute" not in str(e):
                            raise
                        PERMISSIVE.append(f"{cname}.{k}")
                        try:
                            object.__setattr__(self, k, v)
                        except Exception:  # noqa: BLE001
                            pass

                return __setattr__

            cls.__setattr__ = make(orig, cname)
            cls._goliatval_patched = True
            patched.append(f"{mod.__name__}.{cname}")
    report["shim_patched_classes"] = patched
