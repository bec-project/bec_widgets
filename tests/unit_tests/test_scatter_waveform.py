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
    assert curve.config.x_device == ScatterDeviceSignal(name="samx", entry="samx")
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
    assert swf.x_device_name == ""
    assert swf.x_device_entry == ""
    assert swf.y_device_name == ""
    assert swf.y_device_entry == ""
    assert swf.z_device_name == ""
    assert swf.z_device_entry == ""

    # Set devices via plot
    swf.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Check properties return device names and entries separately
    assert swf.x_device_name == "samx"
    assert swf.x_device_entry  # Should have some entry
    assert swf.y_device_name == "samy"
    assert swf.y_device_entry  # Should have some entry
    assert swf.z_device_name == "bpm4i"
    assert swf.z_device_entry  # Should have some entry


def test_device_safe_properties_set_name(qtbot, mocked_client):
    """Test that device SafeProperty setters work for device names."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set x_device_name - should auto-validate entry
    swf.x_device_name = "samx"
    assert swf._main_curve.config.x_device is not None
    assert swf._main_curve.config.x_device.name == "samx"
    assert swf._main_curve.config.x_device.entry is not None  # Entry should be validated
    assert swf.x_device_name == "samx"

    # Set y_device_name
    swf.y_device_name = "samy"
    assert swf._main_curve.config.y_device is not None
    assert swf._main_curve.config.y_device.name == "samy"
    assert swf._main_curve.config.y_device.entry is not None
    assert swf.y_device_name == "samy"

    # Set z_device_name
    swf.z_device_name = "bpm4i"
    assert swf._main_curve.config.z_device is not None
    assert swf._main_curve.config.z_device.name == "bpm4i"
    assert swf._main_curve.config.z_device.entry is not None
    assert swf.z_device_name == "bpm4i"


def test_device_safe_properties_set_entry(qtbot, mocked_client):
    """Test that device entry properties can override default entries."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device name first - this auto-validates entry
    swf.x_device_name = "samx"
    initial_entry = swf.x_device_entry
    assert initial_entry  # Should have auto-validated entry

    # Override with specific entry
    swf.x_device_entry = "samx"
    assert swf._main_curve.config.x_device.entry == "samx"
    assert swf.x_device_entry == "samx"

    # Same for y device
    swf.y_device_name = "samy"
    swf.y_device_entry = "samy_setpoint"
    assert swf._main_curve.config.y_device.entry == "samy_setpoint"

    # Same for z device
    swf.z_device_name = "bpm4i"
    swf.z_device_entry = "bpm4i"
    assert swf._main_curve.config.z_device.entry == "bpm4i"


def test_device_entry_cannot_be_set_without_name(qtbot, mocked_client):
    """Test that setting entry without device name logs warning and does nothing."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Try to set entry without device name
    swf.x_device_entry = "some_entry"
    # Should not crash, entry should remain empty
    assert swf.x_device_entry == ""
    assert swf._main_curve.config.x_device is None


def test_device_safe_properties_set_empty(qtbot, mocked_client):
    """Test that device SafeProperty setters handle empty strings."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device first
    swf.x_device_name = "samx"
    assert swf._main_curve.config.x_device is not None

    # Set to empty string - should clear the device
    swf.x_device_name = ""
    assert swf.x_device_name == ""
    assert swf._main_curve.config.x_device is None


def test_device_safe_properties_auto_plot(qtbot, mocked_client):
    """Test that setting all three devices triggers auto-plot."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set all three devices
    swf.x_device_name = "samx"
    swf.y_device_name = "samy"
    swf.z_device_name = "bpm4i"

    # Check that plot was called (config should be updated)
    assert swf._main_curve.config.x_device is not None
    assert swf._main_curve.config.y_device is not None
    assert swf._main_curve.config.z_device is not None


def test_device_properties_update_labels(qtbot, mocked_client):
    """Test that setting device properties updates axis labels."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set x device - should update x label
    swf.x_device_name = "samx"
    assert swf.x_label == "samx"

    # Set y device - should update y label
    swf.y_device_name = "samy"
    assert swf.y_label == "samy"

    # Note: ScatterWaveform doesn't have a title like Heatmap does for z_device


