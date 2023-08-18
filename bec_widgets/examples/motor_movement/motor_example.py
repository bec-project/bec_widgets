import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from pyqtgraph.Qt import QtCore, QtWidgets, uic
import pyqtgraph as pg


class MotorApp(QWidget):
    motor_position = pyqtSignal(float)  # TODO hook to motor position update

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

        # self.toolButton_left.clicked.connect(lambda: print(self.client))

    def move_motor(self, motor, value: float) -> None:
        scans.mv(motor, value, relative=True)
        self.motor_position.emit(motor.position)


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
