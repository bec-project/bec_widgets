from ast import literal_eval
from typing import Literal

from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.config_helper import CONF as DEVICE_CONF_KEYS
from bec_lib.config_helper import ConfigHelper
from bec_lib.logger import bec_logger
from pydantic import ValidationError, field_validator
from qtpy.QtCore import QSize, Qt, QThreadPool, Signal
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
from bec_widgets.widgets.services.device_browser.device_item.config_communicator import (
    CommunicateConfigAction,
)
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

logger = bec_logger.logger


def _try_literal_eval(value: str):
    if value == "":
        return ""
    try:
        return literal_eval(value)
    except SyntaxError as e:
        raise ValueError(f"Entered config value {value} is not a valid python value!") from e


class DeviceConfigDialog(BECWidget, QDialog):
    RPC = False
    applied = Signal()

    def __init__(
        self,
        *,
        parent=None,
        device: str | None = None,
        config_helper: ConfigHelper | None = None,
        action: Literal["update", "add"] = "update",
        threadpool: QThreadPool | None = None,
        **kwargs,
    ):
        """A dialog to edit the configuration of a device in BEC. Generated from the pydantic model
        for device specification in bec_lib.atlas_models.

        Args:
            parent (QObject): the parent QObject
            device (str | None): the name of the device. used with the "update" action to prefill the dialog and validate entries.
            config_helper (ConfigHelper | None): a ConfigHelper object for communication with Redis, will be created if necessary.
            action (Literal["update", "add"]): the action which the form should perform on application or acceptance.
        """
        self._initial_config = {}
        super().__init__(parent=parent, **kwargs)
        self._config_helper = config_helper or ConfigHelper(
            self.client.connector, self.client._service_name
        )
        self._device = device
        self._action: Literal["update", "add"] = action
        self._q_threadpool = threadpool or QThreadPool()
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
        self.get_bec_shortcuts()
        self._add_form()
        if self._action == "update":
            self._form._validity.setVisible(False)
        else:
            self._set_schema_to_check_devices()
            # TODO: replace when https://github.com/bec-project/bec/issues/528 https://github.com/bec-project/bec/issues/547 are resolved
            # self._form._validity.setVisible(True)
            self._form.validity_proc.connect(self.enable_buttons_for_validity)
        self._add_overlay()
        self._add_buttons()

        self.setLayout(self._container)
        self._form.validate_form()
        self._overlay_widget.setVisible(False)

    def _set_schema_to_check_devices(self):
        class _NameValidatedConfigModel(DeviceConfigModel):
            @field_validator("name")
            @staticmethod
            def _validate_name(value: str, *_):
                if not value.isidentifier():
                    raise ValueError(
                        f"Invalid device name: {value}. Device names must be valid Python identifiers."
                    )
                if value in self.dev:
                    raise ValueError(f"A device with name {value} already exists!")
                return value

        self._form.set_schema(_NameValidatedConfigModel)

    def _add_form(self):
        self._form_widget = QWidget()
        self._form_widget.setLayout(self._layout)
        self._form = DeviceConfigForm()
        self._layout.addWidget(self._form)

        for row in self._form.enumerate_form_widgets():
            if (
                row.label.property("_model_field_name") in DEVICE_CONF_KEYS.NON_UPDATABLE
                and self._action == "update"
            ):
                row.widget._set_pretty_display()

        if self._action == "update" and self._device in self.dev:
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
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._layout.addWidget(self.button_box)

    def _fetch_config(self):
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
        if self._initial_config.get("deviceConfig") in [{}, None] and new_config.get(
            "deviceConfig"
        ) in [{}, None]:
            diff.pop("deviceConfig", None)
        if diff.get("deviceConfig") is not None:
            # TODO: special cased in some parts of device manager but not others, should
            # be removed in config update as with below issue
            diff["deviceConfig"].pop("device_access", None)
            # TODO: replace when https://github.com/bec-project/bec/issues/528 https://github.com/bec-project/bec/issues/547 are resolved
            diff["deviceConfig"] = {
                k: _try_literal_eval(str(v)) for k, v in diff["deviceConfig"].items() if k != ""
            }

        # Due to above issues, if deviceConfig changes we must remove and recreate the device - so we need the whole config
        if "deviceConfig" in diff:
            new_config["deviceConfig"] = diff["deviceConfig"]
            return new_config
        return diff

    @SafeSlot(bool)
    def enable_buttons_for_validity(self, valid: bool):
        # TODO: replace when https://github.com/bec-project/bec/issues/528 https://github.com/bec-project/bec/issues/547 are resolved
        for button in [
            self.button_box.button(b) for b in [QDialogButtonBox.Apply, QDialogButtonBox.Ok]
        ]:
            button.setEnabled(valid)
            button.setToolTip(self._form._validity_message.text())

    @SafeSlot(popup_error=True)
    def apply(self):
        self._process_action()
        self.applied.emit()

    @SafeSlot(popup_error=True)
    def accept(self):
        self._process_action()
        return super().accept()

    def _process_action(self):
        updated_config = self.updated_config()
        if self._action == "add":
            if (name := updated_config.get("name")) in self.dev:
                raise ValueError(
                    f"Can't create a new device with the same name as already existing device {name}!"
                )
            self._proc_device_config_change(updated_config)
        else:
            if updated_config == {}:
                logger.info("No changes made to device config")
                return
            self._proc_device_config_change(updated_config)

    def _proc_device_config_change(self, config: dict):
        logger.info(f"Sending request to {self._action} device config: {config}")

        self._start_waiting_display()
        communicate_update = CommunicateConfigAction(
            self._config_helper, self._device, config, self._action
        )
        communicate_update.signals.error.connect(self.update_error)
        communicate_update.signals.done.connect(self.update_done)
        self._q_threadpool.start(communicate_update)

    @SafeSlot()
    def update_done(self):
        self._stop_waiting_display()
        if self._action == "update":
            self._fetch_config()
            self._fill_form()

    @SafeSlot(Exception, popup_error=True)
    def update_error(self, e: Exception):
        self._stop_waiting_display()
        if self._action == "update":
            self._fetch_config()
            self._fill_form()
        raise e

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
            kwargs = {"device": dev} if (dev := device.text()) else {"action": "add"}
            dialog = DeviceConfigDialog(**kwargs)
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
