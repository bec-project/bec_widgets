import numpy as np
import pyqtgraph as pg
import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QPointF, Qt

from bec_widgets.widgets.plots.image.bec_histogram_lut_item import (
    BECColorBarItem,
    BECHistogramLUTItem,
)
from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.image.image_processor import ImageProcessor, ProcessingConfig
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget

##################################################
# Image widget base functionality tests
##################################################


def _set_signal_config(
    client, device: str, signal_name: str, signal_class: str, ndim: int, obj_name: str | None = None
):
    device = client.device_manager.devices[device]
    device._info["signals"][signal_name] = {
        "obj_name": obj_name or signal_name,
        "signal_class": signal_class,
        "component_name": signal_name,
        "describe": {"signal_info": {"ndim": ndim}},
    }


class _FakeClickEvent:
    """Minimal stand-in for a pyqtgraph MouseClickEvent."""

    def __init__(self, button=Qt.LeftButton):
        self._button = button
        self.accepted = False

    def button(self):
        return self._button

    def accept(self):
        self.accepted = True


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


@pytest.mark.parametrize("colorbar_type", [None, "simple", "full"])
def test_set_vrange_keeps_fractional_values(qtbot, mocked_client, colorbar_type):
    """Regression: tuple ranges went through QPoint, which truncates to int, so
    e.g. v_max = 10.5 could never produce a non-integer level."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.main_image.set_data(np.arange(100, dtype=float).reshape(10, 10))
    if colorbar_type is not None:
        bec_image_view.enable_colorbar(True, colorbar_type)

    bec_image_view.v_range = (0.25, 10.5)
    assert bec_image_view.v_range == QPointF(0.25, 10.5)
    assert bec_image_view.main_image.v_range == (0.25, 10.5)

    bec_image_view.v_max = 42.5
    assert bec_image_view.main_image.v_range == (0.25, 42.5)
    bec_image_view.v_min = 0.75
    assert bec_image_view.main_image.v_range == (0.75, 42.5)

    if colorbar_type == "simple":
        assert bec_image_view._color_bar.levels() == (0.75, 42.5)
    elif colorbar_type == "full":
        assert tuple(bec_image_view._color_bar.getLevels()) == (0.75, 42.5)


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


def test_full_colorbar_uses_bec_histogram_lut_item(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True
    color_bar = bec_image_view._color_bar
    assert isinstance(color_bar, BECHistogramLUTItem)
    # The confusing default pyqtgraph plot menu is replaced on the histogram view.
    assert color_bar.vb.getMenu(None) is color_bar._bec_menu


def test_colorbar_menu_set_levels_updates_vrange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True
    assert bec_image_view.autorange is True

    # Simulate the "Set levels…" context-menu action (image scaling via the
    # region); fractional values must survive (regression: QPoint truncation).
    bec_image_view._color_bar.sigColorLevelsChangeRequested.emit((0.5, 50.5))

    assert bec_image_view.v_range == QPointF(0.5, 50.5)
    assert bec_image_view.main_image.levels == (0.5, 50.5)
    # Setting explicit levels disables autorange.
    assert bec_image_view.autorange is False


def test_colorbar_menu_autoscale_enables_autorange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True
    bec_image_view.autorange = False

    # Simulate the "Autoscale levels" context-menu action.
    bec_image_view._color_bar.sigAutoLevelsRequested.emit()

    assert bec_image_view.autorange is True


def test_colorbar_menu_colormap_updates_image(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True

    # Simulate picking a colormap from the colorbar context menu.
    bec_image_view._color_bar.sigColorMapChangeRequested.emit("viridis")

    assert bec_image_view.color_map == "viridis"
    assert bec_image_view.config.color_map == "viridis"
    assert bec_image_view.main_image.color_map == "viridis"


def test_simple_colorbar_uses_bec_colorbar_item(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_simple_colorbar = True
    assert isinstance(bec_image_view._color_bar, BECColorBarItem)


def test_simple_colorbar_menu_signals_update_image_state(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_simple_colorbar = True

    # "Set levels…" applies explicit levels and disables autorange.
    bec_image_view._color_bar.sigColorLevelsChangeRequested.emit((1.0, 42.0))
    assert bec_image_view.v_range == QPointF(1.0, 42.0)
    assert bec_image_view.autorange is False

    # "Autoscale levels" re-enables autorange.
    bec_image_view._color_bar.sigAutoLevelsRequested.emit()
    assert bec_image_view.autorange is True

    # Picking a colormap goes through the BEC colormap handling (config + image).
    bec_image_view._color_bar.sigColorMapChangeRequested.emit("viridis")
    assert bec_image_view.config.color_map == "viridis"
    assert bec_image_view.main_image.color_map == "viridis"


@pytest.mark.parametrize(
    "first, second", [("full", "simple"), ("simple", "full"), ("full", "full")]
)
def test_switching_colorbar_styles_preserves_manual_levels(qtbot, mocked_client, first, second):
    """Switching between colorbar styles must not reset manually set levels."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.main_image.set_data(np.arange(100, dtype=float).reshape(10, 10))
    bec_image_view.enable_colorbar(True, first)

    bec_image_view.v_range = (5.0, 77.0)
    assert bec_image_view.autorange is False

    bec_image_view.enable_colorbar(True, second)
    assert bec_image_view.autorange is False
    assert bec_image_view.v_range == QPointF(5.0, 77.0)
    assert bec_image_view.main_image.v_range == (5.0, 77.0)


