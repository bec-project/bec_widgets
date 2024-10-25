""" Module for a StatusItem widget to display status and metrics for a BEC service.
The widget is bound to be used with the BECStatusBox widget."""

import enum
import os
from datetime import datetime

from bec_lib.utils.import_utils import lazy_import_from
from bec_qthemes import material_icon
from qtpy.QtCore import Qt, Slot
from qtpy.QtGui import QIcon, QPainter
from qtpy.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import bec_widgets
from bec_widgets.utils.colors import get_accent_colors

# TODO : Put normal imports back when Pydantic gets faster
BECStatus = lazy_import_from("bec_lib.messages", ("BECStatus",))

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class IconsEnum(enum.Enum):
    """Enum class for icons in the status item widget."""

    RUNNING = "done_outline"
    BUSY = "progress_activity"
    IDLE = "progress_activity"
    ERROR = "emergency_home"
    NOTCONNECTED = "signal_disconnected"


class StatusItem(QWidget):
    """A widget to display the status of a service.

    Args:
        parent: The parent widget.
        config (dict): The configuration for the service, must be a BECServiceInfoContainer.
    """

    def __init__(self, parent: QWidget = None, config=None):
        QWidget.__init__(self, parent=parent)
        if config is None:
            # needed because we need parent to be the first argument for QT Designer
            raise ValueError(
                "Please initialize the StatusItem with a BECServiceInfoContainer for config, received None."
            )
        self.accent_colors = get_accent_colors()
        self.config = config
        self.parent = parent
        self.layout = None
        self._label = None
        self._icon = None
        self.icon_size = (24, 24)
        self._popup_label_ref = {}
        self.init_ui()

    def init_ui(self) -> None:
        """Init the UI for the status item widget."""
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.layout)
        self._label = QLabel()
        self._icon = QLabel()
        self.layout.addWidget(self._label)
        self.layout.addWidget(self._icon)
        self.update_ui()

    @Slot(dict)
    def update_config(self, config) -> None:
        """Update the config of the status item widget.

        Args:
            config (dict): Config updates from parent widget, must be a BECServiceInfoContainer.
        """
        if self.config is None or config.service_name != self.config.service_name:
            return
        self.config = config
        self.update_ui()

    def update_ui(self) -> None:
        """Update the UI of the labels, and popup dialog."""
        if self.config is None:
            return
        self.set_text()
        self.set_status()
        self._set_popup_text()

    def set_text(self) -> None:
        """Set the text of the QLabel basae on the config."""
        service = self.config.service_name
        status = self.config.status
        if len(service.split("/")) > 1 and service.split("/")[0].startswith("BEC"):
            service = service.split("/", maxsplit=1)[0] + "/..." + service.split("/")[1][-4:]
        if status == "NOTCONNECTED":
            status = "NOT CONNECTED"
        text = f"{service} is {status}"
        self._label.setText(text)

    def set_status(self) -> None:
        """Set the status icon for the status item widget."""
        status = self.config.status
        if status in ["RUNNING", "BUSY"]:
            color = self.accent_colors.success
        elif status == "IDLE":
            color = self.accent_colors.warning
        elif status in ["ERROR", "NOTCONNECTED"]:
            color = self.accent_colors.emergency
        icon = QIcon(material_icon(IconsEnum[status].value, filled=True, color=color))

        self._icon.setPixmap(icon.pixmap(*self.icon_size))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignRight)

    def show_popup(self) -> None:
        """Method that is invoked when the user double clicks on the StatusItem widget."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self.config.service_name} Details")
        layout = QVBoxLayout()
        popup_label = self._make_popup_label()
        self._set_popup_text()
        layout.addWidget(popup_label)
        dialog.setLayout(layout)
        dialog.finished.connect(self._cleanup_popup_label)
        dialog.exec()

    def _make_popup_label(self) -> QLabel:
        """Create a QLabel for the popup dialog.

        Returns:
            QLabel: The label for the popup dialog.
        """
        label = QLabel()
        label.setWordWrap(True)
        self._popup_label_ref.update({"label": label})
        return label

    def _set_popup_text(self) -> None:
        """Compile the metrics text for the status item widget."""
        if self._popup_label_ref.get("label") is None:
            return
        metrics_text = (
            f"<b>SERVICE:</b> {self.config.service_name}<br><b>STATUS:</b> {self.config.status}<br>"
        )
        metrics_text += f"<b>BEC_LIB VERSION:</b> {self.config.info['version']}<br>"
        if self.config.metrics:
            for key, value in self.config.metrics.items():
                if key == "create_time":
                    value = datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
                metrics_text += f"<b>{key.upper()}:</b> {value}<br>"
        self._popup_label_ref["label"].setText(metrics_text)

    def _cleanup_popup_label(self) -> None:
        """Cleanup the popup label."""
        self._popup_label_ref.clear()
