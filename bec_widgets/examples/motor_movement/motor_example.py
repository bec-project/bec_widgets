import os

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import QThread, pyqtSlot
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from pyqtgraph.Qt import QtWidgets, uic

from bec_lib.core import MessageEndpoints, BECMessage


class MotorApp(QWidget):
    coordinates_updated = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_controller.ui"), self)

        self.limit_x, self.limit_y = None, None

        # QThread for motor movement + signals
        self.motor_thread = MotorControl()
        self.motor_thread.limits_retrieved.connect(self.update_limits)

        # UI
        self.init_ui()
        self.tag_N = 1  # position label for saved coordinates

        # Initialize current coordinates with the provided initial coordinates
        self.motor_thread.retrieve_motor_limits(dev.samx, dev.samy)

        print(f"Init limits: samx:{self.limit_x}, samy:{self.limit_y}")

        self.label_status.setText(
            f"Motor position: ({dev.samx.position():.2f}, {dev.samy.position():.2f})"
        )  # TODO has to be change to get positions from thread not directly from device

    @pyqtSlot(list, list)
    def update_limits(self, x_limits: list, y_limits: list) -> None:
        self.limit_x = x_limits
        self.limit_y = y_limits
        self.spinBox_x_min.setValue(self.limit_x[0])
        self.spinBox_x_max.setValue(self.limit_x[1])
        self.spinBox_y_min.setValue(self.limit_y[0])
        self.spinBox_y_max.setValue(self.limit_y[1])

        for spinBox in (
            self.spinBox_x_min,
            self.spinBox_x_max,
            self.spinBox_y_min,
            self.spinBox_y_max,
        ):
            spinBox.setStyleSheet("")

        self.init_motor_map()  # reinitialize the map with the new limits

    def move_motor_absolute(self, x: float, y: float) -> None:
        target_coordinates = (x, y)
        self.motor_thread.move_to_coordinates(target_coordinates)

    def move_motor_relative(self, motor, value: float) -> None:
        self.motor_thread.move_relative(motor, value)

    def init_ui(self) -> None:
        """Setup all ui elements"""

        ##########################
        # 2D Plot
        ##########################

        self.label_coorditanes = self.glw.addLabel(
            f"Motor position: ({dev.samx.position():.2f}, {dev.samy.position():.2f})", row=0, col=0
        )
        self.plot_map = self.glw.addPlot(row=1, col=0)
        self.image_map = pg.ImageItem()
        self.plot_map.addItem(self.image_map)

        ##########################
        # Signals
        ##########################

        self.toolButton_right.clicked.connect(
            lambda: self.move_motor_relative(dev.samx, self.spinBox_step.value())
        )
        self.toolButton_left.clicked.connect(
            lambda: self.move_motor_relative(dev.samx, -self.spinBox_step.value())
        )
        self.toolButton_up.clicked.connect(
            lambda: self.move_motor_relative(dev.samy, self.spinBox_step.value())
        )
        self.toolButton_down.clicked.connect(
            lambda: self.move_motor_relative(dev.samy, -self.spinBox_step.value())
        )

        # Switch between key shortcuts active
        self.checkBox_enableArrows.stateChanged.connect(self.update_arrow_key_shortcuts)
        self.update_arrow_key_shortcuts()

        # Move to absolute coordinates
        self.pushButton_go_absolute.clicked.connect(
            lambda: self.move_motor_absolute(
                self.spinBox_absolute_x.value(), self.spinBox_absolute_y.value()
            )
        )
        self.pushButton_go_absolute.clicked.connect(self.save_absolute_coordinates)

        # SpinBoxes - Motor Limits #TODO make spinboxes own limits updated, currently is [-1000, 1000]

        # SpinBoxes change color to yellow before updated, limits are updated with update button
        self.spinBox_x_min.valueChanged.connect(lambda: self.param_changed(self.spinBox_x_min))
        self.spinBox_x_max.valueChanged.connect(lambda: self.param_changed(self.spinBox_x_max))
        self.spinBox_y_min.valueChanged.connect(lambda: self.param_changed(self.spinBox_y_min))
        self.spinBox_y_max.valueChanged.connect(lambda: self.param_changed(self.spinBox_y_max))

        self.pushButton_updateLimits.clicked.connect(
            lambda: self.update_all_motor_limits(
                x_limit=[self.spinBox_x_min.value(), self.spinBox_x_max.value()],
                y_limit=[self.spinBox_y_min.value(), self.spinBox_y_max.value()],
            )
        )

        # TODO map with floats as well -> or decide system for higher precision
        self.motor_thread.coordinates_updated.connect(
            lambda x, y: self.update_image_map(int(x), int(y))
        )

        # Coordinates table
        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            self.motor_thread.retrieve_coordinates(),
            tag="Initial",
            precision=0,
        )

    def init_motor_map(self):
        # Get motor limits
        limit_x_min, limit_x_max = self.motor_thread.get_motor_limits(dev.samx)
        limit_y_min, limit_y_max = self.motor_thread.get_motor_limits(dev.samy)

        self.offset_x = limit_x_min
        self.offset_y = limit_y_min

        # Define the size of the image map based on the motor's limits
        map_width = limit_x_max - limit_x_min + 1
        map_height = limit_y_max - limit_y_min + 1

        # Create an empty image map
        self.background_value = 15
        self.image_map_data = np.full(
            (map_width, map_height), self.background_value, dtype=np.float32
        )

        # Set the initial position on the map
        x, y = self.motor_thread.retrieve_coordinates()
        self.update_image_map(x, y)

        # Translate and scale the image item to match the motor coordinates
        self.tr = QtGui.QTransform()
        self.tr.translate(limit_x_min, limit_y_min)
        self.image_map.setTransform(self.tr)

        self.image_map.dataTransform()

    def update_image_map(self, x, y):
        """Update the image map with the new motor position"""

        # Define the dimming factor
        dimming_factor = 0.95

        # Apply the dimming factor only to pixels above the background value
        self.image_map_data[self.image_map_data > 50] *= dimming_factor

        # Mapping of motor coordinates to pixel coordinates
        pixel_x = int(x - self.offset_x)
        pixel_y = int(y - self.offset_y)

        # Set the bright pixel at the new position
        self.image_map_data[pixel_x, pixel_y] = 255

        # Update the display
        self.image_map.updateImage(self.image_map_data, levels=(0, 255))

    def update_all_motor_limits(
        self, x_limit: list = None, y_limit: list = None
    ) -> None:  # TODO will be moved to thread
        self.motor_thread.update_all_motor_limits(x_limit=x_limit, y_limit=y_limit)

    def update_arrow_key_shortcuts(self):
        if self.checkBox_enableArrows.isChecked():
            # Set the arrow key shortcuts for motor movement
            self.toolButton_right.setShortcut(Qt.Key_Right)
            self.toolButton_left.setShortcut(Qt.Key_Left)
            self.toolButton_up.setShortcut(Qt.Key_Up)
            self.toolButton_down.setShortcut(Qt.Key_Down)
        else:
            # Clear the shortcuts
            self.toolButton_right.setShortcut("")
            self.toolButton_left.setShortcut("")
            self.toolButton_up.setShortcut("")
            self.toolButton_down.setShortcut("")

    def generate_table_coordinate(
        self, table: QtWidgets.QTableWidget, coordinates: tuple, tag: str = None, precision: int = 0
    ) -> None:
        current_row_count = table.rowCount()

        table.setRowCount(current_row_count + 1)

        # table.insertRow(current_row_count)

        checkBox = QtWidgets.QCheckBox()
        checkBox.setChecked(True)
        button = QtWidgets.QPushButton("Go")

        table.setItem(current_row_count, 0, QtWidgets.QTableWidgetItem(str(tag)))
        table.setCellWidget(current_row_count, 1, checkBox)
        table.setItem(
            current_row_count, 2, QtWidgets.QTableWidgetItem(str(f"{coordinates[0]:.{precision}f}"))
        )
        table.setItem(
            current_row_count, 3, QtWidgets.QTableWidgetItem(str(f"{coordinates[1]:.{precision}f}"))
        )
        table.setCellWidget(current_row_count, 4, button)

        # hook signals of table
        button.clicked.connect(
            lambda: self.move_motor_absolute(
                float(table.item(current_row_count, 2).text()),
                float(table.item(current_row_count, 3).text()),
            )
        )
        table.resizeColumnsToContents()

    def save_absolute_coordinates(self):
        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            (self.spinBox_absolute_x.value(), self.spinBox_absolute_y.value()),
            tag=f"Pos {self.tag_N}",
            precision=0,
        )

        self.tag_N += 1

    @staticmethod
    def param_changed(ui_element):
        ui_element.setStyleSheet("background-color: #FFA700;")


