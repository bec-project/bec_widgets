import pyqtgraph as pg
import numpy as np

from crosshair import Crosshair


def add_crosshair(plot_item, is_image=False):
    return Crosshair(plot_item, is_image)


app = pg.mkQApp()
win = pg.GraphicsLayoutWidget(show=True)
win.resize(1000, 500)

#####################
# 1D Plot with labels
#####################
label_1d_move = win.addLabel("1D move label", row=0, col=0)
label_1d_click = win.addLabel("1D click label", row=1, col=0)
plot_item_1d = win.addPlot(row=2, col=0)
x_data = np.linspace(0, 10, 1000)
y_data_sine = np.sin(x_data)
y_data_cosine = np.cos(x_data)
plot_item_1d.plot(x_data, y_data_sine)
plot_item_1d.plot(x_data, y_data_cosine)
crosshair_1d = Crosshair(plot_item_1d, precision=2)


def on_coordinates_changed_1d(x, y):
    label_1d_move.setText(f"1D Moved: ({x}, {y})")


def on_data_point_clicked_1d(x, y):
    label_1d_click.setText(f"1D Clicked: ({x}, {y})")


crosshair_1d.coordinatesChanged.connect(on_coordinates_changed_1d)
crosshair_1d.dataPointClicked.connect(on_data_point_clicked_1d)

#####################
# 2D Plot with labels
#####################
label_2d_move = win.addLabel("2D move label", row=0, col=1)
label_2d_click = win.addLabel("2D click label", row=1, col=1)
plot_item_2d = win.addPlot(row=2, col=1)

img = np.random.normal(size=(100, 100))
image_item = pg.ImageItem(img)
plot_item_2d.addItem(image_item)

crosshair_2d = Crosshair(plot_item_2d, precision=2)


def on_coordinates_changed_2d(x, y):
    label_2d_move.setText(f"2D Moved: ({x}, {y})")


def on_data_point_clicked_2d(x, y):
    label_2d_click.setText(f"2D Clicked: ({x}, {y})")


#
crosshair_2d.coordinatesChanged.connect(on_coordinates_changed_2d)
crosshair_2d.dataPointClicked.connect(on_data_point_clicked_2d)

if __name__ == "__main__":
    pg.exec()
