"""Module for the upload redis dialog in the device manager view."""

from __future__ import annotations

from enum import IntEnum
from functools import partial
from typing import TYPE_CHECKING, Any, List, Tuple

from bec_lib.logger import bec_logger
from bec_qthemes import apply_theme, material_icon
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    get_validation_icons,
)

if TYPE_CHECKING:
    from bec_widgets.utils.colors import AccentColor
    from bec_widgets.widgets.control.device_manager.components.device_table.device_table import (
        _ValidationResultIter,
    )

logger = bec_logger.logger


class DeviceStatusItem(QtWidgets.QWidget):
    """Individual device status item widget for the validation display."""

    def __init__(
        self, device_config: dict, config_status: int, connection_status: int, parent=None
    ):
        super().__init__(parent)
        self.device_name = device_config.get("name", "")
        self.device_config: dict = device_config
        self.config_status = ConfigStatus(config_status)
        self.connection_status = ConnectionStatus(connection_status)
        self._transparent_button_style = "background-color: transparent; border: none;"

        # Get validation icons
        self.colors = get_accent_colors()
        self._icon_size = (20, 20)
        self.icons = get_validation_icons(self.colors, self._icon_size)

        self._setup_ui()
        self._update_display()

    def _setup_ui(self):
        """Setup the UI for the device status item."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Device name label
        self.name_label = QtWidgets.QLabel(self.device_name)
        self.name_label.setMinimumWidth(150)
        layout.addWidget(self.name_label)
        layout.addStretch()

        # Config status icon
        self.config_icon_label = self._create_status_icon_label(self._icon_size)
        layout.addWidget(self.config_icon_label)

        # Connection status icon
        self.connection_icon_label = self._create_status_icon_label(self._icon_size)
        layout.addWidget(self.connection_icon_label)

    def _create_status_icon_label(self, icon_size: tuple[int, int]) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton()
        button.setFlat(True)
        button.setEnabled(False)
        button.setStyleSheet(self._transparent_button_style)
        button.setFixedSize(icon_size[0], icon_size[1])
        return button

    def _update_display(self):
        """Update the visual display based on current status."""
        # Update config status
        config_icon = self.icons["config_status"].get(self.config_status.value)
        if config_icon:
            self.config_icon_label.setIcon(config_icon)

        # Update connection status
        connection_icon = self.icons["connection_status"].get(self.connection_status.value)
        if connection_icon:
            self.connection_icon_label.setIcon(connection_icon)

    def update_status(self, config_status: int, connection_status: int):
        """Update the status and refresh display."""
        self.config_status = ConfigStatus(config_status)
        self.connection_status = ConnectionStatus(connection_status)
        self._update_display()


class SortTableItem(QtWidgets.QTableWidgetItem):
    """Custom TableWidgetItem with hidden __column_data attribute for sorting."""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        """Override less-than operator for sorting."""
        if not isinstance(other, QtWidgets.QTableWidgetItem):
            return NotImplemented
        self_data = self.data(QtCore.Qt.ItemDataRole.UserRole)
        other_data = other.data(QtCore.Qt.ItemDataRole.UserRole)
        if self_data is not None and other_data is not None:
            self_data: DeviceStatusItem
            other_data: DeviceStatusItem
            if self_data.config_status != other_data.config_status:
                return self_data.config_status < other_data.config_status
            else:
                return self_data.connection_status < other_data.connection_status
        return super().__lt__(other)

    def __gt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        """Override less-than operator for sorting."""
        if not isinstance(other, QtWidgets.QTableWidgetItem):
            return NotImplemented
        self_data = self.data(QtCore.Qt.ItemDataRole.UserRole)
        other_data = other.data(QtCore.Qt.ItemDataRole.UserRole)
        if self_data is not None and other_data is not None:
            self_data: DeviceStatusItem
            other_data: DeviceStatusItem
            if self_data.config_status != other_data.config_status:
                return self_data.config_status > other_data.config_status
            else:
                return self_data.connection_status > other_data.connection_status
        return super().__gt__(other)


class ValidationSection(QtWidgets.QGroupBox):
    """Section widget for displaying validation results."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent=parent)
        self._setup_ui()
        # self.device_items: Dict[str, DeviceStatusItem] = {}

    def _setup_ui(self):
        """Setup the UI for the validation section."""
        layout = QtWidgets.QVBoxLayout(self)

        # Status summary label
        summary_layout = QtWidgets.QHBoxLayout()
        self.summary_icon = QtWidgets.QLabel()
        self.summary_icon.setFixedSize(24, 24)
        self.summary_label = QtWidgets.QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_icon)
        summary_layout.addWidget(self.summary_label)
        layout.addLayout(summary_layout)

        # Scroll area for device items
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(1)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)  # r
        self.table.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)
        layout.addWidget(self.table)
        QtCore.QTimer.singleShot(0, self.adjustSize)

    def add_device(self, device_config: dict, config_status: int, connection_status: int):
        """
        Add a device to the validation section.

        Args:
            device_config (dict): The device configuration dictionary.
            config_status (int): The configuration status.
            connection_status (int): The connection status.
        """
        self.table.setSortingEnabled(False)
        device_name = device_config.get("name", "")
        row = self._find_row_by_name(device_name)
        if row is not None:
            widget: DeviceStatusItem = self.table.cellWidget(row, 0)
            widget.update_status(config_status, connection_status)
        else:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            sort_item = SortTableItem(device_name)
            sort_item.setText("")
            self.table.setItem(row_position, 0, sort_item)
            device_item = DeviceStatusItem(device_config, config_status, connection_status)
            sort_item.setData(QtCore.Qt.ItemDataRole.UserRole, device_item)
            self.table.setCellWidget(row_position, 0, device_item)
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)

    def _find_row_by_name(self, device_name: str) -> int | None:
        """
        Find a row by device name.

        Args:
            name (str): The name of the device to find.
        Returns:
            int | None: The row index if found, else None.
        """
        for row in range(self.table.rowCount()):
            item: SortTableItem = self.table.item(row, 0)
            widget: DeviceStatusItem = self.table.cellWidget(row, 0)
            if widget.device_name == device_name:
                return row
        return None

    def remove_device(self, device_name: str):
        """Remove a device from the table by name."""
        self.table.setSortingEnabled(False)
        row = self._find_row_by_name(device_name)
        if row is not None:
            self.table.removeRow(row)
        self.table.setSortingEnabled(True)

    def clear_devices(self):
        """Clear all device items."""
        self.table.setSortingEnabled(False)
        while self.table.rowCount() > 0:
            self.table.removeRow(0)
        self.table.setSortingEnabled(True)

    def update_summary(self, text: str, icon: QtGui.QPixmap = None):
        """Update the summary label."""
        self.summary_label.setText(text)
        if icon:
            self.summary_icon.setPixmap(icon)


