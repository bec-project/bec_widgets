from typing import Final

# Denotes a MIME type for JSON-encoded list of device config dictionaries
MIME_DEVICE_CONFIG: Final[str] = "application/x-bec_device_config"

# Custom user roles
SORT_KEY_ROLE: Final[int] = 117
CONFIG_DATA_ROLE: Final[int] = 118

# TODO 882 keep in sync with headers in device_table_view.py
HEADERS_HELP_MD: dict[str, str] = {
    "status": (
        "## Status"
        "\n"
        "The current status of the device. Can be one of the following values: \n"
        "### **LOADED** \n The device with the specified configuration is loaded in the current config.\n"
        "### **CONNECT_READY** \n The device config is valid and the connection has been validated. It has not yet been loaded to the current config.\n"
        "### **CONNECT_FAILED** \n The device config is valid, but the connection could not be established.\n"
        "### **VALID** \n The device config is valid, but the connection has not yet been validated.\n"
        "### **INVALID** \n The device config is invalid and can not be loaded to the current config.\n"
    ),
    "name": ("## Name " "\n" "The name of the device."),
    "deviceClass": (
        "## Device Class"
        "\n"
        "The device class specifies the type of the device. It will be used to create the instance."
    ),
    "readoutPriority": (
        "## Readout Priority"
        "\n"
        "The readout priority of the device. Can be one of the following values: \n"
        "### **monitored** \n The monitored priority is used for devices that are read out during the scan (i.e. at every step) and whose value may change during the scan.\n"
        "### **baseline** \n The baseline priority is used for devices that are read out at the beginning of the scan and whose value does not change during the scan.\n"
        "### **async** \n The async priority is used for devices that are asynchronous to the monitored devices, and send their data independently.\n"
        "### **continuous** \n The continuous priority is used for devices that are read out continuously during the scan.\n"
        "### **on_request** \n The on_request priority is used for devices that should not be read out during the scan, yet are configured to be read out manually.\n"
    ),
    "deviceTags": (
        "## Device Tags"
        "\n"
        "A list of tags associated with the device. Tags can be used to group devices and filter them in the device manager."
    ),
    "enabled": (
        "## Enabled"
        "\n"
        "Indicator whether the device is enabled or disabled. Disabled devices can not be used."
    ),
    "readOnly": ("## Read Only" "\n" "Indicator that a device is read-only or can be modified."),
    "onFailure": (
        "## On Failure"
        "\n"
        "Specifies the behavior of the device in case of a failure. Can be one of the following values: \n"
        "### **buffer** \n The device readback will fall back to the last known value.\n"
        "### **retry** \n The device readback will be retried once, and raises an error if it fails again.\n"
        "### **raise** \n The device readback will raise immediately.\n"
    ),
    "softwareTrigger": (
        "## Software Trigger"
        "\n"
        "Indicator whether the device receives a software trigger from BEC during a scan."
    ),
    "description": ("## Description" "\n" "A short description of the device."),
}
