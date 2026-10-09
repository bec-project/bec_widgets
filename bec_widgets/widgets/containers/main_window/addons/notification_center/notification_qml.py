"""Notification toasts, history drawer and bell rendered with Qt Quick (QML).

Same UX as :mod:`notification_qwidget`; the state comes from
:class:`~.notification_ux_common.NotificationHostBase`.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Qt, Signal, Slot
from qtpy.QtQuickWidgets import QQuickWidget

from bec_widgets.utils.quick import DictListModel, create_quick_widget, release_quick_widget
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
    NotificationHostBase,
)

QML_DIR = Path(__file__).parent / "qml"

ROW_ROLES = [
    "entryId",
    "severity",
    "severityLabel",
    "icon",
    "color",
    "tint",
    "title",
    "body",
    "details",
    "hasDetails",
    "source",
    "meta",
    "time",
    "timeAbs",
    "firstAbs",
    "scan",
    "count",
    "unread",
    "needsAck",
    "critical",
]


class NotificationBackend(QObject):
    """Bridge between :class:`NotificationHostQML` and its three QML views."""

    changed = Signal()

    def __init__(self, host: NotificationHostQML):
        super().__init__(host)
        self._host = host
        self._state: dict = {}
        self._toasts = DictListModel(ROW_ROLES, self)
        self._rows = DictListModel(ROW_ROLES, self)

    def update_from(self, state: dict) -> None:
        """Take a new view state from the host."""
        state = dict(state)
        self._toasts.set_items(state.pop("toasts"))
        self._rows.set_items(state.pop("rows"))
        state["selected"] = state["selected"] or {}
        self._state = state
        self.changed.emit()

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot()
    def toggleDrawer(self) -> None:
        self._host.toggle_drawer()

    @Slot(bool)
    def setDrawerOpen(self, open_: bool) -> None:
        self._host.set_drawer_open(open_)

    @Slot(str)
    def openDetails(self, entry_id: str) -> None:
        self._host.open_details(entry_id)

    @Slot(str)
    def select(self, entry_id: str) -> None:
        self._host.select(entry_id or None)

    @Slot(str)
    def setFilter(self, key: str) -> None:
        self._host.set_filter(key)

    @Slot(str)
    def setSearch(self, text: str) -> None:
        self._host.set_search(text)

    @Slot(str)
    def acknowledge(self, entry_id: str) -> None:
        self._host.acknowledge(entry_id)

    @Slot(str)
    def remove(self, entry_id: str) -> None:
        self._host.remove(entry_id)

    @Slot(str)
    def dismissToast(self, entry_id: str) -> None:
        self._host.dismiss_toast(entry_id)

    @Slot(str, result=bool)
    def copyDetails(self, entry_id: str) -> bool:
        return self._host.copy_details(entry_id)

    @Slot()
    def markAllRead(self) -> None:
        self._host.mark_all_read()

    @Slot()
    def clearHistory(self) -> None:
        self._host.clear_history()

    @Slot(bool)
    def setHovered(self, hovered: bool) -> None:
        self._host.set_toasts_hovered(hovered)

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    toasts = Property(QObject, lambda self: self._toasts, constant=True)
    rows = Property(QObject, lambda self: self._rows, constant=True)


class NotificationHostQML(NotificationHostBase):
    """Notification UI rendered in QML. See :class:`NotificationHostBase`."""

    def _create_views(self) -> None:
        self.backend = NotificationBackend(self)
        props = {"backend": self.backend}
        # toasts float over the window content: a transparent view stacked on top
        self.toasts = create_quick_widget(self.window, QML_DIR / "NotificationToasts.qml", props)
        self.toasts.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.toasts.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.toasts.setClearColor(Qt.GlobalColor.transparent)
        self.toasts.hide()
        self.drawer = create_quick_widget(self.window, QML_DIR / "NotificationDrawer.qml", props)
        self.drawer.hide()
        self.bell = None
        if self.status_bar is not None:
            self.bell = create_quick_widget(
                self.status_bar, QML_DIR / "NotificationBell.qml", props
            )
            self.bell.setFixedSize(36, 24)
            self.bell.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
            self.status_bar.addPermanentWidget(self.bell)
        root = self.toasts.rootObject()
        if root is not None:
            root.implicitHeightChanged.connect(self._place_views)

    def _sync_views(self, state: dict) -> None:
        self.backend.update_from(state)
        self.toasts.setVisible(bool(state["toasts"]))
        self.drawer.setVisible(state["drawerOpen"])

    def _place_views(self, *_args) -> None:
        if self.drawer.isVisible() and not self.drawer_docked:
            self.drawer.setGeometry(self.drawer_geometry())
            self.drawer.raise_()
        if self.toasts.isVisible():
            root = self.toasts.rootObject()
            height = int(root.property("implicitHeight")) if root is not None else 0
            rect = self.toast_geometry(max(0, height - 16))
            self.toasts.setGeometry(rect.adjusted(-8, -8, 8, 8) & self.window.rect())
            self.toasts.raise_()

    def _apply_theme(self) -> None:
        if self.bell is not None:
            self.bell.setClearColor(self.status_bar.palette().window().color())
        self.drawer.setClearColor(self.window.palette().window().color())

    def _destroy_views(self) -> None:
        for view in (self.toasts, self.drawer, self.bell):
            if view is None:
                continue
            release_quick_widget(view)
            view.hide()
            view.deleteLater()
