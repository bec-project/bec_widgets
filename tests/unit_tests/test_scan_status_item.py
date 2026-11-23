from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QSettings

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.containers.main_window.addons.scan_status_item import (
    PILL_FILL_MIN,
    PILL_WIDTHS,
    Reveal,
    ScanStatusItem,
    pill_labels,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import ScanRunState


def status(state="open", **kwargs):
    content = {"scan_id": "s1", "status": state, "scan_number": 12, "scan_name": "line_scan"}
    content.update(kwargs)
    return content, {"RID": "rid-12", "scan_id": "s1"}


def hook(name, ts, hook_status="running"):
    content = {
        "scan_id": "s1",
        "hook": name,
        "status": hook_status,
        "instructions": [],
        "hook_started_at": ts,
        "timestamp": ts,
    }
    return content, {"RID": "rid-12", "scan_id": "s1"}


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "scan_status.ini")


@pytest.fixture
def item(qtbot, mocked_client, settings_path):
    widget = create_widget(
        qtbot,
        ScanStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )
    yield widget


def test_pill_labels_for_every_state():
    assert pill_labels(None) == ("Queue idle",) * 3

    state = ScanRunState(scan_id="s", scan_number=12, scan_name="line_scan")
    state.apply_hook(
        {"hook": "stage", "status": "running", "hook_started_at": 1.0, "timestamp": 1.0}
    )
    short, medium, long = pill_labels(state, now=state.hook_started_local + 3)
    assert short == "Staging 0:03"
    assert medium == "#12 · Staging · 0:03"
    assert long.startswith("#12 line_scan · Staging · 0:03") and long.endswith("next: pre_scan")

    state.apply_hook(
        {"hook": "scan_core", "status": "running", "hook_started_at": 2.0, "timestamp": 2.0}
    )
    state.apply_progress({"value": 20, "max_value": 50})
    short, medium, long = pill_labels(state)
    assert short == "40%"
    assert medium.startswith("#12 · 40%")
    assert "Point 20 of 50 · 40%" in long and long.endswith("next: post_scan")

    state.apply_status({"status": "closed"}, {})
    short, medium, long = pill_labels(state)
    assert short == "Done" and medium.startswith("#12 done · ")

    failed = ScanRunState(scan_id="f", scan_number=13, scan_name="grid_scan")
    failed.apply_hook(
        {"hook": "stage", "status": "running", "hook_started_at": 1.0, "timestamp": 1.0}
    )
    failed.apply_hook(
        {"hook": "stage", "status": "error", "hook_started_at": 2.0, "timestamp": 2.0}
    )
    failed.apply_status({"status": "aborted"}, {})
    short, medium, long = pill_labels(failed)
    assert short == "Aborted" and medium.startswith("#13 aborted in Staging")
    assert long.startswith("#13 grid_scan · Aborted in Staging")


def test_pill_without_a_step_uses_the_big_bar_shape():
    from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import describe_state

    state = ScanRunState(scan_id="s", scan_number=79, scan_name="line_scan")
    state.apply_status({"status": "aborted"}, {})
    short, medium, long = pill_labels(state)
    assert describe_state(state)["bar_text"].startswith("Aborted · ")
    assert short == "Aborted"
    assert medium.startswith("#79 aborted · ") and " in " not in medium
    assert long.startswith("#79 line_scan · Aborted · ")


@pytest.mark.parametrize(
    "status_word, outcome, mode",
    [
        ("closed", "Done", "done"),
        ("user_completed", "Finished early", "done"),
        ("aborted", "Aborted", "error"),
        ("halted", "Halted", "error"),
    ],
)
def test_pill_and_big_widget_share_the_end_state(status_word, outcome, mode):
    from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import describe_state

    state = ScanRunState(scan_id="s", scan_number=75, scan_name="line_scan")
    state.apply_hook(
        {"hook": "scan_core", "status": "running", "hook_started_at": 1.0, "timestamp": 1.0}
    )
    state.apply_status({"status": status_word}, {})
    info = describe_state(state)
    short, medium, long = pill_labels(state)
    assert info["outcome"] == outcome == short
    assert info["bar_mode"] == mode
    for text in (medium, long, info["bar_text"]):
        assert "scan_core" not in text
        assert outcome.lower() in text.lower()
    if mode == "error":
        assert "Measuring" in medium and "Measuring" in info["bar_text"]


def test_abort_shows_the_same_words_in_pill_and_big_widget(item):
    item.tracker.on_scan_status(*status())
    item.tracker.on_scan_hook(*hook("scan_core", 1.0))
    item.tracker.on_scan_status(*status(state="aborted"))
    big = item.card.progress
    assert big.bar.text.startswith("Aborted in Measuring")
    assert item.pill.text.startswith("#12 aborted in Measuring")
    assert big.bar.mode == item.pill.mode == "error"


