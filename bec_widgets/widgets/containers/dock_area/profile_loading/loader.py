"""
Progressive profile loading.

Loading a profile used to build every widget, add each one as a dock and then restore the Qt ADS
layout with the real widgets inside, all in one call on the GUI thread. Restoring the layout around
real widgets is the most expensive step, because every plot re-lays itself out as the docks move.

`ProfileLoadJob` splits the work:

1. Skeleton: one lightweight placeholder dock per manifest entry, then the saved layout is restored
   around them. This is cheap and puts the final layout on screen right away.
2. Fill: the real widgets are built one per event-loop pass and swapped into their docks in place,
   so the GUI keeps painting and responding between widgets. Visible docks fill first.

A job can also run to completion synchronously (for scripted and RPC calls that expect the
widgets to exist when `load_profile` returns).
"""

# The job is the dock area's own helper and drives its private dock-building methods.
# pylint: disable=protected-access
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bec_lib import bec_logger
from qtpy.QtCore import QObject, QSettings, QTimer, Signal
from shiboken6 import isValid

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets.utils.plugin_utils import get_rpc_widget
from bec_widgets.utils.rpc_register import RPCRegister
from bec_widgets.utils.rpc_widget_handler import widget_handler
from bec_widgets.widgets.containers.dock_area.profile_loading.common import loading_ui_variant
from bec_widgets.widgets.containers.dock_area.profile_loading.placeholder import (
    DockPlaceholder,
    SkeletonPlaceholder,
)
from bec_widgets.widgets.containers.dock_area.profile_loading.progress import (
    ProfileLoadProgress,
    ProfileLoadProgressBase,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

logger = bec_logger.logger


def _widget_icon_name(widget_class: str) -> str | None:
    try:
        cls = get_rpc_widget(widget_class, raise_on_missing=False)
    # A broken plugin import must not stop the skeleton
    except Exception:  # pragma: no cover  # pylint: disable=broad-exception-caught
        return None
    return getattr(cls, "ICON_NAME", None) if cls is not None else None


def create_placeholder(widget_class: str, object_name: str, parent=None) -> DockPlaceholder:
    """Create a placeholder in the configured UI variant."""
    icon_name = _widget_icon_name(widget_class)
    if loading_ui_variant() == "qml":
        from bec_widgets.widgets.containers.dock_area.profile_loading.qml_variant import (
            QmlSkeletonPlaceholder,
        )

        return QmlSkeletonPlaceholder(widget_class, object_name, icon_name, parent)
    return SkeletonPlaceholder(widget_class, object_name, icon_name, parent)


def create_progress(parent) -> ProfileLoadProgressBase:
    """Create the progress card in the configured UI variant."""
    if loading_ui_variant() == "qml":
        from bec_widgets.widgets.containers.dock_area.profile_loading.qml_variant import (
            QmlProfileLoadProgress,
        )

        return QmlProfileLoadProgress(parent)
    return ProfileLoadProgress(parent)


class ProfileLoadJob(QObject):
    """
    Build a profile's docks as placeholders, restore the layout, then fill the docks.

    Args:
        area(BECDockArea): Dock area to load into; it must be empty.
        settings(QSettings): Profile settings; kept open until the job is gone.
        items(list[dict]): Manifest entries from `read_manifest`.
        profile_name(str): Profile name, for progress reporting.
        state_keys(dict): Settings keys passed to `load_from_settings`.
    """

    progress = Signal(int, int, str)
    finished = Signal(bool)

    def __init__(
        self,
        area: "BECDockArea",
        settings: QSettings,
        items: list[dict[str, Any]],
        profile_name: str,
        state_keys: dict[str, str | None],
    ):
        super().__init__(area)
        self.area = area
        self.settings = settings
        self.profile_name = profile_name
        self._items = items
        self._state_keys = state_keys
        self._queue: list[str] = []
        self._done = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._step)

    # Public API -------------------------------------------------------------------------------

    @property
    def total(self) -> int:
        """Number of docks in the profile."""
        return len(self._items)

    @property
    def is_running(self) -> bool:
        """True while docks are being filled in the background."""
        return self._running

    def build_skeleton(self) -> None:
        """Create the placeholder docks and restore the saved layout around them."""
        area = self.area
        area._begin_dock_batch()
        try:
            for item in self._items:
                obj_name = item["object_name"]
                if obj_name in area.dock_map():
                    continue
                placeholder = create_placeholder(item["widget_class"], obj_name, parent=area)
                placeholder.load_requested.connect(self.fill)
                floating_state = None
                if item.get("floating"):
                    floating_state = {
                        "relative": item.get("floating_relative"),
                        "absolute": item.get("floating_absolute"),
                        "screen_name": item.get("floating_screen"),
                    }
                area._make_dock(
                    placeholder,
                    closable=item["closable"],
                    floatable=item["floatable"],
                    movable=item["movable"],
                    start_floating=item.get("floating", False),
                    floating_state=floating_state,
                    area=QtAds.DockWidgetArea.RightDockWidgetArea,
                )
            area.load_from_settings(self.settings, keys=self._state_keys)
        finally:
            area._end_dock_batch()
        # Restores the dock area's own properties; placeholders opt out of the state manager
        area.state_manager.load_state(settings=self.settings)
        self._queue = self._fill_order()

    def start(self) -> None:
        """Fill the docks one per event-loop pass."""
        self._running = True
        self.progress.emit(self._done, self.total, self._next_label())
        self._timer.start()

    def run_to_completion(self, paint: bool = False) -> None:
        """
        Fill every remaining dock now, without returning to the event loop.

        Args:
            paint(bool): Repaint each dock right after it is filled, so a visible dock area shows
                the docks appearing even though the event loop is blocked.
        """
        self._timer.stop()
        self._running = True
        with RPCRegister.delayed_broadcast():
            while self._queue:
                dock = self.fill(self._queue[0], emit=False)
                if paint and dock is not None and dock.isVisible():
                    dock.repaint()
        self._complete()

    def cancel(self) -> None:
        """Stop filling; docks that are not built yet offer a "Load now" button."""
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        for obj_name in self._queue:
            placeholder = self._placeholder(obj_name)
            if placeholder is not None:
                placeholder.set_state("paused")
        self.finished.emit(False)

    def pending_placeholders(self) -> list[DockPlaceholder]:
        """Placeholders that still stand in for unbuilt widgets."""
        return [
            dock.widget()
            for dock in self.area.dock_list()
            if isValid(dock) and isinstance(dock.widget(), DockPlaceholder)
        ]

    def fill(self, obj_name: str, emit: bool = True):
        """
        Build the real widget for *obj_name* and swap it into its dock.

        Args:
            obj_name(str): Object name of the dock to fill.
            emit(bool): Emit progress after filling.

        Returns:
            CDockWidget | None: The filled dock, or None if there was nothing to fill.
        """
        if obj_name in self._queue:
            self._queue.remove(obj_name)
        dock = self.area.dock_map().get(obj_name)
        placeholder = self._placeholder(obj_name)
        if dock is None or placeholder is None:
            return None
        placeholder.set_state("loading")
        try:
            widget = widget_handler.create_widget(
                widget_type=placeholder.profile_widget_class, parent=self.area
            )
            widget.setObjectName(obj_name)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # One broken widget must not abort the whole profile
            logger.exception(
                f"Could not create '{placeholder.profile_widget_class}' for {obj_name}"
            )
            placeholder.set_state("failed", str(exc) or exc.__class__.__name__)
            return None
        self.area._replace_dock_widget(dock, widget)
        placeholder.close()
        placeholder.deleteLater()
        self.area.state_manager.load_widget_state(widget, self.settings)
        self._done += 1
        if emit:
            self.progress.emit(self._done, self.total, self._next_label())
        return dock

    # Internals -------------------------------------------------------------------------------

    def _placeholder(self, obj_name: str) -> DockPlaceholder | None:
        dock = self.area.dock_map().get(obj_name)
        if dock is None or not isValid(dock):
            return None
        widget = dock.widget()
        return widget if isinstance(widget, DockPlaceholder) and isValid(widget) else None

    def _fill_order(self) -> list[str]:
        """Docks the user can see first, then hidden tabs and closed docks."""
        visible, hidden = [], []
        for item in self._items:
            obj_name = item["object_name"]
            placeholder = self._placeholder(obj_name)
            if placeholder is None:
                continue
            dock = self.area.dock_map()[obj_name]
            shown = not dock.isClosed() and dock.isCurrentTab()
            (visible if shown else hidden).append(obj_name)
        return visible + hidden

    def _next_label(self) -> str:
        placeholder = self._placeholder(self._queue[0]) if self._queue else None
        return placeholder.profile_widget_class if placeholder is not None else ""

    def _step(self) -> None:
        if not self._running:
            return
        if not self._queue:
            self._complete()
            return
        with RPCRegister.delayed_broadcast():
            self.fill(self._queue[0])
        # Mark the next dock now, so it paints as loading before its widget blocks the loop
        upcoming = self._placeholder(self._queue[0]) if self._queue else None
        if upcoming is not None:
            upcoming.set_state("loading")
        self._timer.start()

    def _complete(self) -> None:
        self._running = False
        self.progress.emit(self._done, self.total, "")
        self.finished.emit(True)
