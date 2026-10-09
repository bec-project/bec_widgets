import pytest

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.progress.scan_progressbar.scan_progress_model import (
    format_count,
    format_duration,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_modern import (
    ScanProgressBarModern,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_qml import ScanProgressBarQml


@pytest.fixture(params=[ScanProgressBarModern, ScanProgressBarQml], ids=["qwidget", "qml"])
def widget_cls(request):
    return request.param


@pytest.fixture
def bar(qtbot, mocked_client, widget_cls):
    return create_widget(qtbot, widget_cls, client=mocked_client)


def _status(bar, status, scan_id="sid", **extra):
    bar.model._on_scan_status({"scan_id": scan_id, "status": status, **extra}, {})


def _progress(bar, value, max_value, done=False, status="open", scan_id="sid", scan_number=7):
    bar.progress_tracker.process_progress_message(
        {"value": value, "max_value": max_value, "done": done},
        {"scan_id": scan_id, "RID": f"rid-{scan_id}", "status": status, "scan_number": scan_number},
    )


def test_format_helpers():
    assert format_duration(None) == "—"
    assert format_duration(5) == "0:05"
    assert format_duration(83) == "1:23"
    assert format_duration(3725) == "1:02:05"
    assert format_count(3.0) == "3"
    assert format_count(2.5) == "2.5"


def test_idle_state(bar):
    m = bar.model
    assert m.state == "idle"
    assert m.title == "No scan yet"
    assert m.percentText == ""
    assert m.timeText == ""


def test_running_scan_shows_name_count_and_percent(bar):
    _status(bar, "open", scan_name="line_scan", scan_number=7)
    _progress(bar, 3, 12)
    m = bar.model
    assert m.state == "running"
    assert m.title == "Scan 7 · line_scan"
    assert m.countText == "3 / 12"
    assert m.percentText == "25 %"
    assert m.fraction == pytest.approx(0.25)
    assert m.timeText in ("estimating…",) or m.timeText.endswith("left")


def test_indeterminate_until_points_are_known(bar):
    _progress(bar, 0, 0)
    assert bar.model.indeterminate
    _progress(bar, 1, 10)
    assert not bar.model.indeterminate


def test_paused_then_resumed(bar):
    _progress(bar, 2, 10)
    _progress(bar, 2, 10, status="paused")
    assert bar.model.state == "paused"
    assert bar.model.timeText.startswith("paused at")
    _progress(bar, 3, 10)
    assert bar.model.state == "running"


def test_done_keeps_result_visible(bar, qtbot):
    with qtbot.waitSignal(bar.progress_finished, timeout=1000):
        _progress(bar, 10, 10, done=True)
    m = bar.model
    assert m.state == "done"
    assert m.percentText == "100 %"
    assert m.timeText.startswith("took")


def test_halted_by_alarm_is_not_overwritten_by_late_progress(bar):
    _progress(bar, 4, 10)
    _status(bar, "halted", reason="alarm")
    assert bar.model.stateLabel == "Halted by alarm"
    _progress(bar, 4, 10, done=True)
    assert bar.model.state == "halted"


def test_new_scan_resets_state(bar):
    _progress(bar, 4, 10)
    _status(bar, "aborted")
    _progress(bar, 1, 5, scan_id="next", scan_number=8)
    assert bar.model.state == "running"
    assert bar.model.title.startswith("Scan 8")


def test_show_properties(bar):
    for name in ("show_elapsed_time", "show_remaining_time", "show_source_label"):
        assert getattr(bar, name) is True
        setattr(bar, name, False)
        assert getattr(bar, name) is False


def test_one_line_design(qtbot, mocked_client, widget_cls):
    widget = create_widget(qtbot, widget_cls, client=mocked_client, one_line_design=True)
    _progress(widget, 1, 2)
    assert widget.height() == 22
    assert widget.model.percentText == "50 %"
