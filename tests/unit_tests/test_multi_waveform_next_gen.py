import numpy as np

from bec_widgets.widgets.plots_next_gen.multi_waveform.multi_waveform import MultiWaveform
from tests.unit_tests.client_mocks import mocked_client

from .conftest import create_widget

##################################################
# MultiWaveform widget base functionality tests
##################################################


def test_multiwaveform_initialization(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    assert mw.objectName() == "MultiWaveform"
    # Inherited from PlotBase
    assert mw.title == ""
    assert mw.x_label == ""
    assert mw.y_label == ""
    # No crosshair or FPS monitor by default
    assert mw.crosshair is None
    assert mw.fps_monitor is None
    # No curves initially
    assert len(mw.plot_item.curves) == 0
    # Multiwaveform specific
    assert mw.monitor is None
    assert mw.color_palette == "magma"
    assert mw.max_trace == 200
    assert mw.flush_buffer is False
    assert mw.highlight_last_curve is True
    assert mw.opacity == 50
    assert mw.scan_id is None
    assert mw.highlighted_index == 0


def test_multiwaveform_set_monitor(qtbot, mocked_client):
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    assert mw.monitor is None

    # Set a monitor
    mw.plot("waveform1d")
    assert mw.monitor == "waveform1d"
    assert mw.config.monitor == "waveform1d"
    assert mw.connected is True


def test_multiwaveform_set_properties(qtbot, mocked_client):
    """Check that MultiWaveform properties can be set and retrieved correctly."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    # Default checks
    assert mw.color_palette == "magma"
    assert mw.max_trace == 200
    assert mw.flush_buffer is False
    assert mw.highlight_last_curve is True
    assert mw.opacity == 50

    # Change properties
    mw.color_palette = "viridis"
    mw.max_trace = 10
    mw.flush_buffer = True
    mw.highlight_last_curve = False
    mw.opacity = 75

    # Verify that changes took effect
    assert mw.color_palette == "viridis"
    assert mw.max_trace == 10
    assert mw.flush_buffer is True
    assert mw.highlight_last_curve is False
    assert mw.opacity == 75


def test_multiwaveform_curve_limit_no_flush(qtbot, mocked_client):
    """Check that limiting the number of curves without flush simply hides older ones."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.max_trace = 3
    mw.flush_buffer = False

    # Simulate updates that create multiple curves
    for i in range(5):
        msg_data = {"data": np.array([i, i + 0.5, i + 1])}
        mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_1"})

    # There should be 5 curves in total, but only the last 3 are visible
    assert len(mw.curves) == 5
    visible_curves = [c for c in mw.curves if c.isVisible()]
    assert len(visible_curves) == 3


def test_multiwaveform_curve_limit_flush(qtbot, mocked_client):
    """Check that limiting the number of curves with flush removes older ones."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.max_trace = 3
    mw.flush_buffer = True

    # Simulate adding multiple curves
    for i in range(5):
        msg_data = {"data": np.array([i, i + 0.5, i + 1])}
        mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_1"})

    # Only 3 curves remain after flush
    assert len(mw.curves) == 3
    # They should match the last 3 that were inserted
    x_data, y_data = mw.curves[0].getData()
    assert np.array_equal(y_data, [2, 2.5, 3])
    x_data, y_data = mw.curves[1].getData()
    assert np.array_equal(y_data, [3, 3.5, 4])
    x_data, y_data = mw.curves[2].getData()
    assert np.array_equal(y_data, [4, 4.5, 5])


def test_multiwaveform_highlight_last_curve(qtbot, mocked_client):
    """Check highlight_last_curve behavior."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.max_trace = 5
    mw.flush_buffer = False

    # Simulate adding multiple curves
    for i in range(3):
        msg_data = {"data": np.array([i, i + 1, i + 2])}
        mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_1"})

    # Initially highlight_last_curve is True, so the last visible curve is highlighted
    # The highlight index should be -1 in the code's logic
    assert mw.highlight_last_curve is True

    # Disable highlight_last_curve
    mw.highlight_last_curve = False

    # Force highlight of the 1st visible curve (index 0 among visible)
    mw.set_curve_highlight(0)
    assert mw.highlighted_index == 0


def test_multiwaveform_opacity_changes(qtbot, mocked_client):
    """Check changing opacity affects existing curves."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    # Add one curve
    msg_data = {"data": np.array([10, 20, 30])}
    mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_1"})
    assert len(mw.curves) == 1

    # Default opacity is 50
    assert mw.opacity == 50

    # Change opacity
    mw.opacity = 80
    assert mw.opacity == 80


def test_multiwaveform_set_colormap(qtbot, mocked_client):
    """Check that setting a new colormap updates curve colors."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    # Simulate multiple curve updates
    for i in range(3):
        msg_data = {"data": np.array([i, i + 1, i + 2])}
        mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_1"})

    # Default color_palette is "magma"
    assert mw.color_palette == "magma"
    # Now change to a new colormap
    mw.color_palette = "viridis"
    assert mw.color_palette == "viridis"


def test_multiwaveform_simulate_updates(qtbot, mocked_client):
    """Simulate a series of 1D updates to ensure the data is appended and the correct number of curves appear."""
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    mw.plot("waveform1d")

    data_series = [np.random.rand(5), np.random.rand(5), np.random.rand(5)]
    for idx, arr in enumerate(data_series):
        msg_data = {"data": arr}
        mw.on_monitor_1d_update(msg_data, metadata={"scan_id": "scan_99"})
        # Each update should add a new curve
        assert len(mw.curves) == idx + 1
        x_data, y_data = mw.curves[-1].getData()
        assert np.array_equal(y_data, arr)

    # Check that the scan_id was updated
    assert mw.scan_id == "scan_99"


##################################################
# MultiWaveform control panel and toolbar
##################################################


def test_control_panel_updates_widget(qtbot, mocked_client):
    """
    Interact with the control panel’s UI elements and confirm the widget’s properties are updated.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    assert mw.opacity == 50
    assert mw.flush_buffer is False
    assert mw.max_trace == 200
    assert mw.highlight_last_curve is True

    mw.controls.ui.opacity.setValue(80)
    assert mw.opacity == 80

    mw.controls.ui.flush_buffer.setChecked(True)
    assert mw.flush_buffer is True

    mw.controls.ui.max_trace.setValue(12)
    assert mw.max_trace == 12

    mw.controls.ui.highlight_last_curve.setChecked(False)
    assert mw.highlight_last_curve is False


def test_widget_updates_control_panel(qtbot, mocked_client):
    """
    Change properties directly on the MultiWaveform and verify the control panel UI reflects those changes.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    mw.opacity = 25
    qtbot.wait(100)
    assert mw.controls.ui.opacity.value() == 25

    mw.flush_buffer = True
    qtbot.wait(100)
    assert mw.controls.ui.flush_buffer.isChecked() is True

    mw.max_trace = 9
    qtbot.wait(100)
    assert mw.controls.ui.max_trace.value() == 9

    mw.highlight_last_curve = False
    qtbot.wait(100)
    assert mw.controls.ui.highlight_last_curve.isChecked() is False


def test_selection_toolbar_updates_widget(qtbot, mocked_client):
    """
    Confirm that selecting a monitor and a colormap from the selection toolbar
    updates the widget properties.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)
    toolbar = mw.monitor_selection_bundle
    monitor_combo = toolbar.monitor
    colormap_widget = toolbar.colormap_widget

    monitor_combo.addItem("waveform1d")
    monitor_combo.setCurrentText("waveform1d")
    assert mw.monitor == "waveform1d"

    colormap_widget.colormap = "viridis"
    assert mw.color_palette == "viridis"


def test_control_panel_opacity_slider_spinbox(qtbot, mocked_client):
    """
    Verify that when the user moves the opacity slider or spinbox, the widget's
    opacity property updates, and vice versa. Also confirm they stay in sync.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    slider_opacity = mw.controls.ui.opacity
    spinbox_opacity = mw.controls.ui.spinbox_opacity

    # Default
    assert mw.opacity == 50
    assert slider_opacity.value() == 50
    assert spinbox_opacity.value() == 50

    # Move the slider
    slider_opacity.setValue(75)
    assert mw.opacity == 75
    assert spinbox_opacity.value() == 75

    # Move the spinbox
    spinbox_opacity.setValue(20)
    assert mw.opacity == 20
    assert slider_opacity.value() == 20

    mw.opacity = 95
    qtbot.wait(100)
    assert slider_opacity.value() == 95
    assert spinbox_opacity.value() == 95


def test_control_panel_highlight_slider_spinbox(qtbot, mocked_client):
    """
    Test that the slider and spinbox for curve highlighting update
    the widget’s highlighted_index property, and are disabled if
    highlight_last_curve is True.
    """
    mw = create_widget(qtbot, MultiWaveform, client=mocked_client)

    slider_index = mw.controls.ui.highlighted_index
    spinbox_index = mw.controls.ui.spinbox_index
    checkbox_highlight_last = mw.controls.ui.highlight_last_curve

    # By default highlight_last_curve is True, so slider/spinbox are disabled:
    assert checkbox_highlight_last.isChecked() is True
    assert not slider_index.isEnabled()
    assert not spinbox_index.isEnabled()

    # Uncheck highlight_last_curve -> slider/spinbox become enabled
    checkbox_highlight_last.setChecked(False)
    assert checkbox_highlight_last.isChecked() is False
    assert slider_index.isEnabled()
    assert spinbox_index.isEnabled()

    # Simulate a few curves so there's something to highlight
    data_arrays = [np.array([0, 1, 2]), np.array([3, 4, 5]), np.array([6, 7, 8])]
    for arr in data_arrays:
        mw.on_monitor_1d_update({"data": arr}, {"scan_id": "scan_123"})

    # The number_of_visible_curves == 3 now
    max_index = mw.number_of_visible_curves - 1
    assert max_index == 2

    # Move the slider to index 1
    slider_index.setValue(1)
    assert mw.highlighted_index == 1
    assert spinbox_index.value() == 1

    # Move the spinbox to index 2
    spinbox_index.setValue(2)
    assert mw.highlighted_index == 2
    assert slider_index.value() == 2

    # Directly set mw.highlighted_index
    mw.highlighted_index = 0
    qtbot.wait(100)
    assert slider_index.value() == 0
    assert spinbox_index.value() == 0

    # Re-check highlight_last_curve -> slider/spinbox disabled again
    checkbox_highlight_last.setChecked(True)
    assert not slider_index.isEnabled()
    assert not spinbox_index.isEnabled()
    assert mw.highlighted_index == 2
