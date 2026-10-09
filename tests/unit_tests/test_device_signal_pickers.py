"""Tests for the searchable device and signal pickers (QWidget and QML popups)."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
import time
from unittest import mock

import pytest
from bec_lib import messages
from bec_lib.device import ReadoutPriority
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.fake_devices import FakeDevice
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
)
from bec_widgets.widgets.control.device_input.picker import picker_common, picker_model
from bec_widgets.widgets.control.device_input.picker.picker_model import (
    PickerController,
    PickerEntry,
    format_value,
    rank_entry,
)
from bec_widgets.widgets.control.device_input.picker.picker_qml import (
    DevicePickerQML,
    PickerPopupQml,
    SignalPickerQML,
)
from bec_widgets.widgets.control.device_input.picker.picker_qwidget import (
    DevicePicker,
    PickerPopupWidget,
    SignalPicker,
)

from .conftest import create_widget


@pytest.fixture(autouse=True)
def _clear_recent():
    picker_model.clear_recent_picks()
    yield
    picker_model.clear_recent_picks()


@pytest.fixture(params=[DevicePicker, DevicePickerQML])
def device_picker(request, qtbot, mocked_client):
    yield create_widget(qtbot, request.param, client=mocked_client)


@pytest.fixture(params=[SignalPicker, SignalPickerQML])
def signal_picker(request, qtbot, mocked_client):
    yield create_widget(qtbot, request.param, client=mocked_client, device="samx")


def _titles(controller: PickerController) -> list[tuple[str, str]]:
    model = controller.model
    return [(model.row(r)["rowType"], model.row(r)["title"]) for r in range(model.rowCount())]


def _wait_closed(qtbot, picker):
    qtbot.waitUntil(lambda: not picker.is_popup_open())


# ---- pure logic ---------------------------------------------------------------------------------


def test_rank_entry_orders_prefix_word_substring_fuzzy():
    def rank(query, title, **kwargs):
        score = rank_entry(query, PickerEntry(value=title, title=title, **kwargs))
        return None if score is None else score[0]

    assert rank("sam", "samx") == 0
    assert rank("x", "slit1_xc") == 1
    assert rank("pm", "bpm4i") == 2
    assert rank("smx", "samx") == 3
    assert rank("motor", "samx", subtitle="EpicsMotor") == 4
    assert rank("zzz", "samx") is None
    assert rank_entry("", PickerEntry(value="a", title="a")) == (0, -1, 0)
    assert rank_entry("BPM", PickerEntry(value="x", title="gauss_bpm")) == (1, 6, 3)


def test_format_value():
    assert format_value(None) == ""
    assert format_value(True) == "true"
    assert format_value(3) == "3"
    assert format_value(1.23456789) == "1.23457"
    assert format_value([1, 2]) == "list [2]"
    assert format_value("x" * 50).endswith("…")


def test_controller_groups_searches_and_navigates(qtbot):
    entries = [
        PickerEntry(value="samx", title="samx", group="Positioners"),
        PickerEntry(value="samy", title="samy", group="Positioners"),
        PickerEntry(value="bpm4i", title="bpm4i", group="Devices"),
    ]
    controller = PickerController("devices")
    controller.open(entries, current="samy")
    assert _titles(controller) == [
        ("header", "Positioners"),
        ("item", "samx"),
        ("item", "samy"),
        ("header", "Devices"),
        ("item", "bpm4i"),
    ]
    # the current value is highlighted and marked
    assert controller.highlight == 2
    assert controller.model.row(2)["isCurrent"]
    assert controller.summary == "3 devices"

    # navigation skips headers and wraps around
    controller.move_highlight(1)
    assert controller.entry_at(controller.highlight).value == "bpm4i"
    controller.move_highlight(1)
    assert controller.entry_at(controller.highlight).value == "samx"
    controller.move_highlight(-1)
    assert controller.entry_at(controller.highlight).value == "bpm4i"

    controller.set_query("y")
    assert _titles(controller) == [("item", "samy")]
    assert controller.summary == "1 of 3"
    assert "<b>" in controller.model.row(0)["titleRich"]

    controller.set_query("nothing")
    assert _titles(controller)[0][0] == "empty"
    assert controller.entry_at(0) is None
    assert not controller.accept()

    controller.set_query("bpm")
    with qtbot.waitSignal(controller.picked) as blocker:
        assert controller.accept()
    assert blocker.args == ["bpm4i"]
    controller.close()


def test_controller_lists_recent_first():
    entries = [PickerEntry(value=f"dev{i}", title=f"dev{i}", group="Devices") for i in range(12)]
    controller = PickerController("devices")
    controller.open(entries, recent=["dev7", "unknown"])
    titles = _titles(controller)
    assert titles[:3] == [("header", "Recent"), ("item", "dev7"), ("header", "Devices")]
    controller.close()


# ---- device picker -------------------------------------------------------------------------------


def test_device_picker_lists_same_devices_as_combobox(qtbot, mocked_client, device_picker):
    combo = create_widget(qtbot, DeviceComboBox, client=mocked_client)
    assert device_picker.devices == combo.devices

    for widget in (combo, device_picker):
        widget.set_device_filter(BECDeviceFilter.POSITIONER)
    assert device_picker.devices == combo.devices
    assert "samx" in device_picker.devices and "bpm4i" not in device_picker.devices

    for widget in (combo, device_picker):
        widget.readout_monitored = False
    assert device_picker.devices == combo.devices

    for widget in (combo, device_picker):
        widget.set_available_devices(["samx", "samy"])
    assert device_picker.devices == combo.devices == ["samx", "samy"]


ASYNC_SIGNALS = [
    (
        "eiger",
        "eiger",
        {
            "obj_name": "eiger",
            "component_name": "eiger",
            "kind_str": "hinted",
            "signal_class": "AsyncSignal",
        },
    )
]


@pytest.fixture
def async_signals(mocked_client):
    with mock.patch.object(
        mocked_client.device_manager, "get_bec_signals", return_value=ASYNC_SIGNALS, create=True
    ):
        yield


def test_device_picker_signal_class_and_write_access_filters(qtbot, mocked_client, async_signals):
    combo = create_widget(
        qtbot,
        DeviceComboBox,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        include_signals_with_write_access=True,
    )
    picker = create_widget(
        qtbot,
        DevicePicker,
        client=mocked_client,
        signal_class_filter=["AsyncSignal"],
        include_signals_with_write_access=True,
    )
    assert picker.devices == combo.devices
    assert "eiger" in picker.devices


def test_readout_filters_refresh_once(qtbot, mocked_client):
    with mock.patch.object(
        picker_common, "device_snapshot", wraps=picker_common.device_snapshot
    ) as snapshot:
        picker = create_widget(qtbot, DevicePicker, client=mocked_client)
        reads_in_init = [c for c in snapshot.call_args_list if c.kwargs.get("force") is not None]
        assert len(reads_in_init) == 1
        snapshot.reset_mock()
        picker.set_readout_priority_filter([ReadoutPriority.MONITORED, ReadoutPriority.BASELINE])
        assert len([c for c in snapshot.call_args_list if "force" in c.kwargs]) == 1


def test_unchanged_device_list_does_not_reemit(qtbot, device_picker):
    device_picker.set_device("samx")
    with qtbot.assertNotEmitted(device_picker.device_selected):
        device_picker.update_devices_from_filters()


def test_device_update_lists_new_device(qtbot, mocked_client, device_picker):
    assert "new_det" not in device_picker.devices
    mocked_client.device_manager.add_devices([FakeDevice("new_det")])
    device_picker.on_device_update("add", {})
    qtbot.waitUntil(lambda: "new_det" in device_picker.devices)


def test_invalid_text_is_painted_not_restyled(device_picker):
    sheet = device_picker.styleSheet()
    device_picker.setCurrentText("not_a_device")
    assert not device_picker.is_valid_input
    assert device_picker.shows_invalid
    device_picker.setCurrentText("")
    assert not device_picker.shows_invalid
    device_picker.setCurrentText("samx")
    assert device_picker.is_valid_input and not device_picker.shows_invalid
    assert device_picker.styleSheet() == sheet
    device_picker.setCurrentText("not_a_device")
    device_picker.setEnabled(False)
    assert not device_picker.shows_invalid


def test_pick_from_popup_selects_device(qtbot, device_picker):
    device_picker.showPopup()
    assert device_picker.is_popup_open()
    popup_cls = PickerPopupQml if isinstance(device_picker, DevicePickerQML) else PickerPopupWidget
    assert isinstance(device_picker.picker_popup, popup_cls)
    controller = device_picker.picker_controller
    assert ("header", "Positioners") in _titles(controller)

    controller.set_query("samy")
    with qtbot.waitSignal(device_picker.device_selected) as blocker:
        controller.accept()
    assert blocker.args == ["samy"]
    assert device_picker.currentText() == "samy"
    _wait_closed(qtbot, device_picker)
    assert picker_model.recent_picks("devices") == ["samy"]


def test_typing_opens_popup_with_query_and_escape_restores(qtbot, device_picker):
    device_picker.set_device("samx")
    device_picker.lineEdit().textEdited.emit("bpm")
    assert device_picker.is_popup_open()
    controller = device_picker.picker_controller
    assert controller.query == "bpm"
    assert all("bpm" in title for kind, title in _titles(controller) if kind == "item")
    device_picker.setCurrentText("bpm")
    controller.dismiss()
    _wait_closed(qtbot, device_picker)
    assert device_picker.currentText() == "samx"


def test_closing_popup_by_clicking_outside_reverts_typed_text(qtbot, device_picker):
    device_picker.set_device("samx")
    device_picker.setCurrentText("bp")
    device_picker.lineEdit().textEdited.emit("bp")
    assert device_picker.is_popup_open()
    device_picker.picker_popup.hide()
    assert device_picker.currentText() == "samx"


def test_footer_shows_cached_and_live_value(qtbot, mocked_client, device_picker):
    now = time.time()
    mocked_client.connector.set_and_publish(
        MessageEndpoints.device_readback("samx"),
        messages.DeviceMessage(signals={"samx": {"value": 2.5, "timestamp": now}}, metadata={}),
    )
    device_picker.set_device("samx")
    device_picker.showPopup()
    controller = device_picker.picker_controller
    assert controller.detail["title"] == "samx"
    qtbot.waitUntil(lambda: controller.detail.get("valueState") == "live", timeout=2000)
    assert controller.detail["value"] == "2.5"
    assert device_picker._live_entry.device == "samx"

    device_picker._on_live_message({"signals": {"samx": {"value": 3.0, "timestamp": now}}}, {})
    assert controller.detail["value"] == "3"

    device_picker.hidePopup()
    _wait_closed(qtbot, device_picker)
    assert device_picker._live_entry is None


def test_popup_follows_theme(qtbot, device_picker):
    from bec_widgets.utils.colors import apply_theme

    device_picker.showPopup()
    apply_theme("dark")
    QApplication.processEvents()
    device_picker.hidePopup()
    apply_theme("light")


def test_qml_popup_loads_without_errors(qtbot, mocked_client):
    picker = create_widget(qtbot, DevicePickerQML, client=mocked_client)
    picker.showPopup()
    view = picker.picker_popup.view
    assert view.errors() == []
    assert view.rootObject() is not None
    picker.hidePopup()


def test_cleanup_releases_popup(qtbot, mocked_client):
    picker = DevicePicker(client=mocked_client)
    qtbot.addWidget(picker)
    picker.showPopup()
    popup = picker.picker_popup
    picker.close()
    assert picker._picker_popup is None
    assert not popup.isVisible()


# ---- signal picker -------------------------------------------------------------------------------


def test_signal_picker_groups_by_kind(signal_picker):
    signal_picker.showPopup()
    titles = _titles(signal_picker.picker_controller)
    headers = [title for kind, title in titles if kind == "header"]
    assert headers == ["Hinted", "Normal", "Config"]
    assert ("item", "samx (readback)") in titles
    signal_picker.hidePopup()


def test_signal_picker_pick_sets_index_and_config(qtbot, signal_picker):
    signal_picker.showPopup()
    controller = signal_picker.picker_controller
    controller.set_query("velo")
    with qtbot.waitSignal(signal_picker.device_signal_changed):
        controller.accept()
    assert signal_picker.currentText() == "velocity"
    assert signal_picker.get_signal_name() == "samx_velocity"
    assert signal_picker.get_signal_config()["obj_name"] == "samx_velocity"
    _wait_closed(qtbot, signal_picker)


def test_signal_picker_by_class_groups_by_device(qtbot, mocked_client, async_signals):
    picker = create_widget(
        qtbot, SignalPicker, client=mocked_client, signal_class_filter=["AsyncSignal"]
    )
    picker.showPopup()
    titles = _titles(picker.picker_controller)
    # a single group is listed without a header
    assert titles == [("item", "eiger")]
    entry = next(
        picker.picker_controller.entry_at(row)
        for row in range(len(titles))
        if titles[row] == ("item", "eiger")
    )
    assert entry.device == "eiger"
    assert entry.group == "eiger"
    picker.hidePopup()
