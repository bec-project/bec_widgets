from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeviceInitializationProgressMessage
from qtpy.QtCore import Signal

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import BECProgressBar


class DeviceInitializationProgressBar(BECProgressBar):
    """A progress bar that displays the progress of device initialization."""

    # Signal emitted for failed device initializations
    failed_devices_changed = Signal(list)

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent, client=client)
        self._latest_device_config_msg: dict | None = None
        self._failed_devices: list[str] = []
        self.bec_dispatcher.connect_slot(
            slot=self._update_device_initialization_progress,
            topics=MessageEndpoints.device_initialization_progress(),
        )
        self._reset_progress_bar()

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
        if msg.finished is False:
            self.label_template = "\n".join(
                [
                    f"Device initialization for '{msg.device}' is in progress...",
                    "$value / $maximum - $percentage %",
                ]
            )
        elif msg.finished is True and msg.success is False:
            self.add_failed_device(msg.device)
            self.label_template = "\n".join(
                [
                    f"Device initialization for '{msg.device}' failed!",
                    "$value / $maximum - $percentage %",
                ]
            )
        else:
            self.label_template = "\n".join(
                [
                    f"Device initialization for '{msg.device}' succeeded!",
                    "$value / $maximum - $percentage %",
                ]
            )
        self.set_maximum(msg.total)
        self.set_value(msg.index)
        self._update_tool_tip()

    def _reset_progress_bar(self) -> None:
        """Reset the progress bar to its initial state."""
        self.label_template = "\n".join(
            ["Waiting for device initialization...", "$value / $maximum - $percentage %"]
        )
        self.set_value(0)
        self.set_maximum(1)
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

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    progressBar = DeviceInitializationProgressBar()

    def my_cb(devices: list):
        print("Failed devices:", devices)

    progressBar.failed_devices_changed.connect(my_cb)
    progressBar.show()

    sys.exit(app.exec())