def test_switching_colorbar_styles_keeps_autorange(qtbot, mocked_client):
    """With autorange on, switching colorbar styles keeps autorange enabled."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.main_image.set_data(np.arange(100, dtype=float).reshape(10, 10))
    bec_image_view.enable_full_colorbar = True
    assert bec_image_view.autorange is True

    bec_image_view.enable_simple_colorbar = True
    assert bec_image_view.autorange is True


@pytest.mark.parametrize("colorbar_type", ["simple", "full"])
def test_disable_colorbar_cleans_up(qtbot, mocked_client, colorbar_type):
    """Disabling the colorbar tears down its parentless menus (no leaked top-levels)."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_colorbar(True, colorbar_type)
    color_bar = bec_image_view._color_bar

    bec_image_view.enable_colorbar(False)

    assert bec_image_view._color_bar is None
    assert bec_image_view.config.color_bar is None
    assert color_bar._cleaned_up_triggered is True


def test_enable_colorbar_invalid_style_raises(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    with pytest.raises(ValueError, match="Invalid colorbar style"):
        bec_image_view.enable_colorbar(True, "fancy")


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

    view.image(device="waveform1d", signal="img")

    # Subscriptions should indicate 1‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_1d"
    assert sub.monitor_type == "1d"
    assert view.device == "waveform1d"
    assert view.signal == "img"

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

    view.image(device="eiger", signal="img2d")

    # Subscriptions should indicate 2‑D preview connection
    sub = view.subscriptions["main"]
    assert sub.source == "device_monitor_2d"
    assert sub.monitor_type == "2d"
    assert view.device == "eiger"
    assert view.signal == "img2d"

    # Simulate a 2‑D image update
    test_data = np.arange(16, dtype=float).reshape(4, 4)
    view.on_image_update_2d({"data": test_data}, {})
    np.testing.assert_array_equal(view.main_image.image, test_data)


def test_switching_device_disconnects_previous_preview_endpoint(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=2)
    _set_signal_config(mocked_client, "waveform1d", "img", signal_class="PreviewSignal", ndim=2)

    connected = []
    disconnected = []
    monkeypatch.setattr(
        view.bec_dispatcher,
        "connect_slot",
        lambda slot, endpoint, *args, **kwargs: connected.append(endpoint),
    )
    monkeypatch.setattr(
        view.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint, *args, **kwargs: disconnected.append(endpoint),
    )

    view.image(device="eiger", signal="img")
    connected.clear()
    disconnected.clear()

    view.device = "waveform1d"

    assert MessageEndpoints.device_preview("eiger", "img") in disconnected
    assert MessageEndpoints.device_preview("waveform1d", "img") in connected


def test_switching_device_disconnects_previous_async_endpoint(qtbot, mocked_client, monkeypatch):
    """
    Verify that switching device while async_update=True disconnects device_async_signal
    endpoints for both scan_id and old_scan_id on the old device before reconnecting to
    the new device.
    """
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "img", signal_class="AsyncSignal", ndim=2, obj_name="async_obj"
    )
    _set_signal_config(
        mocked_client, "waveform1d", "img", signal_class="AsyncSignal", ndim=2, obj_name="async_obj"
    )

    connected = []
    disconnected = []
    monkeypatch.setattr(
        view.bec_dispatcher,
        "connect_slot",
        lambda slot, endpoint, *args, **kwargs: connected.append(endpoint),
    )
    monkeypatch.setattr(
        view.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint, *args, **kwargs: disconnected.append(endpoint),
    )

    view.image(device="eiger", signal="img")
    assert view.async_update is True
    assert view.subscriptions["main"].async_signal_name == "async_obj"

    view.scan_id = "scan_current"
    view.old_scan_id = "scan_previous"
    connected.clear()
    disconnected.clear()

    view.device = "waveform1d"

    # Both scan_id and old_scan_id endpoints for the old device must be disconnected
    assert (
        MessageEndpoints.device_async_signal("scan_current", "eiger", "async_obj") in disconnected
    )
    assert (
        MessageEndpoints.device_async_signal("scan_previous", "eiger", "async_obj") in disconnected
    )
    # The new device's async endpoint for the current scan must be connected
    assert (
        MessageEndpoints.device_async_signal("scan_current", "waveform1d", "async_obj") in connected
    )


