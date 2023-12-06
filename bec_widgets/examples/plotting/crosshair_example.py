import numpy as np
import pyqtgraph as pg
from qtpy.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QLabel,
    QWidget,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
)
from pyqtgraph import mkPen
from pyqtgraph.Qt import QtCore
from bec_widgets.qt_utils import Crosshair


class ExampleApp(QWidget):
    def __init__(self):
        super().__init__()

        # Layout
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        ##########################
        # 1D Plot
        ##########################

        # PlotWidget
        self.plot_widget_1d = pg.PlotWidget(title="1D PlotWidget with multiple curves")
        self.plot_item_1d = self.plot_widget_1d.getPlotItem()
        self.plot_item_1d.setLogMode(True, True)

        # 1D Datasets
        self.x_data = np.linspace(0, 10, 1000)

        def gauss(x, mu, sigma):
            return (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu) / sigma) ** 2)

        # same convention as in line_plot.py
        self.y_value_list = [
            gauss(self.x_data, 1, 1),
            gauss(self.x_data, 1.5, 3),
            abs(np.sin(self.x_data)),
            abs(np.cos(self.x_data)),
            abs(np.sin(2 * self.x_data)),
        ]  # List of y-values for multiple curves

        self.curve_names = ["Gauss(1,1)", "Gauss(1.5,3)", "Abs(Sine)", "Abs(Cosine)", "Abs(Sine2x)"]
        self.curves = []

        ##########################
        # 2D Plot
        ##########################
        self.plot_widget_2d = pg.PlotWidget(title="2D plot with crosshair and ROI square")
        self.data_2D = np.random.random((100, 200))
        self.plot_item_2d = self.plot_widget_2d.getPlotItem()
        self.image_item = pg.ImageItem(self.data_2D)
        self.plot_item_2d.addItem(self.image_item)

        ##########################
        # Table
        ##########################
        self.table = QTableWidget(len(self.curve_names), 2)
        self.table.setHorizontalHeaderLabels(["(X, Y) - Moved", "(X, Y) - Clicked"])
        self.table.setVerticalHeaderLabels(self.curve_names)
        self.table.resizeColumnsToContents()

        ##########################
        # Spinbox for N curves
        ##########################
        self.spin_box = QSpinBox()
        self.spin_box.setMinimum(0)
        self.spin_box.setMaximum(len(self.y_value_list))
        self.spin_box.setValue(2)
        self.spin_box.valueChanged.connect(lambda: self.update_curves(self.spin_box.value()))

        ##########################
        # Adding widgets to layout
        ##########################

        ##### left side #####
        self.column1 = QVBoxLayout()
        self.layout.addLayout(self.column1)

        # SpinBox
        self.spin_row = QHBoxLayout()
        self.column1.addLayout(self.spin_row)
        self.spin_row.addWidget(QLabel("Number of curves:"))
        self.spin_row.addWidget(self.spin_box)

        # label
        self.clicked_label_1d = QLabel("Clicked Coordinates (1D):")
        self.column1.addWidget(self.clicked_label_1d)

        # table
        self.column1.addWidget(self.table)

        # 1D plot
        self.column1.addWidget(self.plot_widget_1d)

        ##### left side #####
        self.column2 = QVBoxLayout()
        self.layout.addLayout(self.column2)

        # labels
        self.clicked_label_2d = QLabel("Clicked Coordinates (2D):")
        self.moved_label_2d = QLabel("Moved Coordinates (2D):")
        self.column2.addWidget(self.clicked_label_2d)
        self.column2.addWidget(self.moved_label_2d)

        # 2D plot
        self.column2.addWidget(self.plot_widget_2d)

        self.update_curves(2)  # just Gaussian curves

    def hook_crosshair(self):
        self.crosshair_1d = Crosshair(self.plot_item_1d, precision=10)
        self.crosshair_1d.coordinatesChanged1D.connect(
            lambda x, y: self.update_table(self.table, x, y, column=0)
        )
        self.crosshair_1d.coordinatesClicked1D.connect(
            lambda x, y: self.update_table(self.table, x, y, column=1)
        )
        # 2D
        self.crosshair_2d = Crosshair(self.plot_item_2d)
        self.crosshair_2d.coordinatesChanged2D.connect(
            lambda x, y: self.moved_label_2d.setText(f"Mouse Moved Coordinates (2D): x={x}, y={y}")
        )
        self.crosshair_2d.coordinatesClicked2D.connect(
            lambda x, y: self.clicked_label_2d.setText(f"Clicked Coordinates (2D): x={x}, y={y}")
        )

    def update_table(self, table_widget, x, y_values, column):
        """Update the table with the new coordinates"""
        for i, y in enumerate(y_values):
            table_widget.setItem(i, column, QTableWidgetItem(f"({x}, {y})"))
            table_widget.resizeColumnsToContents()

    def update_curves(self, num_curves):
        """Update the number of curves"""

        self.plot_item_1d.clear()

        # Curves
        color_list = ["#384c6b", "#e28a2b", "#5E3023", "#e41a1c", "#984e83", "#4daf4a"]
        self.plot_item_1d.addLegend()
        self.curves = []

        y_value_list = self.y_value_list[:num_curves]

        for ii, y_value in enumerate(y_value_list):
            pen = mkPen(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            curve = pg.PlotDataItem(
                self.x_data, y_value, pen=pen, skipFiniteCheck=True, name=self.curve_names[ii]
            )
            self.plot_item_1d.addItem(curve)
            self.curves.append(curve)

        self.hook_crosshair()


if __name__ == "__main__":
    app = QApplication([])
    window = ExampleApp()
    window.show()
    app.exec()
