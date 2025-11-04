"""
Helper functions for running bash commands in Jupyter notebooks.

This module provides utilities for executing bash commands with proper
encoding and real-time output streaming, especially useful on Windows.
"""

import subprocess
import os
import sys
from pathlib import Path


def _kill_process_tree(process):
    """Kill a process and all its children on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            # Send CTRL_BREAK_EVENT to kill entire process group
            ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, process.pid)  # CTRL_BREAK_EVENT
            # Wait a bit for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it didn't terminate gracefully
                process.kill()
                process.wait()
        except Exception:
            # Fallback: just terminate
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    else:
        # On Unix, terminate sends SIGTERM to process group
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def get_run_bash():
    """Get run_bash function for use in Jupyter notebooks.
    
    This finds the project root, sets up imports, and returns run_bash.
    Call this once at the start of your notebook.
    
    Returns:
        run_bash function ready to use
    
    Example:
        >>> run_bash = get_run_bash()
        >>> run_bash('goliat study near_field_config')
    """
    import importlib.util
    
    # Find project root by searching up for scripts/notebook_helpers.py
    project_root = Path.cwd()
    while not (project_root / 'scripts' / 'notebook_helpers.py').exists():
        if project_root == project_root.parent:
            raise RuntimeError("Could not find project root (scripts/notebook_helpers.py)")
        project_root = project_root.parent
    
    # Add project root to sys.path if not already there
    project_root_str = str(project_root.resolve())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    
    return run_bash




def run_bash(command, cwd=None):
    """
    Run a bash command and stream output in real-time with color support.
    
    This function automatically finds bash (including Git Bash on Windows),
    sources .bashrc, and runs the specified command. Output is streamed
    in real-time with proper UTF-8 encoding to preserve colors and special
    characters.
    
    Args:
        command: Command to run (will be prefixed with 'source .bashrc && ')
        cwd: Working directory (defaults to current or parent if .bashrc found)
    
    Returns:
        Return code of the command, or None if bash not found
    
    Example:
        >>> run_bash('goliat init')
        Running: source .bashrc && goliat init
        ------------------------------------------------------------
        ✓ GOLIAT initialization complete!
        ------------------------------------------------------------
        Command completed with return code: 0
    """
    # Find bash executable
    bash_exe = None
    for possible_bash in ['bash', 'C:\\Program Files\\Git\\bin\\bash.exe', 'C:\\Program Files\\Git\\usr\\bin\\bash.exe']:
        try:
            result = subprocess.run([possible_bash, '--version'], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                bash_exe = possible_bash
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    if not bash_exe:
        print("⚠️  Bash not found. Please run this command manually in your terminal/bash shell:")
        print(f"  source .bashrc && {command}")
        return None
    
    # Find project root (where .bashrc is) by searching up from cwd
    project_root = Path(cwd) if cwd else Path(os.getcwd())
    while not (project_root / '.bashrc').exists():
        if project_root == project_root.parent:
            break  # Reached filesystem root
        project_root = project_root.parent
    
    # Build full command
    full_command = f'source .bashrc && {command}'
    
    print(f"Running: {full_command}\n")
    print("-" * 60)
    
    # Set environment variables to force color output
    env = os.environ.copy()
    env['FORCE_COLOR'] = '1'
    env['CLICOLOR_FORCE'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    env['TERM'] = 'xterm-256color'
    env['NO_COLOR'] = '0'
    # Tell colorama to not strip ANSI codes even when not a TTY (for Jupyter)
    env['COLORAMA_STRIP'] = '0'
    env['JUPYTER_NOTEBOOK'] = '1'  # Signal to goliat that we're in Jupyter
    
    try:
        # Prepare subprocess arguments
        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'universal_newlines': False,  # Keep as bytes for proper encoding
            'env': env,
        }
        
        # On Windows, use CREATE_NEW_PROCESS_GROUP for proper process tree termination
        # This ensures all child processes (goliat GUI, Sim4Life) are killed together
        if sys.platform == "win32":
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        # Use Popen for real-time output with proper encoding
        process = subprocess.Popen(
            [bash_exe, '-c', full_command],
            cwd=str(project_root),
            **popen_kwargs
        )
        
        # Stream output in real-time - Jupyter supports ANSI codes directly
        try:
            for line in iter(process.stdout.readline, b''):
                # Decode with error handling for special characters
                try:
                    decoded = line.decode('utf-8', errors='replace')
                except:
                    decoded = line.decode('latin-1', errors='replace')
                
                # Print directly - Jupyter will render ANSI codes
                print(decoded, end='')
                sys.stdout.flush()
            
            process.wait()
        except KeyboardInterrupt:
            # Handle Ctrl+C from notebook - kill the process tree
            print("\n\n⚠️  Interrupted by user - terminating process...")
            _kill_process_tree(process)
            raise
        
        print("-" * 60)
        print(f"\nCommand completed with return code: {process.returncode}")
        return process.returncode
        
    except Exception as e:
        print(f"❌ Error running command: {e}")
        print("\nPlease run this command manually in your terminal/bash shell:")
        print(f"  source .bashrc && {command}")
        return None

