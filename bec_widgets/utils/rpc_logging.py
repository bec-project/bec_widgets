from __future__ import annotations


def elapsed_seconds(start: float | int | None, stop: float) -> float | None:
    if start is None:
        return None
    try:
        return max(0.0, stop - float(start))
    except (TypeError, ValueError):
        return None


def format_elapsed(elapsed: float | None) -> str:
    if elapsed is None:
        return "unknown"
    return f"{elapsed:.3f}"
