import pyqtgraph as pg
import pytest

from bec_widgets.utils.round_frame import RoundedFrame


def cleanup_pyqtgraph(plot_widget):
    item = plot_widget.getPlotItem()
    item.vb.menu.close()
    item.vb.menu.deleteLater()
    item.ctrlMenu.close()
    item.ctrlMenu.deleteLater()


@pytest.fixture
def basic_rounded_frame(qtbot):
    frame = RoundedFrame()
    qtbot.addWidget(frame)
    qtbot.waitExposed(frame)
    yield frame


@pytest.fixture
def plot_rounded_frame(qtbot):
    plot_widget = pg.PlotWidget()
    plot_widget.plot([0, 1, 2], [2, 1, 0])
    frame = RoundedFrame(content_widget=plot_widget)
    qtbot.addWidget(frame)
    qtbot.waitExposed(frame)
    yield frame
    cleanup_pyqtgraph(plot_widget)


def test_basic_rounded_frame_initialization(basic_rounded_frame):
    assert basic_rounded_frame.radius == 10
    assert basic_rounded_frame.content_widget is None
    assert basic_rounded_frame.background_color is None


def test_set_radius(basic_rounded_frame):
    basic_rounded_frame.radius = 20
    assert basic_rounded_frame.radius == 20


def test_apply_theme_light(plot_rounded_frame):
    plot_rounded_frame.apply_theme("light")

    assert plot_rounded_frame.background_color == "#e9ecef"


def test_apply_theme_dark(plot_rounded_frame):
    plot_rounded_frame.apply_theme("dark")

    assert plot_rounded_frame.background_color == "#141414"


def test_apply_plot_widget_style(plot_rounded_frame):
    # Verify that a PlotWidget can have its style applied
    plot_rounded_frame.apply_plot_widget_style(border="1px solid red")

    # Ensure style application did not break anything
    assert plot_rounded_frame.content_widget is not None
    assert isinstance(plot_rounded_frame.content_widget, pg.PlotWidget)
