"""Tours, steps and the progress store of the tour guide."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from qtpy.QtCore import QRect, QSettings
from qtpy.QtGui import QAction
from qtpy.QtWidgets import QWidget

#: What a step can point at: a widget, an action, a rectangle in main-window coordinates, an object
#: with ``get_toolbar_button()`` (toolbar actions) or a callable returning one of those.
StepTarget = QWidget | QAction | QRect | Callable[[], object] | object | None


@dataclass
class TourStep:
    """One step of a tour.

    Args:
        title(str): Short title of the step.
        text(str): One or two sentences explaining what the target is for.
        target(StepTarget): What to highlight. None shows the card centred, without a spotlight.
        view(str | None): View the step lives in; the guide switches to it before the step.
        hint(str): Optional "try it" line telling the user what to do with the target. The target
            stays clickable during every step.
        available(Callable[[], bool] | None): Predicate deciding whether the step is part of the
            tour at all, evaluated when the tour starts (e.g. only in experimental mode).
    """

    title: str
    text: str
    target: StepTarget = None
    view: str | None = None
    hint: str = ""
    available: Callable[[], bool] | None = None


@dataclass
class Tour:
    """A short, task-focused tour.

    Args:
        id(str): Unique id, used for progress and the command palette.
        title(str): Task-style title, e.g. "Build a workspace".
        summary(str): One sentence saying what the user will be able to do afterwards.
        steps(list[TourStep]): Three to six steps.
        icon(str): Material icon name.
        view(str | None): View the tour belongs to; entering it the first time offers the tour.
        order(int): Sort order in the tour list.
    """

    id: str
    title: str
    summary: str
    steps: list[TourStep] = field(default_factory=list)
    icon: str = "explore"
    view: str | None = None
    order: int = 100

    def available_steps(self) -> list[TourStep]:
        """Steps whose ``available`` predicate passes."""
        return [step for step in self.steps if step.available is None or step.available()]

    @property
    def minutes(self) -> int:
        """Rough duration, about 15 s per step, at least one minute."""
        return max(1, round(len(self.available_steps()) * 15 / 60))


class TourProgress:
    """Remembers finished tours, where an unfinished tour stopped and which offers were seen.

    Stored in ``QSettings`` under ``tour_guide/``, so it survives restarts and is per user.

    Args:
        settings(QSettings | None): Store to use; the application's default settings if None.
    """

    GROUP = "tour_guide"

    def __init__(self, settings: QSettings | None = None):
        self._settings = settings if settings is not None else QSettings("bec", "bec_widgets")

    def _key(self, name: str) -> str:
        return f"{self.GROUP}/{name}"

    def _list(self, name: str) -> list[str]:
        value = self._settings.value(self._key(name), [])
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    def _set_list(self, name: str, values: list[str]) -> None:
        self._settings.setValue(self._key(name), list(dict.fromkeys(values)))
        self._settings.sync()

    def completed(self) -> list[str]:
        """Ids of finished tours."""
        return self._list("completed")

    def is_completed(self, tour_id: str) -> bool:
        """Whether the tour was finished at least once."""
        return tour_id in self.completed()

    def mark_completed(self, tour_id: str) -> None:
        """Remember that the tour was finished and forget its resume position."""
        self._set_list("completed", [*self.completed(), tour_id])
        self.clear_position(tour_id)

    def position(self, tour_id: str) -> int | None:
        """Step index where the tour was left, or None."""
        value = self._settings.value(self._key(f"position/{tour_id}"), None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def save_position(self, tour_id: str, index: int) -> None:
        """Remember the step index to resume from."""
        self._settings.setValue(self._key(f"position/{tour_id}"), int(index))
        self._settings.sync()

    def clear_position(self, tour_id: str) -> None:
        """Forget the resume position."""
        self._settings.remove(self._key(f"position/{tour_id}"))
        self._settings.sync()

    @property
    def welcome_dismissed(self) -> bool:
        """Whether the first-run welcome card was turned off."""
        value = self._settings.value(self._key("welcome_dismissed"), False)
        return value in (True, "true", "1", 1)

    @welcome_dismissed.setter
    def welcome_dismissed(self, value: bool) -> None:
        self._settings.setValue(self._key("welcome_dismissed"), bool(value))
        self._settings.sync()

    def offered(self) -> list[str]:
        """Ids of tours whose view hint was already shown."""
        return self._list("offered")

    def mark_offered(self, tour_id: str) -> None:
        """Remember that the view hint of the tour was shown."""
        self._set_list("offered", [*self.offered(), tour_id])

    def reset(self) -> None:
        """Forget everything (used by "Reset tour progress")."""
        self._settings.remove(self.GROUP)
        self._settings.sync()
