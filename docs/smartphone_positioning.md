# Smartphone Positioning and Orientation: "In Front of the Eyes" Scenario

This document summarizes the positioning and orientation of the smartphone for the "in front of the eyes" exposure scenario, as detailed in `context/TableAntennaPositionandType14032024_corrected.docx.pdf`.

## Reference Points

*   **On the Head:** The reference point is the **nasion**.
*   **On the Phone:** The reference point is the intersection of the vertical centerline and a horizontal line passing through the speaker output (located 1 cm below the top edge of the PCB).

## Positional Variations

The phone's position is varied on the YZ-plane. The reference document specifies a total of 4 unique spatial positions for the "in front of the eyes" scenario. The phrase *"The variation is of one coordinate each time on the plane YZ (4 positions)"*, found in [`context/TableAntennaPositionandType14032024_corrected.docx.pdf`](context/TableAntennaPositionandType14032024_corrected.docx.pdf:139), indicates a cross-shaped testing pattern, not a full grid. This interpretation is visually confirmed by **Figure 1b** in the reference study [`context/Near-field_GOLIAT.pdf`](context/Near-field_GOLIAT.pdf:166), which shows the positions arranged in this pattern.

*   **X-axis (sagittal, posterior-anterior):** Fixed at **20 cm** from the nasion for all positions.
*   **Possible Y-axis coordinates:** -2.5 cm, 0 cm, 2.5 cm
*   **Possible Z-axis coordinates:** -10 cm, -4 cm

The 4 positions are derived by taking a central point and varying one coordinate at a time:

1.  **Center:** `(Y=0 cm, Z=-10 cm)`
2.  **Left:** `(Y=-2.5 cm, Z=-10 cm)`
3.  **Right:** `(Y=2.5 cm, Z=-10 cm)`
4.  **Up:** `(Y=0 cm, Z=-4 cm)`

## Orientations

For each of the 4 spatial positions, the phone is tested in two distinct orientations:

1.  **Vertical:** The phone is aligned parallel to the Z-axis (longitudinal).
2.  **Horizontal:** The phone is rotated +90 degrees around its Y-axis (transversal) from the vertical position.
---

# Smartphone Positioning: "Near the Ear" Scenario

This section details the positioning for the "Near the Ear" exposure scenario, which includes both "Cheek" and "Tilt" positions as described in [`context/TableAntennaPositionandType14032024_corrected.docx.pdf`](context/TableAntennaPositionandType14032024_corrected.docx.pdf:43).

## Reference Points

*   **On the Head:** The reference point is the **tragus of the ear**.
*   **On the Phone:** The reference point is the intersection of the vertical centerline and a horizontal line passing through the speaker output (1 cm below the top edge of the PCB).

## Positions and Alignments

For both "Cheek" and "Tilt" positions, the phone is placed at a distance of **0.8 cm** from the head. For each of these two base positions, 3 alignments are tested, resulting in a total of 6 unique simulations.

1.  **Alignment 1 (Base):** The vertical centerline of the phone is aligned with the line connecting the ear and the mouth.
2.  **Alignment 2 (Up):** The phone is rotated 10° upwards from the base alignment.
3.  **Alignment 3 (Down):** The phone is rotated 10° downwards from the base alignment.