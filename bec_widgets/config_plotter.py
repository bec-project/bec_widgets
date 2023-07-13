from typing import List

import numpy as np
import pyqtgraph as pg
from pyqtgraph import mkPen
from pyqtgraph.Qt import QtCore, QtWidgets


class ConfigPlotter(pg.GraphicsWidget):
    """
    ConfigPlotter is a widget that can be used to plot data from multiple channels
    in a grid layout. The layout is specified by a list of dicts, where each dict
    specifies the position of the plot in the grid, the channels to plot, and the
    type of plot to use. The plot type is specified by the name of the pyqtgraph
    item to use. For example, to plot a single channel in a PlotItem, the config
    would look like this:

    config = [
        {
            "cols": 1,
            "rows": 1,
            "y": 0,
            "x": 0,
            "config": {"channels": ["a"], "label_xy": ["", "a"], "item": "PlotItem"},
        }
    ]

    """

    def __init__(self, configs: List[dict], parent=None):
        super().__init__(parent)
        self.configs = configs
        self.plots = {}
        self._init_ui()
        self._init_plots()

    def _init_ui(self):
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

        # pylint: disable=no-member
        self.pen = mkPen(color=(56, 76, 107), width=4, style=QtCore.Qt.SolidLine)

        self.view = pg.GraphicsView()
        self.view.setAntialiasing(True)
        self.view.show()

        self.layout = pg.GraphicsLayout()
        self.view.setCentralWidget(self.layout)

    def _init_plots(self):
        for config in self.configs:
            channels = config["config"]["channels"]
            for channel in channels:
                item = pg.PlotItem()
                self.layout.addItem(
                    item,
                    row=config["y"],
                    col=config["x"],
                    rowspan=config["rows"],
                    colspan=config["cols"],
                )

                # call the corresponding init function, e.g. init_plotitem
                init_func = getattr(self, f"init_{config['config']['item']}")
                init_func(channel, config["config"], item)

                # self.init_ImageItem(channel, config["config"], item)

    def init_PlotItem(self, channel: str, config: dict, item: pg.GraphicsItem):
        """
        Initialize a PlotItem

        Args:
            channel(str): channel to plot
            config(dict): config dict for the channel
            item(pg.GraphicsItem): PlotItem to plot the data
        """
        # pylint: disable=invalid-name
        plot_data = item.plot(np.random.rand(100), pen=self.pen)
        item.setLabel("left", channel)
        self.plots[channel] = {"item": item, "plot_data": plot_data}

    def init_ImageItem(self, channel: str, config: dict, item: pg.GraphicsItem):
        """
        Initialize an ImageItem

        Args:
            channel(str): channel to plot
            config(dict): config dict for the channel
            item(pg.GraphicsItem): ImageItem to plot the data
        """
        # pylint: disable=invalid-name
        img = pg.ImageItem()
        item.addItem(img)
        img.setImage(np.random.rand(100, 100))
        self.plots[channel] = {"item": item, "plot_data": img}


if __name__ == "__main__":
    import sys

    CONFIG = [
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
            "config": {"channels": ["b"], "label_xy": ["", "b"], "item": "PlotItem"},
        },
        {
            "cols": 1,
            "rows": 2,
            "y": 0,
            "x": 1,
            "config": {"channels": ["c"], "label_xy": ["", "c"], "item": "ImageItem"},
        },
    ]

    app = QtWidgets.QApplication(sys.argv)
    win = ConfigPlotter(CONFIG)
    pg.exec()
