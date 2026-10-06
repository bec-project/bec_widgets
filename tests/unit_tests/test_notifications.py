import pytest
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_banner import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    SEVERITY,
    BECNotificationBroker,
    NotificationCentre,
    NotificationIndicator,
    NotificationToast,
    SeverityKind,
)

from .client_mocks import mocked_client


@pytest.fixture
def toast(qtbot):
    """Return a NotificationToast with a very short lifetime (50 ms) for fast tests."""
    t = NotificationToast(
        title="Test Title", body="Test Body", kind=SeverityKind.WARNING, lifetime_ms=50  # 0.05 s
    )
    qtbot.addWidget(t)
    qtbot.waitExposed(t)
    return t


def test_initial_state(toast):
    """Constructor should correctly propagate title / body / kind."""
    assert toast.title == "Test Title"
    assert toast.body == "Test Body"
    assert toast.kind == SeverityKind.WARNING
    # progress bar height fixed at 4 px
    assert toast.progress.maximumHeight() == 4


def test_apply_theme_updates_colours(qtbot, toast):
    """apply_theme("light") should inject LIGHT palette colours into stylesheets."""
    toast.apply_theme("light")
    assert LIGHT_PALETTE["title"] in toast._title_lbl.styleSheet()
    assert "border: 1px solid" in toast.trace_view.styleSheet()
    assert "border:none" not in toast.trace_view.styleSheet()

    toast.apply_theme("dark")
    assert DARK_PALETTE["title"] in toast._title_lbl.styleSheet()


def test_toast_updates_from_qapp_theme_changed_signal(qtbot, toast):
    app = QtWidgets.QApplication.instance()
    assert hasattr(app, "theme")

    app.theme.theme_changed.emit("light")
    qtbot.wait(10)

    assert LIGHT_PALETTE["title"] in toast._title_lbl.styleSheet()


def test_expired_signal(qtbot, toast):
    """Toast must emit expired once its lifetime finishes."""
    with qtbot.waitSignal(toast.expired, timeout=1000):
        pass
    assert toast._expired


def test_closed_signal(qtbot, toast):
    """Calling close() must emit closed."""
    with qtbot.waitSignal(toast.closed, timeout=1000):
        toast.close()


def test_property_setters_update_ui(qtbot, toast):
    """Changing properties through setters should update both state and label text."""

    # title
    toast.title = "New Title"
    assert toast.title == "New Title"
    assert toast._title_lbl.text() == "New Title"

    # body
    toast.body = "New Body"
    assert toast.body == "New Body"
    assert toast._body_lbl.text() == "New Body"

    # kind
    toast.kind = SeverityKind.MINOR
    assert toast.kind == SeverityKind.MINOR
    expected_color = SEVERITY["minor"]["color"]
    assert toast._accent_color.name() == QtGui.QColor(expected_color).name()

    # traceback
    new_tb = "Traceback: divide by zero"
    toast.traceback = new_tb
    assert toast.traceback == new_tb
    assert toast.trace_view.toPlainText() == new_tb


def _make_enter_event(widget):
    """Utility: synthetic QEnterEvent centred on *widget*."""
    centre = widget.rect().center()
    local = QtCore.QPointF(centre)
    scene = QtCore.QPointF(widget.mapTo(widget.window(), centre))
    global_ = QtCore.QPointF(widget.mapToGlobal(centre))
    return QtGui.QEnterEvent(local, scene, global_)


def test_time_label_toggle_absolute(qtbot, toast):
    """Hovering time-label switches between relative and absolute timestamp."""
    rel_text = toast.time_lbl.text()

    # Enter
    QtWidgets.QApplication.sendEvent(toast.time_lbl, _make_enter_event(toast.time_lbl))
    qtbot.wait(100)
    abs_text = toast.time_lbl.text()
    assert abs_text != rel_text and "-" in abs_text and ":" in abs_text

    # Leave
    QtWidgets.QApplication.sendEvent(toast.time_lbl, QtCore.QEvent(QtCore.QEvent.Leave))
    qtbot.wait(100)
    assert toast.time_lbl.text() != abs_text


