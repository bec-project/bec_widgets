import pytest

from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.reference_utils import snap_and_compare
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget


@pytest.fixture
def spinner_widget(qtbot):
    apply_theme("light")
    spinner = SpinnerWidget()
    qtbot.addWidget(spinner)
    qtbot.waitExposed(spinner)
    yield spinner
    spinner.close()


def test_spinner_widget_paint_event(spinner_widget, qtbot):
    spinner_widget.paintEvent(None)


def test_spinnner_with_float_angle(spinner_widget, qtbot):
    spinner_widget.start()
    spinner_widget.angle = 0.123453453453453
    spinner_widget.paintEvent(None)


def test_spinner_widget_rendered(spinner_widget, qtbot, tmpdir):
    spinner_widget.update()
    qtbot.wait(200)
    snap_and_compare(spinner_widget, str(tmpdir), suffix="")

    spinner_widget._started = True
    spinner_widget.update()
    qtbot.wait(200)

    snap_and_compare(spinner_widget, str(tmpdir), suffix="started")
