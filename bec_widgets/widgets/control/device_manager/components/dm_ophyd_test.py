"""Module to run a static test for the current config and see if it is valid."""

from __future__ import annotations

import enum

import bec_lib
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.editors.web_console.web_console import WebConsole

READY_TO_TEST = False

logger = bec_logger.logger

try:
    import bec_server
    import ophyd_devices

    READY_TO_TEST = True
except ImportError:
    logger.warning(f"Optional dependencies not available: {ImportError}")
    ophyd_devices = None
    bec_server = None


class ValidationStatus(int, enum.Enum):
    """Validation status for device configurations."""

    UNKNOWN = 0  # colors.default
    ERROR = 1  # colors.emergency
    VALID = 2  # colors.highlight
    CANT_CONNECT = 3  # colors.warning
    CONNECTED = 4  # colors.success


class DeviceValidationListItem(QtWidgets.QWidget):
    """Custom list item widget showing device name and validation status."""

    status_changed = QtCore.Signal(int)  # Signal emitted when status changes -> ValidationStatus
    # Signal emitted when device was validated with name, success, msg
    device_validated = QtCore.Signal(str, str)

    def __init__(
        self,
        device_config: dict[str, dict],
        status: ValidationStatus,
        status_icons: dict[ValidationStatus, QtGui.QPixmap],
        validate_icon: QtGui.QPixmap,
        parent=None,
        static_device_test=None,
    ):
        super().__init__(parent)
        if len(device_config.keys()) > 1:
            logger.warning(
                f"Multiple devices found for config: {list(device_config.keys())}, using first one"
            )
        self._static_device_test = static_device_test
        self.device_name = list(device_config.keys())[0]
        self.device_config = device_config
        self.status: ValidationStatus = status
        colors = get_accent_colors()
        self._status_icon = status_icons
        self._validate_icon = validate_icon
        self._setup_ui()
        self._update_status_indicator()

    def _setup_ui(self):
        """Setup the UI for the list item."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Device name label
        self.name_label = QtWidgets.QLabel(self.device_name)
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name_label)

        # Make sure status is on the right
        layout.addStretch()
        self.request_validation_button = QtWidgets.QPushButton("Validate")
        self.request_validation_button.setIcon(self._validate_icon)
        if self._static_device_test is None:
            self.request_validation_button.setDisabled(True)
        else:
            self.request_validation_button.clicked.connect(self.on_request_validation)
            # self.request_validation_button.setVisible(False) -> Hide it??
        layout.addWidget(self.request_validation_button)
        # Status indicator
        self.status_indicator = QtWidgets.QLabel()
        self._update_status_indicator()
        layout.addWidget(self.status_indicator)

    @SafeSlot()
    def on_request_validation(self):
        """Handle validate button click."""
        if self._static_device_test is None:
            logger.warning("Static device test not available.")
            return
        self._static_device_test.config = self.device_config
        # TODO logic if connect is allowed
        ret = self._static_device_test.run_with_list_output(connect=False)[0]
        if ret.success:
            self.set_status(ValidationStatus.VALID)
        else:
            self.set_status(ValidationStatus.ERROR)
        self.device_validated.emit(ret.name, ret.message)

    def _update_status_indicator(self):
        """Update the status indicator color based on validation status."""
        self.status_indicator.setPixmap(self._status_icon[self.status])

    def set_status(self, status: ValidationStatus):
        """Update the validation status."""
        self.status = status
        self._update_status_indicator()
        self.status_changed.emit(self.status)

    def get_status(self) -> ValidationStatus:
        """Get the current validation status."""
        return self.status


class DeviceManagerOphydTest(BECWidget, QtWidgets.QWidget):

    config_changed = QtCore.Signal(
        dict, dict
    )  # Signal emitted when the device config changed, new_config, old_config

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent, client=client)
        if not READY_TO_TEST:
            self._set_disabled()
            static_device_test = None
        else:
            from ophyd_devices.utils.static_device_test import StaticDeviceTest

            static_device_test = StaticDeviceTest(config_dict={})
        self._static_device_test = static_device_test
        self._device_config: dict[str, dict] = {}
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(4)

        # Setup icons
        colors = get_accent_colors()
        self._validate_icon = material_icon(
            icon_name="play_arrow", color=colors.default, filled=True
        )
        self._status_icons = {
            ValidationStatus.UNKNOWN: material_icon(
                icon_name="circle", size=(12, 12), color=colors.default, filled=True
            ),
            ValidationStatus.ERROR: material_icon(
                icon_name="circle", size=(12, 12), color=colors.emergency, filled=True
            ),
            ValidationStatus.VALID: material_icon(
                icon_name="circle", size=(12, 12), color=colors.highlight, filled=True
            ),
            ValidationStatus.CANT_CONNECT: material_icon(
                icon_name="circle", size=(12, 12), color=colors.warning, filled=True
            ),
            ValidationStatus.CONNECTED: material_icon(
                icon_name="circle", size=(12, 12), color=colors.success, filled=True
            ),
        }

        self.setLayout(self._main_layout)

        # splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._main_layout.addWidget(self.splitter)

        # Add custom list
        self.setup_device_validation_list()

        # Setup text box
        self.setup_text_box()

        # Connect signals
        self.config_changed.connect(self.on_config_updated)

    @SafeSlot(list)
    def on_device_config_update(self, config: list[dict]):
        old_cfg = self._device_config
        self._device_config = self._compile_device_config_list(config)
        self.config_changed.emit(self._device_config, old_cfg)

    def _compile_device_config_list(self, config: list[dict]) -> dict[str, dict]:
        return {dev["name"]: {k: v for k, v in dev.items() if k != "name"} for dev in config}

    @SafeSlot(dict, dict)
    def on_config_updated(self, new_config: dict, old_config: dict):
        """Handle config updates and refresh the validation list."""
        # Find differences for potential re-validation
        diffs = self._find_diffs(new_config, old_config)
        # Check diff first
        for diff in diffs:
            if not diff:
                continue
            if len(diff) > 1:
                logger.warning(f"Multiple devices found in diff: {diff}, using first one")
            name = list(diff.keys())[0]
            if name in self.client.device_manager.devices:
                status = ValidationStatus.CONNECTED
            else:
                status = ValidationStatus.UNKNOWN
            if self.get_device_status(diff) is None:
                self.add_device(diff, status)
            else:
                self.update_device_status(diff, status)

    def _find_diffs(self, new_config: dict, old_config: dict) -> list[dict]:
        """
        Return list of keys/paths where d1 and d2 differ. This goes recursively through the dictionary.

        Args:
            new_config: The first dictionary to compare.
            old_config: The second dictionary to compare.
        """
        diffs = []
        keys = set(new_config.keys()) | set(old_config.keys())
        for k in keys:
            if k not in old_config:  # New device
                diffs.append({k: new_config[k]})
                continue
            if k not in new_config:  # Removed device
                diffs.append({k: old_config[k]})
                continue
            # Compare device config if exists in both
            v1, v2 = old_config[k], new_config[k]
            if isinstance(v1, dict) and isinstance(v2, dict):
                if self._find_diffs(v2, v1):  # recurse: something inside changed
                    diffs.append({k: new_config[k]})
            elif v1 != v2:
                diffs.append({k: new_config[k]})
        return diffs

    def setup_device_validation_list(self):
        """Setup the device validation list."""
        # Create the custom validation list widget
        self.validation_list = QtWidgets.QListWidget()
        self.validation_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.splitter.addWidget(self.validation_list)
        # self._main_layout.addWidget(self.validation_list)

    def setup_text_box(self):
        """Setup the text box for device validation messages."""
        self.validation_text_box = QtWidgets.QTextEdit()
        self.validation_text_box.setReadOnly(True)
        self.splitter.addWidget(self.validation_text_box)
        # self._main_layout.addWidget(self.validation_text_box)

    @SafeSlot(str, str)
    def on_device_validated(self, device_name: str, message: str):
        """Handle device validation results."""
        text = f"Device {device_name} was validated. Message: {message}"
        self.validation_text_box.setText(text)

    def _set_disabled(self) -> None:
        """Disable the full view"""
        self.setDisabled(True)

    def add_device(
        self, device_config: dict[str, dict], status: ValidationStatus = ValidationStatus.UNKNOWN
    ):
        """Add a device to the validation list."""
        # Create the custom widget
        item_widget = DeviceValidationListItem(
            device_config=device_config,
            status=status,
            status_icons=self._status_icons,
            validate_icon=self._validate_icon,
            static_device_test=self._static_device_test,
        )

        # Create a list widget item
        list_item = QtWidgets.QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())

        # Add item to list and set custom widget
        self.validation_list.addItem(list_item)
        self.validation_list.setItemWidget(list_item, item_widget)
        item_widget.device_validated.connect(self.on_device_validated)

    def update_device_status(self, device_config: dict[str, dict], status: ValidationStatus):
        """Update the validation status for a specific device."""
        for i in range(self.validation_list.count()):
            item = self.validation_list.item(i)
            widget = self.validation_list.itemWidget(item)
            if (
                isinstance(widget, DeviceValidationListItem)
                and widget.device_config == device_config
            ):
                widget.set_status(status)
                break

    def clear_devices(self):
        """Clear all devices from the list."""
        self.validation_list.clear()

    def get_device_status(self, device_config: dict[str, dict]) -> ValidationStatus | None:
        """Get the validation status for a specific device."""
        for i in range(self.validation_list.count()):
            item = self.validation_list.item(i)
            widget = self.validation_list.itemWidget(item)
            if (
                isinstance(widget, DeviceValidationListItem)
                and widget.device_config == device_config
            ):
                return widget.get_status()
        return None


if __name__ == "__main__":
    import sys

    # pylint: disable=ungrouped-imports
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    device_manager_ophyd_test = DeviceManagerOphydTest()
    cfg = device_manager_ophyd_test.client.device_manager._get_redis_device_config()
    cfg.append({"name": "Wrong_Device", "type": "test"})
    device_manager_ophyd_test.on_device_config_update(cfg)
    device_manager_ophyd_test.show()
    device_manager_ophyd_test.setWindowTitle("Device Manager Ophyd Test")
    device_manager_ophyd_test.resize(800, 600)
    sys.exit(app.exec_())