def test_switching_signal_disconnects_previous_preview_endpoint(qtbot, mocked_client, monkeypatch):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img_a", signal_class="PreviewSignal", ndim=2)
    _set_signal_config(mocked_client, "eiger", "img_b", signal_class="PreviewSignal", ndim=2)

    connected = []
    disconnected = []
    monkeypatch.setattr(
        view.bec_dispatcher,
        "connect_slot",
        lambda slot, endpoint, *args, **kwargs: connected.append(endpoint),
    )
    monkeypatch.setattr(
        view.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint, *args, **kwargs: disconnected.append(endpoint),
    )

    view.image(device="eiger", signal="img_a")
    connected.clear()
    disconnected.clear()

    view.signal = "img_b"

    assert MessageEndpoints.device_preview("eiger", "img_a") in disconnected
    assert MessageEndpoints.device_preview("eiger", "img_b") in connected


def test_switching_signal_disconnects_previous_async_endpoint(qtbot, mocked_client, monkeypatch):
    """
    When the current monitor is an async signal, switching to a different signal must
    disconnect the previous async endpoint (based on scan_id/async_signal_name) before
    reconnecting with the new signal's async endpoint.
    """
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(
        mocked_client, "eiger", "img_a", signal_class="AsyncSignal", ndim=2, obj_name="async_obj_a"
    )
    _set_signal_config(
        mocked_client, "eiger", "img_b", signal_class="AsyncSignal", ndim=2, obj_name="async_obj_b"
    )

    connected = []
    disconnected = []
    monkeypatch.setattr(
        view.bec_dispatcher,
        "connect_slot",
        lambda slot, endpoint, *args, **kwargs: connected.append(endpoint),
    )
    monkeypatch.setattr(
        view.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint, *args, **kwargs: disconnected.append(endpoint),
    )

    # Connect to img_a as an async signal; scan_id is None so no actual subscription is made
    view.image(device="eiger", signal="img_a")
    assert view.async_update is True
    assert view.subscriptions["main"].async_signal_name == "async_obj_a"
    assert view.subscriptions["main"].source == "device_monitor_2d"

    # Simulate an active scan so that the async endpoint is real
    view.scan_id = "scan_123"
    connected.clear()
    disconnected.clear()

    # Switch to a different signal
    view.signal = "img_b"

    # The previous async endpoint for img_a must have been disconnected
    expected_disconnect = MessageEndpoints.device_async_signal("scan_123", "eiger", "async_obj_a")
    assert expected_disconnect in disconnected

    # The new async endpoint for img_b must have been connected
    expected_connect = MessageEndpoints.device_async_signal("scan_123", "eiger", "async_obj_b")
    assert expected_connect in connected


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

    view.image(device="eiger", signal="img")
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

    view.image(device="eiger", signal="img")
    view.scan_id = "scan_x"
    view.old_scan_id = "scan_y"
    view.subscriptions["main"].async_signal_name = "async_obj"

    # Avoid touching real dispatcher
    monkeypatch.setattr(view.bec_dispatcher, "disconnect_slot", lambda *args, **kwargs: None)

    view.disconnect_monitor(device="eiger", signal="img")

    assert view.subscriptions["main"].async_signal_name is None
    assert view.async_update is False


