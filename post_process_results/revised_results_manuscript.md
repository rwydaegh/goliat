# Results and Scientific Inquiry

This document presents a comprehensive analysis of the near-field dosimetric assessment for the 'Thelonius' child phantom. We begin by interpreting the primary simulation results and then proceed to a deeper, hypothesis-driven inquiry to uncover novel insights and formulate new research questions.

## 1. Primary Findings from Near-Field Exposure Scenarios

The initial analysis reveals a strong dependency of the Specific Absorption Rate (SAR) on both the frequency and the position of the radiating source. The two primary scenarios, "by_belly" and "front_of_eyes," exhibit distinct and noteworthy SAR profiles.

### 1.1. The "By Belly" Scenario: Trunk Dominance and Resonant Peaks

In the "by_belly" scenario, where the device is positioned near the abdomen, the trunk absorbs the majority of the radiated energy. The frequency response, however, is not linear. As shown below, the average trunk SAR peaks at **1450 MHz**, reaching 1.18 mW/kg. This suggests a potential resonant effect between the device and the torso at this frequency.

![Average Normalized SAR for Scenario: by_belly](plots/average_sar_bar_by_belly.png)

### 1.2. The "Front of Eyes" Scenario: A 700 MHz Hotspot

The "front_of_eyes" scenario presents a more alarming picture. The head is the primary site of energy deposition, with a striking peak at **700 MHz**, where the average head SAR reaches **2.08 mW/kg**. This value is more than double the next highest SAR value observed in this scenario (0.80 mW/kg at 1450 MHz). This finding is of critical importance as the 700 MHz band is widely used in modern wireless communications.

Equally intriguing is the sharp dip in head SAR at 835 MHz. This dramatic drop suggests a complex interaction between the antenna's radiation pattern and the head's anatomy at this specific frequency, which could be a key area for future mitigation studies.

![Average Normalized SAR for Scenario: front_of_eyes](plots/average_sar_bar_front_of_eyes.png)

### 1.3. Localized SAR (psSAR10g) Distributions: The Story of the Outliers

The boxplots showing the distribution of 10-gram peak spatial-average SAR (psSAR10g) reveal another critical layer of the story: the risk of localized hotspots.

For the **brain** in the "front_of_eyes" scenario, while the median SAR is modest, the presence of extreme outliers at 700 MHz (reaching up to 80 mW/kg) is a major concern. This indicates that specific device orientations can lead to exceptionally high localized SAR values, far exceeding the average. A similar, though less extreme, pattern is visible for the **eyes**.

![Distribution of Normalized psSAR10g Brain for Scenario: front_of_eyes](plots/boxplot_psSAR10g_brain_front_of_eyes.png)
![Distribution of Normalized psSAR10g Eyes for Scenario: front_of_eyes](plots/boxplot_psSAR10g_eyes_front_of_eyes.png)

In the "by_belly" scenario, the **skin** is the most affected tissue, with a broad peak in psSAR10g between 1450 MHz and 2450 MHz. The wide distribution and numerous outliers suggest a high sensitivity to the precise placement of the device on the torso.

![Distribution of Normalized psSAR10g Skin for Scenario: by_belly](plots/boxplot_psSAR10g_skin_by_belly.png)

### 1.4. The Critical Role of Antenna Technology

A crucial insight into the observed SAR behavior comes from the simulation's antenna configuration. The simulations employ two different types of antennas based on the frequency band:

*   **700 & 835 MHz:** A **Planar Inverted-F Antenna (PIFA)** is used. PIFAs are known for their compact size and are common in mobile devices, but their performance is highly sensitive to the surrounding environment, including the user's body.
*   **≥ 1450 MHz:** An **Inverted-F Antenna (IFA)** is used.

This change in antenna technology is a primary driver of the observed SAR patterns.

*   **The 1450 MHz Peak ("by_belly"):** The peak trunk SAR at 1450 MHz coincides with the introduction of the IFA. It is plausible that the IFA's radiation pattern couples more efficiently with the human torso at this specific frequency and distance (100 mm) compared to the PIFAs at lower frequencies or the IFAs at higher frequencies, where superficial absorption (the skin effect) becomes more dominant.

*   **The 700/835 MHz Anomaly ("front_of_eyes"):** The dramatic peak at 700 MHz and the subsequent dip at 835 MHz, despite both using a PIFA, strongly suggests a resonant phenomenon. The head acts as a dielectric load, altering the antenna's properties. The 700 MHz PIFA appears to be operating near a resonant peak when placed close to the eyes, leading to highly efficient energy transfer and a correspondingly high SAR. Conversely, the 835 MHz PIFA may be significantly detuned by the head's presence, or a null in its radiation pattern may be aligned with the head, causing the sharp drop in SAR. This highlights the extreme sensitivity of near-field exposure to small changes in frequency and antenna design.

### 1.5. Pinpointing the Source of SAR Hotspots

The boxplots revealed the presence of significant outliers, which represent worst-case exposure scenarios. Our analysis has successfully identified the precise simulation parameters responsible for these hotspots.

**"Front of Eyes" at 700 MHz:** The extreme outliers for both brain and eye SAR (reaching up to 76.6 mW/kg in the brain) are consistently generated by two specific placements: `front_of_eyes_right_horizontal` and `front_of_eyes_left_horizontal`. This finding is of paramount importance. It demonstrates that a **horizontally oriented** device, when positioned slightly to the left or right of the eyes, creates a resonant condition at 700 MHz that results in exceptionally high and potentially hazardous localized energy absorption.

