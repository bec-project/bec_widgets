import pytest

from bec_widgets.widgets.utility.command_palette.palette_intents import (
    DeviceIntent,
    parse_intent,
    tokenize,
)


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