##############################################
# Connection guardrails


def test_image_setup_rejects_unsupported_signal_class(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img", signal_class="Signal", ndim=2)

    view.image(device="eiger", signal="img")

    assert view.subscriptions["main"].source is None
    assert view.subscriptions["main"].monitor_type is None
    assert view.async_update is False


def test_image_disconnects_with_missing_entry(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img", signal_class="PreviewSignal", ndim=2)

    view.image(device="eiger", signal="img")
    assert view.device == "eiger"
    assert view.signal == "img"

    view.image(device="eiger", signal=None)
    assert view.device == ""
    assert view.signal == ""


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

    assert bec_image_view.device == "eiger"
    assert bec_image_view.signal == "img"
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


def test_crosshair_roi_switch_is_mutually_exclusive(qtbot, mocked_client):
    """
    Switching the crosshair/ROI tool via the switcher menu must disable the
    previously active mode. In particular, switching from the ROI-crosshair back
    to the plain crosshair has to hide the ROI panels (and vice versa); the two
    modes are mutually exclusive.
    """
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    crosshair_action = switch.actions["crosshair"].action
    crosshair_roi_action = switch.actions["crosshair_roi"].action

    def panels_visible() -> bool:
        return bec_image_view.side_panel_x.panel_height > 0 and (
            bec_image_view.side_panel_y.panel_width > 0
        )

    # Activate the ROI-crosshair mode -> panels visible, crosshair hooked.
    switch.set_default_action("crosshair_roi")
    qtbot.waitUntil(panels_visible, timeout=500)
    assert bec_image_view.crosshair is not None
    assert crosshair_roi_action.isChecked()
    assert not crosshair_action.isChecked()

    # Switch to the plain crosshair -> ROI panels must hide (the regression).
    switch.set_default_action("crosshair")
    qtbot.waitUntil(lambda: not panels_visible(), timeout=500)
    assert bec_image_view.crosshair is not None  # crosshair still active
    assert crosshair_action.isChecked()
    assert not crosshair_roi_action.isChecked()

    # Switch back to the ROI-crosshair -> panels visible again.
    switch.set_default_action("crosshair_roi")
    qtbot.waitUntil(panels_visible, timeout=500)
    assert crosshair_roi_action.isChecked()
    assert not crosshair_action.isChecked()


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


def test_roi_plots_ignore_rgb_images_and_clear_stale_curves(qtbot, mocked_client):
    """RGB images have vector-valued pixels and cannot produce scalar profile curves."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    scalar_image = np.arange(25).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": scalar_image}, {})

    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.waitUntil(lambda: bec_image_view.crosshair is not None, timeout=1000)
    bec_image_view.update_image_slices((0, 2, 3))
    bec_image_view.crosshair.set_pin(2.0, 3.0)
    assert bec_image_view.x_roi_curve is not None
    assert bec_image_view.y_roi_curve is not None
    assert bec_image_view.x_roi_pinned is not None
    assert bec_image_view.y_roi_pinned is not None

    rgb_image = np.zeros((5, 5, 3), dtype=np.uint8)
    bec_image_view.on_image_update_2d({"data": rgb_image}, {})

    assert bec_image_view._compute_image_slices(bec_image_view.main_image, 2, 3) is None
    assert bec_image_view.x_roi_curve is None
    assert bec_image_view.y_roi_curve is None
    assert bec_image_view.x_roi_pinned is None
    assert bec_image_view.y_roi_pinned is None
    assert bec_image_view.x_roi.plot_item.listDataItems() == []
    assert bec_image_view.y_roi.plot_item.listDataItems() == []


def test_pinned_roi_profiles_freeze_and_clear(qtbot, mocked_client):
    """Clicking pins a frozen copy of the X/Y profiles that survives live updates."""
    import numpy as np

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})

    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    assert bec_image_view.x_roi_pinned is None
    assert bec_image_view.y_roi_pinned is None

    # Pin at pixel (row=2, col=3) -> freezes the corresponding profiles.
    bec_image_view.crosshair.set_pin(2.0, 3.0)
    assert bec_image_view.x_roi_pinned is not None
    assert bec_image_view.y_roi_pinned is not None
    _, x_pinned = bec_image_view.x_roi_pinned.getData()
    np.testing.assert_array_equal(x_pinned, test_data[:, 3])
    y_pinned, _ = bec_image_view.y_roi_pinned.getData()
    np.testing.assert_array_equal(y_pinned, test_data[2])

    # A live update at another location must NOT wipe the frozen pinned curves.
    pinned_item = bec_image_view.x_roi_pinned
    bec_image_view.update_image_slices((0, 1, 1))
    assert bec_image_view.x_roi_pinned is pinned_item
    assert pinned_item in bec_image_view.x_roi.plot_item.listDataItems()

    # Clearing the pin removes the frozen curves.
    bec_image_view.crosshair.clear_pin()
    assert bec_image_view.x_roi_pinned is None
    assert bec_image_view.y_roi_pinned is None
    assert pinned_item not in bec_image_view.x_roi.plot_item.listDataItems()


def test_pinned_roi_profiles_keep_style_on_theme_change(qtbot, mocked_client):
    """Theme changes re-pen the live profile curves but must not restyle the
    frozen (dashed) pinned reference curves."""
    import numpy as np

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    bec_image_view.update_image_slices((0, 2, 3))  # ensure the live curve exists
    pinned = bec_image_view.x_roi_pinned
    assert pinned.opts["pen"].color().name() == "#f2c037"

    bec_image_view.x_roi.apply_theme("light")

    # The pinned reference keeps its amber styling, the live curve is re-penned.
    assert pinned.opts["pen"].color().name() == "#f2c037"
    assert bec_image_view.x_roi_curve.opts["pen"].color().name() == "#000000"


def test_pin_survives_scan_reset(qtbot, mocked_client):
    """A scan transition (crosshair.reset()) must not wipe the pin or its frozen profiles."""
    import numpy as np

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    assert bec_image_view.x_roi_pinned is not None
    pin_point = bec_image_view.crosshair.pinned_point
    assert pin_point is not None

    # Image._handle_scan_change calls crosshair.reset() on each new scan id.
    bec_image_view.crosshair.reset()

    # The pin marker and the frozen reference profiles must still be there.
    assert bec_image_view.crosshair.pinned_point is pin_point
    assert bec_image_view.crosshair.pinned_pos is not None
    assert bec_image_view.x_roi_pinned is not None
    assert bec_image_view.y_roi_pinned is not None


def test_pin_and_profiles_restored_after_roi_toggle(qtbot, mocked_client):
    """Toggling crosshair-ROI off then on restores both the marker and its frozen profiles."""
    import numpy as np

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    assert bec_image_view.x_roi_pinned is not None
    pin_point = bec_image_view.crosshair.pinned_point

    # Toggle the ROI crosshair off: marker persists, frozen curves are cleared.
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(20)
    assert bec_image_view.crosshair is None
    assert bec_image_view._detached_pin is not None
    assert bec_image_view.x_roi_pinned is None

    # Toggle back on: marker is re-adopted AND the frozen profiles are rebuilt.
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(20)
    assert bec_image_view.crosshair is not None
    assert bec_image_view.crosshair.pinned_point is pin_point
    assert bec_image_view.x_roi_pinned is not None
    assert bec_image_view.y_roi_pinned is not None
    _, x_pinned = bec_image_view.x_roi_pinned.getData()
    np.testing.assert_array_equal(x_pinned, test_data[:, 3])


def test_detached_pin_can_be_removed_with_right_click(qtbot, mocked_client, monkeypatch):
    """A pin left on the plot after disabling crosshair remains removable."""
    from qtpy.QtWidgets import QMenu

    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(20)
    assert bec_image_view.crosshair is None
    assert bec_image_view._detached_pin is not None

    pin_point = bec_image_view._detached_pin["point"]
    cleared = []
    bec_image_view.crosshair_pin_cleared.connect(lambda: cleared.append(True))
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: self.actions()[0])

    event = _FakeClickEvent(button=Qt.RightButton)
    pin_point.mouseClickEvent(event)

    assert bec_image_view._detached_pin is None
    assert pin_point not in bec_image_view.plot_item.items
    assert event.accepted is True
    assert cleared == [True]


def test_pinned_profiles_follow_image_updates(qtbot, mocked_client):
    """Pinned profile curves keep their position but follow incoming image data,
    exactly like the pin's intensity label."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25, dtype=float).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    _, x_pinned = bec_image_view.x_roi_pinned.getData()
    np.testing.assert_array_equal(x_pinned, test_data[:, 3])

    updated = test_data + 100.0
    bec_image_view.on_image_update_2d({"data": updated}, {})

    qtbot.waitUntil(
        lambda: np.array_equal(bec_image_view.x_roi_pinned.getData()[1], updated[:, 3]), timeout=500
    )
    y_pinned, _ = bec_image_view.y_roi_pinned.getData()
    np.testing.assert_array_equal(y_pinned, updated[2])


def test_detached_pin_profiles_follow_image_updates(qtbot, mocked_client):
    """Pinned profiles keep following image data while the crosshair is toggled off."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25, dtype=float).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    bec_image_view.toggle_crosshair(False)  # pin becomes detached, panels stay active
    assert bec_image_view.crosshair is None
    assert bec_image_view.x_roi_pinned is not None

    updated = test_data + 100.0
    bec_image_view.on_image_update_2d({"data": updated}, {})

    qtbot.waitUntil(
        lambda: np.array_equal(bec_image_view.x_roi_pinned.getData()[1], updated[:, 3]), timeout=500
    )


def test_crosshair_moves_update_profiles_immediately(qtbot, mocked_client):
    """Crosshair moves update the live profiles synchronously; new frames refresh
    them at the current crosshair position."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25, dtype=float).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})
    switch = bec_image_view.toolbar.components.get_action("image_switch_crosshair")
    switch.actions["crosshair_roi"].action.trigger()
    qtbot.wait(50)

    # Position the crosshair lines and emit the snapped pixel (as mouse_moved does).
    bec_image_view.crosshair.mouse_moved(manual_pos=(1.2, 2.2))

    np.testing.assert_array_equal(bec_image_view.x_roi_curve.getData()[1], test_data[:, 2])

    # New frames refresh the live profile at the crosshair position.
    updated = test_data + 100.0
    bec_image_view.on_image_update_2d({"data": updated}, {})
    np.testing.assert_array_equal(bec_image_view.x_roi_curve.getData()[1], updated[:, 2])


def test_live_label_intensity_updates_on_image_update(qtbot, mocked_client):
    """The live crosshair label refreshes its intensity when the image changes,
    not only when the mouse moves."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.arange(25, dtype=float).reshape(5, 5)
    bec_image_view.on_image_update_2d({"data": test_data}, {})
    bec_image_view.hook_crosshair()

    bec_image_view.crosshair.mouse_moved(manual_pos=(2.5, 3.5))
    assert "Intensity: 13.000" in bec_image_view.crosshair.coord_label.toPlainText()

    bec_image_view.on_image_update_2d({"data": test_data + 100.0}, {})
    assert "Intensity: 113.000" in bec_image_view.crosshair.coord_label.toPlainText()


def test_active_pin_label_intensity_updates_on_image_update(qtbot, mocked_client):
    """Pinned crosshair label intensity follows image updates at the pinned position."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    bec_image_view.hook_crosshair()

    bec_image_view.crosshair.set_pin(2.0, 3.0)
    assert bec_image_view.crosshair.pinned_label.toPlainText() == (
        "pin (2.500, 3.500)\nIntensity: 13.000"
    )

    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5) + 100}, {})

    qtbot.waitUntil(
        lambda: bec_image_view.crosshair.pinned_label.toPlainText()
        == "pin (2.500, 3.500)\nIntensity: 113.000",
        timeout=500,
    )