class MotorControl(QThread):
    coordinates_updated = pyqtSignal(float, float)  # Signal to emit current coordinates
    limits_retrieved = pyqtSignal(list, list)  # Signal to emit current limits (samx, samy)
    # progress_updated = pyqtSignal(int)  #TODO  Signal to emit progress percentage

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_coordinates = None
        self.running = False

        # Initialize current coordinates with the provided initial coordinates
        (
            self.current_x,
            self.current_y,
        ) = self.get_coordinates()  # TODO maybe not needed, coordinates always stored in redis

        # Create consumer for samx and samy
        self.samx_consumer = client.connector.consumer(
            topics=[MessageEndpoints.device_readback("samx")],
            cb=self._device_status_callback_samx,
            parent=self,
        )

        self.samy_consumer = client.connector.consumer(
            topics=[MessageEndpoints.device_readback("samy")],
            cb=self._device_status_callback_samy,
            parent=self,
        )

        self.samx_consumer.start()
        self.samy_consumer.start()

    def get_coordinates(self) -> tuple:
        # TODO decide if the get_coordinates and retrieve coordinates makes sense
        # TODO or move also to signal/slot as in the case of limits
        # TODO or move just to redis CB function
        """Get current motor position"""
        x = dev.samx.position()
        y = dev.samy.position()
        return x, y

    def retrieve_coordinates(self) -> tuple:
        """Get current motor position for export to main app"""
        return self.current_x, self.current_y

    def get_motor_limits(self, motor) -> list:
        """Get the limits of a motor"""
        return motor.limits

    def retrieve_motor_limits(self, motor_x, motor_y):
        limit_x = self.get_motor_limits(motor_x)
        limit_y = self.get_motor_limits(motor_y)
        self.limits_retrieved.emit(limit_x, limit_y)

    def update_motor_limits(self, motor, low_limit=None, high_limit=None) -> None:
        current_low_limit, current_high_limit = self.get_motor_limits(motor)

        # Check if the low limit has changed and is not None
        if low_limit is not None and low_limit != current_low_limit:
            motor.low_limit = low_limit

        # Check if the high limit has changed and is not None
        if high_limit is not None and high_limit != current_high_limit:
            motor.high_limit = high_limit

    def update_all_motor_limits(self, x_limit: list = None, y_limit: list = None) -> None:
        # TODO can be generalized to any motor not just samx samy
        current_position = self.get_coordinates()

        if x_limit is not None:
            if current_position[0] < x_limit[0] or current_position[0] > x_limit[1]:
                raise ValueError("Current motor position is outside the new limits (X)")
            else:
                self.update_motor_limits(dev.samx, low_limit=x_limit[0], high_limit=x_limit[1])

        if y_limit is not None:
            if current_position[1] < y_limit[0] or current_position[1] > y_limit[1]:
                raise ValueError("Current motor position is outside the new limits (Y)")
            else:
                self.update_motor_limits(dev.samy, low_limit=y_limit[0], high_limit=y_limit[1])

        self.retrieve_motor_limits(dev.samx, dev.samy)

    def move_to_coordinates(self, target_coordinates: tuple):
        self.action = "move_to_coordinates"
        self.target_coordinates = target_coordinates
        self.start()

    def move_relative(self, motor, value: float):
        self.action = "move_relative"
        self.motor = motor
        self.value = value
        self.start()

    def run(self):
        if self.action == "move_to_coordinates":
            self.move_motor_coordinate()
        elif self.action == "move_relative":
            self.move_motor_relative(self.motor, self.value)

    def set_target_coordinates(self, target_coordinates: tuple) -> None:
        self.target_coordinates = target_coordinates

    def move_motor_coordinate(self) -> None:
        """Move the motor to the specified coordinates"""
        scans.mv(
            dev.samx,
            self.target_coordinates[0],
            dev.samy,
            self.target_coordinates[1],
            relative=False,
        )

    def move_motor_relative(self, motor, value: float) -> None:
        scans.mv(motor, value, relative=True)

    # TODO decide if one or multiple callback functions
    @staticmethod
    def _device_status_callback_samx(msg, *, parent, **_kwargs) -> None:
        deviceMSG = BECMessage.DeviceMessage.loads(msg.value)
        parent.current_x = deviceMSG.content["signals"]["samx"]["value"]
        print(f"samx moving: {parent.current_x,parent.current_y}")
        parent.coordinates_updated.emit(parent.current_x, parent.current_y)

    @staticmethod
    def _device_status_callback_samy(msg, *, parent, **_kwargs) -> None:
        deviceMSG = BECMessage.DeviceMessage.loads(msg.value)
        parent.current_y = deviceMSG.content["signals"]["samy"]["value"]
        print(f"samy moving: {parent.current_x,parent.current_y}")
        parent.coordinates_updated.emit(parent.current_x, parent.current_y)


if __name__ == "__main__":
    from bec_lib import BECClient

    # from bec_lib.core import ServiceConfig,RedisConnector

    client = BECClient()
    # client.initialize(config=ServiceConfig(config_path="test_config.yaml"))

    # Client initialization - by dispatcher
    # client = bec_dispatcher.client
    client.start()
    dev = client.device_manager.devices
    scans = client.scans

    app = QApplication([])
    window = MotorApp()
    window.show()
    app.exec_()
