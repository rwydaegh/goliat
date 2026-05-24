"""Helper for the optional ``run_tag`` simulation-output-isolation feature.

A ``run_tag`` lets simulation variants that share the same physical identity
(phantom/freq/direction/polarization) write to distinct results folders instead
of overwriting each other. The tag is appended as a sanitized ``__{tag}`` suffix
to the per-simulation "placement" folder name.
"""

import re

# Any character outside this set is replaced with '_' so the resulting suffix is
# a safe single path component on both Windows and POSIX.
_TAG_SANITIZE = re.compile(r"[^A-Za-z0-9._-]")


def apply_run_tag(placement_name: str, run_tag: object) -> str:
    """Append a sanitized ``__{run_tag}`` suffix to a placement name.

    Returns ``placement_name`` unchanged when ``run_tag`` is falsy (None or
    empty), not a string, or sanitizes to an empty string (e.g. whitespace-only).
    The sanitizer replaces any character outside ``[A-Za-z0-9._-]`` with ``'_'``.

    ``run_tag`` is typed as ``object`` because it comes straight from the config
    (whose accessor returns a broad type); non-string values are treated as "no
    tag" rather than raising.

    Args:
        placement_name: The base placement/folder component.
        run_tag: The optional run tag from config.

    Returns:
        The (possibly suffixed) placement name.
    """
    if not run_tag or not isinstance(run_tag, str):
        return placement_name
    safe = _TAG_SANITIZE.sub("_", run_tag.strip())
    if not safe:
        return placement_name
    return f"{placement_name}__{safe}"
