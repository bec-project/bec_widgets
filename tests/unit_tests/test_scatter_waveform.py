from unittest.mock import patch

import numpy as np

from bec_widgets.widgets.plots.scatter_waveform.scatter_curve import (
    ScatterCurveConfig,
    ScatterDeviceSignal,
)
from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
from bec_widgets.widgets.plots.scatter_waveform.settings.scatter_curve_setting import (
    ScatterCurveSettings,
)
from tests.unit_tests.client_mocks import create_dummy_scan_item, mocked_client

from .conftest import create_widget


def test_waveform_initialization(qtbot, mocked_client):
    """
    Test that a new Waveform widget initializes with the correct defaults.
    """
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    assert swf.objectName() == "ScatterWaveform"
    # Inherited from PlotBase
    assert swf.title == ""
    assert swf.x_label == ""
    assert swf.y_label == ""
    # No crosshair or FPS monitor by default
    assert swf.crosshair is None
    assert swf.fps_monitor is None
    assert swf.main_curve is not None


def test_scatter_waveform_plot(qtbot, mocked_client):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    curve = swf.plot("samx", "samy", "bpm4i")

    assert curve is not None
    assert isinstance(curve.config, ScatterCurveConfig)
    assert curve.config.device_x == ScatterDeviceSignal(device="samx", signal="samx")
    assert curve.config.label == "bpm4i-bpm4i"


def test_scatter_waveform_color_map(qtbot, mocked_client):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)
    assert swf.color_map == "plasma"

    swf.color_map = "plasma"
    assert swf.color_map == "plasma"


