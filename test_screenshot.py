import s4l_v1._api.application as app
import XCoreUI
import XCore
import os
import s4l_v1.document as document
from s4l_v1.model import Vec3

def set_view_and_capture(axis, file_path):
    """Sets the view direction and captures a screenshot."""
    direction = Vec3(0, 0, 0)
    if axis.lower() == 'x':
        direction = Vec3(1, 0, 0)
    elif axis.lower() == 'y':
        direction = Vec3(0, 1, 0)
    elif axis.lower() == 'z':
        direction = Vec3(0, 0, 1)
    
    XCoreUI.SetViewDirection(direction)
    
    # Get the UI application
    ui_app = XCoreUI.GetUIApp()
    if not ui_app:
        print("Sim4Life GUI not running. Please run this script from within Sim4Life.")
        return

    main_view = ui_app.MainFrame
    if not main_view:
        print("Could not get the MainFrame.")
        return

    # Capture the image
    print(f"Capturing main window for {axis.upper()} axis...")
    image = main_view.CaptureImage()

    if image:
        print(f"Saving screenshot to {file_path}")
        image.Save(file_path)
        print("Screenshot saved successfully.")
    else:
        print("Failed to capture image.")

def main():
    # It is assumed that this script is run with the Sim4Life python interpreter
    # The application should already be running.
    
    # Define output path
    output_dir = "d:/users/rwydaegh/goliat/screenshots"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # X-axis
    file_path_x = os.path.join(output_dir, "main_window_capture_x.png")
    set_view_and_capture('x', file_path_x)

    # Y-axis
    file_path_y = os.path.join(output_dir, "main_window_capture_y.png")
    set_view_and_capture('y', file_path_y)

    # Z-axis
    file_path_z = os.path.join(output_dir, "main_window_capture_z.png")
    set_view_and_capture('z', file_path_z)
    

if __name__ == "__main__":
    main()