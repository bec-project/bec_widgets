"""Positioner box rendered with Qt Quick (QML), same API as :class:`PositionerBox`."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Signal, Slot

from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.widgets.control.device_control.positioner_box.positioner_ux_common import (
    PositionerBoxPortBase,
)

QML_FILE = Path(__file__).parent / "qml" / "PositionerBoxView.qml"


class PositionerBackend(QObject):
    """Bridge between :class:`PositionerBoxQML` and ``PositionerBoxView.qml``."""

    changed = Signal()
    positioners_changed = Signal()

    def __init__(self, box: "PositionerBoxQML"):
        super().__init__(box)
        self._box = box
        self._state: dict = {}
        self._positioners: list[str] = []

    def update_from(self, state: dict) -> None:
        """Take a new view state from the box."""
        self._state = state
        self.changed.emit()

    @Slot()
    def refreshPositioners(self) -> None:  # pylint: disable=invalid-name
        """Reload the positioner list, e.g. when the selector opens."""
        names = self._box.positioner_names()
        if names != self._positioners:
            self._positioners = names
            self.positioners_changed.emit()

    @Slot(str)
    def selectDevice(self, name: str) -> None:  # pylint: disable=invalid-name
        """Switch to another positioner."""
        self._box.set_positioner(name)

    @Slot(str, result=str)
    def validate(self, text: str) -> str:
        """Return an error message for a move target or an empty string."""
        return self._box.validate_target(text)

    @Slot(str, result=bool)
    def moveTo(self, text: str) -> bool:  # pylint: disable=invalid-name
        """Request an absolute move."""
        return self._box.move_to(text)

    @Slot(int)
    def tweak(self, direction: int) -> None:
        """Tweak by one step; direction is -1 or 1."""
        if direction < 0:
            self._box.on_tweak_left()
        else:
            self._box.on_tweak_right()

    @Slot(float)
    def setStep(self, step: float) -> None:  # pylint: disable=invalid-name
        """Change the tweak step."""
        self._box.step_size = step

    @Slot()
    def stop(self) -> None:
        """Stop the positioner."""
        self._box.on_stop()

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    positioners = Property(
        "QStringList", lambda self: self._positioners, notify=positioners_changed
    )


class PositionerBoxQML(PositionerBoxPortBase):
    """Positioner box with the modernised UX rendered in QML."""

    def _init_view(self) -> None:
        self.backend = PositionerBackend(self)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.view.setMinimumSize(260, 250)
        self.main_layout.addWidget(self.view)

    def _sync_view(self) -> None:
        self.backend.update_from(self.view_state())

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        self.view.setClearColor(self.palette().window().color())

    def cleanup(self):
        release_quick_widget(self.view)
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = PositionerBoxQML(device="samx")
    widget.show()
    sys.exit(app.exec())
