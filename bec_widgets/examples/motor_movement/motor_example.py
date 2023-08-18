import os

import numpy as np
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from pyqtgraph.Qt import QtCore, QtWidgets, uic
import pyqtgraph as pg


class MotorApp(QWidget):
    motor_position = pyqtSignal(float)  # TODO hook to motor position update
    motor_update = pyqtSignal()

    def __init__(self):
        super().__init__()
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_controller.ui"), self)

        # UI

        self.init_ui()

    def init_ui(self):
        """Setup all ui elements"""
        ##########################
        # 2D Plot
        ##########################

        self.label_coorditanes = self.glw.addLabel("Current Motor Coordinates", row=0, col=0)
        self.plot_map = self.glw.addPlot(row=1, col=0)
        self.image_map = pg.ImageItem()
        self.plot_map.addItem(self.image_map)

        self.image_map_data = np.zeros((100, 100), dtype=np.float32)
        x, y = self.get_xy()  # Assuming get_xy returns the motor position
        self.update_image_map(x, y)
        self.image_map.setImage(self.image_map_data.T)  # Set the image
        ##########################
        # Signals
        ##########################
        # Buttons - Motor Movement
        self.toolButton_right.clicked.connect(
            lambda: self.move_motor(dev.samx, self.spinBox_step.value())
        )
        self.toolButton_left.clicked.connect(
            lambda: self.move_motor(dev.samx, -self.spinBox_step.value())
        )
        self.toolButton_up.clicked.connect(
            lambda: self.move_motor(dev.samy, self.spinBox_step.value())
        )
        self.toolButton_down.clicked.connect(
            lambda: self.move_motor(dev.samy, -self.spinBox_step.value())
        )

        # Map
        self.motor_position.connect(lambda x: self.update_image_map(*self.get_xy()))

        # make keybindings for motor movement
        self.toolButton_right.setShortcut("Right")
        self.toolButton_left.setShortcut("Left")
        self.toolButton_up.setShortcut("Up")
        self.toolButton_down.setShortcut("Down")

        # self.toolButton_left.clicked.connect(lambda: print(self.client))

        self.motor_position.connect(lambda x: print(f"motor position updated: {x}"))
        self.motor_update.connect(
            lambda: self.label_status.setText(
                f"Motor position: ({dev.samx.position():.2f}, {dev.samy.position():.2f})"
            )
        )

    def move_motor(self, motor, value: float) -> None:
        scans.mv(motor, value, relative=True)
        motor_position = motor.position()

        self.motor_position.emit(motor_position)
        self.motor_update.emit()

    def get_xy(self):  # TODO decide if useful
        """Get current motor position"""
        x = dev.samx.position()
        y = dev.samy.position()
        return x, y

    def update_image_map(self, x, y):
        """Update the image map with the new motor position"""

        # Reduce the brightness of all pixels by a fixed fraction (e.g., 5%)
        self.image_map_data *= 0.8

        # Modify this mapping as needed
        pixel_x = int(x)
        pixel_y = int(y)

        # Set the bright pixel at the new position
        self.image_map_data[pixel_x, pixel_y] = 255

        # Update the display
        self.image_map.setImage(self.image_map_data)


if __name__ == "__main__":
    from bec_widgets.bec_dispatcher import bec_dispatcher

    # Client initialization
    client = bec_dispatcher.client
    client.start()
    dev = client.device_manager.devices
    scans = client.scans

    app = QApplication([])
    window = MotorApp()
    window.show()
    app.exec_()