def test_image_update_does_not_replay_active_crosshair_mouse_handling(
    qtbot, mocked_client, monkeypatch
):
    """Image updates refresh a pin without re-snapping or emitting live crosshair updates."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    bec_image_view.hook_crosshair()
    bec_image_view.crosshair.set_pin(2.0, 3.0)

    mouse_moves = []
    monkeypatch.setattr(
        bec_image_view.crosshair,
        "mouse_moved",
        lambda *args, **kwargs: mouse_moves.append((args, kwargs)),
    )

    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5) + 100}, {})

    qtbot.waitUntil(
        lambda: bec_image_view.crosshair.pinned_label.toPlainText()
        == "pin (2.500, 3.500)\nIntensity: 113.000",
        timeout=500,
    )
    assert mouse_moves == []


def test_detached_pin_label_intensity_updates_on_image_update(qtbot, mocked_client):
    """Detached pin labels keep following image updates while crosshair is disabled."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5)}, {})
    bec_image_view.hook_crosshair()
    bec_image_view.crosshair.set_pin(2.0, 3.0)
    bec_image_view.unhook_crosshair()

    assert bec_image_view.crosshair is None
    assert bec_image_view._detached_pin is not None
    assert bec_image_view._detached_pin["label"].toPlainText() == (
        "pin (2.500, 3.500)\nIntensity: 13.000"
    )

    bec_image_view.on_image_update_2d({"data": np.arange(25).reshape(5, 5) + 200}, {})

    qtbot.waitUntil(
        lambda: bec_image_view._detached_pin["label"].toPlainText()
        == "pin (2.500, 3.500)\nIntensity: 213.000",
        timeout=500,
    )


