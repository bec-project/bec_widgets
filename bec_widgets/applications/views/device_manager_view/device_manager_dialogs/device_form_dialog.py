"""Dialogs for device configuration forms and ophyd testing."""

from typing import Any, Iterable, Tuple

from bec_lib.atlas_models import Device as DeviceModel
from bec_lib.logger import bec_logger
from ophyd_devices.interfaces.device_config_templates.ophyd_templates import OPHYD_DEVICE_TEMPLATES
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components import OphydValidation
from bec_widgets.widgets.control.device_manager.components.device_config_template.device_config_template import (
    DeviceConfigTemplate,
)
from bec_widgets.widgets.control.device_manager.components.device_config_template.template_items import (
    validate_name,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    format_error_to_md,
)

DEFAULT_DEVICE = "CustomDevice"
_ValidationResultIter = Iterable[Tuple[dict[str, Any], ConfigStatus, ConnectionStatus, str]]


logger = bec_logger.logger


class DeviceManagerOphydValidationDialog(QtWidgets.QDialog):
    """Popup dialog to test Ophyd device configurations interactively."""

    def __init__(self, parent=None, config: dict | None = None):  # type:ignore
        super().__init__(parent)
        self.setWindowTitle("Device Manager Ophyd Test")
        self._config_status = ConfigStatus.UNKNOWN.value
        self._connection_status = ConnectionStatus.UNKNOWN.value
        self._validated_config: dict = {}
        self._validation_msg: str = ""

        layout = QtWidgets.QVBoxLayout(self)

        # Core test widget
        self.device_manager_ophyd_test = OphydValidation()
        layout.addWidget(self.device_manager_ophyd_test)

        # Log/Markdown box for messages
        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setReadOnly(True)
        layout.addWidget(self.text_box)

        # Load and apply configuration
        config = config or {}
        device_name = config.get("name", None)
        if device_name:
            self.device_manager_ophyd_test.add_device_to_keep_visible_after_validation(device_name)

        self.device_manager_ophyd_test.change_device_configs([config], True, True)

        # Dialog Buttons: equal size, stacked horizontally
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        for button in button_box.buttons():
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
            )
            button.clicked.connect(self.accept)
        # button_box.setCenterButtons(False)
        layout.addWidget(button_box)
        self.device_manager_ophyd_test.validation_completed.connect(self._on_device_validated)
        self._resize_dialog()
        self.finished.connect(self._finished)

    def _resize_dialog(self):
        """Resize the dialog based on the screen size."""
        app: QtCore.QCoreApplication = QtWidgets.QApplication.instance()
        screen = app.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        # 70% of screen height, keep 4:3 ratio
        height = int(screen_height * 0.7)
        width = int(height * (4 / 3))

        # If width exceeds screen width, scale down
        if width > screen_width * 0.9:
            width = int(screen_width * 0.9)
            height = int(width / (4 / 3))

        self.resize(width, height)

    def _on_device_validated(
        self, device_config: dict, config_status: int, connection_status: int, validation_msg: str
    ):
        device_name = device_config.get("name", "")
        self._config_status = config_status
        self._connection_status = connection_status
        self._validated_config = device_config
        self._validation_msg = validation_msg
        self.text_box.setMarkdown(format_error_to_md(device_name, validation_msg))

    @SafeSlot(int)
    def _finished(self, state: int):
        self.device_manager_ophyd_test.close()
        self.device_manager_ophyd_test.deleteLater()

    @property
    def validation_result(self) -> tuple[dict, int, int, str]:
        """
        Return the result of the validation as a tuple of

        Returns:
            result (Tuple[dict, int, int]): A tuple containing:
                                            validated_config (dict): The validated device configuration.
                                            config_status (int): The configuration status.
                                            connection_status (int): The connection status.

        """
        return (
            self._validated_config,
            self._config_status,
            self._connection_status,
            self._validation_msg,
        )


