# Scientific Inquiry: Final Status Report

This document summarizes the completed analysis tasks and the new research questions formulated during the deep-dive investigation of the GOLIAT near-field dataset.

### High-Priority Questions & Data Digging

-   [x] **Investigate SAR Peaks (1450 MHz & 700/835 MHz):**
    -   **Completed:** The investigation revealed a switch from PIFA to IFA antenna technology. The manuscript (Section 1.4) now includes a detailed hypothesis linking these antenna types to the observed SAR peaks and resonant effects.

-   [x] **Identify Outlier Placements:**
    -   **Completed:** A targeted script (`investigate_outliers.py`) successfully identified the `horizontal` placements in the "front_of_eyes" scenario and the `up_vertical` placement in the "by_belly" scenario as the definitive sources of the worst-case outliers. This is now detailed in the manuscript (Section 1.5).

### Plot & Data Integrity Checks

-   [x] **Missing Eye SAR Data:**
    -   **Completed:** A deep investigation (`investigate_belly_eye_data.py`) confirmed that the "disappearing" eye data in the `by_belly` plot is due to **missing (`NaN`) values** for all frequencies above 1450 MHz. The manuscript now correctly identifies this as a data integrity issue and a limitation of the current dataset (Section 2.1).

-   [x] **Heatmap Comparison:**
    -   **Completed:** The manuscript now includes a side-by-side comparison of the `psSAR10g` and mass-averaged SAR heatmaps, with a clear physical explanation for the difference in "smoothness" based on the nature of peak vs. average measurements (Section 2.2).

-   [x] **Fix Correlation Plot Legend & Enhance Fit:**
    -   **Completed:** The correlation plot was corrected and significantly enhanced. It now includes a predictive linear regression model (`Eye_SAR = 5.12 * Head_SAR + 0.86`) and the corresponding R-squared value, which are presented in the manuscript (Section 3.1).

### Manuscript & Analysis Enhancements

-   [x] **Remove Non-Essential Sections:**
    -   **Completed:** All references to the "Total Exposure Index (TEI)" and "Machine Learning" have been meticulously removed from all analysis scripts and the final manuscript.

-   [x] **Explain Penetration Depth (Hypothesis 2):**
    -   **Completed:** The manuscript now provides a clear, physics-based explanation of the "skin effect" to account for the observed frequency-dependent SAR penetration (Section 3.2).

### New Research Questions (Incorporated into Manuscript's "Future Directions")

Based on this completed analysis, the following new research questions have been formulated and are now part of the final manuscript's "Synthesis and Future Directions" section:

1.  **Detailed Antenna Analysis:** What is the precise relationship between the antenna's radiation characteristics and the observed SAR peaks?
2.  **Granular Intra-Organ SAR Distribution:** How is SAR distributed *within* critical organs like the brain and eyes?
3.  **Missing Data Investigation:** What is the root cause of the missing eye SAR data in the `by_belly` scenario? Is it a simulation artifact or a data extraction error?
4.  **Anatomical Variation:** How would these results change when run on different phantom models?