def test_pill_follows_hooks_and_width_mode(item):
    assert item.pill.mode == "idle" and item.pill.text == "Queue idle"
    item.tracker.on_scan_status(*status())
    item.tracker.on_scan_hook(*hook("stage", 1.0))
    assert item.pill.mode == "busy"
    assert item.pill.text.startswith("#12 · Staging")
    item.tracker.on_scan_hook(*hook("scan_core", 2.0))
    item.tracker.on_scan_progress({"value": 10, "max_value": 40}, {"scan_id": "s1"})
    assert item.pill.mode == "progress"
    assert item.pill.fraction == pytest.approx(0.25)
    item.set_width_mode("compact")
    assert item.pill.text == "25%"
    assert item.pill.width() == PILL_WIDTHS["compact"][0]
    item.set_width_mode("wide")
    assert "Point 10 of 40" in item.pill.text


def test_stop_only_when_stoppable_and_uses_the_shared_stop(item, qtbot):
    from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton

    assert isinstance(item.stop_button, StopButton)
    assert item.stop_button.isHidden()
    item.tracker.on_scan_status(*status())
    assert not item.stop_button.isHidden()
    with mock.patch.object(item.stop_button.queue, "request_scan_abortion") as abort:
        item.stop_button.click()
    abort.assert_called_once_with(request_id="rid-12")
    assert item.stop_button.button.text() == "Emergency Stop"
    item.tracker.on_scan_status(*status(state="closed"))
    qtbot.waitUntil(item.stop_button.isHidden, timeout=2000)
    item.close_card()


def _cursor_at(monkeypatch, point):
    from bec_widgets.utils import hover_card

    monkeypatch.setattr(hover_card.QCursor, "pos", staticmethod(lambda: point))


def _show_settled(item, qtbot):
    """
    Show the item as a roomy window (room for the Stop to slide in, as in the status bar) and
    wait until the window system has settled its size: a resized window closes the card.
    """
    item.resize(900, 60)
    item.show()
    qtbot.waitExposed(item)
    window = item.window().windowHandle()
    qtbot.waitUntil(lambda: window.size() == item.size(), timeout=2000)
    qtbot.wait(50)


def test_outline_clears_without_a_leave_event_once_the_card_closes(item, qtbot, monkeypatch):
    from qtpy.QtCore import QEvent, QObject, QPoint, Qt
    from qtpy.QtGui import QCursor

    class SwallowLeave(QObject):
        """Like macOS with the card shown: the pill never gets its Leave event."""

        def eventFilter(self, _obj, event):  # pylint: disable=invalid-name
            return event.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave)

    _show_settled(item, qtbot)
    swallow = SwallowLeave()
    item.pill.installEventFilter(swallow)
    inside = item.pill.mapToGlobal(QPoint(5, 5))
    _cursor_at(monkeypatch, inside)
    qtbot.mouseClick(item.pill, Qt.MouseButton.LeftButton)
    assert item.card.isVisible() and item.pill.outlined
    assert not item._poll.isActive()  # no cursor poll for a click card

    outside = inside + QPoint(2000, 2000)
    QCursor.setPos(outside)
    _cursor_at(monkeypatch, outside)
    qtbot.wait(item.GRACE_MS + 150)
    assert item.card.isVisible()  # leaving does not close it
    item.close_card()  # e.g. a click elsewhere
    assert not item.pill.hovered and not item.pill.outlined
    item.pill.removeEventFilter(swallow)


