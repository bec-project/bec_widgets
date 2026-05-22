from __future__ import annotations

from typing import Any


def format_rpc_payload(value: Any, limit: int = 500) -> str:
    try:
        text = repr(value)
    except Exception as exc:  # pragma: no cover - defensive logging helper
        text = f"<unrepresentable {type(value).__name__}: {exc}>"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


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
