from unittest import mock

import pytest
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QProgressBar

from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import (
    BECProgressBar,
    ProgressState,
)


@pytest.fixture
def progressbar(qtbot):
    widget = BECProgressBar()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def static_progressbar(qtbot):
    widget = BECProgressBar(enable_dynamic_stylesheet=False)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_progressbar(progressbar):
    progressbar.update()


def test_progressbar_set_value(qtbot, progressbar):
    progressbar.set_minimum(0)
    progressbar.set_maximum(100)
    progressbar.set_value(50)

    assert isinstance(progressbar.progressbar, QProgressBar)
    assert progressbar._value == progressbar._user_value * progressbar._oversampling_factor
    assert progressbar.progressbar.value() == 50 * progressbar._oversampling_factor


def test_progressbar_label(progressbar):
    progressbar.label_template = "Test: $value"
    progressbar.set_value(50)
    assert progressbar._get_label() == "Test: 50"
    assert progressbar.center_label.text() == "Test: 50"


def test_progressbar_equal_minimum_and_maximum_does_not_raise(progressbar):
    progressbar.set_minimum(0)
    progressbar.set_maximum(0)
    progressbar.set_value(0)

    assert progressbar._get_label() == "0 / 0 - 100 %"
    assert progressbar.progressbar.value() == progressbar.progressbar.maximum()


def test_progressbar_uses_static_stylesheet_with_palette_state_color(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_value(50)
    progressbar.state = ProgressState.PAUSED

    style_sheet = progressbar.progressbar.styleSheet()
    assert "QProgressBar::chunk" in style_sheet
    assert "background-color: palette(highlight);" in style_sheet
    assert "background-color: palette(mid);" in style_sheet
    assert "border-radius: 7px;" in style_sheet
    assert (
        progressbar.progressbar.palette().color(QPalette.ColorRole.Highlight)
        == progressbar._state_colors[ProgressState.PAUSED]
    )


def test_progressbar_value_updates_do_not_rebuild_stylesheet_within_same_chunk_mode(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_value(30)

    with mock.patch.object(
        progressbar, "_setup_style_sheet", wraps=progressbar._setup_style_sheet
    ) as setup_style_sheet:
        progressbar.set_value(35)
        progressbar.set_value(42)
        progressbar.set_value(50)

    setup_style_sheet.assert_not_called()


def test_progressbar_value_updates_skip_chunk_radius_after_target_reached(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_value(30)
    assert progressbar._chunk_radius == progressbar._target_chunk_radius()

    with mock.patch.object(
        progressbar, "_update_chunk_radius", wraps=progressbar._update_chunk_radius
    ) as update_chunk_radius:
        progressbar.set_value(35)
        progressbar.set_value(42)
        progressbar.set_value(50)

    update_chunk_radius.assert_not_called()


def test_progressbar_repeated_same_maximum_does_not_reset_chunk_radius(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_maximum(100)
    progressbar.set_value(30)
    assert progressbar._chunk_radius == progressbar._target_chunk_radius()

    with mock.patch.object(
        progressbar, "_update_chunk_radius", wraps=progressbar._update_chunk_radius
    ) as update_chunk_radius:
        progressbar.set_maximum(100)
        progressbar.set_value(40)

    update_chunk_radius.assert_not_called()


def test_progressbar_can_disable_dynamic_stylesheet(static_progressbar):
    static_progressbar.progressbar.resize(100, 20)
    assert static_progressbar.enable_dynamic_stylesheet is False
    assert static_progressbar._chunk_radius == static_progressbar._target_chunk_radius()

    with mock.patch.object(
        static_progressbar, "_setup_style_sheet", wraps=static_progressbar._setup_style_sheet
    ) as setup_style_sheet:
        static_progressbar.set_value(1)
        static_progressbar.set_value(2)
        static_progressbar.set_value(3)

    setup_style_sheet.assert_not_called()
    assert "border-radius: 7px;" in static_progressbar.progressbar.styleSheet()


def test_progressbar_dynamic_stylesheet_can_be_toggled(progressbar):
    progressbar.enable_dynamic_stylesheet = False

    assert progressbar.enable_dynamic_stylesheet is False
    assert progressbar._chunk_radius == progressbar._target_chunk_radius()
    assert "border-radius: 7px;" in progressbar.progressbar.styleSheet()


def test_progressbar_rebuilds_stylesheet_until_chunk_radius_reaches_target(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_value(9)

    with mock.patch.object(
        progressbar, "_setup_style_sheet", wraps=progressbar._setup_style_sheet
    ) as setup_style_sheet:
        progressbar.set_value(12)
        progressbar.set_value(25)
        progressbar.set_value(30)

    assert setup_style_sheet.call_count == 2
    assert "border-radius: 7px;" in progressbar.progressbar.styleSheet()


def test_progressbar_resets_chunk_radius_when_value_goes_backwards(progressbar):
    progressbar.progressbar.resize(100, 20)
    progressbar.set_value(30)
    assert "border-radius: 7px;" in progressbar.progressbar.styleSheet()

    progressbar.set_value(4)

    assert "border-radius: 2px;" in progressbar.progressbar.styleSheet()


def test_progress_state_from_bec_status():
    """ProgressState.from_bec_status() maps BEC literals correctly."""
    mapping = {
        "open": ProgressState.NORMAL,
        "paused": ProgressState.PAUSED,
        "aborted": ProgressState.INTERRUPTED,
        "halted": ProgressState.PAUSED,
        "closed": ProgressState.COMPLETED,
        "UNKNOWN": ProgressState.NORMAL,  # fallback
    }
    for text, expected in mapping.items():
        assert ProgressState.from_bec_status(text) is expected


def test_progressbar_state_setter(progressbar):
    """Setting .state reflects internally."""
    progressbar.state = ProgressState.PAUSED
    assert progressbar.state is ProgressState.PAUSED
