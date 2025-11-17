import numpy as np
import pyqtgraph as pg
import pytest
from qtpy.QtCore import QPointF

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.plots.image.image import Image
from tests.unit_tests.conftest import create_widget

##################################################
# Image widget base functionality tests
##################################################


def test_initialization_defaults(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    assert bec_image_view.color_map == "plasma"
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.config.lock_aspect_ratio is True
    assert bec_image_view.main_image is not None
    assert bec_image_view._color_bar is None


def test_setting_color_map(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.color_map = "viridis"
    assert bec_image_view.color_map == "viridis"
    assert bec_image_view.config.color_map == "viridis"


def test_invalid_color_map_handling(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    previous_colormap = bec_image_view.color_map
    bec_image_view.color_map = "invalid_colormap_name"
    assert bec_image_view.color_map == previous_colormap
    assert bec_image_view.main_image.color_map == previous_colormap


def test_toggle_autorange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.autorange = False
    assert bec_image_view.autorange is False

    bec_image_view.toggle_autorange(True, "max")
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "max"

    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "max"
    assert bec_image_view.main_image.config.autorange is True
    assert bec_image_view.main_image.config.autorange_mode == "max"


def test_lock_aspect_ratio(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.lock_aspect_ratio = True
    assert bec_image_view.lock_aspect_ratio is True
    assert bool(bec_image_view.plot_item.getViewBox().state["aspectLocked"]) is True
    assert bec_image_view.config.lock_aspect_ratio is True


def test_set_vrange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.v_range = (10, 100)
    assert bec_image_view.v_range == QPointF(10, 100)
    assert bec_image_view.main_image.levels == (10, 100)
    assert bec_image_view.main_image.config.v_range == (10, 100)


def test_enable_simple_colorbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_simple_colorbar = True
    assert bec_image_view.enable_simple_colorbar is True
    assert bec_image_view.config.color_bar == "simple"
    assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)

    # Enabling color bar should not cancel autorange
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "mean"


def test_enable_full_colorbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True
    assert bec_image_view.enable_full_colorbar is True
    assert bec_image_view.config.color_bar == "full"
    assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)

    # Enabling color bar should not cancel autorange
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "mean"


@pytest.mark.parametrize("colorbar_type", ["simple", "full"])
def test_enable_colorbar_with_vrange(qtbot, mocked_client, colorbar_type):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_colorbar(True, colorbar_type, (0, 100))

    if colorbar_type == "simple":
        assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)
        assert bec_image_view.enable_simple_colorbar is True
    else:
        assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)
        assert bec_image_view.enable_full_colorbar is True
    assert bec_image_view.config.color_bar == colorbar_type
    assert bec_image_view.v_range == QPointF(0, 100)
    assert bec_image_view.main_image.levels == (0, 100)
    assert bec_image_view._color_bar is not None


##############################################
# Preview‑signal update mechanism


def test_image_setup_preview_signal_1d(qtbot, mocked_client, monkeypatch):
    """
    Ensure that calling .image() with a (device, signal, config) tuple representing
    a 1‑D PreviewSignal connects using the 1‑D path and updates correctly.
    """
    import numpy as np

    view = create_widget(qtbot, Image, client=mocked_client)

    signal_config = {
        "obj_name": "waveform1d_img",
        "signal_class": "PreviewSignal",
        "describe": {"signal_info": {"ndim": 1}},
    }

    # Set the image monitor to the preview signal
    view.image(monitor=("waveform1d", "img", signal_config))

    # Subscriptions should indicate 1‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_1d"
    assert sub.monitor_type == "1d"
    assert sub.monitor == ("waveform1d", "img", signal_config)

    # Simulate a waveform update from the dispatcher
    waveform = np.arange(25, dtype=float)
    view.on_image_update_1d({"data": waveform}, {"scan_id": "scan_test"})
    assert view.main_image.raw_data.shape == (1, 25)
    np.testing.assert_array_equal(view.main_image.raw_data[0], waveform)


def test_image_setup_preview_signal_2d(qtbot, mocked_client, monkeypatch):
    """
    Ensure that calling .image() with a (device, signal, config) tuple representing
    a 2‑D PreviewSignal connects using the 2‑D path and updates correctly.
    """
    import numpy as np

    view = create_widget(qtbot, Image, client=mocked_client)

    signal_config = {
        "obj_name": "eiger_img2d",
        "signal_class": "PreviewSignal",
        "describe": {"signal_info": {"ndim": 2}},
    }

    # Set the image monitor to the preview signal
    view.image(monitor=("eiger", "img2d", signal_config))

    # Subscriptions should indicate 2‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_2d"
    assert sub.monitor_type == "2d"
    assert sub.monitor == ("eiger", "img2d", signal_config)

    # Simulate a 2‑D image update
    test_data = np.arange(16, dtype=float).reshape(4, 4)
    view.on_image_update_2d({"data": test_data}, {})
    np.testing.assert_array_equal(view.main_image.image, test_data)