def test_card_stays_while_a_stop_waits_for_confirmation(item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint

    item.tracker.on_scan_status(*status())
    _show_settled(item, qtbot)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    item.card.progress.confirm_before_stop = True
    item.open_card()
    item.card.progress.ask_stop()
    qtbot.wait(item.GRACE_MS + 300)
    assert item.card.isVisible()
    item.close_card()
    assert not item.card.isVisible() and not item._poll.isActive()


def test_menu_changes_width_and_persists(item, qtbot, mocked_client, settings_path):
    fills = []
    item.fill_changed.connect(fills.append)
    menu = item.build_menu()
    wide = next(a for a in menu.actions() if a.data() == "wide")
    wide.trigger()
    assert item.width_mode == "wide"
    fill = next(a for a in menu.actions() if a.data() == "fill")
    fill.trigger()
    assert fills == [True]
    assert item.pill.minimumWidth() == PILL_FILL_MIN
    large = next(a for a in menu.actions() if a.text() == "Large status bar")
    large.trigger()
    assert item.large and item.pill.height() == 34
    menu.deleteLater()

    again = create_widget(
        qtbot,
        ScanStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )
    assert again.width_mode == "fill" and again.large


def test_waiting_chip_starts_hidden_without_a_queue_status(qtbot, mocked_client, settings_path):
    with mock.patch.object(mocked_client.connector, "get", return_value=None):
        widget = create_widget(
            qtbot,
            ScanStatusItem,
            client=mocked_client,
            settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
        )
    assert widget.waiting_chip.isHidden()


def test_waiting_chip_counts_pending_scans(item, qtbot):
    item.on_queue_status({"queue": {"primary": {"info": []}}}, {})
    qtbot.waitUntil(item.waiting_chip.isHidden, timeout=2000)
    infos = [{"status": "RUNNING"}, {"status": "PENDING"}, {"status": "PENDING"}]
    item.on_queue_status({"queue": {"primary": {"info": infos}}}, {})
    assert not item.waiting_chip.isHidden()
    assert item.waiting_chip.text() == "2 waiting"
    item.on_queue_status({"queue": {"primary": {"info": infos[:1]}}}, {})
    qtbot.waitUntil(item.waiting_chip.isHidden, timeout=2000)
    qtbot.waitUntil(lambda: not item.waiting_reveal.active, timeout=2000)


def test_stop_slides_in_and_does_not_blink(item, qtbot):
    item.show()
    qtbot.waitExposed(item)
    assert item.stop_button.isHidden() and item.stop_button.maximumWidth() == 0
    item.tracker.on_scan_status(*status())
    assert not item.stop_button.isHidden()
    widths = []
    qtbot.waitUntil(
        lambda: widths.append(item.stop_button.maximumWidth()) or not item.stop_reveal.active,
        timeout=2000,
    )
    assert widths[0] < item.stop_button.sizeHint().width() <= max(widths)

    # a short flip (e.g. scan closed and the next one opened) never hides it
    item.tracker.on_scan_status(*status(state="closed"))
    qtbot.wait(200)
    item.tracker.on_scan_status(*status(scan_id="s2", state="open"))
    qtbot.wait(Reveal.HIDE_DELAY_MS + Reveal.DURATION_MS + 100)
    assert not item.stop_button.isHidden() and item.stop_button.isEnabled()

    # not stoppable for longer than the delay: it slides out
    item.tracker.on_scan_status(*status(scan_id="s2", state="closed"))
    qtbot.waitUntil(item.stop_button.isHidden, timeout=2000)
    assert item.stop_button.maximumWidth() == 0
    assert not item.stop_reveal.active


def test_pill_shows_the_scan_by_its_own_name():
    state = ScanRunState(scan_id="s", scan_number=12, scan_name="line_scan")
    state.user_metadata = {"scan_name": "My Scan"}
    short, medium, long = pill_labels(state)
    assert long.startswith("#12 My Scan")


def test_pill_stripes_stop_while_hidden_or_minimized(item, qtbot):
    item.show()
    qtbot.waitExposed(item)
    timer = item.pill._stripe_timer
    item.tracker.on_scan_status(*status())
    item.tracker.on_scan_hook(*hook("stage", 1.0))
    assert item.pill.mode == "busy"
    assert timer.isActive() and timer.interval() == 100

    item.hide()
    assert not timer.isActive()
    item.tracker.on_scan_hook(*hook("pre_scan", 2.0))  # an update while hidden
    assert not timer.isActive()
    item.show()
    qtbot.waitExposed(item)
    assert timer.isActive()

    item.showMinimized()
    qtbot.waitUntil(lambda: not timer.isActive())
    item.tracker.on_scan_hook(*hook("open_scan", 3.0))
    assert not timer.isActive()
    item.showNormal()
    qtbot.waitUntil(timer.isActive)


@pytest.mark.parametrize(
    "reason, outlined",
    [
        ("ActiveWindowFocusReason", False),  # the window is activated or the app switched back
        ("OtherFocusReason", False),
        ("MouseFocusReason", False),
        ("TabFocusReason", True),  # the user tabbed to the pill
        ("BacktabFocusReason", True),
    ],
)
def test_focus_never_opens_the_card_and_tab_outlines(item, qtbot, monkeypatch, reason, outlined):
    from qtpy.QtCore import QEvent, QPoint, Qt
    from qtpy.QtGui import QFocusEvent
    from qtpy.QtWidgets import QApplication

    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    QApplication.sendEvent(
        item.pill, QFocusEvent(QEvent.Type.FocusIn, getattr(Qt.FocusReason, reason))
    )
    assert not item.card.isVisible()
    assert item.pill.keyboard_focus is outlined
    assert item.pill.outlined is outlined


def test_card_has_no_native_window_shadow(item):
    """Only the card's own rounded shadow; macOS would add a square one for the whole window."""
    from qtpy.QtCore import Qt

    flags = item.card.windowFlags()
    assert flags & Qt.WindowType.NoDropShadowWindowHint
    assert flags & Qt.WindowType.FramelessWindowHint
    assert item.card.card.graphicsEffect() is not None


def test_card_stays_while_its_stop_menu_is_open(item, qtbot, monkeypatch):
    """The emergency-stop path: the Stop's menu usually reaches past the card's right edge."""
    from qtpy.QtCore import QPoint

    from .test_status_pill import _press_in_window

    item.tracker.on_scan_status(*status())
    _show_settled(item, qtbot)
    item.open_card()
    stop = item.card.progress.stop_button
    card = item.card.card
    stop.menu.popup(card.mapToGlobal(QPoint(card.width() - 30, card.height() - 40)))
    qtbot.waitUntil(stop.menu.isVisible)
    _cursor_at(monkeypatch, stop.menu.geometry().bottomRight() - QPoint(5, 5))
    qtbot.wait(item.GRACE_MS + 300)
    assert item.card.isVisible() and stop.menu.isVisible()
    elsewhere = item.mapToGlobal(QPoint(item.width() - 2, item.height() // 2))
    _press_in_window(item, elsewhere)
    assert item.card.isVisible()  # a popup of the card is open

    stop.menu.close()
    qtbot.waitUntil(lambda: not stop.menu.isVisible())
    assert item.card.isVisible()  # closing the menu does not close the card
    _press_in_window(item, elsewhere)
    assert not item.card.isVisible()


def _stored_queue_status(waiting: int):
    infos = [{"status": "RUNNING"}] + [{"status": "PENDING"}] * waiting
    return mock.MagicMock(content={"queue": {"primary": {"info": infos}}}, metadata={})


def _blocking_get(msg):
    """A connector.get that waits for release in the thread pool, recording its thread."""
    import threading

    started, release, threads = threading.Event(), threading.Event(), []

    def get(endpoint, *args, **kwargs):
        if endpoint != MessageEndpoints.scan_queue_status():
            return None  # the card's progress bar reads the scan status itself
        threads.append(threading.get_ident())
        started.set()
        release.wait(5)
        return msg

    return get, started, release, threads


def _make_item(qtbot, mocked_client, settings_path):
    return create_widget(
        qtbot,
        ScanStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )


def test_stored_queue_status_is_read_off_the_gui_thread(qtbot, mocked_client, settings_path):
    import threading

    get, started, release, threads = _blocking_get(_stored_queue_status(2))
    with mock.patch.object(mocked_client.connector, "get", side_effect=get):
        widget = _make_item(qtbot, mocked_client, settings_path)
        assert started.wait(5)  # the pill is built while the read still blocks
        assert widget.waiting_chip.isHidden()
        release.set()
        qtbot.waitUntil(lambda: not widget.waiting_chip.isHidden(), timeout=2000)
    assert widget.waiting_chip.text() == "2 waiting"
    assert threads and threading.main_thread().ident not in threads


def test_a_live_queue_status_wins_over_the_stored_one(qtbot, mocked_client, settings_path):
    from qtpy.QtCore import QThreadPool

    get, started, release, _threads = _blocking_get(_stored_queue_status(3))
    with mock.patch.object(mocked_client.connector, "get", side_effect=get):
        widget = _make_item(qtbot, mocked_client, settings_path)
        assert started.wait(5)
        widget.on_queue_status({"queue": {"primary": {"info": [{"status": "PENDING"}]}}}, {})
        release.set()
        qtbot.waitUntil(lambda: QThreadPool.globalInstance().activeThreadCount() == 0, timeout=5000)
        qtbot.wait(50)  # the stored status arrives after the live one and is dropped
    assert widget.waiting_chip.text() == "1 waiting"


def test_closing_while_the_queue_status_is_read_is_safe(qtbot, mocked_client, settings_path):
    from qtpy.QtCore import QThreadPool

    get, started, release, _threads = _blocking_get(_stored_queue_status(2))
    with mock.patch.object(mocked_client.connector, "get", side_effect=get):
        widget = _make_item(qtbot, mocked_client, settings_path)
        assert started.wait(5)
        widget.close()  # cleanup while the read is still running
        release.set()
        qtbot.waitUntil(lambda: QThreadPool.globalInstance().activeThreadCount() == 0, timeout=5000)
        qtbot.wait(50)  # the queued result is delivered and dropped
    assert widget._waiting == 0
