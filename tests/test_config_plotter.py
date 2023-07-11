import pyqtgraph as pg
from pytestqt import qtbot

from bec_widgets import config_plotter


def test_config_plotter(qtbot):
    """Test ConfigPlotter"""

    config = [
        {
            "cols": 1,
            "rows": 1,
            "y": 0,
            "x": 0,
            "config": {"channels": ["a"], "label_xy": ["", "a"], "item": "PlotItem"},
        }
    ]
    plotter = config_plotter.ConfigPlotter(config)

    assert isinstance(plotter.plots["a"]["item"], pg.PlotItem)


def test_config_plotter_image(qtbot):
    """Test ConfigPlotter"""

    config = [
        {
            "cols": 1,
            "rows": 1,
            "y": 0,
            "x": 0,
            "config": {"channels": ["a"], "label_xy": ["", "a"], "item": "PlotItem"},
        },
        {
            "cols": 1,
            "rows": 1,
            "y": 1,
            "x": 0,
            "config": {"channels": ["b"], "label_xy": ["", "b"], "item": "ImageItem"},
        },
    ]
    plotter = config_plotter.ConfigPlotter(config)

    assert isinstance(plotter.plots["a"]["item"], pg.PlotItem)