def test_scatter_waveform_update_with_scan_history(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    mocked_client.history.get_by_scan_id.return_value = dummy_scan
    mocked_client.history.__getitem__.return_value = dummy_scan

    swf.plot("samx", "samy", "bpm4i", label="test_curve")
    swf.update_with_scan_history(scan_id="dummy")
    qtbot.wait(500)

    assert swf.scan_item == dummy_scan

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


def test_scatter_waveform_live_update(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    monkeypatch.setattr(swf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    swf.plot("samx", "samy", "bpm4i", label="live_curve")

    # Simulate scan status indicating new scan start
    msg = {"scan_id": "dummy"}
    meta = {}
    swf.on_scan_status(msg, meta)

    assert swf.scan_id == "dummy"
    assert swf.scan_item == dummy_scan

    qtbot.wait(500)

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


def test_scatter_waveform_scan_progress(qtbot, mocked_client, monkeypatch):
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    dummy_scan = create_dummy_scan_item()
    monkeypatch.setattr(swf.queue.scan_storage, "find_scan_by_ID", lambda scan_id: dummy_scan)

    swf.plot("samx", "samy", "bpm4i")

    # Simulate scan status indicating scan progress
    swf.scan_id = "dummy"
    swf.scan_item = dummy_scan

    msg = {"progress": 50}
    meta = {}
    swf.on_scan_progress(msg, meta)
    qtbot.wait(500)

    # swf.update_sync_curves()

    x_data, y_data = swf.main_curve.getData()
    np.testing.assert_array_equal(x_data, [10, 20, 30])
    np.testing.assert_array_equal(y_data, [5, 10, 15])


# def test_scatter_waveform_settings_popup(qtbot, mocked_client):
#     """
#     Test that the settings popup is created correctly.
#     """
#     swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

#     scatter_popup_action = swf.toolbar.widgets["scatter_waveform_settings"].action
#     assert not scatter_popup_action.isChecked(), "Should start unchecked"

#     swf.show_scatter_curve_settings()

#     assert swf.scatter_dialog is not None
#     assert swf.scatter_dialog.isVisible()
#     assert scatter_popup_action.isChecked()

#     swf.scatter_dialog.close()
#     assert swf.scatter_dialog is None
#     assert not scatter_popup_action.isChecked(), "Should be unchecked after closing dialog"


################################################################################
# Device Property Tests
################################################################################


def test_device_safe_properties_get(qtbot, mocked_client):
    """Test that device SafeProperty getters work correctly."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Initially devices should be empty
    assert swf.device_x == ""
    assert swf.signal_x == ""
    assert swf.device_y == ""
    assert swf.signal_y == ""
    assert swf.device_z == ""
    assert swf.signal_z == ""

    # Set devices via plot
    swf.plot(device_x="samx", device_y="samy", device_z="bpm4i")

    # Check properties return device names and entries separately
    assert swf.device_x == "samx"
    assert swf.signal_x  # Should have some entry
    assert swf.device_y == "samy"
    assert swf.signal_y  # Should have some entry
    assert swf.device_z == "bpm4i"
    assert swf.signal_z  # Should have some entry


def test_device_safe_properties_set_name(qtbot, mocked_client):
    """Test that device SafeProperty setters work for device names."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device_x - should auto-validate entry
    swf.device_x = "samx"
    assert swf._main_curve.config.device_x is not None
    assert swf._main_curve.config.device_x.device == "samx"
    assert swf._main_curve.config.device_x.signal is not None  # Entry should be validated
    assert swf.device_x == "samx"

    # Set device_y
    swf.device_y = "samy"
    assert swf._main_curve.config.device_y is not None
    assert swf._main_curve.config.device_y.device == "samy"
    assert swf._main_curve.config.device_y.signal is not None
    assert swf.device_y == "samy"

    # Set device_z
    swf.device_z = "bpm4i"
    assert swf._main_curve.config.device_z is not None
    assert swf._main_curve.config.device_z.device == "bpm4i"
    assert swf._main_curve.config.device_z.signal is not None
    assert swf.device_z == "bpm4i"


def test_device_safe_properties_set_entry(qtbot, mocked_client):
    """Test that device entry properties can override default entries."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device name first - this auto-validates entry
    swf.device_x = "samx"
    initial_entry = swf.signal_x
    assert initial_entry  # Should have auto-validated entry

    # Override with specific entry
    swf.signal_x = "samx"
    assert swf._main_curve.config.device_x.signal == "samx"
    assert swf.signal_x == "samx"

    # Same for y device
    swf.device_y = "samy"
    swf.signal_y = "samy_setpoint"
    assert swf._main_curve.config.device_y.signal == "samy_setpoint"

    # Same for z device
    swf.device_z = "bpm4i"
    swf.signal_z = "bpm4i"
    assert swf._main_curve.config.device_z.signal == "bpm4i"


def test_device_entry_cannot_be_set_without_name(qtbot, mocked_client):
    """Test that setting entry without device name logs warning and does nothing."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Try to set entry without device name
    swf.signal_x = "some_entry"
    # Should not crash, entry should remain empty
    assert swf.signal_x == ""
    assert swf._main_curve.config.device_x is None


def test_device_safe_properties_set_empty(qtbot, mocked_client):
    """Test that device SafeProperty setters handle empty strings."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device first
    swf.device_x = "samx"
    assert swf._main_curve.config.device_x is not None

    # Set to empty string - should clear the device
    swf.device_x = ""
    assert swf.device_x == ""
    assert swf._main_curve.config.device_x is None


def test_device_safe_properties_auto_plot(qtbot, mocked_client):
    """Test that setting all three devices triggers auto-plot."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set all three devices
    swf.device_x = "samx"
    swf.device_y = "samy"
    swf.device_z = "bpm4i"

    # Check that plot was called (config should be updated)
    assert swf._main_curve.config.device_x is not None
    assert swf._main_curve.config.device_y is not None
    assert swf._main_curve.config.device_z is not None


def test_device_properties_update_labels(qtbot, mocked_client):
    """Test that setting device properties updates axis labels."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set x device - should update x label
    swf.device_x = "samx"
    assert swf.x_label == "samx"

    # Set y device - should update y label
    swf.device_y = "samy"
    assert swf.y_label == "samy"

    # Note: ScatterWaveform doesn't have a title like Heatmap does for z_device


def test_device_properties_partial_configuration(qtbot, mocked_client):
    """Test that widget handles partial device configuration gracefully."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set only x device
    swf.device_x = "samx"
    assert swf.device_x == "samx"
    assert swf.device_y == ""
    assert swf.device_z == ""

    # Set only y device (x already set)
    swf.device_y = "samy"
    assert swf.device_x == "samx"
    assert swf.device_y == "samy"
    assert swf.device_z == ""

    # Auto-plot should not trigger yet (z missing)
    # But devices should be configured
    assert swf._main_curve.config.device_x is not None
    assert swf._main_curve.config.device_y is not None


def test_device_properties_in_user_access(qtbot, mocked_client):
    """Test that device properties are exposed in USER_ACCESS for RPC."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    assert "device_x" in ScatterWaveform.USER_ACCESS
    assert "device_x.setter" in ScatterWaveform.USER_ACCESS
    assert "signal_x" in ScatterWaveform.USER_ACCESS
    assert "signal_x.setter" in ScatterWaveform.USER_ACCESS
    assert "device_y" in ScatterWaveform.USER_ACCESS
    assert "device_y.setter" in ScatterWaveform.USER_ACCESS
    assert "signal_y" in ScatterWaveform.USER_ACCESS
    assert "signal_y.setter" in ScatterWaveform.USER_ACCESS
    assert "device_z" in ScatterWaveform.USER_ACCESS
    assert "device_z.setter" in ScatterWaveform.USER_ACCESS
    assert "signal_z" in ScatterWaveform.USER_ACCESS
    assert "signal_z.setter" in ScatterWaveform.USER_ACCESS


def test_device_properties_validation(qtbot, mocked_client):
    """Test that device entries are validated through entry_validator."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device name - entry should be auto-validated
    swf.device_x = "samx"
    initial_entry = swf.signal_x

    # The entry should be validated (will be "samx" in the mock)
    assert initial_entry == "samx"

    # Set a different entry - should also be validated
    swf.signal_x = "samx"  # Use same name as validated entry
    assert swf.signal_x == "samx"


def test_device_properties_with_plot_method(qtbot, mocked_client):
    """Test that device properties reflect values set via plot() method."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Use plot method
    swf.plot(device_x="samx", device_y="samy", device_z="bpm4i")

    # Properties should reflect the plotted devices
    assert swf.device_x == "samx"
    assert swf.device_y == "samy"
    assert swf.device_z == "bpm4i"

    # Entries should be validated
    assert swf.signal_x == "samx"
    assert swf.signal_y == "samy"
    assert swf.signal_z == "bpm4i"


def test_device_properties_overwrite_via_properties(qtbot, mocked_client):
    """Test that device properties can overwrite values set via plot()."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # First set via plot
    swf.plot(device_x="samx", device_y="samy", device_z="bpm4i")

    # Overwrite x device via properties
    swf.device_x = "samz"
    assert swf.device_x == "samz"
    assert swf._main_curve.config.device_x.device == "samz"

    # Overwrite y device entry
    swf.signal_y = "samy"
    assert swf.signal_y == "samy"


def test_device_properties_clearing_devices(qtbot, mocked_client):
    """Test clearing devices by setting to empty string."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set all devices
    swf.device_x = "samx"
    swf.device_y = "samy"
    swf.device_z = "bpm4i"

    # Clear x device
    swf.device_x = ""
    assert swf.device_x == ""
    assert swf._main_curve.config.device_x is None

    # Y and Z should still be set
    assert swf.device_y == "samy"
    assert swf.device_z == "bpm4i"


def test_device_properties_property_changed_signal(qtbot, mocked_client):
    """Test that property_changed signal is emitted when devices are set."""
    from unittest.mock import Mock

    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Connect mock to property_changed signal
    mock_handler = Mock()
    swf.property_changed.connect(mock_handler)

    # Set device name
    swf.device_x = "samx"

    # Signal should have been emitted
    assert mock_handler.called
    # Check it was called with correct arguments
    mock_handler.assert_any_call("device_x", "samx")


def test_device_entry_validation_with_invalid_device(qtbot, mocked_client):
    """Test that invalid device names are handled gracefully."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Try to set invalid device name
    swf.device_x = "nonexistent_device"

    # Should not crash, but device might not be set if validation fails
    # The implementation silently fails, so we just check it doesn't crash


def test_device_properties_sequential_entry_changes(qtbot, mocked_client):
    """Test changing device entry multiple times."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device
    swf.device_x = "samx"

    # Change entry multiple times
    swf.signal_x = "samx_velocity"
    assert swf.signal_x == "samx_velocity"

    swf.signal_x = "samx_setpoint"
    assert swf.signal_x == "samx_setpoint"

    swf.signal_x = "samx"
    assert swf.signal_x == "samx"


def test_device_properties_with_none_values(qtbot, mocked_client):
    """Test that None values are handled as empty strings."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Device name None should be treated as empty
    swf.device_x = None
    assert swf.device_x == ""

    # Set a device first
    swf.device_y = "samy"

    # Entry None should not change anything
    swf.signal_y = None
    assert swf.signal_y  # Should still have validated entry


################################################################################
# ScatterCurveSettings Tests
################################################################################


def test_scatter_curve_settings_accept_changes(qtbot, mocked_client):
    """Test that accept_changes correctly extracts data from widgets and calls plot()."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Create the settings widget
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Set up the widgets with test values
    settings.ui.device_x.set_device("samx")
    settings.ui.device_y.set_device("samy")
    settings.ui.device_z.set_device("bpm4i")

    # Mock the plot method to verify it gets called with correct arguments
    with patch.object(swf, "plot") as mock_plot:
        settings.accept_changes()

        # Verify plot was called
        mock_plot.assert_called_once()

        # Get the call arguments
        call_kwargs = mock_plot.call_args[1]

        # Verify device names were extracted correctly
        assert call_kwargs["device_x"] == "samx"
        assert call_kwargs["device_y"] == "samy"
        assert call_kwargs["device_z"] == "bpm4i"


def test_scatter_curve_settings_accept_changes_with_entries(qtbot, mocked_client):
    """Test that accept_changes correctly extracts signal entries from SignalComboBox."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Create the settings widget
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Set devices first to populate signal comboboxes
    settings.ui.device_x.set_device("samx")
    settings.ui.device_y.set_device("samy")
    settings.ui.device_z.set_device("bpm4i")
    qtbot.wait(100)  # Allow time for signals to populate

    # Mock the plot method
    with patch.object(swf, "plot") as mock_plot:
        settings.accept_changes()

        mock_plot.assert_called_once()
        call_kwargs = mock_plot.call_args[1]

        # Verify entries are extracted (will use get_signal_name())
        assert "signal_x" in call_kwargs
        assert "signal_y" in call_kwargs
        assert "signal_z" in call_kwargs


def test_scatter_curve_settings_accept_changes_color_map(qtbot, mocked_client):
    """Test that accept_changes correctly extracts color_map from widget."""

    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Create the settings widget
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Set devices
    settings.ui.device_x.set_device("samx")
    settings.ui.device_y.set_device("samy")
    settings.ui.device_z.set_device("bpm4i")

    # Get the current colormap
    color_map = settings.ui.color_map.colormap

    with patch.object(swf, "plot") as mock_plot:
        settings.accept_changes()
        call_kwargs = mock_plot.call_args[1]
        assert call_kwargs["color_map"] == color_map


def test_scatter_curve_settings_fetch_all_properties(qtbot, mocked_client):
    """Test that fetch_all_properties correctly populates the settings from target widget."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # First set up the scatter waveform with some data
    swf.plot(device_x="samx", device_y="samy", device_z="bpm4i")

    # Create the settings widget - it should fetch properties automatically
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Verify the settings widget has fetched the values
    assert settings.ui.device_x.currentText() == "samx"
    assert settings.ui.device_y.currentText() == "samy"
    assert settings.ui.device_z.currentText() == "bpm4i"
