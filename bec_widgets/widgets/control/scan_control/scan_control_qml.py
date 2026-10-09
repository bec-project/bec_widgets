"""Scan control rendered with Qt Quick (QML), same API as :class:`ScanControl`."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Signal, Slot
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.widgets.control.scan_control.scan_control_ux_common import ScanControlPortBase

QML_FILE = Path(__file__).parent / "qml" / "ScanControlView.qml"


class ScanControlBackend(QObject):
    """Bridge between :class:`ScanControlQML` and ``ScanControlView.qml``."""

    changed = Signal()
    structure_changed = Signal()

    def __init__(self, control: "ScanControlQML"):
        super().__init__(control)
        self._control = control
        self._state: dict = {}
        self._groups: list = []
        self._devices: list[str] = []

    def update_from(self, control: ScanControlPortBase, structure: bool) -> None:
        """Copy the control state; the field structure only when it changed."""
        self._state = control.view_state()
        if structure:
            self._groups = control.form.groups()
            self._devices = control._device_names()  # pylint: disable=protected-access
            self.structure_changed.emit()
        self.changed.emit()

    @Slot(str)
    def selectScan(self, name: str) -> None:  # pylint: disable=invalid-name
        """Switch to another scan."""
        self._control.on_scan_selection_changed(name)

    @Slot(str, "QVariant")
    def setField(self, key: str, value) -> None:  # pylint: disable=invalid-name
        """Store an edited field value."""
        self._control.set_field(key, value)

    @Slot()
    def addRow(self) -> None:  # pylint: disable=invalid-name
        """Add an argument row."""
        self._control.add_row()

    @Slot(int)
    def removeRow(self, index: int) -> None:  # pylint: disable=invalid-name
        """Remove an argument row."""
        self._control.remove_row(index)

    @Slot()
    def run(self) -> None:
        """Start the scan."""
        self._control.run_scan()

    @Slot()
    def stop(self) -> None:
        """Stop the running scan."""
        self._control.stop_scan()

    @Slot()
    def restoreLast(self) -> None:  # pylint: disable=invalid-name
        """Load the parameters of the last run of this scan."""
        self._control.request_last_executed_scan_parameters()

    @Slot()
    def openInfo(self) -> None:  # pylint: disable=invalid-name
        """Show the scan documentation."""
        self._control.show_selected_scan_info()

    @Slot()
    def openFilter(self) -> None:  # pylint: disable=invalid-name
        """Choose the scans shown in the selector."""
        self._control.show_scan_selector_settings()

    @Slot()
    def openMetadata(self) -> None:  # pylint: disable=invalid-name
        """Edit the scan metadata."""
        self._control.show_metadata_dialog()

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    groups = Property("QVariantList", lambda self: self._groups, notify=structure_changed)
    devices = Property("QStringList", lambda self: self._devices, notify=structure_changed)


class ScanControlQML(ScanControlPortBase):
    """Scan control with the modernised UX rendered in QML."""

    def _init_view(self) -> None:
        self.backend = ScanControlBackend(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.view.setMinimumSize(320, 360)
        layout.addWidget(self.view)

    def _sync_view(self, structure: bool) -> None:
        if hasattr(self, "backend"):
            self.backend.update_from(self, structure)

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
    widget = ScanControlQML()
    widget.show()
    sys.exit(app.exec())
