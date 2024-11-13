import os
import re
from typing import Optional

from bec_lib.callback_handler import EventType
from pyqtgraph import SignalProxy
from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QListWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.services.device_browser.device_item import DeviceItem


class DeviceBrowser(BECWidget, QWidget):
    device_update: Signal = Signal()
    PLUGIN = True
    ICON_NAME = "lists"

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config=None,
        client=None,
        gui_id: Optional[str] = None,
    ) -> None:
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent)

        self.get_bec_shortcuts()
        self.ui = None
        self.ini_ui()

        self.proxy_device_update = SignalProxy(
            self.ui.filter_input.textChanged, rateLimit=500, slot=self.update_device_list
        )
        self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.device_update.connect(self.update_device_list)

        self.update_device_list()

    def ini_ui(self) -> None:
        """
        Initialize the UI by loading the UI file and setting the layout.
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        ui_file_path = os.path.join(os.path.dirname(__file__), "device_browser.ui")
        self.ui = UILoader(self).loader(ui_file_path)
        layout.addWidget(self.ui)
        self.setLayout(layout)

    def on_device_update(self, action: str, content: dict) -> None:
        """
        Callback for device update events. Triggers the device_update signal.

        Args:
            action (str): The action that triggered the event.
            content (dict): The content of the config update.
        """
        if action in ["add", "remove", "reload"]:
            self.device_update.emit()

    @Slot()
    def update_device_list(self) -> None:
        """
        Update the device list based on the filter input.
        There are two ways to trigger this function:
        1. By changing the text in the filter input.
        2. By emitting the device_update signal.

        Either way, the function will filter the devices based on the filter input text and update the device list.
        """
        filter_text = self.ui.filter_input.text()
        try:
            regex = re.compile(filter_text, re.IGNORECASE)
        except re.error:
            regex = None  # Invalid regex, disable filtering

        dev_list = self.ui.device_list
        dev_list.clear()
        for device in self.dev:
            if regex is None or regex.search(device):
                item = QListWidgetItem(dev_list)
                device_item = DeviceItem(device)

                # pylint: disable=protected-access
                tooltip = self.dev[device]._config.get("description", "")
                device_item.setToolTip(tooltip)
                item.setSizeHint(device_item.sizeHint())
                dev_list.setItemWidget(item, device_item)
                dev_list.addItem(item)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("light")
    widget = DeviceBrowser()
    widget.show()
    sys.exit(app.exec_())
