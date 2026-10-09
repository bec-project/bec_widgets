# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access
import threading
import time
import traceback
from unittest import mock

import pytest
from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QWidget

from bec_widgets.utils.error_popups import ErrorPopupUtility, SafeSlot, WarningPopupUtility
from bec_widgets.widgets.containers.main_window.addons.notification_center import (
    notification_ux_common as common,
)
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_qml import (
    NotificationHostQML,
)
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_qwidget import (
    NotificationHostQWidget,
)
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
    NotificationHub,
    Severity,
    ToastQueue,
)

TRACE = """Traceback (most recent call last):
  File "x.py", line 1, in move
    raise ValueError("Target 12.5 is outside the limits.")
ValueError: Target 12.5 is outside the limits."""


@pytest.fixture
def hub():
    yield NotificationHub.instance()
    NotificationHub.reset_instance()


@pytest.fixture
def window(qtbot):
    win = QMainWindow()
    win.setCentralWidget(QLabel("content"))
    win.statusBar().addWidget(QLabel("status"))
    win.resize(1000, 700)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    yield win


@pytest.fixture(params=["qwidget", "qml"])
def host(request, window, hub, qtbot):
    cls = NotificationHostQWidget if request.param == "qwidget" else NotificationHostQML
    attached = cls(window)
    yield attached
    attached.cleanup()


def flush(qtbot, host):
    """Run the coalesced view update."""
    host.sync_now()
    qtbot.wait(10)


def toast_count(host) -> int:
    if isinstance(host, NotificationHostQML):
        return host.backend.toasts.rowCount()
    return len(host.toasts.cards)


def row_count(host) -> int:
    if isinstance(host, NotificationHostQML):
        return host.backend.rows.rowCount()
    return host.drawer.model.rowCount()


# ---------------------------------------------------------------------------- pure helpers


@pytest.mark.parametrize(
    "value, expected",
    [
        ("info", Severity.INFO),
        ("minor", Severity.ERROR),
        ("major", Severity.CRITICAL),
        (0, Severity.WARNING),
        (1, Severity.ERROR),
        (2, Severity.CRITICAL),
        (Severity.SUCCESS, Severity.SUCCESS),
        ("nonsense", Severity.WARNING),
        (None, Severity.WARNING),
    ],
)
def test_to_severity(value, expected):
    assert common.to_severity(value) == expected


def test_split_traceback():
    assert common.split_traceback(TRACE) == ("ValueError", "Target 12.5 is outside the limits.")
    assert common.split_traceback("") == ("Error", "")
    assert common.split_traceback("something odd happened") == ("Error", "something odd happened")
    assert common.split_traceback("ophyd.utils.errors.WaitTimeoutError: late")[0] == (
        "WaitTimeoutError"
    )


def test_relative_time():
    now = time.time()
    assert common.relative_time(now - 5, now) == "just now"
    assert common.relative_time(now - 300, now) == "5 min ago"


# ---------------------------------------------------------------------------- hub


def test_hub_is_singleton(hub):
    assert NotificationHub.instance() is hub


def test_notify_adds_entry_newest_first(hub):
    first = hub.notify("A", "one")
    second = hub.notify("B", "two", "warning", source="x")
    assert [e.id for e in hub.entries] == [second, first]
    assert hub.get(second).severity == Severity.WARNING
    assert hub.unread_count() == 2


def test_repeated_notifications_fold_into_one_entry(hub):
    first = hub.notify("Readback failed", "timeout", "error", source="samx")
    hub.notify("Other", "x")
    again = hub.notify("Readback failed", "timeout", "error", source="samx")
    assert again == first
    assert len(hub.entries) == 2
    assert hub.entries[0].id == first  # moved to the top
    assert hub.get(first).count == 2
    # a different source is a different problem
    hub.notify("Readback failed", "timeout", "error", source="samy")
    assert len(hub.entries) == 3


def test_same_entry_id_is_posted_once(hub):
    hub.notify("A", entry_id="fixed")
    hub.notify("A changed", entry_id="fixed")
    assert len(hub.entries) == 1


def test_history_is_trimmed_but_keeps_open_critical(hub, monkeypatch):
    monkeypatch.setattr(NotificationHub, "MAX_ENTRIES", 5)
    critical = hub.notify("Beam lost", severity="critical")
    for i in range(10):
        hub.notify(f"info {i}")
    assert len(hub.entries) == 5
    assert hub.get(critical) is not None


