"""Dialogs for device configuration forms and ophyd testing."""

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

        # Connect signal for validation messages

        # Load and apply configuration
        config = config or {}
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

    @SafeSlot(int)
    def _finished(self, state: int):
        for widget in self._control_widgets.values():
            widget.close()
            widget.deleteLater()

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

    def _add_config(self):
        config = self._device_config_template.get_config_fields()
        config_status = ConfigStatus.UNKNOWN.value
        connection_status = ConnectionStatus.UNKNOWN.value
        validation_msg = ""
        try:
            if DeviceModel.model_validate(config) == DeviceModel.model_validate(
                self._validation_result[0]
            ):
                config_status = self._validation_result[1]
                connection_status = self._validation_result[2]
                validation_msg = self._validation_result[3]
        except Exception:
            logger.debug(
                f"Device config validation changed for config: {config} compared to {self._validation_result[0]}. Returning UNKNOWN statuses."
            )

        if not validate_name(config.get("name", "")):
            msg_box = self._create_warning_message_box(
                "Invalid Device Name",
                f"Device is invalid, can not be empty with spaces. Please provide a valid name. {config.get('name', '')!r} ",
            )
            msg_box.exec()
            return
        if config_status == ConfigStatus.INVALID.value:
            msg_box = self._create_warning_message_box(
                "Invalid Device Configuration",
                f"Device configuration is invalid. Last known validation message:\n\nErrors:\n{validation_msg}",
            )
            msg_box.exec()
            return

        self.accepted_data.emit(
            config, config_status, connection_status, validation_msg, self._old_device_name
        )
        self.accept()

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
            # self._device_config_template.set_config_fields(self.config_validation_result[0])

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
