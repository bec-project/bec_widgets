from dataclasses import replace
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import shiboken6
from bec_lib import messages
from bec_lib.data_api import CONTINUOUS_GROUP
from bec_lib.data_api.models import SourceData, SubscriptionUpdate
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtTest import QSignalSpy

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.plots.motor_map.motor_map import MotorConfig, MotorMap, MotorMapConfig
from bec_widgets.widgets.plots.motor_map.settings.motor_map_settings import MotorMapSettings

from .conftest import create_widget

##################################################
# Test helpers (DataAPI fake bridge + updates)
##################################################


def _fake_bridge_factory(monkeypatch):
    created = []

    class _FakeBridge:
        def __init__(self, client, sources=None, scan="live", parent=None, **kwargs):
            self.client = client
            self.sources = list(sources) if sources is not None else None
            self.devices = list(kwargs.get("devices") or [])
            self.correlation = kwargs.get("correlation", "ordinal")
            self.scan = scan
            self.max_points = kwargs.get("max_points")
            self.healthy = True
            # What the widgets read of a real bridge about its binding.
            self.groups = {}
            self.routes = {}
            self.unbound_sources = []
            self.closed = False
            self.updated = MagicMock()

        def close(self):
            self.closed = True

    def factory(client, sources=None, scan="live", parent=None, **kwargs):
        bridge = _FakeBridge(client, sources, scan=scan, **kwargs)
        created.append(bridge)
        return bridge

    monkeypatch.setattr("bec_widgets.widgets.plots.motor_map.motor_map.QtDataSubscription", factory)
    return created


def _pair_update(xs, ys, start=0):
    """Build a full-state continuous (sample-and-hold) snapshot of both motors."""
    ordinals = tuple(range(start, start + len(xs)))
    sources = {}
    for motor, values in (("samx", xs), ("samy", ys)):
        sources[(motor, motor)] = SourceData(
            device=motor,
            entry=motor,
            kind="unindexed",
            ordinals=ordinals,
            values=tuple(values),
            timestamps=tuple(float(ordinal) for ordinal in ordinals),
            complete=True,
            metadata={"stream": "readback"},
        )
    return SubscriptionUpdate(
        scan_id="",
        reason="live",
        sources=sources,
        aligned_ordinals=ordinals,
        complete=True,
        metadata={"group": CONTINUOUS_GROUP},
    )


def test_motor_map_initialization(qtbot, mocked_client):
    """Test the initialization of the MotorMap widget."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # test default values
    assert mm.config.widget_class == "MotorMap"
    assert mm.config.scatter_size == 5
    assert mm.config.max_points == 5000
    assert mm.config.num_dim_points == 100
    assert mm.x_grid is True
    assert mm.y_grid is True


def test_motor_map_select_motor(qtbot, mocked_client):
    """Test selecting motors for the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    mm.map(device_x="samx", device_y="samy", validate_bec=True)

    assert mm.config.device_x.device == "samx"
    assert mm.config.device_y.device == "samy"
    assert mm.config.device_x.limits == [-10, 10]
    assert mm.config.device_y.limits == [-5, 5]
    assert mm.config.scatter_size == 5
    assert mm.config.max_points == 5000
    assert mm.config.num_dim_points == 100
    assert mm.x_grid is True
    assert mm.y_grid is True


