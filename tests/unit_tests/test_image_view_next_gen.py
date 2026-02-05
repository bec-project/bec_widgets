import numpy as np
import pyqtgraph as pg
import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QPointF

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.plots.image.image import Image

##################################################
# Image widget base functionality tests
##################################################


def _set_signal_config(
    client,
    device_name: str,
    signal_name: str,
    signal_class: str,
    ndim: int,
    obj_name: str | None = None,
):
    device = client.device_manager.devices[device_name]
    device._info["signals"][signal_name] = {
        "obj_name": obj_name or signal_name,
        "signal_class": signal_class,
        "component_name": signal_name,
        "describe": {"signal_info": {"ndim": ndim}},
    }


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
# Device/signal update mechanism


def test_image_setup_preview_signal_1d(qtbot, mocked_client):
    """
    Ensure that calling .image() with a 1‑D PreviewSignal connects using the 1‑D path
    and updates correctly.
    """
    import numpy as np

    view = create_widget(qtbot, Image, client=mocked_client)

    _set_signal_config(
        mocked_client,
        "waveform1d",
        "img",
        signal_class="PreviewSignal",
        ndim=1,
        obj_name="waveform1d_img",
    )

    view.image(device_name="waveform1d", device_entry="img")

    # Subscriptions should indicate 1‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_1d"
    assert sub.monitor_type == "1d"
    assert view.device_name == "waveform1d"
    assert view.device_entry == "img"

    # Simulate a waveform update from the dispatcher
    waveform = np.arange(25, dtype=float)
    view.on_image_update_1d({"data": waveform}, {"scan_id": "scan_test"})
    assert view.main_image.raw_data.shape == (1, 25)
    np.testing.assert_array_equal(view.main_image.raw_data[0], waveform)


def test_image_setup_preview_signal_2d(qtbot, mocked_client):
    """
    Ensure that calling .image() with a 2‑D PreviewSignal connects using the 2‑D path
    and updates correctly.
    """
    import numpy as np

    view = create_widget(qtbot, Image, client=mocked_client)

    _set_signal_config(
        mocked_client,
        "eiger",
        "img2d",
        signal_class="PreviewSignal",
        ndim=2,
        obj_name="eiger_img2d",
    )

    view.image(device_name="eiger", device_entry="img2d")

    # Subscriptions should indicate 2‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_2d"
    assert sub.monitor_type == "2d"
    assert view.device_name == "eiger"
    assert view.device_entry == "img2d"

    # Simulate a 2‑D image update
    test_data = np.arange(16, dtype=float).reshape(4, 4)
    view.on_image_update_2d({"data": test_data}, {})
    np.testing.assert_array_equal(view.main_image.image, test_data)


def test_preview_signals_skip_0d_entries(qtbot, mocked_client, monkeypatch):
    """
    Preview/async combobox should omit 0‑D signals.
    """
    view = create_widget(qtbot, Image, client=mocked_client)

    def fake_get(signal_class_filter):
        signal_classes = (
            signal_class_filter
            if isinstance(signal_class_filter, (list, tuple, set))
            else [signal_class_filter]
        )
        if "PreviewSignal" in signal_classes:
            return [
                (
                    "eiger",
                    "sig0d",
                    {
                        "obj_name": "sig0d",
                        "signal_class": "PreviewSignal",
                        "describe": {"signal_info": {"ndim": 0}},
                    },
                ),
                (
                    "eiger",
                    "sig2d",
                    {
                        "obj_name": "sig2d",
                        "signal_class": "PreviewSignal",
                        "describe": {"signal_info": {"ndim": 2}},
                    },
                ),
            ]
        return []

    monkeypatch.setattr(view.client.device_manager, "get_bec_signals", fake_get)
    device_selection = view.toolbar.components.get_action("device_selection").widget
    device_selection.signal_combo_box.set_device("eiger")
    device_selection.signal_combo_box.update_signals_from_signal_classes()

    texts = [
        device_selection.signal_combo_box.itemText(i)
        for i in range(device_selection.signal_combo_box.count())
    ]
    assert "sig0d" not in texts
    assert "sig2d" in texts