def test_device_properties_partial_configuration(qtbot, mocked_client):
    """Test that widget handles partial device configuration gracefully."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set only x device
    swf.x_device_name = "samx"
    assert swf.x_device_name == "samx"
    assert swf.y_device_name == ""
    assert swf.z_device_name == ""

    # Set only y device (x already set)
    swf.y_device_name = "samy"
    assert swf.x_device_name == "samx"
    assert swf.y_device_name == "samy"
    assert swf.z_device_name == ""

    # Auto-plot should not trigger yet (z missing)
    # But devices should be configured
    assert swf._main_curve.config.x_device is not None
    assert swf._main_curve.config.y_device is not None


def test_device_properties_in_user_access(qtbot, mocked_client):
    """Test that device properties are exposed in USER_ACCESS for RPC."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    assert "x_device_name" in ScatterWaveform.USER_ACCESS
    assert "x_device_name.setter" in ScatterWaveform.USER_ACCESS
    assert "x_device_entry" in ScatterWaveform.USER_ACCESS
    assert "x_device_entry.setter" in ScatterWaveform.USER_ACCESS
    assert "y_device_name" in ScatterWaveform.USER_ACCESS
    assert "y_device_name.setter" in ScatterWaveform.USER_ACCESS
    assert "y_device_entry" in ScatterWaveform.USER_ACCESS
    assert "y_device_entry.setter" in ScatterWaveform.USER_ACCESS
    assert "z_device_name" in ScatterWaveform.USER_ACCESS
    assert "z_device_name.setter" in ScatterWaveform.USER_ACCESS
    assert "z_device_entry" in ScatterWaveform.USER_ACCESS
    assert "z_device_entry.setter" in ScatterWaveform.USER_ACCESS


def test_device_properties_validation(qtbot, mocked_client):
    """Test that device entries are validated through entry_validator."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device name - entry should be auto-validated
    swf.x_device_name = "samx"
    initial_entry = swf.x_device_entry

    # The entry should be validated (will be "samx" in the mock)
    assert initial_entry == "samx"

    # Set a different entry - should also be validated
    swf.x_device_entry = "samx"  # Use same name as validated entry
    assert swf.x_device_entry == "samx"


def test_device_properties_with_plot_method(qtbot, mocked_client):
    """Test that device properties reflect values set via plot() method."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Use plot method
    swf.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Properties should reflect the plotted devices
    assert swf.x_device_name == "samx"
    assert swf.y_device_name == "samy"
    assert swf.z_device_name == "bpm4i"

    # Entries should be validated
    assert swf.x_device_entry == "samx"
    assert swf.y_device_entry == "samy"
    assert swf.z_device_entry == "bpm4i"


def test_device_properties_overwrite_via_properties(qtbot, mocked_client):
    """Test that device properties can overwrite values set via plot()."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # First set via plot
    swf.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Overwrite x device via properties
    swf.x_device_name = "samz"
    assert swf.x_device_name == "samz"
    assert swf._main_curve.config.x_device.name == "samz"

    # Overwrite y device entry
    swf.y_device_entry = "samy"
    assert swf.y_device_entry == "samy"


def test_device_properties_clearing_devices(qtbot, mocked_client):
    """Test clearing devices by setting to empty string."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set all devices
    swf.x_device_name = "samx"
    swf.y_device_name = "samy"
    swf.z_device_name = "bpm4i"

    # Clear x device
    swf.x_device_name = ""
    assert swf.x_device_name == ""
    assert swf._main_curve.config.x_device is None

    # Y and Z should still be set
    assert swf.y_device_name == "samy"
    assert swf.z_device_name == "bpm4i"