def test_motor_map_properties(qtbot, mocked_client):
    """Test setting and getting properties of MotorMap."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")

    # Test color property
    mm.color = (100, 150, 200, 255)
    assert mm.color == (100, 150, 200, 255)

    mm.color = "#FF5500"  # Test hex color
    assert mm.color[0] == 255
    assert mm.color[1] == 85
    assert mm.color[2] == 0

    # Test scatter_size property
    mm.scatter_size = 10
    qtbot.wait(200)
    assert mm.scatter_size == 10
    assert mm.config.scatter_size == 10
    assert mm._trace.opts["size"] == 10

    # Test max_points property
    mm.max_points = 2000
    assert mm.max_points == 2000
    assert mm.config.max_points == 2000

    # Test precision property
    mm.precision = 3
    assert mm.precision == 3
    assert mm.config.precision == 3

    # Test num_dim_points property
    mm.num_dim_points = 50
    assert mm.num_dim_points == 50
    assert mm.config.num_dim_points == 50

    # Test background_value property
    mm.background_value = 40
    qtbot.wait(200)
    assert mm.background_value == 40
    assert mm.config.background_value == 40
    filled_rect = mm._limit_map
    rect_color = filled_rect._brush.color().getRgb()
    expected = (40, 40, 40, 150)
    assert rect_color == expected


def test_motor_map_get_limits(qtbot, mocked_client):
    """Test getting motor limits."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")
    expected_limits = {"samx": [-10, 10], "samy": [-5, 5]}

    for motor_name, expected_limit in expected_limits.items():
        actual_limit = mm._get_motor_limit(motor_name)
        assert actual_limit == expected_limit


def test_motor_map_initial_position_comes_from_data_api(qtbot, mocked_client):
    """An idle motor is initialized by the API's Redis backfill, without Device.read()."""
    for device, value in (("samx", 2.5), ("samy", -1.25)):
        mocked_client.connector.set_and_publish(
            MessageEndpoints.device_readback(device),
            messages.DeviceMessage(signals={device: {"value": value, "timestamp": 1.0}}),
        )
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    with (
        patch.object(mm.dev["samx"], "read", side_effect=AssertionError("direct read")),
        patch.object(mm.dev["samy"], "read", side_effect=AssertionError("direct read")),
    ):
        mm.map("samx", "samy")
        qtbot.waitUntil(lambda: mm._buffer == {"x": [2.5], "y": [-1.25]})
    assert mm.v_line.value() == 2.5
    assert mm.h_line.value() == -1.25


@pytest.mark.parametrize("preconfigured", [False, True])
def test_motor_map_selected_devices_start_data_delivery(qtbot, mocked_client, preconfigured):
    for device, value in (("samx", 2.5), ("samy", -1.25)):
        mocked_client.connector.set_and_publish(
            MessageEndpoints.device_readback(device),
            messages.DeviceMessage(signals={device: {"value": value, "timestamp": 1.0}}),
        )
    config = MotorMapConfig(
        widget_class="MotorMap",
        device_x=MotorConfig(device="samx"),
        device_y=MotorConfig(device="samy"),
    )
    mm = create_widget(
        qtbot, MotorMap, client=mocked_client, config=config if preconfigured else None
    )
    selection = mm.toolbar.components.get_action("motor_selection").widget
    selection.motor_x.setCurrentText("samx")
    selection.motor_y.setCurrentText("samy")
    assert selection.motor_x.currentText() == "samx"
    assert selection.motor_y.currentText() == "samy"
    assert mm._data_bridge is not None
    qtbot.waitUntil(lambda: mm._buffer == {"x": [2.5], "y": [-1.25]})
    assert mm.v_line.value() == 2.5
    assert mm.h_line.value() == -1.25


def test_motor_map_partial_config_starts_when_second_motor_is_selected(qtbot, mocked_client):
    config = MotorMapConfig(widget_class="MotorMap", device_x=MotorConfig(device="samx"))
    mm = create_widget(qtbot, MotorMap, client=mocked_client, config=config)
    assert mm._data_bridge is None
    selection = mm.toolbar.components.get_action("motor_selection").widget
    selection.motor_y.setCurrentText("samy")
    assert mm._data_bridge is not None
    assert mm._data_bridge.sources == [("samx", "samx"), ("samy", "samy")]


