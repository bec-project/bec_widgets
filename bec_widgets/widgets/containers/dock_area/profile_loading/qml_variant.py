"""
QML variant of the profile loading UI (``BEC_PROFILE_LOADING_UI=qml``).

The placeholders and the progress card keep the Python interface of the QWidget variant and host
their QML scenes in a `QQuickWidget`. All placeholders share one QML engine, so only the first one
pays for engine start-up.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QColor
from qtpy.QtQml import QQmlEngine
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.widgets.containers.dock_area.profile_loading.common import (
    loading_palette,
    skeleton_kind,
    skeleton_seed,
)
from bec_widgets.widgets.containers.dock_area.profile_loading.placeholder import DockPlaceholder
from bec_widgets.widgets.containers.dock_area.profile_loading.progress import (
    ProfileLoadProgressBase,
)

_QML_DIR = Path(__file__).resolve().parent / "qml"
_ENGINE: QQmlEngine | None = None


def _shared_engine() -> QQmlEngine:
    global _ENGINE  # pylint: disable=global-statement
    if _ENGINE is None:
        _ENGINE = QQmlEngine()
    return _ENGINE


def _qml_palette() -> dict[str, str]:
    return {key: color.name(QColor.NameFormat.HexArgb) for key, color in loading_palette().items()}


def _quick_widget(parent: QWidget, source: str, properties: dict) -> QQuickWidget:
    view = QQuickWidget(_shared_engine(), parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties(properties)
    view.setSource(QUrl.fromLocalFile(str(_QML_DIR / source)))
    return view


class QmlSkeletonPlaceholder(DockPlaceholder):
    """Placeholder whose skeleton is a QML scene."""

    def __init__(
        self,
        widget_class: str,
        object_name: str,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(widget_class, object_name, icon_name, parent)
        self._view = _quick_widget(
            self,
            "DockSkeleton.qml",
            {
                "widgetClass": widget_class,
                "kind": skeleton_kind(widget_class),
                "seed": skeleton_seed(object_name) % 100000,
                "colors": _qml_palette(),
            },
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        root = self._view.rootObject()
        if root is not None:
            root.loadRequested.connect(lambda: self.load_requested.emit(self.profile_object_name))

    def _on_state_changed(self) -> None:
        root = self._view.rootObject()
        if root is None:
            return
        root.setProperty("loadState", self.state)
        root.setProperty("message", self.message)

    def closeEvent(self, event):  # noqa: N802 - Qt API
        """Unload the scene when the placeholder is replaced."""
        # Stop the shimmer animation right away; the widget is deleted later
        self._view.setSource(QUrl())
        super().closeEvent(event)


class QmlProfileLoadProgress(ProfileLoadProgressBase):
    """Progress card rendered in QML."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._view = _quick_widget(self, "LoadProgress.qml", {"colors": _qml_palette()})
        self._view.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        self._view.setClearColor(Qt.GlobalColor.transparent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        root = self._view.rootObject()
        if root is not None:
            root.cancelRequested.connect(self.cancel_requested.emit)

    def _render(self) -> None:
        root = self._view.rootObject()
        if root is None:
            return
        root.setProperty("colors", _qml_palette())
        root.setProperty("profile", self._profile)
        root.setProperty("subtitle", self.subtitle())
        root.setProperty("fraction", self.fraction())