def test_device_properties_property_changed_signal(qtbot, mocked_client):
    """Test that property_changed signal is emitted when devices are set."""
    from unittest.mock import Mock

    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Connect mock to property_changed signal
    mock_handler = Mock()
    swf.property_changed.connect(mock_handler)

    # Set device name
    swf.x_device_name = "samx"

    # Signal should have been emitted
    assert mock_handler.called
    # Check it was called with correct arguments
    mock_handler.assert_any_call("x_device_name", "samx")


def test_device_entry_validation_with_invalid_device(qtbot, mocked_client):
    """Test that invalid device names are handled gracefully."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Try to set invalid device name
    swf.x_device_name = "nonexistent_device"

    # Should not crash, but device might not be set if validation fails
    # The implementation silently fails, so we just check it doesn't crash


def test_device_properties_sequential_entry_changes(qtbot, mocked_client):
    """Test changing device entry multiple times."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Set device
    swf.x_device_name = "samx"

    # Change entry multiple times
    swf.x_device_entry = "samx_velocity"
    assert swf.x_device_entry == "samx_velocity"

    swf.x_device_entry = "samx_setpoint"
    assert swf.x_device_entry == "samx_setpoint"

    swf.x_device_entry = "samx"
    assert swf.x_device_entry == "samx"


def test_device_properties_with_none_values(qtbot, mocked_client):
    """Test that None values are handled as empty strings."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Device name None should be treated as empty
    swf.x_device_name = None
    assert swf.x_device_name == ""

    # Set a device first
    swf.y_device_name = "samy"

    # Entry None should not change anything
    swf.y_device_entry = None
    assert swf.y_device_entry  # Should still have validated entry


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
    settings.ui.x_name.set_device("samx")
    settings.ui.y_name.set_device("samy")
    settings.ui.z_name.set_device("bpm4i")

    # Mock the plot method to verify it gets called with correct arguments
    with patch.object(swf, "plot") as mock_plot:
        settings.accept_changes()

        # Verify plot was called
        mock_plot.assert_called_once()

        # Get the call arguments
        call_kwargs = mock_plot.call_args[1]

        # Verify device names were extracted correctly
        assert call_kwargs["x_name"] == "samx"
        assert call_kwargs["y_name"] == "samy"
        assert call_kwargs["z_name"] == "bpm4i"


def test_scatter_curve_settings_accept_changes_with_entries(qtbot, mocked_client):
    """Test that accept_changes correctly extracts signal entries from SignalComboBox."""
    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Create the settings widget
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Set devices first to populate signal comboboxes
    settings.ui.x_name.set_device("samx")
    settings.ui.y_name.set_device("samy")
    settings.ui.z_name.set_device("bpm4i")
    qtbot.wait(100)  # Allow time for signals to populate

    # Mock the plot method
    with patch.object(swf, "plot") as mock_plot:
        settings.accept_changes()

        mock_plot.assert_called_once()
        call_kwargs = mock_plot.call_args[1]

        # Verify entries are extracted (will use get_signal_name())
        assert "x_entry" in call_kwargs
        assert "y_entry" in call_kwargs
        assert "z_entry" in call_kwargs


def test_scatter_curve_settings_accept_changes_color_map(qtbot, mocked_client):
    """Test that accept_changes correctly extracts color_map from widget."""

    swf = create_widget(qtbot, ScatterWaveform, client=mocked_client)

    # Create the settings widget
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Set devices
    settings.ui.x_name.set_device("samx")
    settings.ui.y_name.set_device("samy")
    settings.ui.z_name.set_device("bpm4i")

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
    swf.plot(x_name="samx", y_name="samy", z_name="bpm4i")

    # Create the settings widget - it should fetch properties automatically
    settings = ScatterCurveSettings(parent=None, target_widget=swf, popup=True)
    qtbot.addWidget(settings)

    # Verify the settings widget has fetched the values
    assert settings.ui.x_name.currentText() == "samx"
    assert settings.ui.y_name.currentText() == "samy"
    assert settings.ui.z_name.currentText() == "bpm4i"
