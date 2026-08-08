# Release guide

GOLIAT releases are built from an annotated version tag on `master`. The
release workflow validates the tag and project metadata, builds the wheel and
source distribution, uploads the same artifacts to PyPI, and publishes the
GitHub release only after the PyPI upload succeeds.

Do not create or move a release tag until the release commit is final.

## Prepare the release commit

1. Start from a clean, up-to-date `master` and confirm CI, lint, documentation,
   and tests pass.
2. Choose the next semantic version and release date.
3. Move the applicable entries from `## [Unreleased]` in `CHANGELOG.md` into a
   dated section such as `## [1.5.0] - 2026-08-08`, leaving a new empty
   `## [Unreleased]` section above it.
4. Set the same version in:

   - `pyproject.toml` under `[project].version`;
   - `CITATION.cff` under `version`, and update `date-released`;
   - the BibTeX citation in `README.md`.

5. Run the release checks:

   ```powershell
   uv lock --check
   uv run pre-commit run --all-files
   uv run pytest
   uv run mkdocs build --clean
   python -m build
   python -m twine check dist/*
   ```

6. Commit the synchronized metadata with a conventional message:

   ```powershell
   git add CHANGELOG.md pyproject.toml CITATION.cff README.md
   git commit -m "chore(release): prepare v1.5.0"
   ```

## Tag and publish

The Release workflow is intentionally disabled between releases. Enable it in
GitHub Actions only after the release commit and credentials are ready. The
repository must provide a valid `PYPI_API_TOKEN` Actions secret.

Push `master` before the tag, then create and push an annotated tag pointing to
the release commit:

```powershell
git push origin master
git tag -a v1.5.0 -m "GOLIAT v1.5.0"
git push origin v1.5.0
```

`.github/workflows/release.yml` then:

1. verifies that the tag is on `master` and that all version metadata agrees;
2. builds and validates the wheel and source distribution;
3. creates or updates a draft GitHub release;
4. uploads the same distributions to PyPI using `--skip-existing`; and
5. publishes the GitHub release only after the PyPI upload succeeds.

The workflow does not commit to `master`, move tags, or use semantic-release.

## Verify the release

- Confirm the GitHub release is public and contains both distributions.
- Confirm the version and metadata on PyPI.
- Install or inspect the uploaded wheel and source distribution.
- Download the source distribution and confirm its version matches the tag.
- Disable the Release workflow again if releases should remain explicitly
  gated.

If publication fails, diagnose the existing tag and draft release before
retrying. Do not delete and recreate a published version or move its tag.
