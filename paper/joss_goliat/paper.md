---
title: 'GOLIAT: Configurable near- and far-field RF-EMF dosimetry studies in Sim4Life'
tags:
  - Python
  - electromagnetic dosimetry
  - FDTD
  - Sim4Life
  - reproducible workflows
authors:
  - name: Robin Wydaeghe
    orcid: 0000-0002-1374-0118
    corresponding: true
    email: robin.wydaeghe@ugent.be
    affiliation: 1
  - name: Emmeric Tanghe
    orcid: 0000-0003-0020-6466
    affiliation: 1
  - name: Wout Joseph
    orcid: 0000-0002-8807-0673
    affiliation: 1
affiliations:
  - index: 1
    name: Department of Information Technology, Ghent University - imec, WAVES Research Group, Belgium
    ror: 00cv9y106
date: 7 August 2026
bibliography: paper.bib
header-includes:
  - |
      \usepackage[acronym,nomain,nonumberlist]{glossaries}
      \input{acronyms.tex}
      \glsdisablehyper
---

# Summary

Computer models can estimate how Radiofrequency Electromagnetic Fields (RF-EMFs) deposit
energy in the human body. A study may repeat the same model at many frequencies,
device positions, incident directions, and polarizations. Each case needs a
simulation scene, numerical grid, solver run, extracted result, and analysis
record.

`GOLIAT` is an open-source Python workflow for these repeated studies in
Sim4Life. Users describe a study in hierarchical JavaScript Object Notation (JSON) files. `GOLIAT` validates
the merged settings and expands the study into individual jobs. It then sets up
near-field device scenes or far-field incident-field scenes, runs the jobs
locally or through oSPARC, extracts Specific Absorption Rate (SAR) and Absorbed
Power Density (APD) results, and writes campaign tables and plots. Both exposure
types have the same job identity and result layout.

# Statement of need

\gls{rfemf} dosimetry studies often require hundreds of
\gls{fdtd} simulations [@Hand2008; @Hirata2021]. Researchers
must control the anatomical model, source, frequency, grid, normalization, and
requested quantities in every case. A missed setting or changed file name makes
direct comparison difficult. Large campaigns also need clear progress
records and a way to rerun one failed phase without rebuilding the full study.

Sim4Life has anatomical models, electromagnetic solvers, dosimetry evaluators,
and a Python \gls{api} [@Gosselin2014; @Sim4Life]. Its
interface has the operations for one simulation. However, a study
still needs rules that list cases, set up exposure-specific scenes,
name jobs, choose execution routes, check outputs, and combine results. A
single study script can contain all these rules, but reviewers must then read
program code to find the scientific choices.

`GOLIAT` stores the study choices in validated configuration files. The target
users are dosimetry researchers, device developers, and test laboratories that
run repeated Sim4Life studies. The configuration states the request. Each job
directory records the run. Therefore, users can use one definition for setup,
execution, extraction, and analysis.

Test laboratories can keep a configuration and its job records under change
control for repeated pre-compliance studies. The laboratory still supplies
qualified models, numerical validation, uncertainty analysis, release control,
and its quality system.

# State of the field

The closest alternative is a study-specific program built with the Sim4Life
Python \gls{api}. Through this interface, Sim4Life can create scenes, control the
solver, sweep parameters, run batches, and extract results without the graphical
interface [@Sim4Life]. A custom script can do all these tasks. However,
the script must still define the study: case enumeration, device or
incident-field scenes, normalization, job identity, result records, and
campaign analysis. `GOLIAT` stores these recurring \gls{rfemf} dosimetry choices
in validated configurations and uses the same interfaces for near- and far-field
studies.

Other public tools solve related problems. First, `openEMS` is a free
equivalent-circuit \gls{fdtd} solver with 1 g and 10 g \gls{sar} calculations [@openEMS]. It uses its own geometry,
material, and result stack. Second, `PyAEDT` gives Python access to Ansys
Electronics Desktop [@PyAEDT]. Users can automate its tasks through that
interface.
Third, `Snakemake` schedules file-based tasks across workstations and clusters
[@Koster2012]. It can call a `GOLIAT` command, but it does not define a dosimetry
case. These tools give users a solver, vendor \gls{api}, or scheduler. They do
not have GOLIAT's Sim4Life-specific study layer.