def test_motor_map_waits_for_both_readbacks(qtbot, mocked_client, monkeypatch):
    _fake_bridge_factory(monkeypatch)
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map("samx", "samy")
    mm._on_data_update(_pair_update([], []))
    mm.reset_history()
    mm._update_plot()
    assert mm._buffer == {"x": [], "y": []}
    assert mm.v_line is None
    assert mm.h_line is None
    mm._on_data_update(_pair_update([3.0], [4.0]))
    assert mm.v_line.value() == 3.0
    assert mm.h_line.value() == 4.0


def test_motor_map_reset_history(qtbot, mocked_client):
    """Test resetting the history of motor positions."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(motor_x="samx", motor_y="samy")

    # Simulate some motor movement history
    mm._buffer = {"x": [1.0, 2.0, 3.0, 4.0], "y": [5.0, 6.0, 7.0, 8.0]}

    # Reset history
    mm.reset_history()

    # Should keep only the last point
    assert len(mm._buffer["x"]) == 1
    assert len(mm._buffer["y"]) == 1
    assert mm._buffer["x"][0] == 4.0
    assert mm._buffer["y"][0] == 8.0


def test_motor_map_on_data_update(qtbot, mocked_client):
    """The trail is the continuous group's paired (x, y) columns."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")
    mm._on_data_update(_pair_update([1.0], [2.0]))

    # A held sample (the other motor has not delivered yet) carries no rows.
    mm._on_data_update(_pair_update([], []))
    assert mm._buffer == {"x": [1.0], "y": [2.0]}

    mm._on_data_update(_pair_update([1.0, 3.0], [2.0, 2.0]))
    assert mm._buffer == {"x": [1.0, 3.0], "y": [2.0, 2.0]}
    assert mm._last_row == 1

    # Full-state snapshots replace the trail; a repeated snapshot changes nothing.
    mm._on_data_update(_pair_update([1.0, 3.0, 3.0], [2.0, 2.0, 4.0]))
    mm._on_data_update(_pair_update([1.0, 3.0, 3.0], [2.0, 2.0, 4.0]))
    assert mm._buffer == {"x": [1.0, 3.0, 3.0], "y": [2.0, 2.0, 4.0]}

    # Retention window slid (oldest row dropped by the backend).
    mm._on_data_update(_pair_update([3.0, 3.0, 3.5], [2.0, 4.0, 4.0], start=1))
    assert mm._buffer == {"x": [3.0, 3.0, 3.5], "y": [2.0, 4.0, 4.0]}


def test_motor_map_reset_history_hides_earlier_rows(qtbot, mocked_client):
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")
    mm._on_data_update(_pair_update([1.0, 2.0, 3.0], [1.0, 1.0, 2.0]))
    mm.reset_history()
    assert mm._buffer == {"x": [3.0], "y": [2.0]} and mm._trail_start == 3
    # The next snapshot still carries the old rows: they stay hidden.
    mm._on_data_update(_pair_update([1.0, 2.0, 3.0, 4.0], [1.0, 1.0, 2.0, 2.5]))
    assert mm._buffer == {"x": [4.0], "y": [2.5]}
    mm._on_data_update(_pair_update([2.0, 3.0], [1.0, 2.0], start=1))  # nothing new
    assert mm._buffer == {"x": [4.0], "y": [2.5]}


def test_motor_map_bridge_lifecycle(qtbot, mocked_client, monkeypatch):
    """map() creates one continuous scan-less readback bridge; re-map replaces it."""
    bridges = _fake_bridge_factory(monkeypatch)
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    mm.map(device_x="samx", device_y="samy")
    assert len(bridges) == 1
    assert bridges[-1].devices == ["samx", "samy"] and bridges[-1].sources is None
    assert bridges[-1].correlation == "continuous"
    assert bridges[-1].scan is None
    assert bridges[-1].max_points == mm.config.max_points

    first = bridges[-1]
    mm.map(device_x="samx", device_y="samz")
    assert first.closed is True
    assert bridges[-1].devices == ["samx", "samz"]

    mm._cleanup_data_api_subscription()
    assert bridges[-1].closed is True
    assert mm._data_bridge is None
    assert mm._trail_start == 0 and mm._last_row is None


