import pytest
import qdarktheme

from bec_widgets.utils.reference_utils import snap_and_compare
from bec_widgets.widgets.spinner.spinner import SpinnerWidget


@pytest.fixture
def spinner_widget(qtbot):
    qdarktheme.setup_theme("light")
    spinner = SpinnerWidget()
    qtbot.addWidget(spinner)
    qtbot.waitExposed(spinner)
    yield spinner


def test_spinner_widget_paint_event(spinner_widget, qtbot):
    spinner_widget.paintEvent(None)


def test_spinner_widget_rendered(spinner_widget, qtbot, tmpdir):
    spinner_widget.update()
    qtbot.wait(200)
    snap_and_compare(spinner_widget, str(tmpdir), suffix="")

    spinner_widget._started = True
    spinner_widget.update()
    qtbot.wait(200)

    snap_and_compare(spinner_widget, str(tmpdir), suffix="started")
