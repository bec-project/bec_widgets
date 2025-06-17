import os
import re
from functools import partial

from bec_lib.callback_handler import EventType
from bec_lib.logger import bec_logger
from bec_lib.messages import ConfigAction
from pyqtgraph import SignalProxy
from qtpy.QtCore import QSize, Signal
from qtpy.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.services.device_browser.device_item import DeviceItem
from bec_widgets.widgets.services.device_browser.util import map_device_type_to_icon

logger = bec_logger.logger


class DeviceBrowser(BECWidget, QWidget):
    """
    DeviceBrowser is a widget that displays all available devices in the current BEC session.
    """

    device_update: Signal = Signal()
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
        self.ui = None
        self.ini_ui()
        self.dev_list: QListWidget = self.ui.device_list
        self.dev_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.proxy_device_update = SignalProxy(
            self.ui.filter_input.textChanged, rateLimit=500, slot=self.update_device_list
        )
        self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.device_update.connect(self.update_device_list)

        self.init_device_list()
        self.update_device_list()

    def ini_ui(self) -> None:
        """
        Initialize the UI by loading the UI file and setting the layout.
        """
        layout = QVBoxLayout()
        ui_file_path = os.path.join(os.path.dirname(__file__), "device_browser.ui")
        self.ui = UILoader(self).loader(ui_file_path)
        layout.addWidget(self.ui)
        self.setLayout(layout)

    def on_device_update(self, action: ConfigAction, content: dict) -> None:
        """
        Callback for device update events. Triggers the device_update signal.

        Args:
            action (str): The action that triggered the event.
            content (dict): The content of the config update.
        """
        if action in ["add", "remove", "reload"]:
            self.device_update.emit()

    def init_device_list(self):
        self.dev_list.clear()
        self._device_items: dict[str, QListWidgetItem] = {}

        def _updatesize(item: QListWidgetItem, device_item: DeviceItem):
            device_item.adjustSize()
            item.setSizeHint(QSize(device_item.width(), device_item.height()))
            logger.debug(f"Adjusting {item} size to {device_item.width(), device_item.height()}")

        with RPCRegister.delayed_broadcast():
            for device, device_obj in self.dev.items():
                item = QListWidgetItem(self.dev_list)
                device_item = DeviceItem(
                    parent=self,
                    device=device,
                    devices=self.dev,
                    icon=map_device_type_to_icon(device_obj),
                )
                device_item.expansion_state_changed.connect(partial(_updatesize, item, device_item))
                tooltip = self.dev[device]._config.get("description", "")
                device_item.setToolTip(tooltip)
                device_item.broadcast_size_hint.connect(item.setSizeHint)
                item.setSizeHint(device_item.sizeHint())

                self.dev_list.setItemWidget(item, device_item)
                self.dev_list.addItem(item)
                self._device_items[device] = item

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
        try:
            self.regex = re.compile(filter_text, re.IGNORECASE)
        except re.error:
            self.regex = None  # Invalid regex, disable filtering
            for device in self.dev:
                self._device_items[device].setHidden(False)
            return
        for device in self.dev:
            self._device_items[device].setHidden(not self.regex.search(device))


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import set_theme

    app = QApplication(sys.argv)
    set_theme("light")
    widget = DeviceBrowser()
    widget.show()
    sys.exit(app.exec_())