def test_image_async_signal_uses_obj_name(qtbot, mocked_client, monkeypatch):
    """
    Verify async signals use obj_name for endpoints/payloads and reconnect with scan_id.
    """
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "img", signal_class="AsyncSignal", ndim=1, obj_name="async_obj"
    )

    view.image(device_name="eiger", device_entry="img")
    assert view.subscriptions["main"].async_signal_name == "async_obj"
    assert view.async_update is True

    # Prepare scan ids and capture dispatcher calls
    view.old_scan_id = "old_scan"
    view.scan_id = "new_scan"
    connected = []
    disconnected = []
    monkeypatch.setattr(
        view.bec_dispatcher,
        "connect_slot",
        lambda slot, endpoint, from_start=False, cb_info=None: connected.append(
            (slot, endpoint, from_start, cb_info)
        ),
    )
    monkeypatch.setattr(
        view.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint: disconnected.append((slot, endpoint)),
    )

    view._setup_async_image(view.scan_id)

    expected_new = MessageEndpoints.device_async_signal("new_scan", "eiger", "async_obj")
    expected_old = MessageEndpoints.device_async_signal("old_scan", "eiger", "async_obj")
    assert any(ep == expected_new for _, ep, _, _ in connected)
    assert any(ep == expected_old for _, ep in disconnected)

    # Payload extraction should use obj_name
    payload = np.array([1, 2, 3])
    msg = {"signals": {"async_obj": {"value": payload}}}
    assert np.array_equal(view._get_payload_data(msg), payload)


def test_disconnect_clears_async_state(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "img", signal_class="AsyncSignal", ndim=2, obj_name="async_obj"
    )

    view.image(device_name="eiger", device_entry="img")
    view.scan_id = "scan_x"
    view.old_scan_id = "scan_y"
    view.subscriptions["main"].async_signal_name = "async_obj"

    # Avoid touching real dispatcher
    monkeypatch.setattr(view.bec_dispatcher, "disconnect_slot", lambda *args, **kwargs: None)

    view.disconnect_monitor(device_name="eiger", device_entry="img")

    assert view.subscriptions["main"].async_signal_name is None
    assert view.async_update is False


##############################################
# Connection guardrails


