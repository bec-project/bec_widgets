from ast import literal_eval

from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.config_helper import CONF as DEVICE_CONF_KEYS
from bec_lib.config_helper import ConfigHelper
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
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


class _CommSignals(QObject):
    error = Signal(Exception)
    done = Signal()


class _CommunicateUpdate(QRunnable):

    def __init__(self, config_helper: ConfigHelper, device: str, config: dict) -> None:
        super().__init__()
        self.config_helper = config_helper
        self.device = device
        self.config = config
        self.signals = _CommSignals()

    @SafeSlot()
    def run(self):
        try:
            timeout = self.config_helper.suggested_timeout_s(self.config)
            RID = self.config_helper.send_config_request(
                action="update", config={self.device: self.config}, wait_for_response=False
            )
            logger.info("Waiting for config reply")
            reply = self.config_helper.wait_for_config_reply(RID, timeout=timeout)
            self.config_helper.handle_update_reply(reply, RID, timeout)
            logger.info("Done updating config!")
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.done.emit()


class DeviceConfigDialog(BECWidget, QDialog):
    RPC = False
    applied = Signal()

    def __init__(
        self,
        parent=None,
        device: str | None = None,
        config_helper: ConfigHelper | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, **kwargs)
        self._config_helper = config_helper or ConfigHelper(
            self.client.connector, self.client._service_name
        )
        self.threadpool = QThreadPool()
        self._device = device
        self.setWindowTitle(f"Edit config for: {device}")
        self._container = QStackedLayout()
        self._container.setStackingMode(QStackedLayout.StackAll)

        self._layout = QVBoxLayout()
        user_warning = QLabel(
            "Warning: edit items here at your own risk - minimal validation is applied to the entered values.\n"
            "Items in the deviceConfig dictionary should correspond to python literals, e.g. numbers, lists, strings (including quotes), etc."
        )
        user_warning.setWordWrap(True)
        user_warning.setStyleSheet("QLabel { color: red; }")
        self._layout.addWidget(user_warning)
        self._add_form()
        self._add_overlay()
        self._add_buttons()

        self.setLayout(self._container)
        self._overlay_widget.setVisible(False)

    def _add_form(self):
        self._form_widget = QWidget()
        self._form_widget.setLayout(self._layout)
        self._form = DeviceConfigForm()
        self._layout.addWidget(self._form)

        for row in self._form.enumerate_form_widgets():
            if row.label.property("_model_field_name") in DEVICE_CONF_KEYS.NON_UPDATABLE:
                row.widget._set_pretty_display()

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
        diff = {
            k: v for k, v in new_config.items() if self._initial_config.get(k) != new_config.get(k)
        }
        if diff.get("deviceConfig") is not None:
            # TODO: special cased in some parts of device manager but not others, should
            # be removed in config update as with below issue
            diff["deviceConfig"].pop("device_access", None)
            # TODO: replace when https://github.com/bec-project/bec/issues/528 is resolved
            diff["deviceConfig"] = {
                k: literal_eval(str(v)) for k, v in diff["deviceConfig"].items()
            }
        return diff

    @SafeSlot()
    def apply(self):
        self._process_update_action()
        self.applied.emit()

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
        if self._device is None:
            return
        if config == {}:
            logger.info("No changes made to device config")
            return
        logger.info(f"Sending request to update device config: {config}")

        self._start_waiting_display()
        communicate_update = _CommunicateUpdate(self._config_helper, self._device, config)
        communicate_update.signals.error.connect(self.update_error)
        communicate_update.signals.done.connect(self.update_done)
        self.threadpool.start(communicate_update)

    @SafeSlot()
    def update_done(self):
        self._stop_waiting_display()
        self._fetch_config()
        self._fill_form()

    @SafeSlot(Exception, popup_error=True)
    def update_error(self, e: Exception):
        raise RuntimeError("Failed to update device configuration") from e

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