def test_clear_keeps_unacknowledged_critical(hub):
    critical = hub.notify("Beam lost", severity="critical")
    hub.notify("hello")
    hub.clear()
    assert [e.id for e in hub.entries] == [critical]
    hub.acknowledge(critical)
    hub.clear()
    assert hub.entries == []


def test_acknowledge_and_top_severity(hub):
    hub.notify("w", severity="warning")
    critical = hub.notify("c", severity="critical")
    assert hub.top_unread_severity() == Severity.CRITICAL
    hub.mark_read()
    # still open: a critical error needs an acknowledgement, reading it is not enough
    assert hub.top_unread_severity() == Severity.CRITICAL
    hub.acknowledge(critical)
    assert hub.top_unread_severity() is None


def test_post_alarm_parses_error_info(hub):
    entry_id = hub.post_alarm(
        {
            "severity": 2,
            "alarm_type": "DeviceTimeoutError",
            "info": {
                "id": "abc",
                "error_message": TRACE,
                "compact_error_message": "Device eiger did not respond.",
                "exception_type": "DeviceTimeoutError",
                "device": "eiger",
            },
        },
        {"scan_number": 12, "scan_id": "sid"},
    )
    entry = hub.get(entry_id)
    assert entry_id == "abc"
    assert entry.severity == Severity.CRITICAL
    assert entry.title == "DeviceTimeoutError"
    assert entry.body == "Device eiger did not respond."
    assert entry.source == "Device eiger"
    assert entry.scan_number == 12
    assert "sid" in entry.details and "Traceback" in entry.details
    # the same alarm arriving again is ignored
    assert hub.post_alarm({"severity": 2, "info": {"id": "abc", "error_message": "x"}}) is None


def test_post_alarm_without_info(hub):
    entry_id = hub.post_alarm({"severity": 0, "alarm_type": "Warning", "msg": "low beam"})
    entry = hub.get(entry_id)
    assert entry.severity == Severity.WARNING
    assert entry.body == "low beam"
    assert entry.details == ""


def test_report_exception(hub):
    entry = hub.get(hub.report_exception("Method error", TRACE, source="Box.move"))
    assert entry.title == "ValueError"
    assert entry.body == "Target 12.5 is outside the limits."
    assert entry.source == "Box.move"
    assert entry.severity == Severity.ERROR
    assert "Traceback" in entry.details
    report = entry.copy_text()
    assert "[Error] ValueError" in report and "Source: Box.move" in report and TRACE in report


def test_notify_from_worker_thread_is_queued(hub, qtbot):
    thread = threading.Thread(target=lambda: hub.notify("from thread"))
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: len(hub.entries) == 1, timeout=1000)
    assert hub.entries[0].title == "from thread"


def test_bec_alarm_subscription(hub, bec_dispatcher):
    with mock.patch.object(bec_dispatcher, "connect_slot") as connect:
        hub.connect_bec(bec_dispatcher)
        hub.connect_bec(bec_dispatcher)  # only once
    assert connect.call_count == 2
    with mock.patch.object(bec_dispatcher, "disconnect_slot") as disconnect:
        hub.disconnect_bec()
    assert disconnect.call_count == 2


def test_scan_start_signal(hub, qtbot):
    with qtbot.waitSignal(hub.scan_started, timeout=500):
        hub._on_scan_status({"status": "open"}, {})
    with qtbot.assertNotEmitted(hub.scan_started):
        hub._on_scan_status({"status": "closed"}, {})


# ---------------------------------------------------------------------------- toast queue


@pytest.fixture
def queue(hub):
    toast_queue = ToastQueue(hub)
    yield toast_queue
    toast_queue.cleanup()
    toast_queue.deleteLater()


def test_queue_limits_visible_toasts(hub, queue):
    ids = [hub.notify(f"n{i}", severity="error") for i in range(5)]
    assert queue.visible_ids == ids[-3:]
    assert queue.overflow == 2


def test_queue_critical_evicts_oldest_transient(hub, queue):
    critical = [hub.notify(f"c{i}", severity="critical") for i in range(2)]
    info = hub.notify("info")
    new_critical = hub.notify("c-new", severity="critical")
    assert info not in queue.visible_ids
    assert queue.visible_ids == critical + [new_critical]
    # all slots held by critical errors: a transient toast only counts as overflow
    hub.notify("more info")
    assert queue.visible_ids == critical + [new_critical]


