"""Module with validation items and a validation button for device testing UI."""

from typing import Literal

from bec_lib.logger import bec_logger
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    DeviceTestModel,
    get_validation_icons,
)
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

logger = bec_logger.logger


class ValidationButton(QtWidgets.QPushButton):
    """
    Validation button with flat style and disabled appearance.

    Args:
        parent (QtWidgets.QWidget | None): Parent widget.
        icon (QtGui.QIcon | None): Icon to display on the button.
    """

    def __init__(
        self, parent: QtWidgets.QWidget | None = None, icon: QtGui.QIcon | None = None
    ) -> None:
        super().__init__(parent=parent)
        if icon:
            self.setIcon(icon)
        self.setFlat(True)
        self.setEnabled(True)

    def setEnabled(self, enabled: bool) -> None:
        return super().setEnabled(enabled)


class ValidationDialog(QtWidgets.QDialog):
    """
    Dialog to confirm re-validation with optional parameters. Once accepted,
    the settings timeout, connect and force_connect can be retrieved through .result().

    Args:
        parent (QtWidgets.QWidget, optional): The parent widget.
        timeout (float, optional): The timeout for the validation.
        connect (bool, optional): Whether to attempt connection during validation.
        force_connect (bool, optional): Whether to force connection during validation.
    """

    def __init__(
        self, parent=None, timeout: float = 5.0, connect: bool = False, force_connect: bool = False
    ):
        super().__init__(parent)

        self._result: tuple[float, bool, bool] = (timeout, connect, force_connect)
        # Setup Dialog UI
        self.setWindowTitle("Run Validation")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        # label
        self.label = QtWidgets.QLabel(
            "Do you want to re-run validation with the following options?"
        )
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        # Setup options (note timeout will be simplified to int)
        option_layout = QtWidgets.QVBoxLayout()
        option_layout.setSpacing(16)
        option_layout.setContentsMargins(0, 0, 0, 0)

        # Timeout
        timeout_layout = QtWidgets.QHBoxLayout()
        label_timeout = QtWidgets.QLabel("Timeout(s):")
        self.timeout_spin = QtWidgets.QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setValue(int(timeout))
        timeout_layout.addWidget(label_timeout)
        timeout_layout.addWidget(self.timeout_spin)

        # Connect checkbox
        self.connect_checkbox = QtWidgets.QCheckBox("Test Connection")
        self.connect_checkbox.setChecked(connect)

        # Force Connect checkbox
        self.force_connect_checkbox = QtWidgets.QCheckBox("Force Connect")
        self.force_connect_checkbox.setChecked(force_connect)
        if self.connect_checkbox.isChecked() is False:
            self.force_connect_checkbox.setEnabled(False)
        # Deactivated if connect is unchecked
        self.connect_checkbox.stateChanged.connect(self.force_connect_checkbox.setEnabled)

        # Add widgets to layout
        option_layout.addLayout(timeout_layout)
        option_layout.addWidget(self.connect_checkbox)
        option_layout.addWidget(self.force_connect_checkbox)
        layout.addLayout(option_layout)

        # Dialog Buttons: equal size, stacked horizontally
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.adjustSize()

    def accept(self):
        """Process the dialog acceptance and store the result."""
        self._result = (
            float(self.timeout_spin.value()),
            self.connect_checkbox.isChecked(),
            self.force_connect_checkbox.isChecked(),
        )
        super().accept()

    def result(self):
        return self._result