##############################################
# Device monitor endpoint update mechanism


def test_image_setup_image_2d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="2d")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.subscriptions["main"].source == "device_monitor_2d"
    assert bec_image_view.subscriptions["main"].monitor_type == "2d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_setup_image_1d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="1d")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.subscriptions["main"].source == "device_monitor_1d"
    assert bec_image_view.subscriptions["main"].monitor_type == "1d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_setup_image_auto(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="auto")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.subscriptions["main"].source == "auto"
    assert bec_image_view.subscriptions["main"].monitor_type == "auto"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_data_update_2d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.random.rand(20, 30)
    message = {"data": test_data}
    metadata = {}

    bec_image_view.on_image_update_2d(message, metadata)

    np.testing.assert_array_equal(bec_image_view.main_image.image, test_data)


def test_image_data_update_1d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    waveform1 = np.random.rand(50)
    waveform2 = np.random.rand(60)  # Different length, tests padding logic
    metadata = {"scan_id": "scan_test"}

    bec_image_view.on_image_update_1d({"data": waveform1}, metadata)
    assert bec_image_view.main_image.raw_data.shape == (1, 50)

    bec_image_view.on_image_update_1d({"data": waveform2}, metadata)
    assert bec_image_view.main_image.raw_data.shape == (2, 60)


##############################################
# Toolbar and Actions Tests


