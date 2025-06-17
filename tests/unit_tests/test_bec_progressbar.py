import numpy as np
import pytest

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


def test_progressbar(progressbar):
    progressbar.update()


def test_progressbar_set_value(qtbot, progressbar):
    progressbar.set_minimum(0)
    progressbar.set_maximum(100)
    progressbar.set_value(50)
    progressbar.paintEvent(None)

    qtbot.waitUntil(
        lambda: np.isclose(
            progressbar._value, progressbar._user_value * progressbar._oversampling_factor
        )
    )


def test_progressbar_label(progressbar):
    progressbar.label_template = "Test: $value"
    progressbar.set_value(50)
    assert progressbar.center_label.text() == "Test: 50"


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
