import os
import re
from functools import partial
from typing import Callable

import bec_lib
from bec_lib.callback_handler import EventType
from bec_lib.config_helper import ConfigHelper
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ConfigAction, ScanStatusMessage
from bec_qthemes import material_icon
from pyqtgraph import SignalProxy
from qtpy.QtCore import QSize, QThreadPool, Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.services.device_browser.device_item import DeviceItem
from bec_widgets.widgets.services.device_browser.device_item.device_config_dialog import (
    DeviceConfigDialog,
)
from bec_widgets.widgets.services.device_browser.util import map_device_type_to_icon

logger = bec_logger.logger


class DeviceBrowser(BECWidget, QWidget):
    """
    DeviceBrowser is a widget that displays all available devices in the current BEC session.
    """

    devices_changed: Signal = Signal()
    editing_enabled: Signal = Signal(bool)
    device_update: Signal = Signal(str, dict)
    PLUGIN = True
    ICON_NAME = "lists"

    def __init__(
        self,
        parent: QWidget | None = None,
        config=None,
        client=None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self.get_bec_shortcuts()
        self._config_helper = ConfigHelper(self.client.connector, self.client._service_name)
        self._q_threadpool = QThreadPool()
        self.ui = None
        self.init_ui()
        self.dev_list: QListWidget = self.ui.device_list
        self.dev_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.proxy_device_update = SignalProxy(
            self.ui.filter_input.textChanged, rateLimit=500, slot=self.update_device_list
        )
        self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.bec_dispatcher.client.callbacks.register(
            EventType.SCAN_STATUS, self.scan_status_changed
        )
        self._default_config_dir = os.path.abspath(
            os.path.join(os.path.dirname(bec_lib.__file__), "./configs/")
        )

        self.devices_changed.connect(self.update_device_list)

        self.init_warning_label()
        self.init_tool_buttons()

        self.init_device_list()
        self.update_device_list()

    def init_ui(self) -> None:
        """
        Initialize the UI by loading the UI file and setting the layout.
        """
        layout = QVBoxLayout()
        ui_file_path = os.path.join(os.path.dirname(__file__), "device_browser.ui")
        self.ui = UILoader(self).loader(ui_file_path)
        layout.addWidget(self.ui)
        self.setLayout(layout)

    def init_warning_label(self):
        self.ui.scan_running_warning.setText("Warning: editing diabled while scan is running!")
        self.ui.scan_running_warning.setStyleSheet(
            "background-color: #fcba03; color: rgb(0, 0, 0);"
        )
        scan_status = self.bec_dispatcher.client.connector.get(MessageEndpoints.scan_status())
        initial_status = scan_status.status if scan_status is not None else "closed"
        self.set_editing_mode(initial_status not in ["open", "paused"])

    def init_tool_buttons(self):
        def _setup_button(button: QToolButton, icon: str, slot: Callable, tooltip: str = ""):
            button.clicked.connect(slot)
            button.setIcon(material_icon(icon, size=(20, 20), convert_to_pixmap=False))
            button.setToolTip(tooltip)

        _setup_button(self.ui.add_button, "add", self._create_add_dialog, "add new device")
        _setup_button(self.ui.save_button, "save", self._save_to_file, "save config to file")
        _setup_button(
            self.ui.import_button, "input", self._load_from_file, "append/merge config from file"
        )

    def _create_add_dialog(self):
        dialog = DeviceConfigDialog(parent=self, device=None, action="add")
        dialog.open()

    def on_device_update(self, action: ConfigAction, content: dict) -> None:
        """
        Callback for device update events. Triggers the device_update signal.

        Args:
            action (str): The action that triggered the event.
            content (dict): The content of the config update.
        """
        if action in ["add", "remove", "reload"]:
            self.devices_changed.emit()
        if action in ["update", "reload"]:
            self.device_update.emit(action, content)

    def init_device_list(self):
        self.dev_list.clear()
        self._device_items: dict[str, QListWidgetItem] = {}

        with RPCRegister.delayed_broadcast():
            for device, device_obj in self.dev.items():
                self._add_item_to_list(device, device_obj)

    def _add_item_to_list(self, device: str, device_obj):
        def _updatesize(item: QListWidgetItem, device_item: DeviceItem):
            device_item.adjustSize()
            item.setSizeHint(QSize(device_item.width(), device_item.height()))
            logger.debug(f"Adjusting {item} size to {device_item.width(), device_item.height()}")

        def _remove_item(item: QListWidgetItem):
            self.dev_list.takeItem(self.dev_list.row(item))
            del self._device_items[device]
            self.dev_list.sortItems()

        item = QListWidgetItem(self.dev_list)
        device_item = DeviceItem(
            parent=self,
            device=device,
            devices=self.dev,
            icon=map_device_type_to_icon(device_obj),
            config_helper=self._config_helper,
            q_threadpool=self._q_threadpool,
        )
        device_item.expansion_state_changed.connect(partial(_updatesize, item, device_item))
        device_item.imminent_deletion.connect(partial(_remove_item, item))
        self.editing_enabled.connect(device_item.set_editable)
        self.device_update.connect(device_item.config_update)
        tooltip = self.dev[device]._config.get("description", "")
        device_item.setToolTip(tooltip)
        device_item.broadcast_size_hint.connect(item.setSizeHint)
        item.setSizeHint(device_item.sizeHint())

        self.dev_list.setItemWidget(item, device_item)
        self.dev_list.addItem(item)
        self._device_items[device] = item

    @SafeSlot(dict, dict)
    def scan_status_changed(self, scan_info: dict, _: dict):
        """disable editing when scans are running and enable editing when they are finished"""
        msg = ScanStatusMessage.model_validate(scan_info)
        self.set_editing_mode(msg.status not in ["open", "paused"])

    def set_editing_mode(self, enabled: bool):
        self.ui.add_button.setEnabled(enabled)
        self.ui.scan_running_warning.setHidden(enabled)
        self.editing_enabled.emit(enabled)

    @SafeSlot()
    def reset_device_list(self) -> None:
        self.init_device_list()
        self.update_device_list()

    @SafeSlot()
    @SafeSlot(str)
    def update_device_list(self, *_) -> None:
        """
        Update the device list based on the filter input.
        There are two ways to trigger this function:
        1. By changing the text in the filter input.
        2. By emitting the device_update signal.

        Either way, the function will filter the devices based on the filter input text and update the device list.
        """
        filter_text = self.ui.filter_input.text()
        for device in self.dev:
            if device not in self._device_items:
                # it is possible the device has just been added to the config
                self._add_item_to_list(device, self.dev[device])
        try:
            self.regex = re.compile(filter_text, re.IGNORECASE)
        except re.error:
            self.regex = None  # Invalid regex, disable filtering
            for device in self.dev:
                self._device_items[device].setHidden(False)
            return
        for device in self.dev:
            self._device_items[device].setHidden(not self.regex.search(device))

    @SafeSlot()
    def _load_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Update config from file", self._default_config_dir, "Config files (*.yml *.yaml)"
        )
        if file_path:
            self._config_helper.update_session_with_file(file_path)

    @SafeSlot()
    def _save_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save config to file", self._default_config_dir, "Config files (*.yml *.yaml)"
        )
        if file_path:
            self._config_helper.save_current_session(file_path)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import set_theme

    app = QApplication(sys.argv)
    set_theme("light")
    widget = DeviceBrowser()
    widget.show()
    sys.exit(app.exec_())
