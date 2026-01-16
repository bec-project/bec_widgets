import numpy as np
import pytest
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

from .client_mocks import mocked_client


class _TestBusyWidget(BECWidget, QWidget):
    def __init__(
        self, parent=None, *, start_busy: bool = False, theme_update: bool = False, **kwargs
    ):
        super().__init__(parent=parent, theme_update=theme_update, start_busy=start_busy, **kwargs)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("content", self))


@pytest.fixture
def widget_busy(qtbot, mocked_client):
    w = _TestBusyWidget(client=mocked_client, start_busy=True)
    qtbot.addWidget(w)
    w.resize(320, 200)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture
def widget_idle(qtbot):
    w = _TestBusyWidget(client=mocked_client, start_busy=False)
    qtbot.addWidget(w)
    w.resize(320, 200)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_becwidget_start_busy_shows_overlay(qtbot, widget_busy):
    overlay = getattr(widget_busy, "_busy_overlay", None)
    assert overlay is not None, "BECWidget should create a busy overlay in __init__"
    qtbot.waitUntil(lambda: overlay.geometry() == widget_busy.rect())
    qtbot.waitUntil(lambda: overlay.isVisible())


def test_becwidget_set_busy_toggle_and_text(qtbot, widget_idle):
    overlay = getattr(widget_idle, "_busy_overlay", None)
    assert overlay is None, "Overlay should be lazily created when idle"

    widget_idle.set_busy(True)
    overlay = getattr(widget_idle, "_busy_overlay")
    qtbot.waitUntil(lambda: overlay.isVisible())

    assert hasattr(widget_idle, "_busy_state_widget")
    assert overlay._custom_widget is not None

    label = overlay._custom_widget.findChild(QLabel)
    assert label is not None
    assert label.text() == "Loading..."

    spinner = overlay._custom_widget.findChild(SpinnerWidget)
    assert spinner is not None
    assert spinner.isVisible()
    assert spinner._started is True

    widget_idle.set_busy(False)
    qtbot.waitUntil(lambda: overlay.isHidden())


def test_becwidget_busy_overlay_set_opacity(qtbot, widget_busy):
    overlay = getattr(widget_busy, "_busy_overlay")
    qtbot.waitUntil(lambda: overlay.isVisible())

    # Default opacity is 0.7
    frame = getattr(overlay, "_frame", None)
    assert frame is not None
    sheet = frame.styleSheet()
    _, _, _, a = overlay.scrim_color.getRgb()
    assert np.isclose(a / 255, 0.35, atol=0.02)

    # Change opacity
    overlay.set_opacity(0.7)
    qtbot.waitUntil(lambda: overlay.isVisible())
    _, _, _, a = overlay.scrim_color.getRgb()
    assert np.isclose(a / 255, 0.7, atol=0.02)


def test_becwidget_overlay_tracks_resize(qtbot, widget_busy):
    overlay = getattr(widget_busy, "_busy_overlay")
    qtbot.waitUntil(lambda: overlay.geometry() == widget_busy.rect())

    widget_busy.resize(480, 260)
    qtbot.waitUntil(lambda: overlay.geometry() == widget_busy.rect())


def test_becwidget_overlay_frame_geometry_and_style(qtbot, widget_busy):
    overlay = getattr(widget_busy, "_busy_overlay")
    qtbot.waitUntil(lambda: overlay.isVisible())

    frame = getattr(overlay, "_frame", None)
    assert frame is not None, "Busy overlay must use an internal QFrame for visuals"

    # Insets are 10 px in the implementation
    outer = overlay.rect()
    # Ensure resizeEvent has run and frame geometry is updated
    qtbot.waitUntil(
        lambda: frame.geometry().width() == outer.width() - 20
        and frame.geometry().height() == outer.height() - 20
    )

    inner = frame.geometry()
    assert inner.left() == outer.left() + 10
    assert inner.top() == outer.top() + 10
    assert inner.right() == outer.right() - 10
    assert inner.bottom() == outer.bottom() - 10

    # Style: dashed border + semi-transparent grey background
    ss = frame.styleSheet()
    assert "dashed" in ss
    assert "border" in ss
    assert "rgba(128, 128, 128, 110)" in ss


def test_becwidget_busy_cycle_start_on_off_on(qtbot, widget_busy):
    overlay = getattr(widget_busy, "_busy_overlay", None)
    assert overlay is not None, "Busy overlay should exist on a start_busy widget"

    # Initially visible because start_busy=True
    qtbot.waitUntil(lambda: overlay.isVisible())

    # Switch OFF
    widget_busy.set_busy(False)
    qtbot.waitUntil(lambda: overlay.isHidden())

    # Switch ON again (with new text)
    widget_busy.set_busy(True)
    qtbot.waitUntil(lambda: overlay.isVisible())

    # Same overlay instance reused (no duplication)
    assert getattr(widget_busy, "_busy_overlay") is overlay

    # Geometry follows parent after re-show
    qtbot.waitUntil(lambda: overlay.geometry() == widget_busy.rect())
