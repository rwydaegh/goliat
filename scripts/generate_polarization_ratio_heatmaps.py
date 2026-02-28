#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Polarization Ratio Heatmaps for All Phantoms

This script uses the HeatmapPlotter to generate polarization ratio heatmaps
for Duke, Ella, Eartha, and Thelonious from their aggregated far-field results.

Usage:
    python scripts/generate_polarization_ratio_heatmaps.py
"""

import os
import pickle
import logging
from goliat.analysis.plots.heatmap import HeatmapPlotter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("progress")


def main():
    phantoms = ["duke", "ella", "eartha", "thelonious"]
    base_dir = "."

    logger.info("--- Generating Polarization Ratio Heatmaps for all phantoms ---")

    for phantom in phantoms:
        logger.info(f"\nProcessing {phantom.upper()}...")

        results_dir = os.path.join(base_dir, "results", "far_field", phantom)
        plots_dir = os.path.join(base_dir, "plots", "far_field", phantom)
        pickle_path = os.path.join(results_dir, "aggregated_results.pkl")

        if not os.path.exists(pickle_path):
            logger.warning(f"  - WARNING: Aggregated results not found for {phantom} at {pickle_path}")
            continue

        try:
            # Load cached results
            with open(pickle_path, "rb") as f:
                cached_data = pickle.load(f)

            results_df = cached_data.get("summary_results")

            if results_df is None or results_df.empty:
                logger.warning(f"  - WARNING: No summary results found in cache for {phantom}")
                continue

            # Instantiate HeatmapPlotter
            # Use pdf format as default for publication quality
            plotter = HeatmapPlotter(plots_dir, phantom_name=phantom, plot_format="pdf")

            # Generate the heatmap
            logger.info("  - Generating polarization ratio heatmap...")
            plotter.plot_polarization_ratio_heatmap(results_df)

            # Also generate per-frequency heatmaps as they might be useful
            logger.info("  - Generating per-frequency polarization ratio heatmaps...")
            plotter.plot_polarization_ratio_heatmaps_per_frequency(results_df)

        except Exception as e:
            logger.error(f"  - ERROR processing {phantom}: {e}")
            import traceback

            logger.debug(traceback.format_exc())

    logger.info("\n--- Finished generating polarization ratio heatmaps ---")


if __name__ == "__main__":
    main()
