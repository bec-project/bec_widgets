# pylint: disable=missing-function-docstring
import pytest
from pydantic import ValidationError
from bec_widgets.validation.monitor_config_validator import (
    MonitorConfigValidator,
    Signal,
    AxisSignal,
    PlotConfig,
)

from test_bec_monitor import mocked_client


@pytest.fixture(scope="function")
def setup_devices(mocked_client):
    MonitorConfigValidator.devices = mocked_client.device_manager.devices


def test_signal_validation_name_missing(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        Signal(name=None)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "no_device_name"
    assert "Device name must be provided" in str(excinfo.value)


def test_signal_validation_name_not_in_bec(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        Signal(name="non_existent_device")
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "no_device_bec"
    assert 'Device "non_existent_device" not found in current BEC session' in str(excinfo.value)


def test_signal_validation_entry_not_in_device(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        Signal(name="samx", entry="non_existent_entry")

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "no_entry_for_device"
    assert 'Entry "non_existent_entry" not found in device "samx" signals' in errors[0]["msg"]


def test_signal_validation_success(setup_devices):
    signal = Signal(name="samx")
    assert signal.name == "samx"


def test_plot_config_x_axis_signal_validation(setup_devices):
    # Setup a valid signal
    valid_signal = Signal(name="samx")

    with pytest.raises(ValidationError) as excinfo:
        AxisSignal(x=[valid_signal, valid_signal], y=[valid_signal, valid_signal])

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "x_axis_multiple_signals"
    assert "There must be exactly one signal for x axis" in errors[0]["msg"]


def test_plot_config_unsupported_source_type(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        PlotConfig(sources=[{"type": "unsupported_type", "signals": {}}])

    errors = excinfo.value.errors()
    print(errors)
    assert len(errors) == 1
    assert errors[0]["type"] == "literal_error"


def test_plot_config_no_source_type_provided(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        PlotConfig(sources=[{"signals": {}}])

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "missing"


def test_plot_config_history_source_type(setup_devices):
    history_source = {
        "type": "history",
        "scanID": "valid_scan_id",
        "signals": {"x": [{"name": "samx"}], "y": [{"name": "samx"}]},
    }

    plot_config = PlotConfig(sources=[history_source])

    assert len(plot_config.sources) == 1
    assert plot_config.sources[0].type == "history"
    assert plot_config.sources[0].scanID == "valid_scan_id"


def test_plot_config_redis_source_type(setup_devices):
    history_source = {
        "type": "redis",
        "endpoint": "valid_endpoint",
        "update": "append",
        "signals": {"x": [{"name": "samx"}], "y": [{"name": "samx"}]},
    }

    plot_config = PlotConfig(sources=[history_source])

    assert len(plot_config.sources) == 1
    assert plot_config.sources[0].type == "redis"
