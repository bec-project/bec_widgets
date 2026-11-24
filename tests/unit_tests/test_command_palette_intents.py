from types import SimpleNamespace
from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.utility.command_palette.palette_core import (
    CommandPaletteController,
    PaletteCommand,
)
from bec_widgets.widgets.utility.command_palette.palette_intents import (
    DeviceIntent,
    parse_intent,
    resolve_device,
    tokenize,
    units_match,
)
from bec_widgets.widgets.utility.command_palette.palette_sources import DeviceCommandSource


def move(device, value, relative=False, unit=""):
    return DeviceIntent(kind="move", device=device, value=value, relative=relative, unit=unit)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("samx 10", move("samx", 10.0)),
        ("samx move 10", move("samx", 10.0)),
        ("samx move to 10", move("samx", 10.0)),
        ("move samx to 10", move("samx", 10.0)),
        ("Move samx 10", move("samx", 10.0)),
        ("mv samx 10", move("samx", 10.0)),
        ("umv samx 10", move("samx", 10.0)),
        ("samx to 10", move("samx", 10.0)),
        ("samx = 10", move("samx", 10.0)),
        ("samx=10", move("samx", 10.0)),
        ("samx -2", move("samx", -2.0)),
        ("samx 1e-3", move("samx", 0.001)),
        ("samx .5", move("samx", 0.5)),
        ("samx to +2", move("samx", 2.0)),
    ],
)
def test_absolute_moves(text, expected):
    assert parse_intent(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("samx +2", move("samx", 2.0, relative=True)),
        ("samx += 2", move("samx", 2.0, relative=True)),
        ("samx+=2", move("samx", 2.0, relative=True)),
        ("samx -= 2", move("samx", -2.0, relative=True)),
        ("move samx by -0.5", move("samx", -0.5, relative=True)),
        ("samx by 3", move("samx", 3.0, relative=True)),
        ("umvr samx 1", move("samx", 1.0, relative=True)),
        ("mvr samx -1", move("samx", -1.0, relative=True)),
        ("samx tweak 0.1", move("samx", 0.1, relative=True)),
    ],
)
def test_relative_moves(text, expected):
    assert parse_intent(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("samx 10 mm", move("samx", 10.0, unit="mm")),
        ("samx 10mm", move("samx", 10.0, unit="mm")),
        ("move samx to 10 deg", move("samx", 10.0, unit="deg")),
        ("samx +2 um", move("samx", 2.0, relative=True, unit="um")),
    ],
)
def test_units_are_kept_as_typed(text, expected):
    assert parse_intent(text) == expected


@pytest.mark.parametrize(
    "text", ["samx?", "samx ?", "where samx", "where is samx", "wm samx", "samx pos"]
)
def test_where(text):
    assert parse_intent(text) == DeviceIntent(kind="where", device="samx")


@pytest.mark.parametrize("text", ["stop samx", "samx stop", "halt samx"])
def test_stop(text):
    assert parse_intent(text) == DeviceIntent(kind="stop", device="samx")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "samx",
        "move",
        "stop",
        "wave",
        "scan control",
        "go to dock area",
        "samx ten",
        "samx 10 20",
        "samx 10 mm extra",
        "samx 10mm mm",
        "mvr samx to 1",
        "move 10",
        "10 samx",
        "samx move",
        "where samx now",
        "stop samx 10",
        "sam-x 10",
    ],
)
def test_text_that_is_not_a_command(text):
    assert parse_intent(text) is None


def test_tokenize_splits_operators():
    assert tokenize("samx+=2") == ["samx", "+=", "2"]
    assert tokenize("samx=-1") == ["samx", "=", "-1"]
    assert tokenize("samx?") == ["samx", "?"]
    assert tokenize("samx -> 3") == ["samx", "->", "3"]


# ---------------------------------------------------------------- device resolution


def test_resolve_device_prefers_exact_names():
    names = ["samx", "samy", "samx_offset"]
    assert resolve_device("samx", names) == ["samx"]
    assert resolve_device("SAMY", names) == ["samy"]
    assert resolve_device("sam", names)[:2] == ["samx", "samy"]
    assert resolve_device("nothing", names) == []
    assert resolve_device("sx", names) == ["samx", "samx_offset"]
    assert resolve_device("sx", names, fuzzy=False) == []
    assert resolve_device("sam", names, fuzzy=False) == ["samx", "samy", "samx_offset"]


