"""
Debug helpers for TFRepair.

We keep this tiny and dependency-free so it can be imported from worker
processes without side effects.
"""

import os


def _truthy(value: str) -> bool:
    v = (value or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def is_debug_matching_enabled(explicit: bool | None = None) -> bool:
    """
    Decide whether to print verbose matching diagnostics.

    Enable via:
      - explicit=True passed from CLI, or
      - env var TFREPAIR_DEBUG_MATCHING=1/true/yes/on
    """
    if explicit is not None:
        return bool(explicit)
    return _truthy(os.getenv("TFREPAIR_DEBUG_MATCHING", ""))


def dprint(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg)