class UploadRedisDialog(QtWidgets.QDialog):
    """
    Dialog for uploading device configurations to BEC server with validation checks.
    """

    class UploadAction(IntEnum):
        """Enum for upload actions."""

        CANCEL = QtWidgets.QDialog.DialogCode.Rejected
        OK = QtWidgets.QDialog.DialogCode.Accepted
        CONNECTION_TEST_REQUESTED = 999

    # Request ophyd validation for all untested device connections
    # list of device configs, added: bool, connect: bool
    request_ophyd_validation = QtCore.Signal(list, bool, bool)

    def __init__(self, parent, device_configs: dict[str, Tuple[dict, int, int]] | None = None):
        super().__init__(parent=parent)

        self.device_configs: dict[str, Tuple[dict, int, int]] = device_configs or {}
        self._transparent_button_style = "background-color: transparent; border: none;"

        self.colors = get_accent_colors()
        self.icons = get_validation_icons(self.colors, (20, 20))
        material_icon_partial = partial(material_icon, size=(24, 24), filled=True)
        self._label_icons = {
            "success": material_icon_partial("check_circle", color=self.colors.success),
            "warning": material_icon_partial("warning", color=self.colors.warning),
            "error": material_icon_partial("error", color=self.colors.emergency),
            "reload": material_icon_partial("refresh", color=self.colors.default),
            "upload": material_icon_partial("cloud_upload", color=self.colors.default),
        }

        # Track validation states
        self.has_invalid_configs: int = 0
        self.has_untested_connections: int = 0
        self.has_cannot_connect: int = 0

        self._setup_ui()
        self._update_ui()

    def set_device_config(self, device_configs: dict[str, Tuple[dict, int, int]]):
        """
        Update the device configuration in the dialog.

        Args:
            device_configs (dict[str, Tuple[dict, int, int]]): New device configurations with structure
                                        {device_name: (config_dict, config_status, connection_status)}.
        """
        self.config_section.clear_devices()
        self.device_configs = device_configs
        self._update_ui()

    def _setup_ui(self):
        """Setup the main UI for the dialog."""
        self.setWindowTitle("Upload Configuration to BEC Server")
        self.setModal(True)  # Blocks interaction with other parts of the app

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header_label = QtWidgets.QLabel("Review Configuration Before Upload")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(header_label)

        # Description
        desc_label = QtWidgets.QLabel(
            "Please review the configuration and connection status of all devices before uploading to BEC Server."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(desc_label)

        # Config validation section
        sections_layout = QtWidgets.QHBoxLayout()
        self.config_section = ValidationSection("Configuration Validation")
        sections_layout.addWidget(self.config_section)
        layout.addLayout(sections_layout)

        # Action buttons section
        self._setup_action_buttons(layout)

        # Dialog buttons
        self._setup_dialog_buttons(layout)
        self.adjustSize()

    def _setup_action_buttons(self, parent_layout: QtWidgets.QLayout):
        """Setup the action buttons section."""
        action_group = QtWidgets.QGroupBox("Actions")
        action_layout = QtWidgets.QVBoxLayout(action_group)

        # Validate connections button
        button_layout = QtWidgets.QHBoxLayout()
        self.validate_connections_btn = QtWidgets.QPushButton("Validate All Connections")
        self.validate_connections_btn.setIcon(self._label_icons["reload"])
        self.validate_connections_btn.clicked.connect(self._validate_connections)
        button_layout.addWidget(self.validate_connections_btn)
        button_layout.addStretch()
        button_layout.addSpacing(16)
        action_layout.addLayout(button_layout)

        # Status indicator
        status_layout = QtWidgets.QHBoxLayout()
        self.status_icon = QtWidgets.QPushButton()
        self.status_icon.setFlat(True)
        self.status_icon.setEnabled(False)
        self.status_icon.setStyleSheet(self._transparent_button_style)
        self.status_icon.setFixedSize(24, 24)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        action_layout.addLayout(status_layout)

        parent_layout.addWidget(action_group)

    def _setup_dialog_buttons(self, parent_layout: QtWidgets.QLayout):
        """Setup the dialog buttons."""
        button_layout = QtWidgets.QHBoxLayout()

        # Cancel button
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        # Upload button
        self.upload_btn = QtWidgets.QPushButton("Upload to BEC Server")
        self.upload_btn.setIcon(self._label_icons["upload"])
        self.upload_btn.clicked.connect(self._handle_upload)
        button_layout.addWidget(self.upload_btn)

        parent_layout.addLayout(button_layout)

    def _populate_device_data(self):
        """Populate the dialog with device configuration data."""
        if not self.device_configs:
            return

        self.has_invalid_configs = 0
        self.has_untested_connections = 0
        self.has_cannot_connect = 0

        for device_name, (config, config_status, connection_status) in self.device_configs.items():
            # Add to appropriate sections
            self.config_section.add_device(config, config_status, connection_status)

            # Track statistics
            if config_status == ConfigStatus.INVALID.value:
                self.has_invalid_configs += 1
            if connection_status == ConnectionStatus.UNKNOWN.value:
                self.has_untested_connections += 1
            if connection_status == ConnectionStatus.CANNOT_CONNECT.value:
                self.has_cannot_connect += 1

        # Update section summaries
        num_devices = len(self.device_configs)

        # Config validation summary
        if self.has_invalid_configs > 0:
            icon = self._label_icons["error"]
            text = f"{self.has_invalid_configs} of {num_devices} device configurations are invalid."
        else:
            icon = self._label_icons["success"]
            text = f"All {num_devices} device configurations are valid."
        if self.has_untested_connections > 0:
            icon = self._label_icons["warning"]
            text += f"{self.has_untested_connections} device connections are not tested."
        if self.has_cannot_connect > 0:
            icon = self._label_icons["warning"]
            text += f"{self.has_cannot_connect} device connections cannot be established."
        self.config_section.update_summary(text, icon)

    def _update_ui(self):
        """Update UI state based on validation results."""
        # Update first the device data
        self._populate_device_data()

        # Invalid configuration have highest priority, upload disabled
        if self.has_invalid_configs:
            self.status_icon.setIcon(self._label_icons["error"])
            self.status_label.setText(
                "\n".join(
                    [
                        f"{self.has_invalid_configs} device configurations are invalid.",
                        "Please fix configuration errors before uploading.",
                    ]
                )
            )
            self.upload_btn.setEnabled(False)
            self.validate_connections_btn.setEnabled(False)
            self.validate_connections_btn.setText("Invalid Configurations")

        # Next priority: connections that cannot be established, error but upload is enabled
        elif self.has_cannot_connect:
            self.status_icon.setIcon(self._label_icons["warning"])
            self.status_label.setText(
                "\n".join(
                    [
                        f"{self.has_cannot_connect} connections cannot be established.",
                        "Please fix connection issues before uploading.",
                    ]
                )
            )
            self.upload_btn.setEnabled(True)
            self.validate_connections_btn.setEnabled(True)
            self.validate_connections_btn.setText(
                f"Validate {self.has_untested_connections + self.has_cannot_connect} Connections"
            )

        # Next priority: untested connections, warning but upload is enabled
        elif self.has_untested_connections:
            self.status_icon.setIcon(self._label_icons["warning"])
            self.status_label.setText(
                "\n".join(
                    [
                        f"{self.has_untested_connections} connections have not been tested.",
                        "Consider validating connections before uploading.",
                    ]
                )
            )
            self.upload_btn.setEnabled(True)
            self.validate_connections_btn.setEnabled(True)
            self.validate_connections_btn.setText(
                f"Validate {self.has_untested_connections + self.has_cannot_connect} Connections"
            )

        # All good, upload enabled
        else:
            self.status_icon.setIcon(self._label_icons["success"])
            self.status_label.setText(
                "\n".join(
                    [
                        "All device configurations are valid.",
                        "All connections have been successfully tested.",
                    ]
                )
            )
            self.upload_btn.setEnabled(True)
            self.validate_connections_btn.setEnabled(False)
            self.validate_connections_btn.setText("All Connections Validated")

    @SafeSlot()
    def _validate_connections(self):
        """Request validation of all untested connections. This will close the dialog."""
        testable_devices: List[dict] = []
        for _, (config, _, connection_status) in self.device_configs.items():
            if connection_status == ConnectionStatus.UNKNOWN.value:
                testable_devices.append(config)
            elif connection_status == ConnectionStatus.CANNOT_CONNECT.value:
                testable_devices.append(config)

        if len(testable_devices) > 0:
            self.request_ophyd_validation.emit(testable_devices, True, True)
            self.done(self.UploadAction.CONNECTION_TEST_REQUESTED)

    @SafeSlot()
    def _handle_upload(self):
        """Handle the upload button click with appropriate confirmations."""
        # First priority: invalid configurations, block upload
        if self.has_invalid_configs:
            detailed_text = (
                f"There is {self.has_invalid_configs} device with an invalid configuration."
                if self.has_invalid_configs == 1
                else f"There are {self.has_invalid_configs} devices with invalid configurations."
            )
            text = " ".join(
                [detailed_text, "Invalid configuration can not be uploaded to the BEC Server."]
            )
            QtWidgets.QMessageBox.critical(self, "Device Configurations Invalid", text)
            self.done(self.UploadAction.CANCEL)
            return

        # Next priority: connections that cannot be established, show warning, but allow to proceed
        if self.has_cannot_connect:
            detailed_text = (
                f"There is {self.has_cannot_connect} device that cannot connect"
                if self.has_cannot_connect == 1
                else f"There are {self.has_cannot_connect} devices that cannot connect."
            )
            text = " ".join(
                [
                    detailed_text,
                    "These devices may not be reachable and disabled BEC upon loading the config.",
                    "Consider validating these connections before proceeding.\n\n",
                    "Continue anyway?",
                ]
            )
            reply = QtWidgets.QMessageBox.critical(
                self,
                "Devices cannot Connect",
                text,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # If some connections are untested, warn the user
        if self.has_untested_connections:
            detailed_text = (
                f"There is {self.has_untested_connections} device with untested connections."
                if self.has_untested_connections == 1
                else f"There are {self.has_untested_connections} devices with untested connections."
            )
            text = " ".join(
                [
                    detailed_text,
                    "Uploading without validating connections may result in devices that cannot be reached when the configuration is applied.",
                ]
            )
            reply = QtWidgets.QMessageBox.question(
                self,
                "Untested Connections",
                text,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Final confirmation
        text = " ".join(
            ["You are about to upload the device configurations to BEC Server.", "Please confirm."]
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            "Upload to BEC Server",
            text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.done(self.UploadAction.OK)
        else:
            self.done(self.UploadAction.CANCEL)

    @SafeSlot(dict, int, int, str)
    def _update_from_ophyd_device_tests(
        self,
        device_config: dict,
        config_status: int,
        connection_status: int,
        validation_message: str = "",
    ):
        """
        Update device status from ophyd device tests. This has to be with a connection_status that was updated.

        """
        if connection_status == ConnectionStatus.UNKNOWN.value:
            return
        self.update_device_status(device_config, config_status, connection_status)

    @SafeSlot(list)
    def _multiple_updates_from_ophyd_device_tests(self, validation_results: _ValidationResultIter):
        """
        Callback slot for receiving multiple validation result updates from the ophyd test widget.

        Args:
            validation_results (list): List of tuples containing (device_config, config_status, connection_status, validation_msg).
        """
        for cfg, cfg_status, conn_status, val_msg in validation_results:
            self.update_device_status(cfg, cfg_status, conn_status)
        self._update_ui()

    @SafeSlot(dict, int, int)
    def update_device_status(self, device_config: dict, config_status: int, connection_status: int):
        """Update the status of a specific device."""
        # Update device config status
        self._update_device_configs(device_config, config_status, connection_status, "")
        # Recalculate summaries and UI state
        self._update_ui()

    def _update_device_configs(
        self,
        device_config: dict[str, Any],
        config_status: int,
        connection_status: int,
        validation_msg: str,
    ):
        device_name = device_config.get("name", "")
        old_config, _, _ = self.device_configs.get(device_name, (None, None, None))
        if old_config is not None:
            self.device_configs[device_name] = (device_config, config_status, connection_status)
        else:
            # If device not found, add it
            self.config_section.add_device(device_config, config_status, connection_status)


def main():  # pragma: no cover
    """Test the upload redis dialog."""
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Sample device configurations for testing
    sample_configs = [
        (
            {"name": "motor_x", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
        (
            {"name": "detector_1", "deviceClass": "EpicsSignal"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
        (
            {"name": "detector_2", "deviceClass": "EpicsSignal"},
            ConfigStatus.VALID.value,
            ConnectionStatus.UNKNOWN.value,
        ),
        (
            {"name": "motor_y", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
        (
            {"name": "motor_z", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
        (
            {"name": "motor_x1", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
        (
            {"name": "detector_11", "deviceClass": "EpicsSignal"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CANNOT_CONNECT.value,
        ),
        (
            {"name": "detector_21", "deviceClass": "EpicsSignal"},
            ConfigStatus.INVALID.value,
            ConnectionStatus.UNKNOWN.value,
        ),
        (
            {"name": "motor_y1", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CANNOT_CONNECT.value,
        ),
        (
            {"name": "motor_z1", "deviceClass": "EpicsMotor"},
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
        ),
    ]
    configs = {cfg[0]["name"]: cfg for cfg in sample_configs}
    apply_theme("dark")
    dialog = UploadRedisDialog(parent=None, device_configs=configs)
    dialog.show()

    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