def test_hover_pauses_and_resumes_expiry(qtbot):
    """Countdown must pause on hover and resume on leave."""
    t = NotificationToast(title="Hover", body="x", kind=SeverityKind.INFO, lifetime_ms=200)
    qtbot.addWidget(t)
    qtbot.waitExposed(t)

    qtbot.wait(50)  # allow animation to begin
    # Pause
    QtWidgets.QApplication.sendEvent(t, _make_enter_event(t))
    qtbot.wait(250)  # longer than lifetime, but hover keeps it alive
    assert not t._expired

    # Resume
    QtWidgets.QApplication.sendEvent(t, QtCore.QEvent(QtCore.QEvent.Leave))
    with qtbot.waitSignal(t.expired, timeout=500):
        pass
    assert t._expired


def test_toast_paint_event(qtbot):
    """
    Grabbing the widget as a pixmap forces paintEvent to execute.
    The test passes if no exceptions occur and the resulting pixmap is valid.
    """
    t = NotificationToast(title="Paint", body="Check", kind=SeverityKind.INFO, lifetime_ms=0)
    qtbot.addWidget(t)
    t.resize(420, 160)
    t.show()
    qtbot.waitExposed(t)

    pix = t.grab()
    assert not pix.isNull()


# ------------------------------------------------------------------------
# NotificationCentre tests
# ------------------------------------------------------------------------


@pytest.fixture
def centre(qtbot, mocked_client):
    """NotificationCentre embedded in a live parent widget kept alive for the test."""
    parent = QtWidgets.QWidget()
    parent.resize(600, 400)

    ctr = NotificationCentre(parent=parent, fixed_width=300, margin=8)
    broker = BECNotificationBroker(client=mocked_client)

    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(ctr)

    # Keep a Python reference so GC doesn't drop the parent (and cascade‑delete centre)
    ctr._test_parent_ref = parent  # type: ignore[attr-defined]

    qtbot.addWidget(parent)
    qtbot.addWidget(ctr)
    parent.show()
    qtbot.waitExposed(parent)
    yield ctr
    broker.reset_singleton()


def _post(ctr: NotificationCentre, kind=SeverityKind.INFO, title="T", body="B"):
    """Convenience wrapper that posts a toast and returns it."""
    return ctr.add_notification(title=title, body=body, kind=kind, lifetime_ms=0)


# ------------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------------


def test_add_notification_emits_signal(qtbot, centre):
    """Adding a toast emits toast_added and makes centre visible."""
    with qtbot.waitSignal(centre.toast_added, timeout=500) as sig:
        toast = _post(centre, SeverityKind.INFO)

    assert toast in centre.toasts
    assert sig.args == [SeverityKind.INFO.value]


def test_counts_updated(qtbot, centre):
    """counts_updated reflects current per-kind counts."""
    seen = []

    centre.counts_updated.connect(lambda d: seen.append(d.copy()))
    _post(centre, SeverityKind.INFO)
    _post(centre, SeverityKind.WARNING)
    qtbot.wait(100)

    assert seen[-1][SeverityKind.INFO] == 1
    assert seen[-1][SeverityKind.WARNING] == 1

    centre.clear_all()
    qtbot.wait(100)
    assert seen[-1][SeverityKind.INFO] == 0
    assert seen[-1][SeverityKind.WARNING] == 0


def test_filtering_hides_unrelated_toasts(centre):
    info = _post(centre, SeverityKind.INFO)
    warn = _post(centre, SeverityKind.WARNING)

    centre.apply_filter({SeverityKind.INFO})
    assert info.isVisible()
    assert not warn.isVisible()

    centre.apply_filter(None)
    assert warn.isVisible()


def test_hide_show_all(qtbot, centre):
    _post(centre, SeverityKind.MINOR)

    centre.hide_all()
    assert not centre.isVisible()

    centre.show_all()
    assert centre.isVisible()
    assert all(t.isVisible() for t in centre.toasts)


