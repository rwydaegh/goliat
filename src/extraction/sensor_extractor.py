"""Point sensor data extraction."""

import traceback
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class SensorExtractor:
    """Handles extraction of point sensor E-field data.

    Extracts time-domain E-field measurements from point sensors,
    generates plots, and stores the raw data.
    """

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Initializes the SensorExtractor.

        Args:
            parent: The parent ResultsExtractor instance.
            results_data: The dictionary to store the extracted data.
        """
        self.parent = parent
        self.results_data = results_data
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger

    def extract_point_sensor_data(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts E-field data from point sensors, plots magnitude, and saves raw data.

        Args:
            simulation_extractor: The results extractor from the simulation object.
        """
        self.parent._log("    - Extract point sensors...", level="progress", log_type="progress")
        
        try:
            with self.parent.study.profiler.subtask("extract_point_sensor_data"):  # type: ignore
                num_sensors = self.parent.config.get_setting("simulation_parameters.number_of_point_sensors", 0)
                if num_sensors == 0:
                    return

                plt.ioff()
                plt.rcParams.update({"text.usetex": False})
                fig, ax = plt.subplots()
                ax.grid(True, which="major", axis="y", linestyle="--")

                point_source_order = self.parent.config.get_setting("simulation_parameters.point_source_order", [])
                point_sensor_results = {}

                for i in range(num_sensors):  # type: ignore
                    if i >= len(point_source_order):  # type: ignore
                        self.parent._log(
                            f"    - WARNING: Not enough entries in 'point_source_order' for sensor {i + 1}. Skipping.",
                            log_type="warning",
                        )
                        continue

                    corner_name = point_source_order[i]  # type: ignore
                    full_sensor_name = f"Point Sensor Entity {i + 1} ({corner_name})"

                    try:
                        em_sensor_extractor = simulation_extractor[full_sensor_name]
                        if not em_sensor_extractor:
                            self.parent._log(
                                f"    - WARNING: Could not find sensor extractor for '{full_sensor_name}'",
                                log_type="warning",
                            )
                            continue
                    except Exception as e:
                        self.parent._log(
                            f"    - WARNING: Could not retrieve sensor '{full_sensor_name}'. Error: {e}",
                            log_type="warning",
                        )
                        continue

                    self.parent.document.AllAlgorithms.Add(em_sensor_extractor)

                    if "EM E(t)" not in em_sensor_extractor.Outputs:
                        self.parent._log(
                            f"    - WARNING: 'EM E(t)' output not found for sensor '{full_sensor_name}'",
                            log_type="warning",
                        )
                        self.parent.document.AllAlgorithms.Remove(em_sensor_extractor)
                        continue

                    em_output = em_sensor_extractor.Outputs["EM E(t)"]
                    em_output.Update()

                    time_axis = em_output.Data.Axis
                    ex, ey, ez = (em_output.Data.GetComponent(i) for i in range(3))
                    label = corner_name.replace("_", " ").title()

                    if time_axis is not None and time_axis.size > 0:
                        e_mag = np.sqrt(ex**2 + ey**2 + ez**2)
                        ax.plot(time_axis, e_mag, label=label)
                        point_sensor_results[label] = {
                            "time_s": time_axis.tolist(),
                            "Ex_V_m": ex.tolist(),
                            "Ey_V_m": ey.tolist(),
                            "Ez_V_m": ez.tolist(),
                            "E_mag_V_m": e_mag.tolist(),
                        }
                    else:
                        self.parent._log(
                            f"    - WARNING: No data found for sensor '{full_sensor_name}'",
                            log_type="warning",
                        )

                    self.parent.document.AllAlgorithms.Remove(em_sensor_extractor)

                if point_sensor_results:
                    self.results_data["point_sensor_data"] = point_sensor_results

                self._save_plot(fig, ax)
            
            self.parent._log(
                f"      - Subtask 'extract_point_sensor_data' done in {self.parent.study.profiler.subtask_times['extract_point_sensor_data'][-1]:.2f}s",
                level="progress",
                log_type="success",
            )

        except Exception as e:
            self.parent._log(
                f"  - ERROR: An exception occurred during point sensor data extraction: {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())

    def _save_plot(self, fig, ax):
        """Saves the point sensor plot to disk."""
        import os

        ax.set(
            xlabel="Time (s)",
            ylabel="|E-Field| (V/m)",
            title=f"Point Sensor E-Field Magnitude vs. Time ({self.parent.frequency_mhz} MHz)",
        )
        ax.legend()

        results_dir = os.path.join(
            self.parent.config.base_dir,
            "results",
            self.parent.study_type,
            self.parent.phantom_name,
            f"{self.parent.frequency_mhz}MHz",
            self.parent.placement_name,
        )
        plot_filepath = os.path.join(results_dir, "point_sensor_data.png")
        plt.savefig(plot_filepath, dpi=300)
        plt.close(fig)
        self.parent._log(f"  - Point sensor plot saved to: {plot_filepath}", log_type="info")
