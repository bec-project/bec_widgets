from collections.abc import Iterable, Mapping

from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.control.scan_control.scan_info_dialog import ScanInfoDialog


class _RowCheckBox(QCheckBox):
    """Checkbox whose entire row-sized widget is an activation target."""

    def hitButton(self, position) -> bool:
        return self.isEnabled() and self.rect().contains(position)


class ScanSelectionDialog(QDialog):
    """Dialog for choosing which scans are shown in a scan selector."""

    def __init__(
        self,
        scan_names: Iterable[str],
        selected_scans: Iterable[str],
        scan_docs: Mapping[str, str | None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select available scans")

        self._scan_names = list(scan_names)
        self._scan_docs = dict(scan_docs or {})
        self._scan_checkboxes: dict[str, _RowCheckBox] = {}
        self._scan_info_buttons: dict[str, QToolButton] = {}
        self._scan_info_dialog: ScanInfoDialog | None = None
        selected = set(selected_scans)
        self.scan_list = QListWidget(self)
        self.scan_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for scan_name in self._scan_names:
            item = QListWidgetItem(self.scan_list)
            item.setData(Qt.ItemDataRole.UserRole, scan_name)
            row = QWidget(self.scan_list)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            checkbox = _RowCheckBox(scan_name, row)
            checkbox.setChecked(scan_name in selected)
            checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            row_layout.addWidget(checkbox, 1)

            info_button = QToolButton(row)
            info_button.setAutoRaise(True)
            info_button.setIcon(material_icon("info", size=(18, 18), convert_to_pixmap=False))
            info_button.setToolTip(f"Show information about {scan_name}")
            info_button.setAccessibleName(f"Information for {scan_name}")
            info_button.clicked.connect(
                lambda _checked=False, name=scan_name: self.show_scan_info(name)
            )
            row_layout.addWidget(info_button, 0)

            self._scan_checkboxes[scan_name] = checkbox
            self._scan_info_buttons[scan_name] = info_button
            item.setSizeHint(row.sizeHint())
            self.scan_list.setItemWidget(item, row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.setContentsMargins(4, 4, 4, 4)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.scan_list)
        layout.addWidget(buttons)
        self.resize(360, 420)

    def checkbox_for_scan(self, scan_name: str) -> QCheckBox:
        """Return the checkbox belonging to ``scan_name``."""
        return self._scan_checkboxes[scan_name]

    def info_button_for_scan(self, scan_name: str) -> QToolButton:
        """Return the information button belonging to ``scan_name``."""
        return self._scan_info_buttons[scan_name]

    def show_scan_info(self, scan_name: str) -> None:
        """Show documentation for a scan while keeping this selector open."""
        if self._scan_info_dialog is None:
            self._scan_info_dialog = ScanInfoDialog(self)
        self._scan_info_dialog.show_scan(scan_name, self._scan_docs.get(scan_name))

    def selected_scans(self) -> list[str]:
        """Return checked scans in the same order as displayed."""
        selected = []
        for scan_name in self._scan_names:
            if self._scan_checkboxes[scan_name].isChecked():
                selected.append(scan_name)
        return selected