def test_image_setup_rejects_unsupported_signal_class(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img", signal_class="Signal", ndim=2)

    view.image(device_name="eiger", device_entry="img")

    assert view.subscriptions["main"].source is None
    assert view.subscriptions["main"].monitor_type is None
    assert view.async_update is False


def test_image_disconnects_with_missing_entry(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=2)

    view.image(device_name="eiger", device_entry="img")
    assert view.device_name == "eiger"
    assert view.device_entry == "img"

    view.image(device_name="eiger", device_entry=None)
    assert view.device_name == ""
    assert view.device_entry == ""


def test_handle_scan_change_clears_buffers_and_resets_crosshair(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    view.scan_id = "scan_1"
    view.main_image.buffer = [np.array([1.0, 2.0])]
    view.main_image.max_len = 2

    clear_called = []
    monkeypatch.setattr(view.main_image, "clear", lambda: clear_called.append(True))
    reset_called = []
    if view.crosshair is not None:
        monkeypatch.setattr(view.crosshair, "reset", lambda: reset_called.append(True))

    view._handle_scan_change("scan_2")

    assert view.old_scan_id == "scan_1"
    assert view.scan_id == "scan_2"
    assert clear_called == [True]
    assert view.main_image.buffer == []
    assert view.main_image.max_len == 0
    if view.crosshair is not None:
        assert reset_called == [True]


def test_handle_scan_change_reconnects_async(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    view.scan_id = "scan_1"
    view.async_update = True

    called = []
    monkeypatch.setattr(view, "_setup_async_image", lambda scan_id: called.append(scan_id))

    view._handle_scan_change("scan_2")

    assert called == ["scan_2"]


def test_handle_scan_change_same_scan_noop(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    view.scan_id = "scan_1"
    view.main_image.buffer = [np.array([1.0])]
    view.main_image.max_len = 1

    clear_called = []
    monkeypatch.setattr(view.main_image, "clear", lambda: clear_called.append(True))

    view._handle_scan_change("scan_1")

    assert view.scan_id == "scan_1"
    assert clear_called == []
    assert view.main_image.buffer == [np.array([1.0])]
    assert view.main_image.max_len == 1


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
    assert bec_image_view.toolbar.components.exists("device_selection")


def test_auto_emit_syncs_image_toolbar_actions(qtbot, mocked_client):
    from unittest.mock import Mock

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    fft_action = bec_image_view.toolbar.components.get_action("image_processing_fft").action
    log_action = bec_image_view.toolbar.components.get_action("image_processing_log").action
    transpose_action = bec_image_view.toolbar.components.get_action(
        "image_processing_transpose"
    ).action

    mock_handler = Mock()
    bec_image_view.property_changed.connect(mock_handler)

    bec_image_view.fft = True
    bec_image_view.log = True
    bec_image_view.transpose = True

    assert fft_action.isChecked()
    assert log_action.isChecked()
    assert transpose_action.isChecked()
    mock_handler.assert_any_call("fft", True)
    mock_handler.assert_any_call("log", True)
    mock_handler.assert_any_call("transpose", True)


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


def test_setup_image_from_toolbar(qtbot, mocked_client, monkeypatch):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    _set_signal_config(mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=2)
    monkeypatch.setattr(
        mocked_client.device_manager,
        "get_bec_signals",
        lambda signal_class_filter: (
            [
                (
                    "eiger",
                    "img",
                    {
                        "obj_name": "img",
                        "signal_class": "PreviewSignal",
                        "describe": {"signal_info": {"ndim": 2}},
                    },
                )
            ]
            if "PreviewSignal" in (signal_class_filter or [])
            else []
        ),
    )

    device_selection = bec_image_view.toolbar.components.get_action("device_selection").widget
    device_selection.device_combo_box.update_devices_from_filters()
    device_selection.device_combo_box.setCurrentText("eiger")
    device_selection.signal_combo_box.setCurrentText("img")

    bec_image_view.on_device_selection_changed(None)
    qtbot.wait(200)

    assert bec_image_view.device_name == "eiger"
    assert bec_image_view.device_entry == "img"
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
# Device selection toolbar sync
##############################################


def test_device_selection_syncs_from_properties(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img2d", signal_class="PreviewSignal", ndim=2)
    monkeypatch.setattr(
        view.client.device_manager,
        "get_bec_signals",
        lambda signal_class_filter: (
            [
                (
                    "eiger",
                    "img2d",
                    {
                        "obj_name": "img2d",
                        "signal_class": "PreviewSignal",
                        "describe": {"signal_info": {"ndim": 2}},
                    },
                )
            ]
            if "PreviewSignal" in (signal_class_filter or [])
            else []
        ),
    )

    view.device_name = "eiger"
    view.device_entry = "img2d"

    qtbot.wait(200)  # Allow signal processing

    device_selection = view.toolbar.components.get_action("device_selection").widget
    qtbot.waitUntil(
        lambda: device_selection.device_combo_box.currentText() == "eiger"
        and device_selection.signal_combo_box.currentText() == "img2d",
        timeout=1000,
    )


def test_device_entry_syncs_from_toolbar(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img_a", signal_class="PreviewSignal", ndim=2)
    _set_signal_config(mocked_client, "eiger", "img_b", signal_class="PreviewSignal", ndim=2)

    view.device_name = "eiger"
    view.device_entry = "img_a"

    device_selection = view.toolbar.components.get_action("device_selection").widget
    device_selection.signal_combo_box.blockSignals(True)
    device_selection.signal_combo_box.setCurrentText("img_b")
    device_selection.signal_combo_box.blockSignals(False)

    view._sync_device_entry_from_toolbar()

    assert view.device_entry == "img_b"
