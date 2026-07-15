"""Compatibility wrapper for the shared course cost meter.

Older Lab 5 snippets imported `estimate()` from this file. The current course
uses `../shared/cost_meter.py` directly, but this wrapper keeps old imports
working.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from cost_meter import estimate_session_cost  # noqa: E402


def estimate(model: str, usage) -> float:
    """Return token-only estimated cost for legacy Lab 5 snippets."""

    class _Session:
        pass

    session = _Session()
    session.usage = usage
    session.stats = None
    return float(estimate_session_cost(session, model)["total_cost"])
