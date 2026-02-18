"""
Sim4Life License Installer Automation Script (TEMPLATE)

Automates the Sim4Life License Installer:
1. Launches the License Installer executable
2. Waits for the window to appear
3. Types the license server address into the text box
4. Clicks "Next" and waits for license validation
5. Detects success or failure and clicks "Finish"

Requirements:
    pip install pywinauto

Usage:
    python license_automation.py --license-server @myserver.domain.com

    For personal use, copy to my_license_automation.py and set LICENSE_SERVER below.
"""

import argparse
import os
import subprocess
import sys
import time

# ============================================================================
# CONFIGURATION
# ============================================================================
LICENSE_SERVER = "YOUR_LICENSE_SERVER"  # e.g., "@myserver.domain.com"
LICENSE_INSTALLER_PATH = r"C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe"

WINDOW_WAIT_TIMEOUT_SECONDS = 30
VALIDATION_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2
WINDOW_TITLE = "License Installer"


# ============================================================================
# DEPENDENCY MANAGEMENT
# ============================================================================


def ensure_pywinauto() -> bool:
    """Install pywinauto if missing, restarting the process if necessary.

    Returns True if ready to use, False on unrecoverable error.
    """
    try:
        import win32api  # noqa: F401
        from pywinauto import Application  # noqa: F401

        return True
    except ImportError:
        pass

    if os.environ.get("PYWIN32_INSTALLED") == "1":
        print("ERROR: pywin32 was installed but still cannot import win32api.")
        print("Please restart your terminal and try again.")
        return False

    print("pywinauto or pywin32 not found. Installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "--quiet"])

        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        postinstall_exe = os.path.join(scripts_dir, "pywin32_postinstall.exe")
        if os.path.exists(postinstall_exe):
            subprocess.call(
                [postinstall_exe, "-install", "-silent"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywinauto", "--quiet"])
        print("pywinauto installed. Restarting...")

        env = os.environ.copy()
        env["PYWIN32_INSTALLED"] = "1"
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))

    except Exception as e:
        print(f"ERROR: Failed to install pywinauto: {e}")
        return False


# ============================================================================
# WINDOW MANAGEMENT
# ============================================================================


def launch_license_installer() -> None:
    """Launch the License Installer executable.

    Raises:
        FileNotFoundError: If the installer is not found.
        RuntimeError: If the installer fails to launch.
    """
    print(f"\nLaunching License Installer from: {LICENSE_INSTALLER_PATH}")

    if not os.path.exists(LICENSE_INSTALLER_PATH):
        raise FileNotFoundError(f"License Installer not found at: {LICENSE_INSTALLER_PATH}\nSim4Life may not be installed correctly.")

    subprocess.Popen([LICENSE_INSTALLER_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  License Installer launched.")


def wait_for_window(timeout_seconds: int):
    """Wait for the License Installer window to appear.

    Returns:
        Tuple of (app, window, backend).

    Raises:
        RuntimeError: If the window doesn't appear within the timeout.
    """
    from pywinauto import Application

    print(f"\nWaiting for '{WINDOW_TITLE}' window (up to {timeout_seconds}s)...")

    start = time.time()
    while time.time() - start < timeout_seconds:
        for backend in ["win32", "uia"]:
            try:
                app = Application(backend=backend).connect(title=WINDOW_TITLE, timeout=1)
                window = app.top_window()
                print(f"  Window found after {int(time.time() - start)}s (backend: {backend})")
                return app, window, backend
            except Exception:
                pass
        time.sleep(0.5)

    raise RuntimeError(f"'{WINDOW_TITLE}' window not found after {timeout_seconds}s")


def get_window_text_content(window) -> str:
    """Collect all visible text from the window."""
    try:
        texts = [ctrl.window_text() for ctrl in window.descendants() if ctrl.window_text() and len(ctrl.window_text()) > 5]
        return "\n".join(texts)
    except Exception:
        return ""


def detect_license_status(window) -> str:
    """Detect license validation state.

    Returns:
        One of: "loading", "success", "failure", "unknown".
    """
    content = get_window_text_content(window).lower()

    if "please wait" in content:
        return "loading"

    failure_indicators = ["can't fetch", "cannot fetch", "failed", "kindly re-check", "unable to connect", "connection refused"]
    if any(ind in content for ind in failure_indicators):
        return "failure"

    if ("step 6 of 6" in content or "licenses summary" in content) and "can't fetch" not in content:
        return "success"

    return "unknown"


# ============================================================================
# AUTOMATION STEPS
# ============================================================================


def _click_button(button, backend: str) -> bool:
    """Click a pywinauto button using the most reliable method for the backend.

    Uses message-based methods that work without an active desktop/cursor.

    Returns True on success, False on failure.
    """
    if backend == "uia":
        try:
            button.invoke()
            return True
        except Exception:
            pass

    try:
        button.click()
        return True
    except Exception:
        pass

    try:
        button.type_keys("{ENTER}", set_foreground=False)
        return True
    except Exception:
        return False


def step1_enter_license_and_next(window, backend: str, license_server: str) -> None:
    """Enter the license server address and click Next.

    Uses message-based methods that work in headless/RDP environments.

    Raises:
        RuntimeError: If the text box or Next button cannot be found/clicked.
    """
    print(f"\n[Step 1] Entering license server: {license_server}")

    edit_control = None
    for kwarg in [{"class_name": "Edit"}, {"control_type": "Edit"}]:
        try:
            edit_control = window.child_window(**kwarg)
            break
        except Exception:
            pass

    if edit_control is None:
        raise RuntimeError("Could not find the license server text box.")

    try:
        edit_control.set_edit_text(license_server)
    except Exception:
        edit_control.set_text(license_server)
    print(f"  Entered: {license_server}")

    time.sleep(0.5)

    next_button = None
    for kwarg in [{"title": "Next"}, {"title_re": ".*Next.*"}]:
        try:
            next_button = window.child_window(**kwarg)
            break
        except Exception:
            pass

    if next_button is None:
        raise RuntimeError("Could not find the 'Next' button.")

    if not _click_button(next_button, backend):
        raise RuntimeError("Could not click the 'Next' button.")

    print("  Clicked 'Next'")


def wait_for_validation(window) -> None:
    """Wait for license validation to complete.

    Raises:
        RuntimeError: If validation fails or times out.
    """
    print("\n[Step 2] Waiting for license validation (30-60+ seconds)...")

    start = time.time()
    last_status = None

    while time.time() - start < VALIDATION_TIMEOUT_SECONDS:
        status = detect_license_status(window)

        if status != last_status:
            print(f"  [{int(time.time() - start)}s] Status: {status}")
            last_status = status

        if status == "success":
            return
        if status == "failure":
            raise RuntimeError("License validation FAILED. Check VPN connection and license server.")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise RuntimeError(f"License validation timed out after {VALIDATION_TIMEOUT_SECONDS}s")


def click_finish(window, backend: str) -> None:
    """Click the Finish button to complete the installation.

    Raises:
        RuntimeError: If the button cannot be found or clicked.
    """
    print("\n[Step 3] Clicking 'Finish'...")

    try:
        finish_button = window.child_window(title="Finish")
    except Exception as e:
        raise RuntimeError(f"Could not find 'Finish' button: {e}") from e

    if not _click_button(finish_button, backend):
        raise RuntimeError("Could not click 'Finish' button.")

    print("  Clicked 'Finish'")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate Sim4Life License Installer")
    parser.add_argument("--license-server", type=str, help="License server address (e.g., @myserver.domain.com)")
    args = parser.parse_args()

    license_server = args.license_server or LICENSE_SERVER

    print("=" * 60)
    print("Sim4Life License Installer Automation")
    print("=" * 60)

    if license_server == "YOUR_LICENSE_SERVER":
        print("\nERROR: LICENSE_SERVER not configured.")
        print("Use --license-server or edit this file.")
        sys.exit(1)

    print(f"License server: {license_server}")

    if not ensure_pywinauto():
        sys.exit(1)

    try:
        launch_license_installer()
        time.sleep(0.5)

        _, window, backend = wait_for_window(WINDOW_WAIT_TIMEOUT_SECONDS)

        step1_enter_license_and_next(window, backend, license_server)
        wait_for_validation(window)
        click_finish(window, backend)

        print("\n" + "=" * 60)
        print("LICENSE INSTALLATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except (RuntimeError, FileNotFoundError) as e:
        print(f"\nFAILED: {e}")
        print("\nPossible causes: VPN not connected, license server unreachable, wrong address.")
        sys.exit(1)


if __name__ == "__main__":
    main()