def test_motor_map_max_points_limit(qtbot, mocked_client):
    """Test that the buffer doesn't exceed max_points."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")

    # Add more points than max_points
    mm._buffer = {"x": [1.0, 2.0, 3.0, 4.0], "y": [5.0, 6.0, 7.0, 8.0]}

    mm.config.max_points = 3
    # Trigger update that should trim buffer
    mm._update_plot()

    # Check that buffer was trimmed to max_points
    assert len(mm._buffer["x"]) == 3
    assert len(mm._buffer["y"]) == 3
    # Should keep the most recent points
    assert mm._buffer["x"] == [2.0, 3.0, 4.0]
    assert mm._buffer["y"] == [6.0, 7.0, 8.0]


def test_motor_map_crosshair_creation(qtbot, mocked_client):
    """Test the creation of the coordinate crosshair."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # The Initial state should be None
    assert mm.v_line is None
    assert mm.h_line is None
    assert mm.coord_label is None

    # Create the crosshair
    mm._add_coordinates_crosshair(3.0, 4.0)

    # Check if crosshair elements were created
    assert mm.v_line is not None
    assert mm.h_line is not None
    assert mm.coord_label is not None

    # Test position
    assert mm.v_line.value() == 3.0
    assert mm.h_line.value() == 4.0