def test_queue_auto_dismiss_and_pause(hub, queue, qtbot, monkeypatch):
    monkeypatch.setitem(common.SEVERITY_META[Severity.INFO], "lifetime", 80)
    entry_id = hub.notify("short")
    queue.set_paused(True)
    qtbot.wait(150)
    assert entry_id in queue.visible_ids
    queue.set_paused(False)
    qtbot.waitUntil(lambda: entry_id not in queue.visible_ids, timeout=2000)
    # the entry stays in the history
    assert hub.get(entry_id) is not None


def test_queue_critical_stays_until_acknowledged(hub, queue):
    critical = hub.notify("c", severity="critical")
    assert critical not in queue._timers
    hub.acknowledge(critical)
    assert critical not in queue.visible_ids


def test_queue_scan_start_keeps_critical(hub, queue):
    hub.notify("info")
    critical = hub.notify("c", severity="critical")
    hub.scan_started.emit()
    assert queue.visible_ids == [critical]


def test_queue_repeat_moves_toast_to_newest(hub, queue):
    first = hub.notify("a", "x", "error")
    hub.notify("b", "y", "error")
    hub.notify("a", "x", "error")
    assert queue.visible_ids[-1] == first
    assert len(queue.visible_ids) == 2


def test_queue_suspended_shows_nothing(hub, queue):
    hub.notify("a")
    queue.set_suspended(True)
    assert queue.visible_ids == []
    hub.notify("b")
    assert queue.visible_ids == []


# ---------------------------------------------------------------------------- hosts (both views)


def test_host_shows_toasts_and_bell(host, hub, qtbot):
    hub.notify("Hello", "world")
    hub.notify("Broken", "it failed", "critical")
    flush(qtbot, host)
    assert toast_count(host) == 2
    assert host.toasts.isVisible()
    state = host.view_state()
    assert state["unread"] == 2
    assert state["openCriticals"] == 1
    assert "critical" in state["bellTip"]
    assert host.toasts.geometry().right() <= host.window.width()
    assert host.toasts.geometry().bottom() < host.window.statusBar().geometry().top()


def test_host_drawer_lists_filters_and_details(host, hub, qtbot):
    hub.notify("Info one", "a")
    error = hub.report_exception("Method error", TRACE, source="Box.move")
    hub.notify("Warn", "low beam", "warning")
    host.set_drawer_open(True)
    flush(qtbot, host)
    assert host.drawer.isVisible()
    assert toast_count(host) == 0  # toasts give way to the drawer
    assert hub.unread_count() == 0  # opening the drawer reads everything
    assert row_count(host) == 3
    host.set_filter("errors")
    flush(qtbot, host)
    assert row_count(host) == 1
    host.set_filter("all")
    host.set_search("low beam")
    flush(qtbot, host)
    assert row_count(host) == 1
    host.set_search("")
    host.select(error)
    flush(qtbot, host)
    assert host.view_state()["selected"]["entryId"] == error
    assert host.copy_details(error)
    assert "ValueError" in QApplication.clipboard().text()
    host.remove(error)
    flush(qtbot, host)
    assert hub.get(error) is None
    assert host.view_state()["selected"] is None
    host.set_drawer_open(False)
    flush(qtbot, host)
    assert not host.drawer.isVisible()


def test_host_critical_pinned_on_top(host, hub, qtbot):
    critical = hub.notify("Beam lost", severity="critical")
    hub.notify("newer info")
    host.set_drawer_open(True)
    flush(qtbot, host)
    assert host.view_state()["rows"][0]["entryId"] == critical
    host.acknowledge(critical)
    flush(qtbot, host)
    assert host.view_state()["rows"][0]["entryId"] != critical


def test_host_open_details_from_toast(host, hub, qtbot):
    entry_id = hub.notify("Broken", "x", "error", details="trace")
    flush(qtbot, host)
    host.open_details(entry_id)
    flush(qtbot, host)
    assert host.drawer_open
    assert host.view_state()["selected"]["details"] == "trace"


def test_host_dismiss_critical_toast_acknowledges(host, hub, qtbot):
    critical = hub.notify("Beam lost", severity="critical")
    flush(qtbot, host)
    host.dismiss_toast(critical)
    flush(qtbot, host)
    assert hub.get(critical).acknowledged
    assert toast_count(host) == 0


def test_host_follows_theme(host, hub, qtbot):
    from bec_widgets.utils.colors import apply_theme

    hub.notify("x", severity="warning")
    flush(qtbot, host)
    apply_theme("dark")
    flush(qtbot, host)
    apply_theme("light")
    flush(qtbot, host)
    assert toast_count(host) == 1


