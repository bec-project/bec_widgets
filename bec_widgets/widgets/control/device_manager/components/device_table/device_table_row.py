"""Module with custom table row for the device manager device table view."""

from bec_lib.atlas_models import Device as DeviceModel

from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
)


class DeviceTableRow:
    """
    Custom class to hold data and validation status for a device table row.

    Args:
        data (list[str, dict] | None): Initial data for the row.
    """

    def __init__(self, data: list[str, dict] | None = None):
        """Initialize the DeviceTableRow with optional data.

        Args:
            data (list[str, dict] | None): Initial data for the row.
        """
        self._data = {}
        self.validation_status: tuple[int, int] = (ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)
        self.set_data(data or {})

    @property
    def data(self) -> dict:
        """Get the current data from the row widgets as a dictionary."""
        return self._data

    def set_data(self, data: DeviceModel | dict) -> None:
        """Set the data for the row widgets."""
        if isinstance(data, dict):
            data = DeviceModel.model_validate(data)
        old_data = DeviceModel.model_validate(self._data) if self._data else None
        if old_data is not None and old_data == data:
            return  # No change needed
        self._data = data.model_dump()
        self.set_validation_status(ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)

    def set_validation_status(
        self, valid: ConfigStatus | int, connect_status: ConnectionStatus | int
    ) -> None:
        """
        Set the validation and connection status icons.

        Args:
            valid (ConfigStatus | int): The configuration validation status.
            connect_status (ConnectionStatus | int): The connection status.
        """
        valid = int(valid)
        connect_status = int(connect_status)
        self.validation_status = valid, connect_status