class DeviceFormDialog(QtWidgets.QDialog):

    # Signal emitted when device configuration is accepted, only
    # emitted when the user clicks the "Add Device" button
    # The integer values indicate if the device config was
    # validated: config_status, connection_status
    accepted_data = QtCore.Signal(dict, int, int, str, str)

    def __init__(self, parent=None, add_btn_text: str = "Add Device"):  # type:ignore
        super().__init__(parent)
        # Track old device name if config is edited
        self._old_device_name: str = ""

        # Config validation result
        self._validation_result: tuple[dict, int, int, str] = (
            {},
            ConfigStatus.UNKNOWN.value,
            ConnectionStatus.UNKNOWN.value,
            "",
        )
        # Group to variants mapping
        self._group_variants: dict[str, list[str]] = {
            group: [variant for variant in variants.keys()]
            for group, variants in OPHYD_DEVICE_TEMPLATES.items()
        }

        self._control_widgets: dict[str, QtWidgets.QWidget] = {}

        # Setup layout
        self.setWindowTitle("Device Config Dialog")
        layout = QtWidgets.QVBoxLayout(self)

        # Control panel
        self._control_box = self.create_control_panel()
        layout.addWidget(self._control_box)

        # Device config template display
        self._device_config_template = DeviceConfigTemplate(parent=self)
        self._frame = QtWidgets.QFrame()
        self._frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._frame.setFrameShadow(QtWidgets.QFrame.Raised)
        frame_layout = QtWidgets.QVBoxLayout(self._frame)
        frame_layout.addWidget(self._device_config_template)
        layout.addWidget(self._frame)

        # Custom buttons
        self.add_btn = QtWidgets.QPushButton(add_btn_text)
        self.test_connection_btn = QtWidgets.QPushButton("Test Connection")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.reset_btn = QtWidgets.QPushButton("Reset Form")

        btn_layout = QtWidgets.QHBoxLayout()
        for btn in (self.cancel_btn, self.reset_btn, self.test_connection_btn, self.add_btn):
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            btn_layout.addWidget(btn)
        btn_box = QtWidgets.QGroupBox("Actions")
        btn_box.setLayout(btn_layout)
        frame_layout.addWidget(btn_box)

        # Connect signals to explicit slots
        self.add_btn.clicked.connect(self._add_config)
        self.test_connection_btn.clicked.connect(self._test_connection)
        self.reset_btn.clicked.connect(self._reset_config)
        self.cancel_btn.clicked.connect(self._reject_config)

        # layout.addWidget(self._device_config_template)
        self.update_variant_combo(self._control_widgets["group_combo"].currentText())
        self.finished.connect(self._finished)

        # Wait dialog when adding config
        self._wait_dialog: QtWidgets.QProgressDialog | None = None

    @SafeSlot(int)
    def _finished(self, state: int):
        for widget in self._control_widgets.values():
            widget.close()
            widget.deleteLater()
        if self._wait_dialog is not None:
            self._wait_dialog.close()
            self._wait_dialog.deleteLater()

    @property
    def config_validation_result(self) -> tuple[dict, int, int, str]:
        """Return the result of the last configuration validation."""
        return self._validation_result

    @config_validation_result.setter
    def config_validation_result(self, result: tuple[dict, int, int, str]):
        self._validation_result = result

    def set_device_config(self, device_config: dict):
        """Set the device configuration in the template form."""
        # Figure out which group and variant this config belongs to
        device_class = device_config.get("deviceClass", None)
        for group, variants in OPHYD_DEVICE_TEMPLATES.items():
            for variant, template_info in variants.items():
                if template_info.get("deviceClass", None) == device_class:
                    # Found the matching group and variant
                    self._control_widgets["group_combo"].setCurrentText(group)
                    self.update_variant_combo(group)
                    self._control_widgets["variant_combo"].setCurrentText(variant)
                    self._device_config_template.set_config_fields(device_config)
                    return
        # If no match found, set to default
        self._control_widgets["group_combo"].setCurrentText(DEFAULT_DEVICE)
        self.update_variant_combo(DEFAULT_DEVICE)
        self._device_config_template.set_config_fields(device_config)
        self._old_device_name = device_config.get("name", "")

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(1600, 1000)

    def create_control_panel(self) -> QtWidgets.QGroupBox:
        self._control_box = QtWidgets.QGroupBox("Choose a Device Group")
        layout = QtWidgets.QGridLayout(self._control_box)

        group_label = QtWidgets.QLabel("Device Group:")
        layout.addWidget(group_label, 0, 0)

        group_combo = QtWidgets.QComboBox()
        group_combo.addItems(self._group_variants.keys())
        self._control_widgets["group_combo"] = group_combo
        layout.addWidget(group_combo, 1, 0)

        variant_label = QtWidgets.QLabel("Variants:")
        layout.addWidget(variant_label, 0, 1)

        variant_combo = QtWidgets.QComboBox()
        self._control_widgets["variant_combo"] = variant_combo
        layout.addWidget(variant_combo, 1, 1)

        group_combo.currentTextChanged.connect(self.update_variant_combo)
        variant_combo.currentTextChanged.connect(self.update_device_config_template)

        return self._control_box

    def update_variant_combo(self, group_name: str):
        variant_combo = self._control_widgets["variant_combo"]
        variant_combo.clear()
        variant_combo.addItems(self._group_variants.get(group_name, []))
        if variant_combo.count() <= 1:
            variant_combo.setEnabled(False)
        else:
            variant_combo.setEnabled(True)

    def update_device_config_template(self, variant_name: str):
        group_name = self._control_widgets["group_combo"].currentText()
        template_info = OPHYD_DEVICE_TEMPLATES.get(group_name, {}).get(variant_name, {})
        if template_info:
            self._device_config_template.change_template(template_info)
        else:
            self._device_config_template.change_template(
                OPHYD_DEVICE_TEMPLATES[DEFAULT_DEVICE][DEFAULT_DEVICE]
            )

    def _create_validation_dialog(self) -> QtWidgets.QProgressDialog:
        """
        Create and show a validation progress dialog while validating the device configuration.
        The dialog will be modal and prevent user interaction until validation is complete.
        """
        wait_dialog = QtWidgets.QProgressDialog(
            "Validating config… please wait", None, 0, 0, parent=self
        )
        wait_dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        wait_dialog.setCancelButton(None)
        wait_dialog.setMinimumDuration(0)
        return wait_dialog

    def _create_and_run_ophyd_validation(self, config: dict[str, Any]) -> OphydValidation:
        """Run ophyd validation test on the current device configuration."""
        ophyd_validation = OphydValidation(parent=self)
        ophyd_validation.validation_completed.connect(self._handle_validation_result)
        ophyd_validation.multiple_validations_completed.connect(
            self._handle_devices_already_in_session_results
        )

        # NOTE Use singleShot here to ensure that the signal is emitted after all other scheduled
        # tasks in the event loop are processed. This avoids potential deadlocks. In particular,
        # this is relevant for the _wait_dialog exec which opens a modal dialog during validation
        # and therefore must not have the signal emitted immediately in the same event loop iteration.
        # Otherwise, the callback may be scheduled before the dialog is shown resulting in a deadlock.
        QtCore.QTimer.singleShot(
            0, lambda: ophyd_validation.change_device_configs([config], True, False)
        )
        return ophyd_validation

    @SafeSlot(list)
    def _handle_devices_already_in_session_results(
        self, validation_results: _ValidationResultIter
    ) -> None:
        """Handle completion if device is already in session."""
        if len(validation_results) != 1:
            logger.error(
                "Expected a single device validation result, but got multiple. Using first result."
            )
        result = validation_results[0] if len(validation_results) > 0 else None
        if result is None:
            logger.error(
                f"Received validation results: {validation_results} of unexpected length 0. Returning."
            )
            return
        device_config, config_status, connection_status, validation_msg = result
        self._handle_validation_result(
            device_config, config_status, connection_status, validation_msg
        )

    @SafeSlot(dict, int, int, str)
    def _handle_validation_result(
        self, device_config: dict, config_status: int, connection_status: int, validation_msg: str
    ):
        """Handle completion of validation."""
        try:
            if (
                DeviceModel.model_validate(device_config)
                == DeviceModel.model_validate(self._validation_result[0])
                and connection_status == ConnectionStatus.UNKNOWN.value
            ):
                # Config unchanged, we can reuse previous connection status. Only do this if the new
                # connection status is UNKNOWN as the current validation should not test the connection.
                connection_status = self._validation_result[2]
        except Exception:
            logger.debug(
                f"Device config validation changed for config: {device_config} compared to previous validation. Using status from recent validation."
            )
        self._validation_result = (device_config, config_status, connection_status, validation_msg)
        if self._wait_dialog is not None:
            self._wait_dialog.accept()
            self._wait_dialog.close()
            self._wait_dialog.deleteLater()
            self._wait_dialog = None

    def _add_config(self):
        """
        Adding a config will always run a validation check of the config without a connection test.
        We will check if tests have already run, and reuse the information in case they also tested the connection to the device.
        """
        config = self._device_config_template.get_config_fields()

        # I. First we validate that the device name is valid, as this may create issues within the OphydValidation widget.
        # Validate device name first. If invalid, this should immediately block adding the device.
        if not validate_name(config.get("name", "")):
            msg_box = self._create_warning_message_box(
                "Invalid Device Name",
                f"Device is invalid, can not be empty with spaces. Please provide a valid name. {config.get('name', '')!r} ",
            )
            msg_box.exec()
            return

        # II. Next we will run the validation check of the config without connection test.
        # We will show a wait dialog while this is happening, and compare the results with the last known validation results.
        # If the config is unchanged, we will use the connection status results from the last validation.
        self._wait_dialog = self._create_validation_dialog()
        ophyd_validation: OphydValidation | None = None
        try:
            ophyd_validation = self._create_and_run_ophyd_validation(config)

            # NOTE If dialog was already closed, this means that a validation callback was already received
            # which closed the dialog. In this case, we skip exec to avoid deadlock. With the singleShot above,
            # this should not happen, but we keep the check for safety.
            if self._wait_dialog is not None:
                self._wait_dialog.exec()  # This will block until the validation is complete

            config, config_status, connection_status, validation_msg = self._validation_result

            if config_status == ConfigStatus.INVALID.value:
                msg_box = self._create_warning_message_box(
                    "Invalid Device Configuration",
                    f"Device configuration is invalid. Last known validation message:\n\nErrors:\n{self._validation_result[3]}",
                )
                msg_box.exec()
                return

            self.accepted_data.emit(
                config, config_status, connection_status, validation_msg, self._old_device_name
            )
            self.accept()
        finally:
            if ophyd_validation is not None:
                ophyd_validation.close()
                ophyd_validation.deleteLater()

    def _create_warning_message_box(self, title: str, text: str) -> QtWidgets.QMessageBox:
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        return msg_box

    def _test_connection(self):
        config = self._device_config_template.get_config_fields()
        dialog = DeviceManagerOphydValidationDialog(self, config=config)
        result = dialog.exec()
        if result in (QtWidgets.QDialog.Accepted, QtWidgets.QDialog.Rejected):
            self.config_validation_result = dialog.validation_result

    def _reset_config(self):
        self._device_config_template.reset_to_defaults()

    def _reject_config(self):
        self.reject()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme

    app = QtWidgets.QApplication(sys.argv)
    apply_theme("light")

    dialog = DeviceFormDialog()
    dialog.resize(1200, 800)
    dialog.show()
    sys.exit(app.exec())
