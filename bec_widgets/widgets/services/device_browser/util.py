from bec_lib.device import Device


def map_device_type_to_icon(device_obj: Device) -> str:
    """Associate device types with material icon names"""
    match device_obj._info.get("device_base_class", "").lower():
        case "positioner":
            return "precision_manufacturing"
        case "signal":
            return "vital_signs"
    return "deployed_code"
