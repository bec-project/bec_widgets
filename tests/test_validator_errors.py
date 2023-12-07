# pylint: disable=missing-function-docstring
import pytest
from pydantic import ValidationError
from bec_widgets.validation.monitor_config_validator import (
    MonitorConfigValidator,
    Signal,
    PlotAxis,
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


def test_signal_validation_device_has_no_signals(setup_devices):
    with pytest.raises(ValidationError) as excinfo:
        Signal(name="no_signal_device")

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "no_device_signals"
    assert 'Device "no_signal_device" does not have "signals" defined' in errors[0]["msg"]


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

    # Case with more than one signal for x-axis
    plot_axis_multiple_signals = PlotAxis(
        signals=[valid_signal, valid_signal], label="X Axis Label"
    )
    with pytest.raises(ValidationError) as excinfo:
        PlotConfig(
            plot_name="Test Plot",
            x=plot_axis_multiple_signals,
            y=PlotAxis(signals=[valid_signal], label="Y Axis Label"),
        )

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "x_axis_multiple_signals"
    assert "There must be exactly one signal for x axis" in errors[0]["msg"]
