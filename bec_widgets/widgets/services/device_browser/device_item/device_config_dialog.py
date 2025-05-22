import traceback

from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.config_helper import CONF as DEVICE_CONF_KEYS
from bec_lib.config_helper import ConfigHelper
from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

logger = bec_logger.logger


class DeviceConfigDialog(BECWidget, QDialog):
    RPC = False

    def __init__(
        self, parent=None, device: str | None = None, config_helper: ConfigHelper | None = None
    ):
        super().__init__(parent=parent)
        self._config_helper = config_helper or ConfigHelper(
            self.client.connector, self.client._service_name
        )

        self._device = device
        self.setWindowTitle(f"Edit config for: {device}")
        self._container = QStackedLayout()
        self._container.setStackingMode(QStackedLayout.StackAll)

        self._add_form()
        self._add_overlay()
        self._add_buttons()

        self.setLayout(self._container)
        self._overlay_widget.setVisible(False)

    def _add_form(self):
        self._form_widget = QWidget()
        self._layout = QVBoxLayout()
        self._form_widget.setLayout(self._layout)
        self._form = DeviceConfigForm()
        self._layout.addWidget(self._form)

        self._fetch_config()
        self._fill_form()
        self._container.addWidget(self._form_widget)

    def _add_overlay(self):
        self._overlay_widget = QWidget()
        self._overlay_widget.setStyleSheet("background-color:rgba(128,128,128,128);")
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_layout = QVBoxLayout()
        self._overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setLayout(self._overlay_layout)

        self._spinner = SpinnerWidget(parent=self)
        self._spinner.setMinimumSize(QSize(100, 100))
        self._overlay_layout.addWidget(self._spinner)
        self._container.addWidget(self._overlay_widget)

    def _add_buttons(self):
        button_box = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
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
    def apply(self):
        self._process_update_action()

    @SafeSlot()
    def accept(self):
        self._process_update_action()
        return super().accept()

    def _process_update_action(self):
        updated_config = self.updated_config()
        if (device_name := updated_config.get("name")) == "":
            logger.warning("Can't create a device with no name!")
        elif set(updated_config.keys()) & set(DEVICE_CONF_KEYS.NON_UPDATABLE):
            logger.info(
                f"Removing old device {self._device} and adding new device {device_name or self._device} with modified config: {updated_config}"
            )
        else:
            self._update_device_config(updated_config)

    def _update_device_config(self, config: dict):
        if config == {}:
            logger.info("No changes made to device config")
            return
        logger.info(f"Sending request to update device config: {config}")
        try:
            self._start_waiting_display()
            RID = self._config_helper.send_config_request(
                action="update", config={self._device: config}, wait_for_response=False
            )
            reply = self._config_helper.wait_for_config_reply(
                RID, timeout=self._config_helper.suggested_timeout_s(config)
            )
            self._config_helper.handle_update_reply(reply, RID)
            self._stop_waiting_display()
        except Exception as e:
            self._stop_waiting_display()
            logger.error(f"Error updating config: \n {''.join(traceback.format_exception(e))}")
        finally:
            self._fetch_config()
            self._fill_form()

    def _start_waiting_display(self):
        self._overlay_widget.setVisible(True)
        self._spinner.start()
        QApplication.processEvents()

    def _stop_waiting_display(self):
        self._overlay_widget.setVisible(False)
        self._spinner.stop()
        QApplication.processEvents()


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
