from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.devicemanager import DeviceContainer
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import QMimeData, QSize, Qt, Signal
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QApplication, QHBoxLayout, QToolButton, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.widgets.services.device_browser.device_item.device_config_dialog import (
    DeviceConfigDialog,
)
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtGui import QMouseEvent


logger = bec_logger.logger


class DeviceItem(ExpandableGroupFrame):
    broadcast_size_hint = Signal(QSize)

    RPC = False

    def __init__(self, parent, device: str, devices: DeviceContainer, icon: str = "") -> None:
        super().__init__(parent, title=device, expanded=False, icon=icon)
        self.dev = devices
        self._drag_pos = None
        self._expanded_first_time = False
        self._data = None
        self.device = device
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.set_layout(layout)

        self.adjustSize()

    def _create_title_layout(self, title: str, icon: str):
        super()._create_title_layout(title, icon)
        self.edit_button = QToolButton()
        self.edit_button.setIcon(
            material_icon(icon_name="edit", size=(10, 10), convert_to_pixmap=False)
        )
        self._title_layout.insertWidget(self._title_layout.count() - 1, self.edit_button)
        self.edit_button.clicked.connect(self._create_edit_dialog)

    def _create_edit_dialog(self):
        dialog = DeviceConfigDialog(parent=self, device=self.device)
        dialog.accepted.connect(self._reload_config)
        dialog.applied.connect(self._reload_config)
        dialog.open()

    @SafeSlot()
    def switch_expanded_state(self):
        if not self.expanded and not self._expanded_first_time:
            self._expanded_first_time = True
            self.form = DeviceConfigForm(parent=self, pretty_display=True)
            self._contents.layout().addWidget(self.form)
            self._reload_config()
            self.broadcast_size_hint.emit(self.sizeHint())
        super().switch_expanded_state()
        if self._expanded_first_time:
            self.form.adjustSize()
            self.updateGeometry()
            if self._expanded:
                self.form.set_pretty_display_theme()
        self.adjustSize()
        self.broadcast_size_hint.emit(self.sizeHint())

    @SafeSlot(popup_error=True)
    def _reload_config(self, *_):
        self.set_display_config(self.dev[self.device]._config)

    def set_display_config(self, config_dict: dict):
        """Set the displayed information from a device config dict, which must conform to the
        bec_lib.atlas_models.Device config model."""
        self._data = DeviceConfigModel.model_validate(config_dict)
        if self._expanded_first_time:
            self.form.set_data(self._data)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() and Qt.LeftButton):
            return
        if (event.pos() - self._drag_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.device)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        logger.debug("Double Clicked")
        # TODO: Implement double click action for opening the device properties dialog
        return super().mouseDoubleClickEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys
    from unittest.mock import MagicMock

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
        DeviceConfigForm,
    )
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication(sys.argv)
    widget = QWidget()
    layout = QHBoxLayout()
    widget.setLayout(layout)
    mock_config = {
        "name": "Test Device",
        "enabled": True,
        "deviceClass": "FakeDeviceClass",
        "deviceConfig": {"kwarg1": "value1"},
        "readoutPriority": "baseline",
        "description": "A device for testing out a widget",
        "readOnly": True,
        "softwareTrigger": False,
        "deviceTags": {"tag1", "tag2", "tag3"},
        "userParameter": {"some_setting": "some_ value"},
    }
    item = DeviceItem(widget, "Device", {"Device": MagicMock(enabled=True, _config=mock_config)})
    layout.addWidget(DarkModeButton())
    layout.addWidget(item)
    widget.show()
    sys.exit(app.exec_())
