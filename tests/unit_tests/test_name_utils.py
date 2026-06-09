from bec_widgets.utils.name_utils import pascal_to_snake, sanitize_namespace


def test_pascal_to_snake():
    assert pascal_to_snake("DeviceWithinLimitsState") == "device_within_limits_state"
    assert pascal_to_snake("BECStatusWidget") == "bec_status_widget"


def test_sanitize_namespace():
    assert sanitize_namespace("scan 1 / user") == "scan_1_user"
    assert sanitize_namespace(" beamline.state-1 ") == "beamline.state-1"
    assert sanitize_namespace("   ") is None
    assert sanitize_namespace(None) is None