def test_clear_all(qtbot, centre):
    _post(centre, SeverityKind.INFO)
    _post(centre, SeverityKind.WARNING)

    # expect two toast_removed emissions
    for _ in range(2):
        qtbot.waitSignal(centre.toast_removed, timeout=500, raising=False)

    centre.clear_all()
    assert not centre.toasts
    assert not centre.isVisible()


def test_theme_propagation(qtbot, centre):
    toast = _post(centre, SeverityKind.INFO)
    centre.apply_theme("light")
    assert LIGHT_PALETTE["title"] in toast._title_lbl.styleSheet()


def test_centre_updates_from_qapp_theme_changed_signal(qtbot, centre):
    toast = _post(centre, SeverityKind.INFO)
    centre.apply_theme("dark")

    app = QtWidgets.QApplication.instance()
    assert hasattr(app, "theme")

    app.theme.theme_changed.emit("light")
    qtbot.wait(10)

    assert centre._theme == "light"
    assert LIGHT_PALETTE["title"] in toast._title_lbl.styleSheet()


# ------------------------------------------------------------------------
# NotificationIndicator tests
# ------------------------------------------------------------------------


@pytest.fixture
def indicator(qtbot, centre):
    """Indicator wired to the same centre used in centre fixture."""
    ind = NotificationIndicator()
    qtbot.addWidget(ind)

    # wire signals
    centre.counts_updated.connect(ind.update_counts)
    ind.filter_changed.connect(centre.apply_filter)
    ind.show_all_requested.connect(centre.show_all)
    ind.hide_all_requested.connect(centre.hide_all)

    return ind


def _emit_counts(centre: NotificationCentre, info=0, warn=0, minor=0, major=0):
    """Helper to create dummy toasts and update counts."""
    for _ in range(info):
        _post(centre, SeverityKind.INFO)
    for _ in range(warn):
        _post(centre, SeverityKind.WARNING)
    for _ in range(minor):
        _post(centre, SeverityKind.MINOR)
    for _ in range(major):
        _post(centre, SeverityKind.MAJOR)


def test_indicator_updates_visibility(qtbot, centre, indicator):
    """Indicator shows/hides buttons based on counts."""
    _emit_counts(centre, info=1)
    qtbot.wait(50)

    # "info" button visible, others hidden
    assert indicator._btn[SeverityKind.INFO].isVisible()
    assert not indicator._btn[SeverityKind.WARNING].isVisible()

    # add warning toast → warning button appears
    _emit_counts(centre, warn=1)
    qtbot.wait(50)
    assert indicator._btn[SeverityKind.WARNING].isVisible()

    # clear all → indicator hides itself
    centre.clear_all()
    qtbot.wait(50)
    assert not indicator.isVisible()


def test_indicator_filter_buttons(qtbot, centre, indicator):
    """Toggling buttons emits appropriate filter signals."""
    # add two kinds so indicator is visible
    _emit_counts(centre, info=1, warn=1)
    qtbot.wait(200)

    # click INFO button
    with qtbot.waitSignal(indicator.filter_changed, timeout=500) as sig:
        qtbot.mouseClick(indicator._btn[SeverityKind.INFO], QtCore.Qt.LeftButton)
    assert sig.args[0] == {SeverityKind.INFO}


def test_broker_posts_notification(qtbot, centre, mocked_client):
    """post_notification should create a toast in the centre with correct data."""
    broker = BECNotificationBroker(parent=None, client=mocked_client, centre=centre)
    broker._err_util = ErrorPopupUtility()

    msg = {
        "alarm_type": "ValueError",
        "msg": "test alarm",
        "severity": 2,  # MAJOR
        "source": {"device": "samx", "source": "async_file_writer"},
    }

    broker.post_notification(msg, meta={})
    qtbot.wait(200)  # allow toast to be posted

    # One toast should now exist
    assert len(centre.toasts) == 1
    toast = centre.toasts[0]

    assert toast.title == "ValueError"
    assert "Error occurred. See details." in toast.body
    assert toast.kind == SeverityKind.MAJOR
    assert toast._lifetime == 0