**"By Belly" Skin Exposure:** For every frequency tested above 700 MHz, the single, recurring outlier in the skin SAR plots is caused by the **`by_belly_up_vertical`** placement. This corresponds to the device being shifted 100 mm upwards from the center of the abdomen. This specific location consistently produces the highest localized skin SAR, likely due to a combination of the body's curvature and the antenna's radiation pattern at that position.

Identifying these worst-case scenarios is a critical step towards developing effective mitigation strategies and providing more nuanced safety guidelines for device usage.

## 2. Deeper Inquiry and Data Integrity

The initial findings, while informative, naturally lead to a series of deeper questions that require further investigation.

### 2.1. The Interplay of SAR in Critical Tissues and the Case of the Missing Data

The line plots of average psSAR10g provide a dynamic view of how different tissues are affected across the frequency spectrum.

![Average Normalized psSAR10g for Scenario: front_of_eyes](plots/pssar10g_line_front_of_eyes.png)
![Average Normalized psSAR10g for Scenario: by_belly](plots/pssar10g_line_by_belly.png)

In the "front_of_eyes" scenario, the brain, eyes, and skin all show significant exposure, with their relative contributions changing with frequency. In contrast, for the "by_belly" scenario, the "Eyes" data line disappears for frequencies above 1450 MHz. A deep code audit revealed the precise cause: for these simulations, the SAR in the eye tissues is so negligible that the simulation solver does not record any values for them. The data extraction script (`results_extractor.py`) correctly finds no eye tissues to process and, as a result, does not create an "eyes_group" entry in the output file. When the data is later compiled, these missing entries are represented as `NaN` (Not a Number), causing the plotting library to stop drawing the line. This is not a bug, but rather a feature of the data pipeline that confirms the SAR in the eyes is effectively zero in these scenarios.

### 2.2. Peak vs. Average SAR: A Heatmap Comparison

A visual comparison of the two primary heatmaps reveals the crucial difference between peak and average SAR.

![Peak Spatial-Average SAR 10g (mW/kg)](plots/heatmap_pssar10g_summary.png)
![Min, Avg, and Max SAR (mW/kg) per Tissue](plots/heatmap_sar_summary.png)

The `psSAR10g` heatmap (left) appears "noisy" or "speckled." This is because `psSAR10g` is, by definition, a measure of the **highest SAR value in a small, localized 10-gram volume of tissue**. It is highly sensitive to local "hotspots," causing individual tissue values to vary dramatically.

In contrast, the mass-averaged SAR heatmap (right) is "smoother." It shows the average SAR over an entire organ or tissue. This averaging process naturally smooths out the extreme local variations. The "noisier" `psSAR10g` heatmap is therefore more informative for identifying worst-case exposure scenarios, while the "smoother" mass-averaged SAR heatmap provides a better overall picture of the energy deposition in a given tissue.

## 3. Quantitative Analysis

### 3.1. A Quantitative Model for Head and Eye SAR Correlation

Our analysis reveals a strong, predictive linear relationship between the overall head SAR and the localized `psSAR10g` in the eyes for the "front_of_eyes" scenario. A linear regression yields the following model:

**`Eye_SAR = 5.12 * Head_SAR + 0.86`**

This model has a high coefficient of determination (R² = 0.9783), indicating that it explains over 97% of the variance in the data. This strong linear fit, visualized below, provides a powerful predictive tool. For a given average head SAR, we can now reliably estimate the peak SAR in the eyes, a critical organ for dosimetric assessment.

![Correlation between Head SAR and Eye psSAR10g with Linear Fit](plots/correlation_head_vs_eye_sar.png)

### 3.2. The Physics of SAR Penetration Depth

Our analysis confirms that the ratio of brain SAR to skin SAR decreases significantly with increasing frequency. This is a direct consequence of the **skin effect**, a fundamental principle of electromagnetics.

At lower frequencies (e.g., 700 MHz), the electromagnetic waves have a longer wavelength and can penetrate deeper into biological tissues before their energy is absorbed. As the frequency increases (e.g., to 5800 MHz), the wavelength becomes shorter, and the energy is absorbed much more rapidly in the superficial layers of the body, primarily the skin. This is why the brain-to-skin SAR ratio is orders of magnitude lower at higher frequencies.

![SAR Penetration Depth](plots/penetration_ratio_vs_frequency.png)

## 4. Synthesis and Future Directions

Our comprehensive analysis, from initial data exploration to hypothesis-driven inquiry, has painted a detailed picture of the near-field dosimetric landscape for the 'Thelonius' phantom. We have not only quantified the SAR in various tissues but have also uncovered complex, frequency- and scenario-dependent phenomena that warrant further investigation.

The new research questions formulated throughout this analysis provide a clear roadmap for future work. The next logical steps would be to:

1.  **Perform a detailed antenna analysis** to understand its role in the observed SAR peaks, particularly the 700 MHz resonance and 835 MHz dip.
2.  **Conduct more granular simulations** focused on the worst-case placements (`front_of_eyes_..._horizontal` and `by_belly_up_vertical`) to investigate intra-organ SAR distribution.
3.  **Investigate the impact of anatomical variation** by running these simulations on different phantom models to assess the generalizability of these findings.

By pursuing these avenues, we can build upon the solid foundation laid in this study and continue to advance our understanding of the safe and responsible use of wireless technologies.