class ValidationListItem(QtWidgets.QWidget):
    """List item to display device test validation status."""

    request_rerun_validation = QtCore.Signal(str, dict, bool, bool, float)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        device_model: DeviceTestModel | None = None,
        validation_icons: (
            dict[Literal["config_status", "connection_status"], dict[int, QtGui.QIcon]] | None
        ) = None,
        icon_size: tuple[int, int] = (32, 32),
    ) -> None:
        super().__init__(parent=parent)
        if device_model is None:
            logger.debug("No device config provided to ValidationListItem.")
            return
        self.device_model: DeviceTestModel = device_model
        self.is_running: bool = False
        self._colors = get_accent_colors()
        self._icon_size = icon_size
        self._validation_icons = validation_icons or get_validation_icons(
            colors=self._colors, icon_size=self._icon_size, convert_to_pixmap=False
        )

        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(4)
        self._setup_ui()

    ######################
    ### UI Setup Methods
    ######################

    def _setup_ui(self) -> None:
        """Setup the UI elements of the widget."""
        # Device Name Label
        label = QtWidgets.QLabel(self.device_model.device_name)
        self.main_layout.addWidget(label)
        self.main_layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        # Spinner
        self._spinner = SpinnerWidget()
        self._spinner.speed = 80
        self._spinner.setFixedSize(self._icon_size[0] // 1.5, self._icon_size[1] // 1.5)
        self._spinner.setVisible(False)

        # Add to button layout
        button_layout.addWidget(self._spinner)

        # Config Status Icon
        self.status_button = ValidationButton(
            icon=self._validation_icons["config_status"][self.device_model.config_status]
        )
        self.status_button.setToolTip("Configuration Status")
        self.status_button.clicked.connect(self._on_status_button_clicked)
        button_layout.addWidget(self.status_button)

        # Connection Status Icon
        self.connection_button = ValidationButton(
            icon=self._validation_icons["connection_status"][self.device_model.connection_status]
        )
        self.connection_button.setToolTip("Connection Status")
        self.connection_button.clicked.connect(self._on_connection_button_clicked)
        button_layout.addWidget(self.connection_button)
        self.main_layout.addLayout(button_layout)

    #######################
    ### Event Handlers
    #######################

    def _on_status_button_clicked(self) -> None:
        """Handle status button click event."""
        timeout, connect, force_connect = 5, False, False
        dialog = self._create_validation_dialog_box(timeout, connect, force_connect)
        if dialog.exec():  # Only procs in success
            timeout, connect, force_connect = dialog.result()
            self.request_rerun_validation.emit(
                self.device_model.device_name,
                self.device_model.model_dump(),
                connect,
                force_connect,
                timeout,
            )

    def _on_connection_button_clicked(self) -> None:
        """Handle connection button click event."""
        timeout, connect, force_connect = 5, True, False
        dialog = self._create_validation_dialog_box(timeout, connect, force_connect)
        if dialog.exec():  # Only procs in success
            timeout, connect, force_connect = dialog.result()
            self.request_rerun_validation.emit(
                self.device_model.device_name,
                self.device_model.model_dump(),
                connect,
                force_connect,
                timeout,
            )

    #########################
    ### Helper Methods
    #########################

    def _start_spinner(self):
        """Start the spinner animation."""
        self._spinner.start()

    def _stop_spinner(self):
        """Stop the spinner animation."""
        self._spinner.stop()
        self._spinner.setVisible(False)

    def _create_validation_dialog_box(
        self, timeout: float, connect: bool, force_connect: bool
    ) -> QtWidgets.QDialog:
        """Create a dialog box to confirm re-validation."""
        return ValidationDialog(
            parent=self, timeout=timeout, connect=connect, force_connect=force_connect
        )

    def _update_validation_status(
        self, validation_msg: str, config_status: int, connection_status: int
    ):
        """
        Update the validation status icons and message.

        Args:
            validation_msg (str): The validation message.
            config_status (int): The configuration status.
            connection_status (int): The connection status.
        """
        # Update device config model
        self.device_model.validation_msg = validation_msg
        self.device_model.config_status = ConfigStatus(config_status).value
        self.device_model.connection_status = ConnectionStatus(connection_status).value

        # Update icons
        self.status_button.setIcon(
            self._validation_icons["config_status"][self.device_model.config_status]
        )
        self.connection_button.setIcon(
            self._validation_icons["connection_status"][self.device_model.connection_status]
        )

    ##########################
    ### Public Methods
    ##########################

    @SafeSlot(str, int, int)
    def on_validation_finished(
        self, validation_msg: str, config_status: int, connection_status: int
    ):
        """Handle validation finished event.

        Args:
            validation_msg (str): The validation message.
            config_status (int): The configuration status.
            connection_status (int): The connection status.
        """
        self.is_running = False
        self._stop_spinner()
        self._update_validation_status(validation_msg, config_status, connection_status)

        # Enable/disable buttons based on status
        config_but_en = config_status in [ConfigStatus.UNKNOWN, ConfigStatus.INVALID]
        self.status_button.setEnabled(config_but_en)
        connect_but_en = connection_status in [
            ConnectionStatus.UNKNOWN,
            ConnectionStatus.CANNOT_CONNECT,
        ]
        self.connection_button.setEnabled(connect_but_en)

    @SafeSlot()
    def validation_scheduled(self):
        """Handle validation scheduled event."""
        self._update_validation_status(
            "Validation scheduled...", ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN
        )
        self.status_button.setEnabled(False)
        self.connection_button.setEnabled(False)
        self._spinner.setVisible(True)

    @SafeSlot()
    def validation_started(self):
        """Start validation process."""
        self.is_running = True
        self._start_spinner()
        self._update_validation_status(
            "Validation running...", ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN
        )

    @SafeSlot()
    def start_validation(self):
        """Start validation process."""
        self.validation_scheduled()
        self.validation_started()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme

    app = QtWidgets.QApplication(sys.argv)
    apply_theme("dark")
    w = QtWidgets.QWidget()
    l = QtWidgets.QVBoxLayout(w)

    # Example device model
    device_model = DeviceTestModel(
        uuid="1234",
        device_name="Test Device",
        device_config={"param1": "value1"},
        config_status=ConfigStatus.INVALID.value,
        connection_status=ConnectionStatus.CANNOT_CONNECT.value,
        validation_msg="Initial validation failed.",
    )

    # Create validation list item
    validation_item = ValidationListItem(parent=w, device_model=device_model)
    l.addWidget(validation_item)

    but = QtWidgets.QPushButton("Start Validation")
    but2 = QtWidgets.QPushButton("Finish Validation")
    but.clicked.connect(validation_item.start_validation)
    but2.clicked.connect(
        lambda: validation_item.on_validation_finished(
            "Validation successful.",
            ConfigStatus.VALID.value,
            ConnectionStatus.CANNOT_CONNECT.value,
        )
    )
    l.addWidget(but)
    l.addWidget(but2)

    def _print_callback(name, cfg, conn, force, to):
        print(
            f"Re-run validation requested for dev {name} for config {cfg} with timeout={to}, connect={conn}, force={force}"
        )

    validation_item.request_rerun_validation.connect(_print_callback)
    w.show()
    sys.exit(app.exec())