@pytest.fixture
def broker(mocked_client):
    """The broker singleton, always torn down after the test (even if an assert fails)."""
    brk = BECNotificationBroker(client=mocked_client)
    brk._err_util = ErrorPopupUtility()
    yield brk
    BECNotificationBroker.reset_singleton()


def _make_centre(qtbot) -> NotificationCentre:
    """A NotificationCentre in its own parent widget, as a newly opened window would have."""
    parent = QtWidgets.QWidget()
    parent.resize(600, 400)
    ctr = NotificationCentre(parent=parent, fixed_width=300, margin=8)
    layout = QtWidgets.QVBoxLayout(parent)
    layout.addWidget(ctr)
    # qtbot only keeps a weak reference; hold the parent so GC doesn't delete the centre
    ctr._test_parent_ref = parent  # type: ignore[attr-defined]
    qtbot.addWidget(parent)
    return ctr


def test_broker_survives_parent_window_destruction(qtbot, mocked_client):
    """The broker is an app-wide singleton; closing the window that first created it must
    not destroy it, or every later window gets a dead wrapper and notifications stop."""
    import shiboken6
    from qtpy.QtCore import QEvent, QEventLoop, Qt
    from qtpy.QtWidgets import QApplication, QMainWindow

    w1 = QMainWindow()
    w1.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    qtbot.addWidget(w1)
    try:
        b1 = BECNotificationBroker(parent=w1, client=mocked_client)
        assert b1.parent() is QApplication.instance()

        w1.close()
        qapp = QApplication.instance()
        qapp.sendPostedEvents(None, QEvent.DeferredDelete)
        qapp.processEvents(QEventLoop.AllEvents)

        assert shiboken6.isValid(b1)  # broker outlived the window
        b2 = BECNotificationBroker(parent=None, client=mocked_client)
        assert b2 is b1 and shiboken6.isValid(b2)
        b2.notification_closed.emit("x")  # must not raise RuntimeError
    finally:
        BECNotificationBroker.reset_singleton()


def test_broker_revives_after_hard_destroy(qtbot, mocked_client):
    """If the broker's C++ object is destroyed anyway, the next construction rebuilds a
    fresh, re-subscribed instance instead of returning the dead wrapper."""
    import shiboken6

    try:
        b1 = BECNotificationBroker(parent=None, client=mocked_client)
        shiboken6.delete(b1)
        assert not shiboken6.isValid(b1)

        b2 = BECNotificationBroker(parent=None, client=mocked_client)
        assert b2 is not b1 and shiboken6.isValid(b2)
        b2.notification_closed.emit("y")  # re-subscribed, no RuntimeError
    finally:
        BECNotificationBroker.reset_singleton()


def test_broker_is_not_registered_for_rpc(broker):
    """The broker is internal plumbing: it must stay out of the RPC registry, otherwise the
    launcher reports it as a connection without a top-level window once all windows close."""
    from bec_widgets.utils.rpc_register import RPCRegister

    assert broker not in RPCRegister().list_all_connections().values()


def test_expired_notification_is_replayed_into_new_centre(qtbot, broker):
    """Expiry only soft-hides a toast (it stays in the centre's history), so a centre opened
    later must replay it too and show the same history as the centres already open."""
    ctr_a = _make_centre(qtbot)
    qtbot.wait(20)  # let ctr_a's replay singleShot fire on an EMPTY store first

    broker.post_notification({"alarm_type": "W", "msg": "m", "severity": 0}, meta={})
    qtbot.waitUntil(lambda: len(ctr_a.toasts) == 1, timeout=2000)
    nid = ctr_a.toasts[0].notification_id
    ctr_a.toasts[0].expired.emit()  # simulate auto-expiry
    qtbot.wait(10)
    assert len(ctr_a.toasts) == 1  # still in history, only hidden
    assert nid in broker._active_notifications

    ctr_b = _make_centre(qtbot)  # e.g. a window opened after the toast expired
    qtbot.waitUntil(lambda: len(ctr_b.toasts) == 1, timeout=2000)
    assert ctr_b.toasts[0].notification_id == nid
    assert not ctr_b.toasts[0].isVisible()  # replayed as history, not popped up again


