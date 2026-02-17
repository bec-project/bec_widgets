"""Utility functions for experiment selection."""

from datetime import datetime
from typing import Literal

from bec_lib.messages import ExperimentInfoMessage


def format_name(info: dict | ExperimentInfoMessage) -> str:
    """Format the name from the experiment info."""
    info = ExperimentInfoMessage.model_validate(info) if isinstance(info, dict) else info
    firstname = info.firstname
    lastname = info.lastname
    return " ".join(part for part in [firstname, lastname] if part)


def format_schedule(
    schedule: list[dict[Literal["start", "end"], str]] | None, as_datetime: bool = False
) -> tuple[str, str] | tuple[datetime | None, datetime | None]:
    """Format the schedule information to display start and end times."""
    if not schedule:
        return (None, None) if as_datetime else ("", "")
    start, end = _pick_schedule_entry(schedule)
    if as_datetime:
        return start, end
    return format_datetime(start), format_datetime(end)


def _pick_schedule_entry(
    schedule: list[dict[Literal["start", "end"], str]],
) -> tuple[datetime | None, datetime | None]:
    """Pick the most relevant schedule entry based on the current time."""
    now = datetime.now()
    candidates = []
    for item in schedule:
        if not item:
            continue
        start_raw = item.get("start")
        parsed = _parse_schedule_start(start_raw)
        if parsed is None:
            continue
        candidates.append((parsed, item))

    if not candidates:
        return None, None

    future = [entry for entry in candidates if entry[0] >= now]
    pool = future or candidates
    chosen_start, chosen_item = min(pool, key=lambda entry: abs(entry[0] - now))
    end_raw = chosen_item.get("end")
    return chosen_start, _parse_schedule_start(end_raw)


def _parse_schedule_start(value) -> datetime | None:
    """Parse a schedule start string into a datetime object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def format_datetime(value) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")
