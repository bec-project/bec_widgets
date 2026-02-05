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

    toast.apply_theme("dark")
    assert DARK_PALETTE["title"] in toast._title_lbl.styleSheet()


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