def test_toolbar_actions_presence(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    assert bec_image_view.toolbar.components.exists("image_autorange")
    assert bec_image_view.toolbar.components.exists("lock_aspect_ratio")
    assert bec_image_view.toolbar.components.exists("image_processing_fft")
    assert bec_image_view.toolbar.components.exists("image_device_combo")
    assert bec_image_view.toolbar.components.exists("image_dim_combo")


def test_image_processing_fft_toggle(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.fft = True
    assert bec_image_view.fft is True
    bec_image_view.fft = False
    assert bec_image_view.fft is False


def test_image_processing_log_toggle(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.log = True
    assert bec_image_view.log is True
    bec_image_view.log = False
    assert bec_image_view.log is False


def test_image_rotation_and_transpose(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.num_rotation_90 = 2
    assert bec_image_view.num_rotation_90 == 2

    bec_image_view.transpose = True
    assert bec_image_view.transpose is True


@pytest.mark.parametrize("colorbar_type", ["none", "simple", "full"])
def test_setting_vrange_with_colorbar(qtbot, mocked_client, colorbar_type):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    if colorbar_type == "simple":
        bec_image_view.enable_simple_colorbar = True
    elif colorbar_type == "full":
        bec_image_view.enable_full_colorbar = True

    bec_image_view.v_range = (0, 100)
    assert bec_image_view.v_range == QPointF(0, 100)
    assert bec_image_view.main_image.levels == (0, 100)
    assert bec_image_view.main_image.config.v_range == (0, 100)
    assert bec_image_view.v_min == 0
    assert bec_image_view.v_max == 100

    if colorbar_type == "simple":
        assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)
        assert bec_image_view._color_bar.levels() == (0, 100)
    elif colorbar_type == "full":
        assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)
        assert bec_image_view._color_bar.getLevels() == (0, 100)


###################################
# Toolbar Actions
###################################


def test_setup_image_from_toolbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.device_combo_box.setCurrentText("eiger")
    bec_image_view.dim_combo_box.setCurrentText("2d")

    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.subscriptions["main"].source == "device_monitor_2d"
    assert bec_image_view.subscriptions["main"].monitor_type == "2d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_actions_interactions(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.autorange = False  # Change the initial state to False

    bec_image_view.toolbar.components.get_action("image_autorange_mean").action.trigger()
    assert bec_image_view.autorange is True
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.autorange_mode == "mean"

    bec_image_view.toolbar.components.get_action("image_autorange_max").action.trigger()
    assert bec_image_view.autorange is True
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.autorange_mode == "max"

    bec_image_view.toolbar.components.get_action("lock_aspect_ratio").action.trigger()
    assert bec_image_view.lock_aspect_ratio is False
    assert bool(bec_image_view.plot_item.getViewBox().state["aspectLocked"]) is False


def test_image_toggle_action_fft(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.toolbar.components.get_action("image_processing_fft").action.trigger()

    assert bec_image_view.fft is True
    assert bec_image_view.main_image.fft is True
    assert bec_image_view.main_image.config.processing.fft is True


def test_image_toggle_action_log(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.toolbar.components.get_action("image_processing_log").action.trigger()

    assert bec_image_view.log is True
    assert bec_image_view.main_image.log is True
    assert bec_image_view.main_image.config.processing.log is True


def test_image_toggle_action_transpose(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.toolbar.components.get_action("image_processing_transpose").action.trigger()

    assert bec_image_view.transpose is True
    assert bec_image_view.main_image.transpose is True
    assert bec_image_view.main_image.config.processing.transpose is True


def test_image_toggle_action_rotate_right(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.toolbar.components.get_action("image_processing_rotate_right").action.trigger()

    assert bec_image_view.num_rotation_90 == 3
    assert bec_image_view.main_image.num_rotation_90 == 3
    assert bec_image_view.main_image.config.processing.num_rotation_90 == 3


def test_image_toggle_action_rotate_left(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.toolbar.components.get_action("image_processing_rotate_left").action.trigger()

    assert bec_image_view.num_rotation_90 == 1
    assert bec_image_view.main_image.num_rotation_90 == 1
    assert bec_image_view.main_image.config.processing.num_rotation_90 == 1


def test_image_toggle_action_reset(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    # Setup some processing
    bec_image_view.fft = True
    bec_image_view.log = True
    bec_image_view.transpose = True
    bec_image_view.num_rotation_90 = 2

    bec_image_view.toolbar.components.get_action("image_processing_reset").action.trigger()

    assert bec_image_view.num_rotation_90 == 0
    assert bec_image_view.main_image.num_rotation_90 == 0
    assert bec_image_view.main_image.config.processing.num_rotation_90 == 0
    assert bec_image_view.fft is False
    assert bec_image_view.main_image.fft is False
    assert bec_image_view.log is False
    assert bec_image_view.main_image.log is False
    assert bec_image_view.transpose is False
    assert bec_image_view.main_image.transpose is False


def test_roi_add_remove_and_properties(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    # Add ROIs
    rect = view.add_roi(kind="rect", name="rect_roi", line_width=7)
    circ = view.add_roi(kind="circle", name="circ_roi", line_width=5)
    assert rect in view.roi_controller.rois
    assert circ in view.roi_controller.rois
    assert rect.label == "rect_roi"
    assert circ.label == "circ_roi"
    assert rect.line_width == 7
    assert circ.line_width == 5
    # Change properties
    rect.label = "rect_roi2"
    circ.line_color = "#ff0000"
    assert rect.label == "rect_roi2"
    assert circ.line_color == "#ff0000"
    # Remove by name
    view.remove_roi("rect_roi2")
    assert rect not in view.roi_controller.rois
    # Remove by index
    view.remove_roi(0)
    assert not view.roi_controller.rois


def test_roi_controller_palette_signal(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    controller = view.roi_controller
    changed = []
    controller.paletteChanged.connect(lambda cmap: changed.append(cmap))
    view.add_roi(kind="rect")
    controller.colormap = "plasma"
    assert changed and changed[0] == "plasma"


def test_roi_controller_clear_and_get_methods(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    r1 = view.add_roi(kind="rect", name="r1")
    r2 = view.add_roi(kind="circle", name="c1")
    controller = view.roi_controller
    assert controller.get_roi_by_name("r1") == r1
    assert controller.get_roi(1) == r2
    controller.clear()
    assert not controller.rois


def test_roi_get_data_from_image_with_no_image(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    roi = view.add_roi(kind="rect")
    # Remove all images from scene
    for item in list(view.plot_item.items):
        if hasattr(item, "image"):
            view.plot_item.removeItem(item)

    with pytest.raises(RuntimeError):
        roi.get_data_from_image()


##################################################
# Settings and popups
##################################################
def test_show_roi_manager_popup(qtbot, mocked_client):
    """
    Verify that the ROI-manager dialog opens and closes correctly,
    and that the matching toolbar icon stays in sync.
    """
    view = create_widget(qtbot, Image, client=mocked_client, popups=True)

    # ROI-manager toggle is exposed via the toolbar.
    assert view.toolbar.components.exists("roi_mgr")
    roi_action = view.toolbar.components.get_action("roi_mgr").action
    assert roi_action.isChecked() is False, "Should start unchecked"

    # Open the popup.
    view.show_roi_manager_popup()

    assert view.roi_manager_dialog is not None
    assert view.roi_manager_dialog.isVisible()
    assert roi_action.isChecked() is True, "Icon should toggle on"

    # Close again.
    view.roi_manager_dialog.close()
    assert view.roi_manager_dialog is None
    assert roi_action.isChecked() is False, "Icon should toggle off"


###################################
# ROI Plots & Crosshair Switch
###################################


def test_crosshair_roi_panels_visibility(qtbot, mocked_client):
    """
    Verify that enabling the ROI-crosshair shows ROI panels and disabling hides them.
    """
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")

    # Initially panels should be hidden
    assert bec_image_view.side_panel_x.panel_height == 0
    assert bec_image_view.side_panel_y.panel_width == 0

    # Enable ROI crosshair
    switch.actions["crosshair_roi"].action.trigger()

    # Panels must be visible
    qtbot.waitUntil(
        lambda: all(
            [
                bec_image_view.side_panel_x.panel_height > 0,
                bec_image_view.side_panel_y.panel_width > 0,
            ]
        ),
        timeout=500,
    )

    # Disable ROI crosshair
    switch.actions["crosshair_roi"].action.trigger()

    # Panels hidden again
    qtbot.waitUntil(
        lambda: all(
            [
                bec_image_view.side_panel_x.panel_height == 0,
                bec_image_view.side_panel_y.panel_width == 0,
            ]
        ),
        timeout=500,
    )


def test_roi_plot_data_from_image(qtbot, mocked_client):
    """
    Check that ROI plots receive correct slice data from the 2D image.
    """
    import numpy as np

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    # Provide deterministic 2D data
    test_data = np.arange(25).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})

    # Activate ROI crosshair
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    # Simulate crosshair at row 2, col 3
    bec_image_view.update_image_slices((0, 2, 3))

    # Extract plotted data
    x_items = bec_image_view.x_roi.plot_item.listDataItems()
    y_items = bec_image_view.y_roi.plot_item.listDataItems()

    assert len(x_items) == 1
    assert len(y_items) == 1

    # Vertical slice (column)
    _, v_slice = x_items[0].getData()
    np.testing.assert_array_equal(v_slice, test_data[:, 3])

    # Horizontal slice (row)
    h_slice, _ = y_items[0].getData()
    np.testing.assert_array_equal(h_slice, test_data[2])


##############################################
# MonitorSelectionToolbarBundle specific tests
##############################################


def test_monitor_selection_reverse_device_items(qtbot, mocked_client):
    """
    Verify that _reverse_device_items correctly reverses the order of items in the
    device combobox while preserving the current selection.
    """
    view = create_widget(qtbot, Image, client=mocked_client)
    combo = view.device_combo_box

    # Replace existing items with a deterministic list
    combo.clear()
    combo.addItem("samx", 1)
    combo.addItem("samy", 2)
    combo.addItem("samz", 3)
    combo.setCurrentText("samy")

    # Reverse the items
    view._reverse_device_items()

    # Order should be reversed and selection preserved
    assert [combo.itemText(i) for i in range(combo.count())] == ["samz", "samy", "samx"]
    assert combo.currentText() == "samy"


def test_monitor_selection_populate_preview_signals(qtbot, mocked_client, monkeypatch):
    """
    Verify that _populate_preview_signals adds preview‑signal devices to the combo‑box
    with the correct userData.
    """
    view = create_widget(qtbot, Image, client=mocked_client)

    # Provide a deterministic fake device_manager with get_bec_signals
    class _FakeDM:
        def get_bec_signals(self, _filter):
            return [
                ("eiger", "img", {"obj_name": "eiger_img"}),
                ("async_device", "img2", {"obj_name": "async_device_img2"}),
            ]

    monkeypatch.setattr(view.client, "device_manager", _FakeDM())

    initial_count = view.device_combo_box.count()

    view._populate_preview_signals()

    # Two new entries should have been added
    assert view.device_combo_box.count() == initial_count + 2

    # The first newly added item should carry tuple userData describing the device/signal
    data = view.device_combo_box.itemData(initial_count)
    assert isinstance(data, tuple) and data[0] == "eiger"


def test_monitor_selection_adjust_and_connect(qtbot, mocked_client, monkeypatch):
    """
    Verify that _adjust_and_connect performs the full set-up:
    - fills the combobox with preview signals,
    - reverses their order,
    - and resets the currentText to an empty string.
    """
    view = create_widget(qtbot, Image, client=mocked_client)

    # Deterministic fake device_manager
    class _FakeDM:
        def get_bec_signals(self, _filter):
            return [("eiger", "img", {"obj_name": "eiger_img"})]

    monkeypatch.setattr(view.client, "device_manager", _FakeDM())

    combo = view.device_combo_box
    # Start from a clean state
    combo.clear()
    combo.addItem("", None)
    combo.setCurrentText("")

    # Execute the method under test
    view._adjust_and_connect()

    # Expect exactly two items: preview label followed by the empty default
    assert combo.count() == 2
    # Because of the reversal, the preview label comes first
    assert combo.itemText(0) == "eiger_img"
    # Current selection remains empty
    assert combo.currentText() == ""
