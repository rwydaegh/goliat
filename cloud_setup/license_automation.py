"""
Sim4Life License Installer Automation Script (TEMPLATE)

This script fully automates the Sim4Life License Installer:
1. Launches the License Installer executable
2. Waits for the window to appear
3. Types the license server address into the text box
4. Clicks "Next" and waits for license validation
5. Detects success or failure
6. Clicks "Finish" to complete

Requirements:
    pip install pywinauto

Usage:
    python license_automation.py --license-server @myserver.domain.com

    Or, for personal use, copy this file to my_license_automation.py and
    fill in your LICENSE_SERVER value.
"""

import argparse
import subprocess
import time
import sys
import os

# ============================================================================
# CONFIGURATION - Can be overridden via --license-server argument
# ============================================================================
LICENSE_SERVER = "YOUR_LICENSE_SERVER"  # e.g., "@myserver.domain.com"

# License Installer path (installed with Sim4Life)
LICENSE_INSTALLER_PATH = r"C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe"

# Timing configuration
WINDOW_WAIT_TIMEOUT_SECONDS = 30  # Max time to wait for window to appear
VALIDATION_TIMEOUT_SECONDS = 120  # Max time to wait for license validation
POLL_INTERVAL_SECONDS = 2  # How often to check for state changes

# Window settings
WINDOW_TITLE = "License Installer"


