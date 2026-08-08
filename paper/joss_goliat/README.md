# JOSS manuscript

This directory contains a separate JOSS paper. JOSS requires Markdown source,
so `paper.md` is the submission manuscript. It is not a shortened LaTeX copy of
the SoftwareX paper.

`workflow.tex` is the source for the compact JOSS flowchart. Its natural width
matches the JOSS text column, so the paper can place `workflow.png` at full
width without shrinking the figure labels below the body font size.

## Current JOSS requirements checked

- 750--1750 words.
- Required sections: Summary, Statement of need, State of the field, Software
  design, Research impact statement, AI usage disclosure, Acknowledgements, and
  References.
- The repository and paper must use an OSI-approved license and remain publicly
  accessible for review.
- Reviewers assess installation, documentation, examples, tests, contribution
  guidance, development history, collaborative effort, and research impact.
- The submission uses a tagged version and an archive DOI.

Official guidance:

- https://joss.readthedocs.io/en/latest/submitting.html
- https://joss.readthedocs.io/en/latest/paper.html
- https://joss.readthedocs.io/en/latest/review_criteria.html
- https://joss.readthedocs.io/en/latest/review_checklist.html

## Build

The official JOSS build uses the `openjournals/inara` container. On Linux, run:

```text
docker run --rm \
  --volume <absolute-path-to-this-directory>:/data \
  --user $(id -u):$(id -g) \
  --env JOURNAL=joss \
  openjournals/inara
```