Therefore, `GOLIAT` is a configuration-to-results layer for Sim4Life. It uses
local `iSolve` or oSPARC for the electromagnetic solve [@oSPARC]. It defines
studies, placements, normalization, job records, result schemas, and analysis
rules.

# Software design

The design separates common study management from exposure-specific physics.
The loader merges inherited files, checks the result, and creates the jobs.
Near-field classes place device antenna models relative to anatomical landmarks and
normalize results to input power. Far-field classes create incident plane waves
or beamforming sources and normalize results to incident power density. Shared
components run jobs, record status, track extraction, and analyze campaigns.

![GOLIAT flowchart. The top row shows a study from hierarchical configuration
to analysis. Dashed boxes mark licensed models and external execution
services. Each simulation has a separate configuration, log, and result record.
\label{fig:workflow}](workflow.png){ width=100% }

Reviewers can read validated configuration files without tracing an unrestricted
script. A base file has shared solver, material, and output settings. Smaller files set
the phantoms, sources, frequencies, placements, directions, and polarizations
for one study. `GOLIAT` writes the expanded configuration beside each result.
Thus, users can inspect the exact input without reopening the base files.

Each job has a separate Sim4Life project and result directory. This gives more
files than a single project. However, one solver failure affects one job, and
operators can move jobs across workstations. Setup and extraction can use several \gls{cpu}
processes. Solver jobs can run through local `iSolve` calls, separate workers,
or oSPARC batches. All execution routes use the same job state for progress logs
and deliverable checks.

Extraction writes compact \gls{json}, serialized tissue tables, \gls{html}
reports, and simulation metadata from the Sim4Life results. Campaign analysis
finds these records without reopening every project. It writes detailed and summary \gls{csv} or
Excel tables and groups plots by phantom, frequency, source, placement, and
tissue. The documentation has installation guidance, five tutorials,
configuration references, and an \gls{api} reference
[@GOLIATDocs].

# Research impact statement

`GOLIAT` was developed within the European GOLIAT project and has run two
computational dosimetry campaigns. The near-field campaign has 352 jobs
for two child anatomical models, eight frequencies, and 22 eye, cheek, and
trunk placements. Every expected job directory has its expanded
configuration, logs, and core \gls{sar} results.

The far-field campaign has 550 jobs for two adult and two child anatomical
models at 15 frequencies between 450 MHz and 26 GHz. Its cases use environmental
plane waves or auto-induced exposure. The *Physics in Medicine & Biology* article
used the campaign's numerical data and tables
[@Wydaeghe2026]. Its postprocessed data and configuration family are being
available in Harvard Dataverse [@WydaegheData2026]. Together, the completed campaigns
have 902 job records with the same configuration, execution, extraction, and
analysis structure.

The software is distributed through the Python Package Index and has public
documentation [@GOLIATSoftware; @GOLIATDocs]. Local scene construction and
solver execution require a licensed Sim4Life installation and licensed anatomical
models. The repository tests configuration handling, job management, and
license-free analysis functions without those assets.

# \glsentryshort{ai} usage disclosure

During preparation of this work, the authors used \gls{ai} for language editing and
preparation of the paper figure. The authors reviewed and edited the text and
checked the software claims. The authors take full responsibility for the
manuscript.

# Conflict of interest

The authors declare no financial, personal, or professional conflict of
interest related to this submission.

# Acknowledgements

The authors thank Bryn Lloyd of ZMT Zurich MedTech AG for feedback through
GitHub issues and pull requests. They also thank him for supporting GOLIAT's
addition to the official oSPARC client documentation and for proposing its
addition to the official Sim4Life documentation. The GOLIAT project received
funding from the European Union's Horizon Europe research and innovation
programme under grant agreement No. 101057262. The funding bodies had no role in
the software design, analysis, or decision to publish.

# References
