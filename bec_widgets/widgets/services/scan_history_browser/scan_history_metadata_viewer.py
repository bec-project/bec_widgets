from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.error_popups import SafeSlot

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import ScanHistoryMessage

logger = bec_logger.logger


class ScanHistoryMetadataViewer(BECWidget, QtWidgets.QGroupBox):
    """ScanHistoryView is a widget to display the metadata of a ScanHistoryMessage in a structured format."""

    def __init__(
        self,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        theme_update: bool = True,
        scan_history_msg: ScanHistoryMessage | None = None,
        parent=None,
    ):
        super().__init__(
            parent=parent, client=client, config=config, gui_id=gui_id, theme_update=theme_update
        )
        self._scan_history_msg_labels = {
            "scan_id": "Scan ID",
            "dataset_number": "Dataset Nr",
            "file_path": "File Path",
            "start_time": "Start Time",
            "end_time": "End Time",
            "elapsed_time": "Elapsed Time",
            "exit_status": "Status",
            "scan_name": "Scan Name",
            "num_points": "Nr of Points",
        }
        self.setTitle("No Scan Selected")
        # self.setMinimumHeight(100)
        # self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self._init_grid_layout()
        self.scan_history_msg = scan_history_msg
        if scan_history_msg is not None:
            self.update_view(self.scan_history_msg)
        self.apply_theme()

    def apply_theme(self, theme: str | None = None):
        """Apply the theme to the widget."""
        colors = get_theme_palette()
        palette = QtGui.QPalette()
        palette.setColor(self.backgroundRole(), colors.midlight().color())
        self.setPalette(palette)

    def _init_grid_layout(self):
        """Initialize the layout of the widget."""
        layout: QtWidgets.QGridLayout = self.layout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(0)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)

    def setup_content_widget_label(self) -> None:
        """Setup the labels for the content widget for the scan history view."""
        layout = self.layout()
        for row, k in enumerate(self._scan_history_msg_labels.keys()):
            v = self._scan_history_msg_labels[k]
            # Label for the key
            label = QtWidgets.QLabel(f"{v}:")
            # label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
            layout.addWidget(label, row, 0)
            # Value field
            value_field = QtWidgets.QLabel("")
            value_field.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred
            )
            layout.addWidget(value_field, row, 1)  # Placeholder for value
            # Copy button
            copy_button = QtWidgets.QToolButton()
            copy_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
            copy_button.setContentsMargins(0, 0, 0, 0)
            copy_button.setStyleSheet("padding: 0px; margin: 0px; border: none;")
            copy_button.setIcon(material_icon(icon_name="content_copy", size=(16, 16)))
            copy_button.setToolTip("Copy to clipboard")
            copy_button.setVisible(False)
            copy_button.setEnabled(False)  # Initially disabled
            copy_button.clicked.connect(
                lambda _, field=value_field: QtWidgets.QApplication.clipboard().setText(
                    field.text()
                )
            )
            layout.addWidget(copy_button, row, 2)  # Placeholder for copy button

    @SafeSlot()
    def update_view(self, msg: ScanHistoryMessage):
        """
        Update the view with the given ScanHistoryMessage.

        Args:
            msg (ScanHistoryMessage): The message containing scan metadata.
        """
        if msg == self.scan_history_msg:
            return  # Same message, no update needed
        self.scan_history_msg = msg
        layout = self.layout()
        if layout.count() == 0:
            self.setup_content_widget_label()
        self.setTitle(f"Metadata - Scan {msg.scan_number}")
        for row, k in enumerate(self._scan_history_msg_labels.keys()):
            if k == "elapsed_time":
                value = (
                    f"{(msg.end_time - msg.start_time):.3f}s"
                    if msg.start_time and msg.end_time
                    else None
                )
            else:
                value = getattr(msg, k, None)
                if k in ["start_time", "end_time"]:
                    value = (
                        datetime.fromtimestamp(value).strftime("%a %b %d %H:%M:%S %Y")
                        if value
                        else None
                    )
            if value is None:
                logger.warning(f"ScanHistoryMessage missing value for {k} and msg {msg}.")
                continue
            layout.itemAtPosition(row, 1).widget().setText(str(value))
            if k in ["file_path", "scan_id"]:
                layout.itemAtPosition(row, 2).widget().setVisible(True)
                layout.itemAtPosition(row, 2).widget().setEnabled(True)
            else:
                layout.itemAtPosition(row, 2).widget().setText("")
                layout.itemAtPosition(row, 2).widget().setToolTip("")

    @SafeSlot()
    def clear_view(self, msg: ScanHistoryMessage | None = None):
        """
        Clear the view by resetting the labels and values.
        """
        if self.scan_history_msg is not None and msg != self.scan_history_msg:
            return
        layout = self.layout()
        lauout_counts = layout.count()
        for i in range(lauout_counts):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().close()
                item.widget().deleteLater()
        self.scan_history_msg = None
        self.setTitle("No Scan Selected")
