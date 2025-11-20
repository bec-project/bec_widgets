from typing import Final

# Denotes a MIME type for JSON-encoded list of device config dictionaries
MIME_DEVICE_CONFIG: Final[str] = "application/x-bec_device_config"

# Custom user roles
SORT_KEY_ROLE: Final[int] = 117
CONFIG_DATA_ROLE: Final[int] = 118

# TODO 882 keep in sync with headers in device_table_view.py
HEADERS_HELP_MD: dict[str, str] = {
    "valid": {
        "long": "\n".join(
            [
                "## Valid",
                "The current configuration status of the device. Can be one of the following values: ",
                "### **VALID** \n The device configuration is valid and can be used.",
                "### **INVALID** \n The device configuration is invalid.",
                "### **UNKNOWN** \n The device configuration has not been validated yet.",
            ]
        ),
        "short": "Validation status of the device configuration.",
    },
    "connect": {
        "long": "\n".join(
            [
                "## Connect",
                "The current connection status of the device. Can be one of the following values: ",
                "### **CONNECTED** \n The device is connected and in current session.",
                "### **CAN_CONNECT** \n The connection to the device has been validated. It's not yet loaded in the current session.",
                "### **CANNOT_CONNECT** \n The connection to the device could not be established.",
                "### **UNKNOWN** \n The connection status of the device is unknown.",
            ]
        ),
        "short": "Connection status of the device.",
    },
    "name": {
        "long": "\n".join(["## Name ", "The name of the device."]),
        "short": "Name of the device.",
    },
    "deviceClass": {
        "long": "\n".join(
            [
                "## Device Class",
                "The device class specifies the type of the device. It will be used to create the instance.",
            ]
        ),
        "short": "Python class for the device.",
    },
    "readoutPriority": {
        "long": "\n".join(
            [
                "## Readout Priority",
                "The readout priority of the device. Can be one of the following values: ",
                "### **monitored** \n The monitored priority is used for devices that are read out during the scan (i.e. at every step) and whose value may change during the scan.",
                "### **baseline** \n The baseline priority is used for devices that are read out at the beginning of the scan and whose value does not change during the scan.",
                "### **async** \n The async priority is used for devices that are asynchronous to the monitored devices, and send their data independently.",
                "### **continuous** \n The continuous priority is used for devices that are read out continuously during the scan.",
                "### **on_request** \n The on_request priority is used for devices that should not be read out during the scan, yet are configured to be read out manually.",
            ]
        ),
        "short": "Readout priority of the device for scans in BEC.",
    },
    "deviceTags": {
        "long": "\n".join(
            [
                "## Device Tags",
                "A list of tags associated with the device. Tags can be used to group devices and filter them in the device manager.",
            ]
        ),
        "short": "Tags associated with the device.",
    },
    "enabled": {
        "long": "\n".join(
            [
                "## Enabled",
                "Indicator whether the device is enabled or disabled. Disabled devices can not be used.",
            ]
        ),
        "short": "Enabled status of the device.",
    },
    "readOnly": {
        "long": "\n".join(
            ["## Read Only", "Indicator that a device is read-only or can be modified."]
        ),
        "short": "Read-only status of the device.",
    },
    "onFailure": {
        "long": "\n".join(
            [
                "## On Failure",
                "Specifies the behavior of the device in case of a failure. Can be one of the following values: ",
                "### **buffer** \n The device readback will fall back to the last known value.",
                "### **retry** \n The device readback will be retried once, and raises an error if it fails again.",
                "### **raise** \n The device readback will raise immediately.",
            ]
        ),
        "short": "On failure behavior of the device.",
    },
    "softwareTrigger": {
        "long": "\n".join(
            [
                "## Software Trigger",
                "Indicator whether the device receives a software trigger from BEC during a scan.",
            ]
        ),
        "short": "Software trigger status of the device.",
    },
    "description": {
        "long": "\n".join(["## Description", "A short description of the device."]),
        "short": "Description of the device.",
    },
}
