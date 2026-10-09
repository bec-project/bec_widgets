"""The tour guide: short task tours, a tour list, a first-run welcome and a "What's this?" mode.

The guide owns the logic; an overlay (QWidget or QML, same look) only draws the state the guide
hands it and reports what the user clicked. See ``bec_widgets/utils/tour_guide/README.md``.
"""

from __future__ import annotations

import os
from typing import Callable

from bec_lib.logger import bec_logger
from qtpy.QtCore import QEvent, QObject, QRect, QSettings, Qt, QTimer, Signal
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.tour_guide.geometry import BLOCKING_MODES, spotlight, target_rect
from bec_widgets.utils.tour_guide.model import StepTarget, Tour, TourProgress, TourStep

logger = bec_logger.logger

#: Environment variable choosing the overlay technology: ``qwidget`` (default) or ``qml``.
UI_ENV = "BEC_TOUR_UI"


def tour_ui_from_env() -> str | None:
    """The overlay chosen with ``BEC_TOUR_UI`` (``qwidget`` or ``qml``), or None if unset."""
    value = os.environ.get(UI_ENV, "").strip().lower()
    return value if value in ("qwidget", "qml") else None


class TourGuide(QObject):
    """Runs tours over a window and keeps track of what the user has seen.

    Entry points the guide provides:

    * :meth:`maybe_show_welcome`: a first-run card offering the tours, pointing at the help button.
    * :meth:`open_hub`: the tour list with progress, resume and replay (F1).
    * :meth:`toggle_whats_this`: outlines every documented control; click one to read about it.
    * :meth:`notify_view_entered`: offers a view's tour the first time the view is opened.
    * :meth:`palette_commands` and :meth:`welcome_items`: hooks for the command palette and the
      welcome screen.

    Args:
        window(QWidget): Window the overlay covers, usually the main window.
        ui(str): ``"qwidget"`` or ``"qml"``.
        settings(QSettings | None): Where progress is stored; the default user settings if None.
        view_switcher(Callable[[str], object] | None): Called with a view id before a step that
            lives in another view.
        current_view(Callable[[], str | None] | None): Returns the id of the visible view.
    """

    tour_started = Signal(str)
    tour_finished = Signal(str, bool)  # tour id, completed
    step_changed = Signal(str, int, int)  # tour id, index, count
    mode_changed = Signal(str)

    def __init__(
        self,
        window: QWidget,
        *,
        ui: str = "qwidget",
        settings: QSettings | None = None,
        view_switcher: Callable[[str], object] | None = None,
        current_view: Callable[[], str | None] | None = None,
    ):
        super().__init__(window)
        self._window = window
        self._ui = ui
        self.progress = TourProgress(settings)
        self._view_switcher = view_switcher
        self._current_view = current_view
        self._tours: dict[str, Tour] = {}
        self._help: list[TourStep] = []
        self._help_anchor: StepTarget = None
        self._overlay = None
        self._mode = "hidden"
        self._tour: Tour | None = None
        self._steps: list[TourStep] = []
        self._index = 0
        self._spot: QRect | None = None
        self._hint_tour: str | None = None
        self._selected_anchor = -1
        self._anchors: list[dict] = []
        self._last_finished: str | None = None
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(250)
        self._follow_timer.timeout.connect(self._follow_target)
        self._shortcuts: list[QShortcut] = []
        self._create_shortcuts()
        window.installEventFilter(self)

    # ------------------------------------------------------------------ registry
    def register_tour(self, tour: Tour) -> Tour:
        """Add a tour, replacing one with the same id."""
        self._tours[tour.id] = tour
        return tour

    def tours(self) -> list[Tour]:
        """Registered tours that have at least one available step, in display order."""
        tours = [tour for tour in self._tours.values() if tour.available_steps()]
        return sorted(tours, key=lambda tour: (tour.order, tour.title))

    def tour(self, tour_id: str) -> Tour | None:
        """The tour with this id, or None."""
        return self._tours.get(tour_id)

    def register_help(self, target: StepTarget, title: str, text: str, view: str | None = None):
        """Document a control for "What's this?" without making it part of a tour."""
        self._help.append(TourStep(title=title, text=text, target=target, view=view))

    def set_help_anchor(self, target: StepTarget) -> None:
        """Control the welcome card and view hints point at, typically the Help button."""
        self._help_anchor = target

    @property
    def mode(self) -> str:
        """``hidden``, ``welcome``, ``hint``, ``hub``, ``step``, ``done`` or ``whatsthis``."""
        return self._mode

    @property
    def is_active(self) -> bool:
        """Whether a tour is running."""
        return self._mode == "step"

    @property
    def current_tour(self) -> Tour | None:
        """The running tour."""
        return self._tour if self._mode == "step" else None

    @property
    def current_index(self) -> int:
        """Index of the current step among the tour's available steps."""
        return self._index

    @property
    def overlay(self):
        """The overlay widget, created on first use."""
        if self._overlay is None:
            self._overlay = self._create_overlay()
        return self._overlay

    # ------------------------------------------------------------------ status per tour
    def tour_status(self, tour: Tour) -> dict:
        """Status of a tour for lists: ``new``, ``in_progress`` or ``done`` plus its progress."""
        count = len(tour.available_steps())
        position = self.progress.position(tour.id)
        if position is not None and 0 < position < count:
            return {
                "status": "in_progress",
                "position": position,
                "progress": position / count,
                "label": f"Step {position + 1} of {count}",
            }
        if self.progress.is_completed(tour.id):
            return {"status": "done", "position": 0, "progress": 1.0, "label": "Done"}
        return {"status": "new", "position": 0, "progress": 0.0, "label": "New"}

    def suggested_tour(self, exclude: str | None = None) -> Tour | None:
        """First tour that is not finished yet, preferring one in progress."""
        tours = [tour for tour in self.tours() if tour.id != exclude]
        for wanted in ("in_progress", "new"):
            for tour in tours:
                if self.tour_status(tour)["status"] == wanted:
                    return tour
        return None

    # ------------------------------------------------------------------ entry points
    @SafeSlot()
    def maybe_show_welcome(self) -> bool:
        """Show the first-run welcome card unless it was turned off or something else is open."""
        if self.progress.welcome_dismissed or self._mode != "hidden" or not self.tours():
            return False
        if all(self.tour_status(tour)["status"] == "done" for tour in self.tours()):
            return False
        self._set_mode("welcome")
        return True

    @SafeSlot()
    def show_welcome(self) -> None:
        """Show the welcome card even if it was dismissed before."""
        self._end_tour(save=True)
        self._set_mode("welcome")

    @SafeSlot()
    def open_hub(self) -> None:
        """Show the list of tours."""
        self._end_tour(save=True)
        self._set_mode("hub")

    @SafeSlot()
    def toggle_whats_this(self) -> None:
        """Enter or leave "What's this?" mode."""
        if self._mode == "whatsthis":
            self.close()
            return
        self._end_tour(save=True)
        self._selected_anchor = -1
        self._set_mode("whatsthis")

    @SafeSlot(str)
    def notify_view_entered(self, view_id: str) -> None:
        """Offer the tour of a view the first time the view is opened."""
        if self._mode != "hidden" or not view_id:
            return
        for tour in self.tours():
            if tour.view != view_id or tour.id in self.progress.offered():
                continue
            if self.tour_status(tour)["status"] != "new":
                continue
            self.progress.mark_offered(tour.id)
            self._hint_tour = tour.id
            self._set_mode("hint")
            return

    def palette_commands(self) -> list[dict]:
        """Commands for the command palette, one per tour plus the tour list and "What's this?".

        Each entry has ``uid``, ``title``, ``subtitle``, ``icon``, ``category``, ``keywords`` and
        ``callback``, the fields of ``PaletteCommand``.
        """
        commands = [
            {
                "uid": "tour:hub",
                "title": "Show tours",
                "subtitle": "Learn BEC with short guided tours",
                "icon": "school",
                "category": "help",
                "keywords": "help guide tutorial onboarding learn tour",
                "callback": self.open_hub,
            },
            {
                "uid": "tour:whatsthis",
                "title": "What's this?",
                "subtitle": "Click any control to learn what it does",
                "icon": "help_center",
                "category": "help",
                "keywords": "help explain identify control",
                "callback": self.toggle_whats_this,
            },
        ]
        for tour in self.tours():
            status = self.tour_status(tour)
            verb = "Resume" if status["status"] == "in_progress" else "Tour"
            commands.append(
                {
                    "uid": f"tour:{tour.id}",
                    "title": f"{verb}: {tour.title}",
                    "subtitle": f"{len(tour.available_steps())} steps · {status['label']}",
                    "icon": tour.icon,
                    "category": "help",
                    "keywords": f"help guide tutorial tour {tour.summary}",
                    "callback": lambda tid=tour.id: self.resume_tour(tid),
                }
            )
        return commands

    def welcome_items(self) -> list[dict]:
        """Tours as cards for a welcome screen: id, title, summary, icon, steps, status, progress
        and a ``start`` callback (resumes a tour in progress)."""
        items = []
        for tour in self.tours():
            status = self.tour_status(tour)
            items.append(
                {
                    "id": tour.id,
                    "title": tour.title,
                    "summary": tour.summary,
                    "icon": tour.icon,
                    "steps": len(tour.available_steps()),
                    "minutes": tour.minutes,
                    **status,
                    "start": lambda tid=tour.id: self.resume_tour(tid),
                }
            )
        return items

    # ------------------------------------------------------------------ tours
    @SafeSlot(str)
    def start_tour(self, tour_id: str, index: int = 0) -> bool:
        """Start a tour at ``index`` (0 by default).

        Returns:
            bool: False if the tour does not exist or has no available step.
        """
        tour = self._tours.get(tour_id)
        if tour is None:
            logger.warning(f"Unknown tour {tour_id!r}")
            return False
        steps = tour.available_steps()
        if not steps:
            return False
        self._end_tour(save=True)
        self._tour = tour
        self._steps = steps
        self._index = max(0, min(index, len(steps) - 1))
        self._set_mode("step", refresh=False)
        self.tour_started.emit(tour.id)
        self._show_step(direction=1)
        return True

    @SafeSlot(str)
    def resume_tour(self, tour_id: str) -> bool:
        """Start a tour where the user left it, or from the start."""
        tour = self._tours.get(tour_id)
        if tour is None:
            return False
        status = self.tour_status(tour)
        return self.start_tour(
            tour_id, status["position"] if status["status"] == "in_progress" else 0
        )

    @SafeSlot()
    def next_step(self) -> None:
        """Go to the next step, or finish the tour on the last one."""
        if self._mode != "step":
            return
        if self._index >= len(self._steps) - 1:
            self.finish_tour()
            return
        self._index += 1
        self._show_step(direction=1)

    @SafeSlot()
    def prev_step(self) -> None:
        """Go to the previous step."""
        if self._mode != "step" or self._index == 0:
            return
        self._index -= 1
        self._show_step(direction=-1)

    @SafeSlot()
    def finish_tour(self) -> None:
        """Mark the running tour as done and show the completion card."""
        if self._tour is None:
            return
        tour_id = self._tour.id
        self.progress.mark_completed(tour_id)
        self._tour = None
        self._steps = []
        self._last_finished = tour_id
        self.tour_finished.emit(tour_id, True)
        self._set_mode("done")

    @SafeSlot()
    def close(self) -> None:
        """Close whatever is shown. A running tour keeps its position for later."""
        self._end_tour(save=True)
        self._set_mode("hidden")

    @SafeSlot()
    def dismiss_welcome(self) -> None:
        """Turn the first-run welcome card off for good."""
        self.progress.welcome_dismissed = True
        self.close()

    @SafeSlot()
    def reset_progress(self) -> None:
        """Forget finished tours, resume positions and offers."""
        self.progress.reset()
        if self._mode in ("hub", "welcome"):
            self._refresh()

    def _end_tour(self, save: bool) -> None:
        if self._tour is None:
            return
        tour = self._tour
        if save and self._index > 0:
            self.progress.save_position(tour.id, self._index)
        self._tour = None
        self._steps = []
        self.tour_finished.emit(tour.id, False)

    def _show_step(self, direction: int) -> None:
        """Show the current step, skipping steps whose target is not on screen."""
        while 0 <= self._index < len(self._steps):
            step = self._steps[self._index]
            if step.view and self._view_switcher is not None:
                current = self._current_view() if self._current_view else None
                if current != step.view:
                    self._view_switcher(step.view)
                    QApplication.processEvents()
            if step.target is None:
                self._spot = None
                break
            rect = target_rect(step.target, self._window)
            if rect is not None:
                self._spot = spotlight(rect, self._window.rect())
                break
            logger.info(f"Tour step {step.title!r} has no visible target, skipping it")
            del self._steps[self._index]
            if direction < 0:
                self._index -= 1
            self._index = min(self._index, len(self._steps) - 1)
        if not self._steps or self._index < 0:
            self.close()
            return
        if self._tour is not None and self._index > 0:
            self.progress.save_position(self._tour.id, self._index)
        self.step_changed.emit(self._tour.id, self._index, len(self._steps))
        self._refresh()

    def _follow_target(self) -> None:
        """Keep the spotlight on its target while the layout moves (sidebar animation, resize)."""
        if self._mode != "step" or not self._steps:
            return
        step = self._steps[self._index]
        if step.target is None:
            return
        rect = target_rect(step.target, self._window)
        spot = spotlight(rect, self._window.rect()) if rect is not None else None
        if spot is not None and spot != self._spot:
            self._spot = spot
            self._refresh()

    # ------------------------------------------------------------------ what's this
    def _collect_anchors(self) -> list[dict]:
        current = self._current_view() if self._current_view else None
        anchors: list[dict] = []
        seen: list[QRect] = []

        def add(step: TourStep, tour: Tour | None):
            if step.view and current and step.view != current:
                return
            if step.target is None:
                return
            try:
                rect = target_rect(step.target, self._window)
            except Exception:  # pylint: disable=broad-except
                return
            if rect is None or any(rect == other for other in seen):
                return
            window_area = max(1, self._window.width() * self._window.height())
            if rect.width() * rect.height() > 0.4 * window_area:
                return  # whole areas would hide the controls inside them
            seen.append(rect)
            anchors.append(
                {
                    "rect": rect,
                    "title": step.title,
                    "text": step.text,
                    "tour_id": tour.id if tour else "",
                    "tour_title": tour.title if tour else "",
                }
            )

        for tour in self.tours():
            for step in tour.available_steps():
                add(step, tour)
        for step in self._help:
            add(step, None)
        return anchors

    def select_anchor(self, index: int) -> None:
        """Show the explanation of the ``index``-th documented control in "What's this?"."""
        if self._mode != "whatsthis":
            return
        self._selected_anchor = index if 0 <= index < len(self._anchors) else -1
        self._refresh(collect=False)

    # ------------------------------------------------------------------ overlay state
    def state(self) -> dict:
        """Everything the overlay draws, as plain data. Rectangles are in window coordinates."""
        mode = self._mode
        state: dict = {"mode": mode, "spot": None, "anchor": None}
        if mode in ("welcome", "hint"):
            rect = target_rect(self._help_anchor, self._window) if self._help_anchor else None
            state["anchor"] = rect
        if mode in ("welcome", "hub"):
            tours = self.tours()
            state["tours"] = [
                {
                    "id": tour.id,
                    "title": tour.title,
                    "summary": tour.summary,
                    "icon": tour.icon,
                    "steps": len(tour.available_steps()),
                    "minutes": tour.minutes,
                    **self.tour_status(tour),
                }
                for tour in tours
            ]
            done = sum(1 for item in state["tours"] if item["status"] == "done")
            state["done"] = done
            state["total"] = len(tours)
        if mode == "hint" and self._hint_tour:
            tour = self._tours[self._hint_tour]
            state["tour"] = {
                "id": tour.id,
                "title": tour.title,
                "summary": tour.summary,
                "icon": tour.icon,
                "steps": len(tour.available_steps()),
                "minutes": tour.minutes,
            }
        if mode == "step" and self._steps:
            step = self._steps[self._index]
            state.update(
                spot=self._spot,
                tourId=self._tour.id if self._tour else "",
                tourTitle=self._tour.title if self._tour else "",
                title=step.title,
                text=step.text,
                hint=step.hint,
                index=self._index,
                count=len(self._steps),
            )
        if mode == "done":
            finished = self._tours.get(self._last_finished or "")
            following = self.suggested_tour(exclude=self._last_finished)
            state["finished"] = finished.title if finished else ""
            state["next"] = (
                {
                    "id": following.id,
                    "title": following.title,
                    "steps": len(following.available_steps()),
                }
                if following
                else None
            )
        if mode == "whatsthis":
            state["anchors"] = self._anchors
            state["selected"] = self._selected_anchor
            if 0 <= self._selected_anchor < len(self._anchors):
                state["spot"] = spotlight(
                    self._anchors[self._selected_anchor]["rect"], self._window.rect()
                )
        return state

    def _set_mode(self, mode: str, refresh: bool = True) -> None:
        changed = mode != self._mode
        self._mode = mode
        for shortcut in self._shortcuts:
            shortcut.setEnabled(mode in BLOCKING_MODES)
        if mode == "step":
            self._follow_timer.start()
        else:
            self._follow_timer.stop()
        if refresh:
            self._refresh()
        if changed:
            self.mode_changed.emit(mode)

    def _refresh(self, collect: bool = True) -> None:
        if self._mode == "whatsthis" and collect:
            self._anchors = self._collect_anchors()
        if self._mode == "hidden" and self._overlay is None:
            return
        self.overlay.apply_state(self.state())

    def _create_overlay(self):
        if self._ui == "qml":
            # pylint: disable=import-outside-toplevel
            from bec_widgets.utils.tour_guide.overlay_qml import QmlTourOverlay

            overlay = QmlTourOverlay(self._window)
        else:
            # pylint: disable=import-outside-toplevel
            from bec_widgets.utils.tour_guide.overlay_qwidget import TourOverlay

            overlay = TourOverlay(self._window)
        overlay.triggered.connect(self._on_overlay_action)
        return overlay

    @SafeSlot(str, str)
    def _on_overlay_action(self, action: str, arg: str) -> None:
        handlers: dict[str, Callable[[], object]] = {
            "next": self.next_step,
            "back": self.prev_step,
            "close": self.close,
            "hub": self.open_hub,
            "never": self.dismiss_welcome,
            "whatsthis": self.toggle_whats_this,
            "reset": self.reset_progress,
            "start": lambda: self.start_tour(arg),
            "resume": lambda: self.resume_tour(arg),
            "anchor": lambda: self.select_anchor(int(arg)),
        }
        handler = handlers.get(action)
        if handler is None:
            logger.warning(f"Unknown tour overlay action {action!r}")
            return
        handler()

    # ------------------------------------------------------------------ keyboard and window
    def _create_shortcuts(self) -> None:
        bindings = [
            (Qt.Key.Key_Escape, self._on_escape),
            (Qt.Key.Key_Return, self._on_enter),
            (Qt.Key.Key_Enter, self._on_enter),
            (Qt.Key.Key_Right, self.next_step),
            (Qt.Key.Key_Left, self.prev_step),
            (Qt.Key.Key_Backspace, self.prev_step),
        ]
        for key, slot in bindings:
            shortcut = QShortcut(QKeySequence(key), self._window)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
            shortcut.setEnabled(False)
            self._shortcuts.append(shortcut)

    def _on_escape(self) -> None:
        if self._mode == "whatsthis" and self._selected_anchor >= 0:
            self.select_anchor(-1)
            return
        self.close()

    def _on_enter(self) -> None:
        if self._mode == "step":
            self.next_step()
        elif self._mode == "done":
            self.close()

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        """Follow resizes of the window."""
        if obj is self._window and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            if self._overlay is not None:
                self._overlay.setGeometry(self._window.rect())
            if self._mode == "step":
                self._follow_target()
            elif self._mode != "hidden":
                self._refresh()
        return super().eventFilter(obj, event)

    def cleanup(self) -> None:
        """Stop timers and remove the overlay."""
        self._follow_timer.stop()
        self._window.removeEventFilter(self)
        if self._overlay is not None:
            self._overlay.cleanup()
            self._overlay.deleteLater()
            self._overlay = None