def ensure_pywinauto():
    """Ensure pywinauto and its dependencies are installed.

    Returns True if ready to use, False if script will be restarted.
    """
    # First, try to import win32api to check if pywin32 is properly installed
    try:
        import win32api  # noqa: F401
        from pywinauto import Application  # noqa: F401

        return True  # Everything works
    except ImportError:
        pass  # Need to install

    # Check if we're in a restart loop (env var set by previous run)
    if os.environ.get("PYWIN32_INSTALLED") == "1":
        print("ERROR: pywin32 was installed but still can't import win32api.")
        print("Please restart your terminal/command prompt and run the script again.")
        return False

    print("pywinauto or pywin32 not found/working. Installing...")
    try:
        # Install pywin32 first (required by pywinauto)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "--quiet"])

        # Run pywin32 post-install script directly
        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        postinstall_exe = os.path.join(scripts_dir, "pywin32_postinstall.exe")

        if os.path.exists(postinstall_exe):
            try:
                subprocess.check_call(
                    [postinstall_exe, "-install", "-silent"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print("  pywin32 post-install completed.")
            except subprocess.CalledProcessError:
                pass  # May fail, continue anyway

        # Now install pywinauto
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywinauto", "--quiet"])
        print("pywinauto installed successfully.")

        # Restart this script with same arguments (new Python process sees the DLLs)
        print("Restarting script to load newly installed modules...")
        env = os.environ.copy()
        env["PYWIN32_INSTALLED"] = "1"
        result = subprocess.call([sys.executable] + sys.argv, env=env)
        sys.exit(result)

    except Exception as e:
        print(f"ERROR: Failed to install pywinauto: {e}")
        return False


def launch_license_installer():
    """Launch the License Installer executable."""
    print("\nLaunching License Installer...")
    print(f"  Path: {LICENSE_INSTALLER_PATH}")

    if not os.path.exists(LICENSE_INSTALLER_PATH):
        print(f"ERROR: License Installer not found at: {LICENSE_INSTALLER_PATH}")
        print("Sim4Life may not be installed correctly.")
        return False

    try:
        # Launch in background (non-blocking)
        subprocess.Popen([LICENSE_INSTALLER_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("  License Installer launched.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to launch License Installer: {e}")
        return False


def wait_for_window(timeout_seconds):
    """Wait for the License Installer window to appear."""
    from pywinauto import Application

    print(f"\nWaiting for '{WINDOW_TITLE}' window (up to {timeout_seconds}s)...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        for backend in ["win32", "uia"]:
            try:
                app = Application(backend=backend).connect(title=WINDOW_TITLE, timeout=1)
                window = app.top_window()
                elapsed = int(time.time() - start_time)
                print(f"  Window found after {elapsed}s (using {backend} backend)")
                return app, window, backend
            except Exception:
                pass

        time.sleep(0.5)

    print(f"ERROR: Window not found after {timeout_seconds} seconds")
    return None, None, None


def get_window_text_content(window):
    """Get all text content from the window for status detection."""
    try:
        texts = []
        for ctrl in window.descendants():
            try:
                text = ctrl.window_text()
                if text and len(text) > 5:
                    texts.append(text)
            except Exception:
                pass
        return "\n".join(texts)
    except Exception:
        return ""


def detect_license_status(window):
    """
    Detect if license validation succeeded or failed.
    Returns: "loading", "success", "failure", or "unknown"
    """
    content = get_window_text_content(window).lower()

    # Check for loading state
    if "please wait" in content:
        return "loading"

    # Check for failure indicators
    failure_indicators = [
        "can't fetch",
        "cannot fetch",
        "failed",
        "kindly re-check",
        "unable to connect",
        "connection refused",
    ]

    for indicator in failure_indicators:
        if indicator in content:
            return "failure"

    # Check for success indicators (Step 6 with licenses found)
    if "step 6 of 6" in content or "licenses summary" in content:
        # Make sure it's not a failure
        if "can't fetch" not in content and "kindly re-check" not in content:
            return "success"
        else:
            return "failure"

    return "unknown"


def step1_enter_license_and_next(window, backend):
    """Step 1: Enter license server and click Next."""
    print(f"\n[Step 1] Entering license server: {LICENSE_SERVER}")

    try:
        # Find the Edit control (text box)
        edit_control = None

        if backend == "win32":
            try:
                edit_control = window.child_window(class_name="Edit")
            except Exception:
                pass

        if edit_control is None:
            try:
                edit_control = window.child_window(control_type="Edit")
            except Exception:
                pass

        if edit_control is None:
            print("ERROR: Could not find the text box control.")
            return False

        # Enter the license server
        edit_control.set_focus()
        time.sleep(0.3)
        edit_control.set_edit_text(LICENSE_SERVER)
        print(f"  Entered: {LICENSE_SERVER}")

        # Click Next button
        time.sleep(0.5)
        next_button = window.child_window(title="Next")
        next_button.click()
        print("  Clicked 'Next' button")

        return True

    except Exception as e:
        print(f"ERROR in step 1: {e}")
        return False


def wait_for_validation(window):
    """Wait for license validation to complete."""
    print("\n[Step 2] Waiting for license validation...")
    print("  (This may take 30-60+ seconds)")

    start_time = time.time()
    last_status = None

    while time.time() - start_time < VALIDATION_TIMEOUT_SECONDS:
        status = detect_license_status(window)

        if status != last_status:
            elapsed = int(time.time() - start_time)
            print(f"  [{elapsed}s] Status: {status}")
            last_status = status

        if status == "success":
            return True, "License validation successful!"
        elif status == "failure":
            return False, "License validation FAILED! Check VPN connection and license server."

        time.sleep(POLL_INTERVAL_SECONDS)

    return False, f"Timeout after {VALIDATION_TIMEOUT_SECONDS} seconds"


def click_finish(window):
    """Click the Finish button to complete the process."""
    print("\n[Step 3] Clicking 'Finish' button...")

    try:
        finish_button = window.child_window(title="Finish")
        finish_button.click()
        print("  Clicked 'Finish' button")
        return True
    except Exception as e:
        print(f"  Could not find/click Finish button: {e}")
        return False


def main():
    global LICENSE_SERVER

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automate Sim4Life License Installer")
    parser.add_argument("--license-server", type=str, help="License server address (e.g., @myserver.domain.com)")
    args = parser.parse_args()

    # Override LICENSE_SERVER if provided via command line
    if args.license_server:
        LICENSE_SERVER = args.license_server

    print("=" * 60)
    print("Sim4Life License Installer Automation")
    print("=" * 60)

    # Check configuration
    if LICENSE_SERVER == "YOUR_LICENSE_SERVER":
        print("\nERROR: LICENSE_SERVER not configured!")
        print("Please use --license-server argument or edit this file")
        sys.exit(1)

    print(f"License server: {LICENSE_SERVER}")

    # Ensure pywinauto is installed
    if not ensure_pywinauto():
        sys.exit(1)

    # Import after ensuring it's installed

    # Launch License Installer
    if not launch_license_installer():
        sys.exit(1)

    # Wait for window to appear
    app, window, backend = wait_for_window(WINDOW_WAIT_TIMEOUT_SECONDS)

    if window is None:
        print("\nERROR: Failed to find the License Installer window.")
        sys.exit(1)

    # Bring window to front
    try:
        window.set_focus()
        time.sleep(0.5)
    except Exception:
        pass

    # Step 1: Enter license and click Next
    if not step1_enter_license_and_next(window, backend):
        print("\nFAILED at Step 1")
        sys.exit(1)

    # Step 2: Wait for validation
    success, message = wait_for_validation(window)
    print(f"\n{'SUCCESS' if success else 'FAILURE'}: {message}")

    # Step 3: Click Finish
    click_finish(window)

    # Final result
    print("\n" + "=" * 60)
    if success:
        print("LICENSE INSTALLATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("LICENSE INSTALLATION FAILED!")
        print("=" * 60)
        print("\nPossible causes:")
        print("  - VPN not connected")
        print("  - License server unreachable")
        print("  - Invalid license server address")
        print("\nPlease check your VPN connection and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
