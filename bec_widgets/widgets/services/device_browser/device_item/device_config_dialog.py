from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.config_helper import CONF as DEVICE_CONF_KEYS
from bec_lib.config_helper import ConfigHelper
from bec_lib.logger import bec_logger
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)

logger = bec_logger.logger


class DeviceConfigDialog(BECWidget, QDialog):
    RPC = False

    def __init__(
        self, parent=None, device: str | None = None, config_helper: ConfigHelper | None = None
    ):
        super().__init__(parent=parent)
        self._config_helper = config_helper or ConfigHelper(
            self.client.connector, "gui/device_config_dialog"
        )
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._form = DeviceConfigForm()
        self._layout.addWidget(self._form)
        self._device = device
        self._fetch_config()
        self._fill_form()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._layout.addWidget(button_box)

    def _fetch_config(self):
        self._initial_config = {}
        if (
            self.client.device_manager is not None
            and self._device in self.client.device_manager.devices
        ):
            self._initial_config = self.client.device_manager.devices.get(self._device)._config

    def _fill_form(self):
        self._form.set_data(DeviceConfigModel.model_validate(self._initial_config))

    def updated_config(self):
        new_config = self._form.get_form_data()
        return {
            k: v for k, v in new_config.items() if self._initial_config.get(k) != new_config.get(k)
        }

    @SafeSlot()
    def accept(self):
        updated_config = self.updated_config()
        if (device_name := updated_config.get("name")) == "":
            logger.warning("Can't create a device with no name!")
            super().accept()
            return
        if set(updated_config.keys()) & set(DEVICE_CONF_KEYS.NON_UPDATABLE):
            logger.info(
                f"Removing old device {self._device} and adding new device {device_name or self._device} with modified config: {updated_config}"
            )
            super().accept()
            return
        self._update_device_config(updated_config)
        super().accept()
        return

    def _update_device_config(self, config: dict):
        logger.info(f"Sending request to update device config: {config}")
        try:
            self._config_helper.send_config_request(
                action="update", config={config.pop("name"): config}
            )
        except Exception as e:
            logger.error(e)


def main():  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

    from bec_widgets.utils.colors import set_theme

    dialog = None

    app = QApplication(sys.argv)
    set_theme("light")
    widget = QWidget()
    widget.setLayout(QVBoxLayout())

    device = QLineEdit()
    widget.layout().addWidget(device)

    def _destroy_dialog(*_):
        nonlocal dialog
        dialog = None

    def accept(*args):
        logger.success(f"submitted device config form {dialog} {args}")
        _destroy_dialog()

    def _show_dialog(*_):
        nonlocal dialog
        if dialog is None:
            dialog = DeviceConfigDialog(device=device.text())
            dialog.accepted.connect(accept)
            dialog.rejected.connect(_destroy_dialog)
            dialog.open()

    button = QPushButton("Show device dialog")
    widget.layout().addWidget(button)
    button.clicked.connect(_show_dialog)
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
