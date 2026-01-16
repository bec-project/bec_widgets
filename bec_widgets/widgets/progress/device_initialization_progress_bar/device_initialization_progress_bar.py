"""Module for a ProgressBar for device initialization progress."""

from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeviceInitializationProgressMessage
from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import BECProgressBar


class DeviceInitializationProgressBar(BECWidget, QWidget):
    """A progress bar that displays the progress of device initialization."""

    # Signal emitted for failed device initializations
    failed_devices_changed = Signal(list)

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self._failed_devices: list[str] = []

        # Main Layout with Group Box
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)
        self.group_box = QGroupBox(self)
        self.group_box.setTitle("Config Update Progress")
        main_layout.addWidget(self.group_box)
        lay = QVBoxLayout(self.group_box)
        lay.setContentsMargins(25, 25, 25, 25)
        lay.setSpacing(5)

        # Progress Bar and Label in Layout
        self.progress_bar = BECProgressBar(parent=parent, client=client, **kwargs)
        self.progress_bar.label_template = "$value / $maximum - $percentage %"
        self.progress_label = QLabel("Initializing devices...", self)

        self.progress_label.setStyleSheet("font-size: 12px; font-weight: cursive;")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.progress_bar)

        # Layout for label, to place label properly below progress bar
        # Adjust 10px left margin for aesthetic alignment
        hor_layout = QHBoxLayout()
        hor_layout.setContentsMargins(12, 0, 0, 0)
        hor_layout.addWidget(self.progress_label)
        content_layout.addLayout(hor_layout)
        content_layout.addStretch()

        # Add content layout to main layout
        lay.addLayout(content_layout)

        self.bec_dispatcher.connect_slot(
            slot=self._update_device_initialization_progress,
            topics=MessageEndpoints.device_initialization_progress(),
        )
        self._reset_progress_bar()

    def _update_palette(self) -> None:
        """Update theme palette for the widget."""
        _app = QApplication.instance()
        if hasattr(_app, "theme"):
            theme = _app.theme  # type: ignore[attr-defined]
            text_color = theme.color("FG")
        else:
            text_color = QColor(230, 230, 230)
        self.progress_label.setStyleSheet(
            f"color: {text_color.name()}; font-size: 12px; font-weight: cursive;"
        )

    @SafeProperty(list)
    def failed_devices(self) -> list[str]:
        """Get the list of devices that failed to initialize.

        Returns:
            list[str]: A list of device identifiers that failed during initialization.
        """
        return self._failed_devices

    @failed_devices.setter
    def failed_devices(self, value: list[str]) -> None:
        self._failed_devices = value
        self.failed_devices_changed.emit(self.failed_devices)

    @SafeSlot()
    def reset_failed_devices(self) -> None:
        """Reset the list of failed devices."""
        self._failed_devices.clear()
        self.failed_devices_changed.emit(self.failed_devices)

    @SafeSlot(str)
    def add_failed_device(self, device: str) -> None:
        """Add a device to the list of failed devices.

        Args:
            device (str): The identifier of the device that failed to initialize.
        """
        self._failed_devices.append(device)
        self.failed_devices_changed.emit(self.failed_devices)

    @SafeSlot(dict, dict)
    def _update_device_initialization_progress(self, msg: dict, metadata: dict) -> None:
        """Update the progress bar based on device initialization progress messages.

        Args:
            msg (dict): The device initialization progress message.
            metadata (dict): Additional metadata about the message.
        """
        msg: DeviceInitializationProgressMessage = (
            DeviceInitializationProgressMessage.model_validate(msg)
        )
        # Reset progress bar if index has gone backwards, this indicates a new initialization sequence
        old_value = self.progress_bar._user_value
        if msg.index < old_value:
            self._reset_progress_bar()
        # Update progress based on message content
        if msg.finished is False:
            self.progress_label.setText(f"{msg.device} initialization in progress...")
        elif msg.finished is True and msg.success is False:
            self.add_failed_device(msg.device)
            self.progress_label.setText(f"{msg.device} initialization failed!")
        else:
            self.progress_label.setText(f"{msg.device} initialization succeeded!")
        self.progress_bar.set_maximum(msg.total)
        self.progress_bar.set_value(msg.index)
        self._update_tool_tip()

    def _reset_progress_bar(self) -> None:
        """Reset the progress bar to its initial state."""
        self.progress_bar.set_value(0)
        self.progress_bar.set_maximum(100)
        self.reset_failed_devices()
        self._update_tool_tip()

    def _update_tool_tip(self) -> None:
        """Update the tooltip to show failed devices if any."""
        if self._failed_devices:
            failed_devices_str = ", ".join(sorted(self._failed_devices))
            self.setToolTip(f"Failed devices: {failed_devices_str}")
        else:
            self.setToolTip("No device initialization failures.")


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("dark")

    progressBar = DeviceInitializationProgressBar()

    def my_cb(devices: list):
        print("Failed devices:", devices)

    progressBar.failed_devices_changed.connect(my_cb)
    progressBar.show()

    sys.exit(app.exec())
