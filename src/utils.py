import os
import sys
import contextlib

def ensure_s4l_running():
    """
    Ensures that the Sim4Life application is running.
    """
    from s4l_v1._api import application
    
    if application.get_app_safe() is None:
        print("Starting Sim4Life application...")
        application.run_application(disable_ui_plugins=True)
        print("Sim4Life application started.")

def open_project(project_path):
    """
    Opens a Sim4Life project or creates a new one in memory.
    """
    import s4l_v1.document
    if not os.path.exists(project_path):
        print(f"Project file not found at {project_path}, creating a new one.")
        s4l_v1.document.New()
    else:
        print(f"Opening project: {project_path}")
        s4l_v1.document.Open(project_path)

@contextlib.contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull."""
    with open(os.devnull, 'w') as fnull:
        saved_stdout, saved_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = fnull, fnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = saved_stdout, saved_stderr