def test_closed_notification_is_not_replayed(qtbot, broker):
    """Closing a toast removes it everywhere, including the replay store."""
    ctr_a = _make_centre(qtbot)
    qtbot.wait(20)

    broker.post_notification({"alarm_type": "E", "msg": "m", "severity": 2}, meta={})
    qtbot.waitUntil(lambda: len(ctr_a.toasts) == 1, timeout=2000)
    ctr_a.toasts[0].closed.emit()
    qtbot.wait(10)
    assert broker._active_notifications == {}

    ctr_b = _make_centre(qtbot)
    qtbot.wait(50)
    assert ctr_b.toasts == []


def test_close_after_reset_reaches_all_centres(qtbot, mocked_client):
    """A toast created before reset_singleton() must broadcast its close through the new
    broker; a captured old broker would be deleted and raise 'Signal source has been deleted'."""
    try:
        BECNotificationBroker(client=mocked_client)
        ctr_a = _make_centre(qtbot)
        ctr_b = _make_centre(qtbot)
        qtbot.wait(20)
        for ctr in (ctr_a, ctr_b):
            ctr.add_notification(
                title="t", body="b", kind=SeverityKind.MAJOR, lifetime_ms=0, notification_id="nid"
            )

        BECNotificationBroker.reset_singleton()
        BECNotificationBroker(client=mocked_client)

        ctr_a.toasts[0].closed.emit()
        qtbot.waitUntil(lambda: ctr_a.toasts == [] and ctr_b.toasts == [], timeout=2000)
    finally:
        BECNotificationBroker.reset_singleton()


def test_replay_store_is_bounded(broker, monkeypatch):
    """The replay store keeps only the newest MAX_REPLAY_NOTIFICATIONS entries."""
    monkeypatch.setattr(BECNotificationBroker, "MAX_REPLAY_NOTIFICATIONS", 3)

    for i in range(5):
        broker.post_notification({"alarm_type": f"W{i}", "msg": "m", "severity": 0}, meta={})

    titles = [entry["title"] for entry in broker._active_notifications.values()]
    assert titles == ["W2", "W3", "W4"]


def test_toast_close_after_reset_does_not_recreate_broker(qtbot, mocked_client):
    """Closing a toast after reset_singleton() must not construct a new broker (and new
    dispatcher subscriptions); the toast is still removed from its own centre."""
    try:
        BECNotificationBroker(client=mocked_client)
        ctr = _make_centre(qtbot)
        qtbot.wait(20)
        ctr.add_notification(
            title="t", body="b", kind=SeverityKind.MAJOR, lifetime_ms=0, notification_id="nid"
        )

        BECNotificationBroker.reset_singleton()
        ctr.toasts[0].closed.emit()
        qtbot.waitUntil(lambda: ctr.toasts == [], timeout=2000)
        assert BECNotificationBroker._instance is None
    finally:
        BECNotificationBroker.reset_singleton()


def test_replay_cap_keeps_unacknowledged_major(qtbot, broker, monkeypatch):
    """The cap only evicts non-MAJOR entries: an open MAJOR alarm is still replayed into a
    centre opened after more than MAX_REPLAY_NOTIFICATIONS newer notifications."""
    monkeypatch.setattr(BECNotificationBroker, "MAX_REPLAY_NOTIFICATIONS", 3)

    broker.post_notification({"alarm_type": "MAJOR", "msg": "m", "severity": 2}, meta={})
    for i in range(5):
        broker.post_notification({"alarm_type": f"W{i}", "msg": "m", "severity": 0}, meta={})

    titles = [entry["title"] for entry in broker._active_notifications.values()]
    assert titles == ["MAJOR", "W2", "W3", "W4"]

    ctr = _make_centre(qtbot)
    qtbot.waitUntil(lambda: len(ctr.toasts) == 4, timeout=2000)
    assert [t.kind for t in ctr.toasts].count(SeverityKind.MAJOR) == 1