def test_host_cleanup_unregisters(window, hub):
    attached = NotificationHostQWidget(window)
    assert hub.has_hosts
    attached.cleanup()
    attached.cleanup()  # idempotent
    assert not hub.has_hosts


def test_qml_views_load_without_errors(window, hub):
    attached = NotificationHostQML(window)
    try:
        for view in (attached.toasts, attached.drawer, attached.bell):
            assert view.errors() == []
            assert view.rootObject() is not None
    finally:
        attached.cleanup()


def test_qwidget_toast_buttons(window, hub, qtbot):
    attached = NotificationHostQWidget(window)
    try:
        hub.notify("Broken", "x", "critical", details="trace")
        flush(qtbot, attached)
        card = attached.toasts.cards[0]
        assert card.ack_btn.isVisibleTo(card)
        assert not card.close_btn.isVisibleTo(card)
        card.details_btn.click()
        flush(qtbot, attached)
        assert attached.drawer_open
        attached.drawer.details.ack_btn.click()
        flush(qtbot, attached)
        assert hub.entries[0].acknowledged
    finally:
        attached.cleanup()


# ---------------------------------------------------------------------------- error routing


class _Failing(QWidget):
    @SafeSlot(popup_error=True)
    def fail(self):
        raise ValueError("Target 12.5 is outside the limits.")


def test_safeslot_error_becomes_notification_when_host_attached(window, hub, qtbot):
    attached = NotificationHostQWidget(window)
    widget = _Failing()
    qtbot.addWidget(widget)
    try:
        with (
            mock.patch.object(QMessageBox, "exec_") as exec_,
            qtbot.assertNotEmitted(ErrorPopupUtility().error_occurred),
        ):
            widget.fail()
        exec_.assert_not_called()
        entry = hub.entries[0]
        assert entry.title == "ValueError"
        assert entry.source == "_Failing.fail"
        assert "Traceback" in entry.details
    finally:
        attached.cleanup()


def test_safeslot_error_uses_dialog_without_host(hub, qtbot):
    widget = _Failing()
    qtbot.addWidget(widget)
    with qtbot.waitSignal(ErrorPopupUtility().error_occurred, timeout=1000):
        widget.fail()
    assert hub.entries == []


def test_warning_popup_becomes_notification(window, hub):
    attached = NotificationHostQWidget(window)
    try:
        with mock.patch.object(QMessageBox, "exec_") as exec_:
            WarningPopupUtility().show_warning("Export", "No data to export.", "details", window)
        exec_.assert_not_called()
        entry = hub.entries[0]
        assert (entry.title, entry.body, entry.severity) == (
            "Export",
            "No data to export.",
            Severity.WARNING,
        )
        assert entry.details == "details"
    finally:
        attached.cleanup()


def test_application_error_routed(window, hub):
    attached = NotificationHostQWidget(window)
    try:
        util = ErrorPopupUtility()
        util.enable_global_error_popups(True)
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            util.custom_exception_hook(type(exc), exc, exc.__traceback__)
        assert hub.entries[0].title == "RuntimeError"
        assert hub.entries[0].source == "Application Error"
    finally:
        util.enable_global_error_popups(False)
        attached.cleanup()


# ---------------------------------------------------------------------------- main window opt-in


@pytest.mark.parametrize("variant", ["qwidget", "qml"])
def test_main_window_opt_in(qtbot, monkeypatch, variant, mocked_client):
    from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

    monkeypatch.setenv("BEC_NOTIFICATION_UI", variant)
    win = BECMainWindow(client=mocked_client)
    qtbot.addWidget(win)
    try:
        assert win.notification_centre is None
        assert win.notifications is not None
        assert win.notification_indicator is win.notifications.bell
        win.notifications.hub.notify("hello")
        win.notifications.sync_now()
        assert win.notifications.view_state()["unread"] == 1
    finally:
        win.close()


def test_main_window_default_is_legacy(qtbot, mocked_client, monkeypatch):
    from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

    monkeypatch.delenv("BEC_NOTIFICATION_UI", raising=False)
    win = BECMainWindow(client=mocked_client)
    qtbot.addWidget(win)
    try:
        assert win.notification_centre is not None
        assert win.notifications is None
    finally:
        win.close()


def test_traceback_helper_matches_python():
    try:
        raise KeyError("missing")
    except KeyError:
        text = traceback.format_exc()
    assert common.split_traceback(text) == ("KeyError", "'missing'")
