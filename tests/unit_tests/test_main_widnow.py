import webbrowser

import pytest
from qtpy.QtWidgets import QFrame

from bec_widgets.widgets.containers.main_window.addons.scroll_label import ScrollLabel
from bec_widgets.widgets.containers.main_window.addons.web_links import BECWebLinksMixin
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture
def bec_main_window(qtbot, mocked_client):
    widget = BECMainWindow(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


#################################################################
# Tests for BECMainWindow Initialization and Functionality
#################################################################


def test_bec_main_window_initialization(bec_main_window):
    assert isinstance(bec_main_window, BECMainWindow)
    assert bec_main_window.windowTitle() == "BEC"
    assert bec_main_window.app is not None
    assert bec_main_window.statusBar() is not None
    assert bec_main_window._app_id_label is not None


def test_bec_main_window_display_client_message(qtbot, bec_main_window):
    """
    Verify that display_client_message updates the client‑info label.
    """
    test_msg = "Client connected successfully"
    bec_main_window.display_client_message({"message": test_msg}, {})
    qtbot.wait(200)
    assert bec_main_window._client_info_label.text() == test_msg


def test_status_bar_has_separator(bec_main_window):
    """Ensure the status bar contains at least one vertical separator."""
    status_bar = bec_main_window.statusBar()
    separators = [w for w in status_bar.findChildren(QFrame) if w.frameShape() == QFrame.VLine]
    assert separators, "Expected at least one QFrame separator in the status bar."


#################################################################
# Tests for BECMainWindow Addons
#################################################################

#################################################################
# Tests for ScrollLabel behaviour


def test_scroll_label_does_not_scroll_when_text_fits(qtbot):
    """Label with short text should not activate scrolling timer."""
    lbl = create_widget(qtbot, ScrollLabel)  # shorten delay for test speed
    qtbot.addWidget(lbl)
    lbl.resize(200, 20)
    lbl.setText("Short text")
    # Process events to allow timer logic to run
    qtbot.wait(200)
    assert not lbl._timer.isActive()
    assert not lbl._delay_timer.isActive()


def test_scroll_label_starts_scrolling(qtbot):
    """Label with long text should start _delay_timer; later _timer becomes active."""
    lbl = create_widget(qtbot, ScrollLabel, delay_ms=100)
    lbl.resize(150, 20)
    long_text = "This is a very long piece of text that should definitely overflow the label width"
    lbl.setText(long_text)
    # Immediately after setText, only delay‑timer should be active
    assert lbl._delay_timer.isActive()
    assert not lbl._timer.isActive()
    # Wait until scrolling timer becomes active
    qtbot.waitUntil(lambda: lbl._timer.isActive(), timeout=2000)
    assert lbl._timer.isActive()


def test_scroll_label_scroll_method(qtbot):
    """Directly exercise _scroll to ensure offset advances and paintEvent is invoked."""
    lbl = create_widget(qtbot, ScrollLabel, step_px=5)  # shorten delay for test speed
    qtbot.addWidget(lbl)
    lbl.resize(120, 20)
    lbl.setText("x" * 200)  # long text to guarantee overflow
    qtbot.wait(200)  # let timers configure themselves

    # Capture current offset and force a manual scroll tick
    old_offset = lbl._offset
    lbl._scroll()
    assert lbl._offset == old_offset + 5


def test_scroll_label_paint_event(qtbot):
    """
    Grab the widget as a pixmap; this calls paintEvent under the hood
    and ensures no exceptions occur during rendering.
    """
    lbl = create_widget(qtbot, ScrollLabel)  # shorten delay for test speed
    qtbot.addWidget(lbl)
    lbl.resize(180, 20)
    lbl.setText("Rendering check")
    lbl.show()
    qtbot.wait(200)  # allow Qt to schedule a paint
    pixmap = lbl.grab()
    assert not pixmap.isNull()


def test_display_client_message_with_expiration(qtbot, bec_main_window):
    """
    A message with a finite 'expire' value should disappear once the timer
    fires.
    """
    test_msg = "This message should vanish fast"
    expire_sec = 0.2

    bec_main_window.display_client_message({"message": test_msg, "expire": expire_sec}, {})

    assert bec_main_window._client_info_expire_timer.isActive()
    assert bec_main_window._client_info_label.text() == test_msg

    qtbot.waitUntil(lambda: not bec_main_window._client_info_expire_timer.isActive(), timeout=1000)

    assert bec_main_window._client_info_label.text() == ""


def test_display_client_message_no_expiration(qtbot, bec_main_window):
    """
    A message with 'expire' == 0 must persist and never start the timer.
    """
    test_msg = "Persistent status message"

    bec_main_window.display_client_message({"message": test_msg, "expire": 0}, {})

    assert not bec_main_window._client_info_expire_timer.isActive()
    assert bec_main_window._client_info_label.text() == test_msg

    qtbot.wait(500)
    assert bec_main_window._client_info_label.text() == test_msg


def test_display_client_message_overwrite_resets_timer(qtbot, bec_main_window):
    """
    Sending a second message while the expiration timer is active should
    overwrite the first and stop the timer if the second one is persistent.
    """
    first_msg = "First (temporary)"
    second_msg = "Second (persistent)"

    bec_main_window.display_client_message({"message": first_msg, "expire": 0.3}, {})
    qtbot.wait(200)
    assert bec_main_window._client_info_expire_timer.isActive()

    bec_main_window.display_client_message({"message": second_msg, "expire": 0}, {})

    assert not bec_main_window._client_info_expire_timer.isActive()
    assert bec_main_window._client_info_label.text() == second_msg

    qtbot.wait(400)
    assert bec_main_window._client_info_label.text() == second_msg


#################################################################
# Tests for BECWebLinksMixin (webbrowser opening)


def test_bec_weblinks(monkeypatch):
    opened_urls = []

    def fake_open(url):
        opened_urls.append(url)

    monkeypatch.setattr(webbrowser, "open", fake_open)

    BECWebLinksMixin.open_bec_docs()
    BECWebLinksMixin.open_bec_widgets_docs()
    BECWebLinksMixin.open_bec_bug_report()

    assert opened_urls == [
        "https://beamline-experiment-control.readthedocs.io/en/latest/",
        "https://bec.readthedocs.io/projects/bec-widgets/en/latest/",
        "https://gitlab.psi.ch/groups/bec/-/issues/",
    ]


#################################################################
# Tests for scan‑progress bar animations


def test_scan_progress_bar_show_animation(qtbot, bec_main_window):
    """
    _show_scan_progress_bar should animate the container's maximumWidth
    from 0 to the configured target width.
    """
    container = bec_main_window._scan_progress_bar_with_separator

    # Pre‑condition: collapsed
    assert container.maximumWidth() == 0

    bec_main_window._show_scan_progress_bar()

    target = bec_main_window._scan_progress_bar_target_width
    qtbot.waitUntil(lambda: container.maximumWidth() == target, timeout=2000)

    assert container.maximumWidth() == target


def test_scan_progress_bar_hide_animation(qtbot, bec_main_window):
    """
    _animate_hide_scan_progress_bar should collapse the container back to 0 width.
    """
    container = bec_main_window._scan_progress_bar_with_separator

    # First expand it
    bec_main_window._show_scan_progress_bar()
    target = bec_main_window._scan_progress_bar_target_width
    qtbot.waitUntil(lambda: container.maximumWidth() == target, timeout=2000)

    # Trigger hide animation
    bec_main_window._animate_hide_scan_progress_bar()

    qtbot.waitUntil(lambda: container.maximumWidth() == 0, timeout=2000)

    assert container.maximumWidth() == 0
