import re
from enum import IntEnum
from functools import partial
from typing import Any, Literal

from bec_qthemes import material_icon
from pydantic import BaseModel, Field
from qtpy import QtGui

from bec_widgets.utils.colors import AccentColors


def format_error_to_md(device_name: str, raw_msg: str) -> str:
    """
    Method to format a raw validation method into markdown for display.
    The recognized patterns are:
        - "'DEVICE_NAME' is OK. DETAIL"
        - "ERROR: 'DEVICE_NAME' is not valid: DETAIL"
        - "ERROR: 'DEVICE_NAME' is not connectable: DETAIL"
        - "ERROR: 'DEVICE_NAME' failed: DETAIL"
    If no patterns matched, the raw message is returned as a code block.

    Args:
        device_name (str): The name of the device.
        raw_msg (str): The raw validation message.

    Returns:
        str: The formatted markdown message.
    """
    if not raw_msg.strip() or raw_msg.strip() == "Validation in progress...":
        return f"### Validation in progress for {device_name}... \n\n"

    # Regex to catch OK pattern
    ok_pat = re.compile(r"(?P<device>\S+)\s+is\s+OK\.?(?:\s*(?P<detail>.*))?$", re.IGNORECASE)
    ok_match = ok_pat.search(raw_msg)
    if ok_match:
        device = ok_match.group("device")
        detail = ok_match.group("detail").strip(".").strip()
        return f"## Validation Success for {device}\n```\n{detail}\n```"

    # Regex to capture repeated ERROR patterns
    pat = re.compile(
        r"ERROR:\s*(?P<device>[^\s]+)\s+"
        r"(?P<status>is not valid|is not connectable|failed):\s*"
        r"(?P<detail>.*?)(?=ERROR:|$)",
        re.DOTALL,
    )
    blocks = []
    for m in pat.finditer(raw_msg):
        dev = m.group("device")
        status = m.group("status")
        detail = m.group("detail").strip()
        lines = [f"## Error for {dev}", f"**{dev} {status}**", f"```\n{detail}\n```"]
        blocks.append("\n\n".join(lines))

    # Fallback: If no patterns matched, return the raw message
    if not blocks:
        return f"## Error for {device_name}\n```\n{raw_msg.strip()}\n```"

    return "\n\n---\n\n".join(blocks)


############################
### Status Enums
############################


class ConfigStatus(IntEnum):
    """Validation status for device config validity. This includes the deviceClass check."""

    INVALID = 0
    VALID = 1
    UNKNOWN = 2

    def description(self) -> str:
        """Get a human-readable description of the config status.

        Returns:
            str: The description of the config status.
        """
        descriptions = {
            ConfigStatus.INVALID: "Invalid Configuration",
            ConfigStatus.VALID: "Valid Configuration",
            ConfigStatus.UNKNOWN: "Unknown",
        }
        return descriptions.get(self, "Unknown")


class ConnectionStatus(IntEnum):
    """Connection status for device connectivity."""

    CANNOT_CONNECT = 0
    CAN_CONNECT = 1
    CONNECTED = 2
    UNKNOWN = 3

    def description(self) -> str:
        """Get a human-readable description of the connection status.

        Returns:
            str: The description of the connection status.
        """
        descriptions = {
            ConnectionStatus.CANNOT_CONNECT: "Cannot Connect",
            ConnectionStatus.CAN_CONNECT: "Can Connect",
            ConnectionStatus.CONNECTED: "Connected and Loaded",
            ConnectionStatus.UNKNOWN: "Unknown",
        }
        return descriptions.get(self, "Unknown")


class DeviceTestModel(BaseModel):
    """Model to hold device test parameters and results."""

    uuid: str
    device_name: str
    device_config: dict[str, Any]
    config_status: int = Field(
        default=ConfigStatus.UNKNOWN.value,
        description="Validation status of the device configuration.",
    )
    connection_status: int = Field(
        default=ConnectionStatus.UNKNOWN.value, description="Connection status of the device."
    )
    validation_msg: str = Field(default="", description="Message from the last validation attempt.")


def get_validation_icons(
    colors: AccentColors, icon_size: tuple[int, int], convert_to_pixmap: bool = False
) -> dict[Literal["config_status", "connection_status"], dict[int, QtGui.QPixmap | QtGui.QIcon]]:
    """Get icons for validation statuses for ConfigStatus and ConnectionStatus.

    Args:
        colors (AccentColors): The accent colors to use for the icons.
        icon_size (tuple[int, int]): The size of the icons.
        convert_to_pixmap (bool, optional): Whether to convert icons to pixmaps. Defaults to False.

    Returns:
        dict: A dictionary with icons for config and connection statuses.
    """
    material_icon_partial = partial(
        material_icon, size=icon_size, convert_to_pixmap=convert_to_pixmap
    )
    icons = {
        "config_status": {
            ConfigStatus.UNKNOWN.value: material_icon_partial(
                icon_name="question_mark", color=colors.default
            ),
            ConfigStatus.VALID.value: material_icon_partial(
                icon_name="check_circle", color=colors.success
            ),
            ConfigStatus.INVALID.value: material_icon_partial(
                icon_name="error", color=colors.emergency
            ),
        },
        "connection_status": {
            ConnectionStatus.UNKNOWN.value: material_icon_partial(
                icon_name="question_mark", color=colors.default
            ),
            ConnectionStatus.CANNOT_CONNECT.value: material_icon_partial(
                icon_name="cable", color=colors.emergency
            ),
            ConnectionStatus.CAN_CONNECT.value: material_icon_partial(
                icon_name="cable", color=colors.success
            ),
            ConnectionStatus.CONNECTED.value: material_icon_partial(
                icon_name="cast_connected", color=colors.success
            ),
        },
    }
    return icons
