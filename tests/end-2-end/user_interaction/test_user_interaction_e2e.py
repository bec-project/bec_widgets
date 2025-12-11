"""
End-to-end tests single gui instance across the full session.

Each test will use the same gui instance, simulating a real-world scenario where the gui is not
restarted for each test. The interaction is tested through the rpc calls.

Note: wait_for_namespace_created is a utility method that helps to wait for the namespace to be
created in the gui. This is necessary because the rpc calls are asynchronous and the namespace
may not be created immediately after the rpc call is made.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np
import pytest

from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCReference

PYTEST_TIMEOUT = 50

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.cli import client
    from bec_widgets.cli.client_utils import BECGuiClient

# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=protected-access
# pylint: disable=unused-variable


def wait_for_namespace_change(
    qtbot,
    gui: BECGuiClient,
    parent_widget: RPCBase | RPCReference,
    object_name: str,
    widget_gui_id: str,
    timeout: float = 10000,
    exists: bool = True,
):
    """
    Utility method to wait for the namespace to be created in the widget.

    Args:
        qtbot: The qtbot fixture.
        gui: The client_utils.BECGuiClient 'gui' object from the CLI.
        parent_widget: The widget that creates a new widget.
        object_name: The name of the widget that was created. Must appear as attribute in namespace of parent.
        widget_gui_id: The gui_id of the created widget.
        timeout: The timeout in milliseconds for the qtbot to wait for changes to appear.
        exists: If True, wait for the object to be created. If False, wait for the object to be removed.
    """
    # GUI object is not registered in the registry (yet)
    if parent_widget is gui:

        def check_reference_registered():
            # Check server registry
            obj = gui._server_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False
            # CHeck Ipython registry
            obj = gui._ipython_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False

    else:

        def check_reference_registered():
            # Check server registry
            obj = gui._server_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False
            # CHeck Ipython registry
            obj = gui._ipython_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False
            # Check reference registry
            ref = parent_widget._rpc_references.get(widget_gui_id, None)
            if exists:
                return ref is not None
            return ref is None

    try:
        qtbot.waitUntil(check_reference_registered, timeout=timeout)
    except Exception as e:
        raise RuntimeError(
            f"Timeout waiting for {parent_widget.object_name}.{object_name} to be created."
        ) from e


def create_widget(qtbot, gui: BECGuiClient, widget_cls_name: str) -> RPCReference:
    """Utility method to create a widget and wait for the namespaces to be created."""
    if hasattr(gui, "dock_area"):
        dock_area = gui.dock_area
    else:
        dock_area = gui.new(name="dock_area")
    wait_for_namespace_change(qtbot, gui, gui, dock_area.object_name, dock_area._gui_id)
    widget = dock_area.new(widget=widget_cls_name)
    wait_for_namespace_change(qtbot, gui, dock_area, widget.object_name, widget._gui_id)
    return widget


@pytest.fixture(scope="module")
def random_generator_from_seed(request):
    """Fixture to get a random seed for the following tests."""
    seed = request.config.getoption("--random-order-seed").split(":")[-1]
    try:
        seed = int(seed)
    except ValueError:  # Should not be required...
        seed = 42
    rng = random.Random(seed)
    yield rng


def maybe_remove_dock_area(qtbot, gui: BECGuiClient, random_int_gen: random.Random):
    """Utility method to remove all dock_ares from gui object, likelihood 50%."""
    random_int = random_int_gen.randint(0, 100)
    if random_int >= 50:
        # Needed, reference gets deleted in the gui
        name = gui.dock_area.object_name
        gui_id = gui.dock_area._gui_id
        gui.dock_area.delete_all()  # start fresh
        gui.delete("dock_area")
        wait_for_namespace_change(
            qtbot, gui=gui, parent_widget=gui, object_name=name, widget_gui_id=gui_id, exists=False
        )


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_bec_progress_bar(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the BECProgressBar widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.BECProgressBar)
    widget: client.BECProgressBar

    # Check rpc calls
    assert widget.label_template == "$value / $maximum - $percentage %"
    widget.set_maximum(100)
    widget.set_minimum(50)
    widget.set_value(75)

    assert widget._get_label() == "75 / 100 - 50 %"

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_bec_queue(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the BECQueue widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.BECQueue)
    widget: client.BECQueue

    # No rpc calls to test so far
    #  maybe we can add an rpc call to check the queue length

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_bec_status_box(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the BECStatusBox widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.BECStatusBox)

    # Check rpc calls
    assert widget.get_server_state() in ["RUNNING", "IDLE", "BUSY", "ERROR"]

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_dap_combo_box(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DAPComboBox widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.DapComboBox)
    widget: client.DAPComboBox

    # Check rpc calls
    widget.select_fit_model("PseudoVoigtModel")
    widget.select_x_axis("samx")
    widget.select_y_axis("bpm4i")

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_device_browser(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DeviceBrowser widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.DeviceBrowser)
    widget: client.DeviceBrowser

    # No rpc calls yet to check

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_device_combo_box(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DeviceComboBox widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.DeviceComboBox)
    widget: client.DeviceComboBox

    assert "samx" in widget.devices
    assert "bpm4i" in widget.devices

    widget.set_device("samx")

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_device_line_edit(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DeviceLineEdit widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.DeviceLineEdit)
    widget: client.DeviceLineEdit

    assert widget._is_valid_input is False
    assert "samx" in widget.devices
    assert "bpm4i" in widget.devices

    widget.set_device("samx")
    assert widget._is_valid_input is True

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_signal_line_edit(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DeviceSignalLineEdit widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.SignalLineEdit)
    widget: client.SignalLineEdit

    widget.set_device("samx")
    assert widget._is_valid_input is False
    assert widget.signals == [
        "readback",
        "setpoint",
        "motor_is_moving",
        "velocity",
        "acceleration",
        "tolerance",
    ]
    widget.set_signal("readback")
    assert widget._is_valid_input is True

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_signal_combobox(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the DeviceSignalComboBox widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.SignalComboBox)
    widget: client.SignalComboBox

    widget.set_device("samx")
    info = bec.device_manager.devices.samx._info["signals"]
    assert widget.signals == [
        ["samx (readback)", info.get("readback")],
        ["setpoint", info.get("setpoint")],
        ["motor_is_moving", info.get("motor_is_moving")],
        ["velocity", info.get("velocity")],
        ["acceleration", info.get("acceleration")],
        ["tolerance", info.get("tolerance")],
    ]
    widget.set_signal("samx (readback)")

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_image(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the Image widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.Image)
    widget: client.Image

    scans = bec.scans
    dev = bec.device_manager.devices
    # Test rpc calls
    img = widget.image(dev.eiger)
    assert img.get_data() is None
    # Run a scan and plot the image
    s = scans.line_scan(dev.samx, -3, 3, steps=50, exp_time=0.01, relative=False)
    s.wait()

    def _wait_for_scan_in_history():
        # Get scan item from history
        scan_item = bec.history.get_by_scan_id(s.scan.scan_id)
        return scan_item is not None

    qtbot.waitUntil(_wait_for_scan_in_history, timeout=7000)

    # Check that last image is equivalent to data in Redis
    last_img = bec.device_monitor.get_data(
        dev.eiger, count=1
    )  # Get last image from Redis monitor 2D endpoint
    assert np.allclose(img.get_data(), last_img)

    # Now add a device with a preview signal
    img = widget.image(["eiger", "preview"])
    s = scans.line_scan(dev.samx, -3, 3, steps=50, exp_time=0.01, relative=False)
    s.wait()

    qtbot.waitUntil(_wait_for_scan_in_history, timeout=7000)

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


# TODO re-enable when issue is resolved #560
# @pytest.mark.timeout(PYTEST_TIMEOUT)
# def test_widgets_e2e_log_panel(qtbot, connected_client_gui_obj, random_generator_from_seed):
#     """Test the LogPanel widget."""
#     gui = connected_client_gui_obj
#     bec = gui._client
#     # Create dock_area and widget
#     widget = create_widget(qtbot, gui, gui.available_widgets.LogPanel)
#     widget: client.LogPanel

#     # No rpc calls to check so far

#     # Test removing the widget, or leaving it open for the next test
#     maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_minesweeper(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the MineSweeper widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.Minesweeper)
    widget: client.MineSweeper

    # No rpc calls to check so far

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_motor_map(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the MotorMap widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.MotorMap)
    widget: client.MotorMap

    # Test RPC calls
    dev = bec.device_manager.devices
    scans = bec.scans
    # Set motor map to names
    widget.map(dev.samx, dev.samy)
    # Move motor samx to pos
    pos = dev.samx.limits[1] - 1  # -1 from higher limit
    scans.mv(dev.samx, pos, relative=False).wait()
    # Check that data is up to date
    assert np.isclose(widget.get_data()["x"][-1], pos, dev.samx.precision)
    # Move motor samy to pos
    pos = dev.samy.limits[0] + 1  # +1 from lower limit
    scans.mv(dev.samy, pos, relative=False).wait()
    # Check that data is up to date
    assert np.isclose(widget.get_data()["y"][-1], pos, dev.samy.precision)

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_multi_waveform(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test MultiWaveform widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.MultiWaveform)
    widget: client.MultiWaveform

    # Test RPC calls
    dev = bec.device_manager.devices
    scans = bec.scans
    # test plotting
    cm = "cividis"
    widget.plot(dev.waveform, color_palette=cm)
    assert widget.monitor == dev.waveform.name
    assert widget.color_palette == cm

    # Scan with BEC
    s = scans.line_scan(dev.samx, -3, 3, steps=5, exp_time=0.01, relative=False)
    s.wait()

    def _wait_for_scan_in_history():
        # Get scan item from history
        scan_item = bec.history.get_by_scan_id(s.scan.scan_id)
        return scan_item is not None

    qtbot.waitUntil(_wait_for_scan_in_history, timeout=7000)
    # Wait for data in history (should be plotted?)

    # TODO how can we check that the data was plotted, implement get_data()

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_positioner_indicator(
    qtbot, connected_client_gui_obj, random_generator_from_seed
):
    """Test the PositionIndicator widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.PositionIndicator)
    widget: client.PositionIndicator

    # TODO check what these rpc calls are supposed to do! Issue created #461
    widget.set_value(5)

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_positioner_box(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the PositionerBox widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.PositionerBox)
    widget: client.PositionerBox

    # Test rpc calls
    dev = bec.device_manager.devices
    scans = bec.scans
    # No rpc calls to check so far
    widget.set_positioner(dev.samx)
    widget.set_positioner(dev.samy.name)

    scans.mv(dev.samy, -3, relative=False).wait()

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_positioner_box_2d(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the PositionerBox2D widget."""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.PositionerBox2D)
    widget: client.PositionerBox2D

    # Test rpc calls
    dev = bec.device_manager.devices
    scans = bec.scans
    # No rpc calls to check so far
    widget.set_positioner_hor(dev.samx)
    widget.set_positioner_ver(dev.samy)

    # Try moving the motors
    scans.mv(dev.samx, 3, relative=False).wait()
    scans.mv(dev.samy, -3, relative=False).wait()

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_positioner_control_line(
    qtbot, connected_client_gui_obj, random_generator_from_seed
):
    """Test the positioner control line widget"""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.PositionerControlLine)
    widget: client.PositionerControlLine

    # Test rpc calls
    dev = bec.device_manager.devices
    scans = bec.scans
    # Set positioner
    widget.set_positioner(dev.samx)
    scans.mv(dev.samx, 3, relative=False).wait()
    widget.set_positioner(dev.samy.name)
    scans.mv(dev.samy, -3, relative=False).wait()

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


# TODO passes locally, fails on CI for some reason... -> issue #1003
# @pytest.mark.timeout(PYTEST_TIMEOUT)
# def test_widgets_e2e_ring_progress_bar(qtbot, connected_client_gui_obj, random_generator_from_seed):
#     """Test the RingProgressBar widget"""
#     gui = connected_client_gui_obj
#     bec = gui._client
#     # Create dock_area and widget
#     widget = create_widget(qtbot, gui, gui.available_widgets.RingProgressBar)
#     widget: client.RingProgressBar
#
#     widget.set_number_of_bars(3)
#     widget.rings[0].set_update("manual")
#     widget.rings[0].set_value(30)
#     widget.rings[0].set_min_max_values(0, 100)
#     widget.rings[1].set_update("scan")
#     widget.rings[2].set_update("device", device="samx")
#
#     # Test rpc calls
#     dev = bec.device_manager.devices
#     scans = bec.scans
#     # Do a scan
#     scans.line_scan(dev.samx, -3, 3, steps=50, exp_time=0.01, relative=False).wait()
#
#     # Test removing the widget, or leaving it open for the next test
#     maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_scan_control(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the ScanControl widget"""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.ScanControl)
    widget: client.ScanControl

    # No rpc calls to check so far

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_scatter_waveform(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the ScatterWaveform widget"""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.ScatterWaveform)
    widget: client.ScatterWaveform

    # Test rpc calls
    dev = bec.device_manager.devices
    scans = bec.scans
    widget.plot(dev.samx, dev.samy, dev.bpm4i)
    scans.grid_scan(dev.samx, -5, 5, 5, dev.samy, -5, 5, 5, exp_time=0.01, relative=False).wait()

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_text_box(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the TextBox widget"""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.TextBox)
    widget: client.TextBox

    # RPC calls
    widget.set_plain_text("Hello World")
    widget.set_html_text("<b> Hello World HTML </b>")

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)


