import os
import shutil
import sys
import time
from QTech import Vec3
import s4l_v1
import s4l_v1.model
import s4l_v1.renderer
import s4l_v1.ui
import XCoreUI
import XController


def set_view_and_capture(view_name, direction, file_path):
    """Sets the view direction, zooms to an entity, and captures a screenshot."""
    s4l_v1.renderer.SetViewDirection(direction)

    # Get the UI application and force an update
    ui_app = XCoreUI.GetUIApp()
    if ui_app and ui_app.MainFrame:
        ui_app.MainFrame.UpdateView()
    else:
        print("Could not get MainFrame to force view update.")

    # Capture the active 3D view
    folder = os.path.dirname(file_path)
    filename_prefix = os.path.splitext(os.path.basename(file_path))[0]

    # The C++ signature requires separate folder and prefix arguments, not a full path.
    s4l_v1.renderer.SaveScreenCapture(output_folder=folder, output_prefix=filename_prefix)


def get_phantom_entity(phantom_name):
    """
    Finds and returns the phantom entity based on its name.
    """
    all_entities = s4l_v1.model.AllEntities()
    for entity in all_entities:
        if hasattr(entity, "Name") and phantom_name.lower() in entity.Name.lower():
            return entity
    print("Phantom entity not found.")
    return None


def main():
    # It is assumed that this script is run with the Sim4Life python interpreter
    # The application should already be running.
    # Add a warning and confirmation before proceeding
    print(
        "WARNING: Please ensure you have manually selected the desired simulation in the Sim4Life UI, and that you have made the grid invisible."
    )

    # Set the output directory to be the same as the project file's directory.
    project_file_path = s4l_v1.document.FilePath
    if not project_file_path or not os.path.isabs(project_file_path):
        print(f"Error: Could not get a valid project path from Sim4Life. Received: '{project_file_path}'")
        return
    screenshots_dir = os.path.join(os.path.dirname(project_file_path), "screenshots")
    print(screenshots_dir)

    # Overwrite or delete any previous screenshots
    if os.path.exists(screenshots_dir):
        shutil.rmtree(screenshots_dir)
    os.makedirs(screenshots_dir)

    # Get the phantom to zoom to
    phantom_name_to_find = "thelonious"
    phantom_entity = get_phantom_entity(phantom_name_to_find)

    # Remove grid and View Voxels
    s4l_v1.model.AllEntities()["Grid"].Visible = False

    # Force a UI update to ensure the grid disappears
    ui_app = XCoreUI.GetUIApp()
    if ui_app and ui_app.MainFrame:
        ui_app.MainFrame.UpdateView()

    time.sleep(1)

    toggle_voxels()

    views = {
        "x_pos": Vec3(1, 0, 0),
        "x_neg": Vec3(-1, 0, 0),
        "y_pos": Vec3(0, 1, 0),
        "y_neg": Vec3(0, -1, 0),
        "z_pos": Vec3(0, 0, 1),
        "z_neg": Vec3(0, 0, -1),
    }

    s4l_v1.renderer.SetViewDirection(views["x_pos"])
    s4l_v1.renderer.ZoomToEntity(phantom_entity)

    for name, direction in views.items():
        file_path = os.path.join(screenshots_dir, f"{name}.png")
        set_view_and_capture(name, direction, file_path)


def toggle_voxels():
    """
    Toggles the voxel view by finding the correct UI action and triggering it.
    It is assumed the correct simulation/grid is already selected in the UI.
    """
    s4l_v1.ui.ChangeCurrentMode("Simulation")

    # Force a UI update to ensure the context is set
    ui_app = XCoreUI.GetUIApp()
    if ui_app and ui_app.MainFrame:
        ui_app.MainFrame.UpdateView()

    mode_manager = XController.ModeManagerInterface.Instance()
    current_mode = mode_manager.CurrentMode()
    if not current_mode:
        return

    main_tool = current_mode.Tool
    if not main_tool:
        return

    # The action objects returned by the API are temporary and must be
    # acted upon inside the loop where they are found.
    actions_iterator = main_tool.CollectToolActions(False)

    action_found = False
    for action in actions_iterator:
        if action.Label == "View Voxels":
            action_found = True
            if action.Enabled:
                action.Trigger()
            else:
                raise RuntimeError(
                    "The 'View Voxels' action is not enabled. Please ensure voxels have been created for the selected simulation."
                )
            # Once found and handled, our job is done.
            break

    if not action_found:
        print("Warning: 'View Voxels' action not found in the current context.")


if __name__ == "__main__":
    main()
