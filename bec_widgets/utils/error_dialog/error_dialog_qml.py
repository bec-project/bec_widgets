"""QML version of the error dialog.

A :class:`~qtpy.QtWidgets.QDialog` hosts a :class:`~qtpy.QtQuickWidgets.QQuickWidget` that renders
``qml/ErrorDialog.qml``. The QWidget twin lives in
:mod:`bec_widgets.utils.error_dialog.error_dialog_qwidget`; both share
:class:`ErrorDialogController`.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QSize, Signal, Slot
from qtpy.QtWidgets import QDialog, QVBoxLayout, QWidget

from bec_widgets.utils.error_dialog.error_dialog_common import (
    ErrorDialogController,
    ErrorDialogWindowMixin,
)
from bec_widgets.utils.quick.host import (
    ThemeTokens,
    create_quick_widget,
    quick_engine,
    release_quick_widget,
)

QML_FILE = Path(__file__).parent / "qml" / "ErrorDialog.qml"


class ErrorDialogBackend(QObject):
    """Expose the controller state and actions to QML."""

    stateChanged = Signal()
    closeRequested = Signal()

    def __init__(self, controller: ErrorDialogController, parent: QObject | None = None):
        super().__init__(parent)
        self.controller = controller
        self._state = controller.view_state()
        controller.changed.connect(self._refresh)

    def _refresh(self) -> None:
        self._state = self.controller.view_state()
        self.stateChanged.emit()

    def _get_state(self) -> dict:
        return self._state

    state = Property("QVariant", _get_state, notify=stateChanged)

    # pylint: disable=missing-function-docstring
    @Slot(str)
    def select(self, error_id: str) -> None:
        self.controller.select(error_id)

    @Slot(int)
    def step(self, delta: int) -> None:
        self.controller.step(delta)

    @Slot()
    def dismiss(self) -> None:
        self.controller.dismiss()

    @Slot()
    def clear(self) -> None:
        self.controller.clear()

    @Slot(bool)
    def setShowLibrary(self, show: bool) -> None:  # pylint: disable=invalid-name
        self.controller.set_show_library(show)

    @Slot(str)
    def setMode(self, mode: str) -> None:  # pylint: disable=invalid-name
        self.controller.set_mode(mode)

    @Slot(str)
    def toggleFrame(self, key: str) -> None:  # pylint: disable=invalid-name
        self.controller.toggle_frame(key)

    @Slot(str)
    def toggleGroup(self, key: str) -> None:  # pylint: disable=invalid-name
        self.controller.toggle_group(key)

    @Slot(result=bool)
    def copyReport(self) -> bool:  # pylint: disable=invalid-name
        return bool(self.controller.copy_report())

    @Slot(result=bool)
    def copyLocation(self) -> bool:  # pylint: disable=invalid-name
        return bool(self.controller.copy_location())

    @Slot()
    def reportIssue(self) -> None:  # pylint: disable=invalid-name
        self.controller.report_issue()

    @Slot()
    def close(self) -> None:
        self.closeRequested.emit()


class ErrorDialogQML(ErrorDialogWindowMixin, QDialog):
    """Resizable error dialog with summary, navigable traceback and an error list (QML)."""

    def __init__(self, parent: QWidget | None = None, controller: ErrorDialogController = None):
        super().__init__(parent)
        self.controller = controller or ErrorDialogController(self)
        self.backend = ErrorDialogBackend(self.controller, self)
        self.backend.closeRequested.connect(self.close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        quick_engine()
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        layout.addWidget(self.view)
        self.init_window()
        self.controller.changed.connect(self._update_title)

    def _update_title(self) -> None:
        current = self.backend.state.get("current")
        if current:
            self.setWindowTitle(f"{current['type']} · {current['title']}")

    def apply_theme(self) -> None:
        """Match the window background to the theme; QML follows the shared theme bridge."""
        tokens = ThemeTokens()
        self.setStyleSheet(f"ErrorDialogQML {{ background: {tokens.bg.name()}; }}")
        if getattr(self, "view", None) is not None:
            self.view.setClearColor(tokens.bg)

    def grab_image(self):
        """Render the QML scene to an image, e.g. for screenshots."""
        return self.view.grabFramebuffer()

    def cleanup(self) -> None:
        """Unload the scene before the backend goes away."""
        release_quick_widget(self.view)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Default size of the dialog."""
        return QSize(960, 680)