def test_units_match_aliases():
    assert units_match("mm", "mm")
    assert units_match("MM", "mm")
    assert units_match("deg", "°")
    assert units_match("um", "µm")
    assert not units_match("um", "mm")


# ---------------------------------------------------------------- palette rows


@pytest.fixture
def source(mocked_client):
    widget = SimpleNamespace(
        client=mocked_client, submit_task=mock.MagicMock(), bec_dispatcher=mock.MagicMock()
    )
    source = DeviceCommandSource(widget)
    yield source
    source.release()


def rows(source, text, scope="all"):
    return [(cmd.title, cmd.subtitle, cmd.enabled) for cmd in source(text, scope)]


def test_move_preview_shows_position_and_limits(source):
    assert rows(source, "samx 5") == [
        ("Move samx to 5.000", "now 2.000 · limits −10.000 … 10.000", True)
    ]
    assert rows(source, "move samx to -2.5") == [
        ("Move samx to −2.500", "now 2.000 · limits −10.000 … 10.000", True)
    ]


def test_relative_move_preview_shows_the_target(source):
    assert rows(source, "samx +2") == [
        ("Move samx by +2.000", "now 2.000 → 4.000 · limits −10.000 … 10.000", True)
    ]
    assert rows(source, "umvr samx -1") == [
        ("Move samx by −1.000", "now 2.000 → 1.000 · limits −10.000 … 10.000", True)
    ]


def test_move_outside_the_limits_is_refused(source):
    [command] = source("samx 20", "all")
    assert not command.enabled and command.tone == "danger"
    assert command.subtitle == "20.000 is outside the limits −10.000 … 10.000"
    [command] = source("samx +9", "all")
    assert not command.enabled and command.subtitle.startswith("11.000 is outside")
    # a device without limits takes any target
    assert rows(source, "aptrx 1000")[0][2]


def test_move_is_refused_for_devices_that_cannot_move(source, mocked_client, monkeypatch):
    assert rows(source, "bpm4i 3") == [("Move bpm4i to 3.000", "bpm4i is not a motor", False)]
    monkeypatch.setattr(mocked_client.device_manager.devices["samy"], "_enabled", False)
    assert rows(source, "samy 1") == [("Move samy to 1.000", "samy is disabled", False)]


def test_move_checks_the_unit(source, mocked_client, monkeypatch):
    samx = mocked_client.device_manager.devices["samx"]
    assert rows(source, "samx 5 mm")[0][1:] == ("samx reports no unit, leave out “mm”", False)
    monkeypatch.setattr(samx, "egu", lambda: "mm")
    assert rows(source, "samx 5 mm") == [
        ("Move samx to 5.000 mm", "now 2.000 mm · limits −10.000 … 10.000", True)
    ]
    assert rows(source, "samx 5 um")[0][1:] == ("samx is in mm, not um", False)


def test_ambiguous_device_lists_the_candidates(source):
    commands = source("sam 1", "all")
    header, candidates = commands[0], commands[1:]
    assert not header.enabled and header.title == "“sam” matches 3 devices"
    assert [cmd.title for cmd in candidates] == [
        "Move samx to 1.000",
        "Move samy to 1.000",
        "Move samz to 1.000",
    ]
    assert all(cmd.enabled for cmd in candidates)
    # with "@", a partial name that fits one device is enough
    assert rows(source, "sax 1", "devices")[0][0] == "Move samx to 1.000"
    assert source("sax 1", "all") == []


def test_text_that_is_no_device_command_adds_nothing(source):
    assert source("waveform", "all") == []
    assert source("wave 2", "all") == []
    assert rows(source, "wave 2", "devices")[0][1:] == ("waveform1d is not a motor", False)
    assert source("samx 5", "widgets") == []
    assert rows(source, "samx 5", "devices")[0][0] == "Move samx to 5.000"


def test_where_and_stop(source, qtbot):
    [where] = source("samx?", "all")
    assert (where.title, where.hint) == ("samx is at 2.000", "Copy")
    where.callback()
    assert QApplication.clipboard().text() == "2.000"
    [stop] = source("stop samx", "all")
    assert (stop.title, stop.hint, stop.enabled) == ("Stop samx", "Stop", True)