def test_detached_pin_label_omits_scalar_intensity_for_rgb_image(qtbot, mocked_client):
    """Detached RGB pin labels only show coordinates because a pixel is an array."""
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.on_image_update_2d({"data": np.zeros((5, 5, 3))}, {})
    bec_image_view.hook_crosshair()
    bec_image_view.crosshair.set_pin(2.0, 3.0)
    bec_image_view.unhook_crosshair()

    assert bec_image_view.crosshair is None
    assert bec_image_view._detached_pin is not None
    assert bec_image_view._detached_pin["label"].toPlainText() == "pin (2.500, 3.500)"


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

    view.device = "eiger"
    view.signal = "img2d"

    qtbot.wait(200)  # Allow signal processing

    device_selection = view.toolbar.components.get_action("device_selection").widget
    qtbot.waitUntil(
        lambda: device_selection.device_combo_box.currentText() == "eiger"
        and device_selection.signal_combo_box.currentText() == "img2d",
        timeout=1000,
    )


def test_signal_syncs_from_toolbar(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_signal_config(mocked_client, "eiger", "img_a", signal_class="PreviewSignal", ndim=2)
    _set_signal_config(mocked_client, "eiger", "img_b", signal_class="PreviewSignal", ndim=2)

    view.device = "eiger"
    view.signal = "img_a"

    device_selection = view.toolbar.components.get_action("device_selection").widget
    device_selection.signal_combo_box.blockSignals(True)
    device_selection.signal_combo_box.setCurrentText("img_b")
    device_selection.signal_combo_box.blockSignals(False)

    view._sync_signal_from_toolbar()

    assert view.signal == "img_b"


##############################################
# Log scale / non-finite data crash regression
##############################################


@pytest.mark.parametrize(
    "data",
    [
        -np.abs(np.random.rand(20, 30)).astype(np.float32) - 1.0,  # all negative -> all NaN
        np.zeros((20, 30), dtype=np.uint16),  # all zeros -> uniform floor
        np.where(np.eye(20, 30) > 0, -5.0, 3.0).astype(np.float32),  # mixed sign
    ],
    ids=["all_negative", "all_zeros", "mixed_sign"],
)
def test_log_scale_does_not_crash_with_full_colorbar(qtbot, mocked_client, data):
    """Log scaling of non-positive data must not produce NaN levels that crash
    the full (HistogramLUTItem) colorbar. Regression for fix/image-crashing."""
    view = create_widget(qtbot, Image, client=mocked_client)
    view.enable_full_colorbar = True
    assert isinstance(view._color_bar, pg.HistogramLUTItem)

    view.log = True
    # This is the exact path that used to raise "Cannot set range [nan, nan]".
    view.on_image_update_2d({"data": data}, {})

    vmin, vmax = view.main_image.v_range
    assert np.isfinite(vmin) and np.isfinite(vmax)
    assert vmin <= vmax
    # Colorbar levels stay finite as well.
    low, high = view._color_bar.getLevels()
    assert np.isfinite(low) and np.isfinite(high)


def test_log_scale_all_negative_keeps_finite_image(qtbot, mocked_client):
    """All-negative input must still yield a finite, displayed image under log."""
    view = create_widget(qtbot, Image, client=mocked_client)
    view.log = True
    data = (-np.abs(np.random.rand(15, 15)) - 1.0).astype(np.float32)

    view.on_image_update_2d({"data": data}, {})

    assert view.main_image.image is not None
    assert np.all(np.isfinite(view.main_image.image))


def test_set_v_range_ignores_non_finite_levels(qtbot, mocked_client):
    """Non-finite v_range requests are rejected rather than forwarded to pg."""
    view = create_widget(qtbot, Image, client=mocked_client)
    view.on_image_update_2d({"data": np.random.rand(10, 10)}, {})
    good = view.main_image.v_range

    view.main_image.set_v_range((np.nan, np.nan))
    assert view.main_image.v_range == good  # unchanged

    # Inverted ranges are normalised, not propagated as-is.
    view.main_image.set_v_range((10.0, 2.0))
    lo, hi = view.main_image.v_range
    assert (lo, hi) == (2.0, 10.0)


def test_image_processor_log_is_finite_for_non_positive():
    """ImageProcessor.log must never emit NaN/inf for zero/negative input."""
    proc = ImageProcessor(config=ProcessingConfig(log=True))
    data = np.array([[-100.0, -1.0], [0.0, 1000.0]], dtype=np.float32)
    out = proc.log(data)
    assert np.all(np.isfinite(out))
    # Non-positive pixels collapse to the floor log10(0.1) == -1; a count of 1
    # maps to 0.
    assert out[0, 0] == pytest.approx(-1.0)
    assert out[1, 0] == pytest.approx(-1.0)
    assert proc.log(np.array([[1.0]]))[0, 0] == pytest.approx(0.0)


##############################################
# Shape / dtype edge cases in the data path
##############################################


def test_adjust_image_buffer_coerces_list_and_scalar(qtbot, mocked_client):
    """Non-ndarray payloads (python list, 0-d scalar) must not crash the
    1D buffer accumulation."""
    view = create_widget(qtbot, Image, client=mocked_client)
    image = view.main_image

    buf = view.adjust_image_buffer(image, [1, 2, 3])  # python list
    assert buf.shape == (1, 3)
    buf = view.adjust_image_buffer(image, np.array(42.0))  # 0-d scalar
    assert buf.shape[0] == 2


##############################################
# Teardown safety
##############################################


def test_layer_accessors_safe_after_teardown(qtbot, mocked_client):
    """Once layer_manager is gone (post-cleanup), signal-driven accessors must
    not raise. They used to subscript None or resurrect the 'main' layer."""
    view = create_widget(qtbot, Image, client=mocked_client)
    view.enable_full_colorbar = True
    view.layer_manager = None  # simulate post-cleanup state

    # None of these should raise:
    assert view.autorange is False
    assert view.autorange_mode == "mean"
    view.toggle_autorange(True, "mean")
    view._set_autorange(True)
    view.autorange_mode = "max"
    view._sync_autorange_switch()
    view._sync_colorbar_levels()
