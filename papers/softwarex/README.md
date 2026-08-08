# GOLIAT SoftwareX paper

This directory contains the current LaTeX manuscript for an Original Software
Publication in *SoftwareX* and its latest clean PDF.

## Manuscript files

- `main.tex`: submission source using Elsevier's `elsarticle` class with the
  `preprint,12pt,a4paper` options.
- `preview.tex`: wrapper for the Elsevier CRC-styled reading copy.
- `SoftwareX.pdf`: CRC-styled reading copy for visual review. The exact final
  ScienceDirect layout is applied by Elsevier after acceptance.
- `workflow.tex` and `workflow.pdf`: configuration-to-results workflow figure.
- `exposure_modes.tex` and `exposure_modes.pdf`: near- and far-field setup figure.
- `near_field_campaign.tex` and `near_field_campaign.pdf`: coverage and solver-load figure for the completed 352-job near-field campaign.
- `run_directory.tex` and `run_directory.pdf`: representative files in a completed scenario directory.
- `monitoring_and_output.tex` and `monitoring_and_output.pdf`: monitoring and output overview.
- `monitoring_worker_crop.png`, `point_sensor_plot.png`, and `phantom_renders/`:
  raster assets referenced by the manuscript and figures.
- `references.bib`: manuscript references.

The complete running text is about 2,600 words by `texcount`. SoftwareX sets a 3,000-word limit for the descriptive paper.

## Template note

Published ScienceDirect PDFs use Elsevier's production system. The public
submission source therefore uses the standard `elsarticle` author class. The
CRC-styled PDF is a reading copy and should only be submitted if the editors
request that format.

- https://www.elsevier.com/researcher/author/tools-and-resources/research-elements-journals
- https://www.elsevier.com/en-in/researcher/author/policies-and-guidelines/latex-instructions

## Build

From this directory:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error workflow.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error exposure_modes.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error near_field_campaign.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error run_directory.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error monitoring_and_output.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=SoftwareX preview.tex
```