def test_enter_sends_the_move_from_a_worker(source, mocked_client):
    [command] = source("samx +2", "all")
    command.callback()
    submit = source.widget.submit_task
    func, *args = submit.call_args.args
    assert args == ["samx", 2.0, True]
    with mock.patch.object(mocked_client, "scans") as scans:
        func(*args)
    scans.mv.assert_called_once_with(
        mocked_client.device_manager.devices["samx"], 2.0, relative=True
    )


def test_stop_sends_the_device_stop(source, mocked_client):
    [command] = source("samx stop", "all")
    command.callback()
    func, *args = source.widget.submit_task.call_args.args
    with mock.patch.object(mocked_client.connector, "send") as send:
        func(*args)
    endpoint, msg = send.call_args.args
    assert endpoint == MessageEndpoints.stop_devices() and msg.value == ["samx"]


# ---------------------------------------------------------------- controller


def test_controller_lists_query_rows_first_and_skips_refused_ones(qtbot, source):
    controller = CommandPaletteController(
        [lambda: [PaletteCommand(uid="device:samx", title="samx", callback=lambda: None)]]
    )
    controller.add_query_source(source)
    controller.refresh()
    controller.set_query("samx 20")
    assert controller.results[0].uid == "intent:move:samx"
    accepted = []
    controller.accepted.connect(accepted.append)
    controller.execute()
    assert accepted == [] and not source.widget.submit_task.called
    controller.set_query("samx 5")
    controller.execute()
    # a move keeps the palette open so its row can follow the motor
    qtbot.waitUntil(lambda: source.widget.submit_task.called, timeout=1000)
    assert accepted == []
    controller.deleteLater()


# ---------------------------------------------------------------- after Enter


def readback(source, value, moving=None):
    signals = {"samx": {"value": value}}
    if moving is not None:
        signals["samx_motor_is_moving"] = {"value": int(moving)}
    source._on_readback({"signals": signals}, {})


def test_row_follows_the_readback_after_enter(source):
    dispatcher = source.widget.bec_dispatcher
    [command] = source("samx 5", "all")
    dispatcher.connect_slot.assert_called_once_with(
        source._on_readback, MessageEndpoints.device_readback("samx")
    )
    changed = []
    source.changed.connect(lambda: changed.append(True))
    command.callback()
    assert changed and source("samx 5", "all")[0].subtitle == "moving · now 2.000"
    readback(source, 3.5, moving=True)
    assert source("samx 5", "all")[0].subtitle == "moving · now 3.500"
    readback(source, 5.0, moving=False)
    assert source("samx 5", "all")[0].subtitle == "arrived · now 5.000"
    # other text shows a fresh preview again; leaving the device stops following it
    assert source("samx 6", "all")[0].subtitle.startswith("now 5.000")
    source("waveform", "all")
    dispatcher.disconnect_slot.assert_called_once_with(
        source._on_readback, MessageEndpoints.device_readback("samx")
    )


def test_relative_move_tracks_the_target_taken_on_enter(source):
    [command] = source("samx +2", "all")
    command.callback()
    readback(source, 4.0, moving=False)
    [command] = source("samx +2", "all")
    assert command.subtitle == "arrived · now 4.000"
    assert command.title == "Move samx by +2.000"


def test_a_stopped_motor_short_of_the_target(source):
    [command] = source("samx 9", "all")
    command.callback()
    readback(source, 6.0, moving=False)
    assert source("samx 9", "all")[0].subtitle == "stopped · now 6.000"


def test_a_failed_send_is_shown_on_the_row(source):
    [command] = source("samx 5", "all")
    command.callback()
    source._on_failed("Traceback (most recent call last):\n  ...\nRuntimeError: queue locked\n")
    [command] = source("samx 5", "all")
    assert command.subtitle == "Not sent: RuntimeError: queue locked"
    assert command.tone == "danger" and command.enabled  # Enter tries again


def test_stop_row_after_enter(source):
    [command] = source("stop samx", "all")
    command.callback()
    assert source("stop samx", "all")[0].subtitle == "stop sent · now 2.000"


def test_release_forgets_the_last_move(source):
    [command] = source("samx 5", "all")
    command.callback()
    source.release()
    source.widget.bec_dispatcher.disconnect_slot.assert_called_once()
    assert source("samx 5", "all")[0].subtitle.startswith("now 2.000")