def test_motor_map_limit_map(qtbot, mocked_client):
    """Test the creation of the limit map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Create a limit map
    limit_map = mm._make_limit_map([0, 10], [0, 5])

    from qtpy import QtCore

    from bec_widgets.widgets.plots.motor_map.motor_map import FilledRectItem

    assert isinstance(limit_map, FilledRectItem)
    rect = limit_map.boundingRect()
    # For [0,10] on x and [0,5] on y, width=10, height=5
    assert rect == QtCore.QRectF(0, 0, 10, 5)


def test_motor_map_change_limits(qtbot, mocked_client):
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(device_x="samx", device_y="samy")

    # Original mocked limits are
    # samx: [-10, 10]
    # samy: [-5, 5]

    # Original Limits Map
    rect = mm._limit_map.boundingRect()
    assert rect.width() == 20  # -10 to 10 inclusive
    assert rect.height() == 10  # -5 to 5 inclusive
    assert mm.config.device_x.limits == [-10, 10]
    assert mm.config.device_y.limits == [-5, 5]

    # Change the limits of the samx motor
    mm.dev["samx"].limits = [-20, 20]
    msg = {"signals": {"high": {"value": 20}, "low": {"value": -20}}}
    mm.on_device_limits(msg, {})
    qtbot.wait(200)  # Allow time for the update to process

    # Check that the limits map was updated
    assert mm.config.device_x.limits == [-20, 20]
    assert mm.config.device_y.limits == [-5, 5]
    rect = mm._limit_map.boundingRect()
    assert rect.width() == 40  # -20 to 20 inclusive
    assert rect.height() == 10  # -5 to 5 inclusive -> same as before

    # Change back the limits
    mm.dev["samx"].limits = [-10, 10]


def test_motor_map_get_data(qtbot, mocked_client):
    """Test getting data from the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Set up some test data
    mm._buffer = {"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]}

    # Get data
    data = mm.get_data()

    # Check that the data is correct
    assert "x" in data
    assert "y" in data
    assert data["x"] == [1.0, 2.0, 3.0]
    assert data["y"] == [4.0, 5.0, 6.0]


def test_motor_map_toolbar_selection(qtbot, mocked_client):
    """Test motor selection via the toolbar bundle."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Verify toolbar bundle was created during initialization
    motor_selection = mm.toolbar.components.get_action("motor_selection")

    motor_selection.widget.motor_x.setCurrentText("samx")
    motor_selection.widget.motor_y.setCurrentText("samy")

    assert mm.config.device_x.device == "samx"
    assert mm.config.device_y.device == "samy"

    motor_selection.widget.motor_y.setCurrentText("samz")

    assert mm.config.device_x.device == "samx"
    assert mm.config.device_y.device == "samz"


def test_motor_selection_set_motors_blocks_signals(qtbot, mocked_client):
    """Ensure set_motors updates both comboboxes without emitting change signals."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    motor_selection = mm.toolbar.components.get_action("motor_selection").widget

    spy_x = QSignalSpy(motor_selection.motor_x.currentTextChanged)
    spy_y = QSignalSpy(motor_selection.motor_y.currentTextChanged)

    motor_selection.set_motors("samx", "samy")

    assert motor_selection.motor_x.currentText() == "samx"
    assert motor_selection.motor_y.currentText() == "samy"
    assert spy_x.count() == 0
    assert spy_y.count() == 0


def test_motor_properties_partial_then_complete_map(qtbot, mocked_client):
    """Setting x then y via properties should map once both are valid."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    spy = QSignalSpy(mm.property_changed)
    mm.device_x = "samx"

    assert mm.config.device_x.device == "samx"
    assert mm.config.device_y.device is None
    assert mm._trace is None  # map not triggered yet
    assert spy.at(0) == ["device_x", "samx"]

    mm.device_y = "samy"

    assert mm.config.device_x.device == "samx"
    assert mm.config.device_y.device == "samy"
    assert mm._trace is not None  # map called once both valid
    assert spy.at(1) == ["device_y", "samy"]
    assert mm._buffer == {"x": [], "y": []}


def test_set_motor_name_emits_and_syncs_toolbar(qtbot, mocked_client):
    """_set_motor_name should emit property changes and sync toolbar widgets."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    motor_selection = mm.toolbar.components.get_action("motor_selection").widget

    spy = QSignalSpy(mm.property_changed)
    mm._set_motor_name("x", "samx")

    assert mm.config.device_x.device == "samx"
    assert motor_selection.motor_x.currentText() == "samx"
    assert spy.at(0) == ["device_x", "samx"]

    # Calling with same name should be a no-op
    initial_count = spy.count()
    mm._set_motor_name("x", "samx")
    assert spy.count() == initial_count


def test_motor_map_settings_dialog(qtbot, mocked_client):
    """Test the settings dialog for the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client, popups=True)

    assert "axis_popup" in mm.toolbar.bundles
    for action_ref in mm.toolbar.bundles["axis_popup"].bundle_actions.values():
        assert action_ref().action.isVisible()

    # set properties to be fetched by dialog
    mm.map(device_x="samx", device_y="samy")
    mm.precision = 2
    mm.max_points = 1000
    mm.scatter_size = 10
    mm.background_value = 50
    mm.num_dim_points = 20
    mm.color = (255, 0, 0, 255)

    mm.show_motor_map_settings()
    qtbot.wait(200)

    assert mm.motor_map_settings is not None
    assert mm.motor_map_settings.isVisible() is True

    # Check that the settings dialog has the correct values
    assert mm.motor_map_settings.widget.ui.precision.value() == 2
    assert mm.motor_map_settings.widget.ui.max_points.value() == 1000
    assert mm.motor_map_settings.widget.ui.scatter_size.value() == 10
    assert mm.motor_map_settings.widget.ui.background_value.value() == 50
    assert mm.motor_map_settings.widget.ui.num_dim_points.value() == 20
    assert mm.motor_map_settings.widget.ui.color_scatter.color == "#ff0000"

    mm.motor_map_settings.close()
    qtbot.wait(200)
    assert mm.motor_map_settings is None


def test_motor_map_settings_color_live_sync(qtbot, mocked_client):
    """The side panel color button and the motor map color follow each other."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    settings = create_widget(qtbot, MotorMapSettings, target_widget=mm, popup=False)

    mm.color = (0, 0, 255, 255)
    assert settings.ui.color_scatter.color == "#0000ff"

    settings.ui.color_scatter.set_color("#00ff00")
    assert mm.color == (0, 255, 0, 255)
    assert settings.ui.color_scatter.color == "#00ff00"


def test_motor_map_settings_color_accept(qtbot, mocked_client):
    """Applying the dialog sets a new color and keeps the alpha of an unchanged one."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.color = (255, 0, 0, 100)
    settings = create_widget(qtbot, MotorMapSettings, target_widget=mm, popup=True)
    assert settings.ui.color_scatter.color == "#ff0000"

    settings.accept_changes()
    assert mm.color == (255, 0, 0, 100)

    settings.ui.color_scatter.set_color("#00ff00")
    assert mm.color == (255, 0, 0, 100)
    settings.accept_changes()
    assert mm.color == (0, 255, 0, 255)


def test_motor_map_cleanup_detaches_update_proxy(qtbot, mocked_client):
    """
    A plot update still queued in proxy_update_plot when the MotorMap is cleaned up, or
    requested afterwards, must not reach _update_plot of the closed widget.
    """
    with mock.patch.object(MotorMap, "_update_plot") as update_plot:
        mm = create_widget(qtbot, MotorMap, client=mocked_client)
        qtbot.wait(100)  # let anything queued during construction drain
        update_plot.reset_mock()

        proxy = mm.proxy_update_plot
        mm.update_signal.emit()  # queued in the proxy
        assert proxy.timer.timer.isActive()  # pg's ThreadsafeTimer wraps a QTimer
        mm.close()  # closeEvent -> cleanup()
        mm.update_signal.emit()  # requested after cleanup

        qtbot.wait(200)
        update_plot.assert_not_called()
        assert not proxy.timer.timer.isActive()
        assert proxy.args is None


def test_motor_map_cleanup_closes_settings_popup(qtbot, mocked_client):
    """
    Closing the MotorMap must also close its settings popup instead of leaving it open
    on top of the removed widget.
    """
    mm = create_widget(qtbot, MotorMap, client=mocked_client, popups=True)
    mm.map(device_x="samx", device_y="samy")
    mm.show_motor_map_settings()
    dialog = mm.motor_map_settings
    assert dialog.isVisible()

    mm.close()  # closeEvent -> cleanup()
    try:
        assert mm.motor_map_settings is None
        assert not dialog.isVisible()
    finally:
        if shiboken6.isValid(dialog) and dialog.isVisible():
            dialog.reject()  # keep a failure on main from leaking the popup into later tests


def test_motor_switch_disconnects_old_limit_endpoints(qtbot, mocked_client):
    """Switching motors must disconnect the previously connected limits
    endpoints, not the ones derived from the already-updated config."""
    from unittest import mock

    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map("samx", "samy")
    first_endpoints = list(mm._connected_limit_endpoints)
    assert first_endpoints

    with mock.patch.object(mm.bec_dispatcher, "disconnect_slot") as disc:
        mm.map("samx", "samz")
    disc.assert_called_once_with(mm.on_device_limits, first_endpoints)


def test_motor_map_rebind_resets_history_cutoff(qtbot, mocked_client, monkeypatch):
    _fake_bridge_factory(monkeypatch)
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map("samx", "samy")
    mm._on_data_update(_pair_update([1.0, 2.0], [3.0, 4.0]))
    mm.reset_history()
    assert mm._trail_start == 2

    mm._on_data_update(replace(_pair_update([], []), generation=1))
    assert mm._buffer == {"x": [], "y": []}
    assert not mm.v_line.isVisible()
    mm._on_data_update(replace(_pair_update([5.0], [6.0]), generation=1))
    mm._update_plot()
    assert mm._buffer == {"x": [5.0], "y": [6.0]}
    assert mm._trail_start == 0
    assert mm.v_line.isVisible()
    assert mm.v_line.value() == 5.0