@pytest.mark.timeout(PYTEST_TIMEOUT)
def test_widgets_e2e_waveform(qtbot, connected_client_gui_obj, random_generator_from_seed):
    """Test the Waveform widget"""
    gui = connected_client_gui_obj
    bec = gui._client
    # Create dock_area and widget
    widget = create_widget(qtbot, gui, gui.available_widgets.Waveform)
    widget: client.Waveform

    # Test rpc calls
    dev = bec.device_manager.devices
    scans = bec.scans
    widget.plot(dev.bpm4i)
    s = scans.line_scan(dev.samx, -3, 3, steps=50, exp_time=0.01, relative=False)
    s.wait()

    def _wait_for_scan_in_history():
        # Get scan item from history
        scan_item = bec.history.get_by_scan_id(s.scan.scan_id)
        return scan_item is not None

    qtbot.waitUntil(_wait_for_scan_in_history, timeout=7000)

    scan_item = bec.history.get_by_scan_id(s.scan.scan_id)
    samx_data = scan_item.devices.samx.samx.read()["value"]
    bpm4i_data = scan_item.devices.bpm4i.bpm4i.read()["value"]
    curve = widget.curves[0]
    assert np.allclose(curve.get_data()[0], samx_data)
    assert np.allclose(curve.get_data()[1], bpm4i_data)

    # Test removing the widget, or leaving it open for the next test
    maybe_remove_dock_area(qtbot, gui=gui, random_int_gen=random_generator_from_seed)
