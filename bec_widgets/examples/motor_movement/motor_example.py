import os

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import QThread, pyqtSlot
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from pyqtgraph.Qt import QtWidgets, uic

from bec_lib.core import MessageEndpoints, BECMessage


# TODO - General features
#  - setting motor speed and frequency
#  - setting motor acceleration
#  - updating motor precision
#  - put motor status (moving, stopped, etc)
#  - add spinBox for motor scatter size
#  - add mouse interactions with the plot -> click to select coordinates, double click to move?
#  - adjust right click actions


class MotorApp(QWidget):
    coordinates_updated = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_controller.ui"), self)

        # Motor Control Thread
        self.motor_thread = MotorControl()

        self.motor_x, self.motor_y = None, None
        self.limit_x, self.limit_y = None, None

        # Coordinates tracking
        self.motor_positions = np.array([])
        self.max_points = 5000  # Maximum number of points to keep
        self.num_dim_points = 15  # Number of points to dim gradually

        # QThread for motor movement + signals
        self.motor_thread.motors_loaded.connect(self.get_available_motors)
        self.motor_thread.motors_selected.connect(self.get_selected_motors)
        self.motor_thread.limits_retrieved.connect(self.update_limits)

        # UI
        self.init_ui()
        self.tag_N = 1  # position label for saved coordinates

        # Get all motors available
        self.motor_thread.retrieve_all_motors()

        # Initialize current coordinates with the provided initial coordinates
        # self.motor_thread.retrieve_motor_limits(self.motor_x, self.motor_y) #TODO move after connection of motors

        # print(f"Init limits: samx:{self.limit_x}, samy:{self.limit_y}")  # TODO get to motor connect

        # Initialize the image map
        # self.init_motor_map()

    def connect_motor(self, motor_x_name: str, motor_y_name: str):
        self.motor_thread.connect_motors(motor_x_name, motor_y_name)
        self.motor_thread.retrieve_motor_limits(self.motor_x, self.motor_y)
        self.init_motor_map()

        self.motorControl.setEnabled(True)
        self.motorControl_absolute.setEnabled(True)
        self.tabWidget_tables.setTabEnabled(1, True)

    @pyqtSlot(object, object)
    def get_selected_motors(self, motor_x, motor_y):
        self.motor_x, self.motor_y = motor_x, motor_y

    @pyqtSlot(list, list)
    def get_available_motors(self, motors_x, motors_y):
        self.comboBox_motor_x.addItems(motors_x)
        self.comboBox_motor_y.addItems(motors_y)
        print(f"got motors {motors_x} and {motors_y}")

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

    @pyqtSlot()
    def enable_motor_control(self):
        self.motorControl.setEnabled(True)

    def enable_motor_controls(self, disable: bool) -> None:
        self.motorControl.setEnabled(disable)
        self.motorSelection.setEnabled(disable)

        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.motorControl_absolute.findChildren(QtWidgets.QWidget):
            widget.setEnabled(disable)

        # Enable the pushButton_stop if the motor is moving
        self.pushButton_stop.setEnabled(not disable)

    def move_motor_absolute(self, x: float, y: float) -> None:
        self.enable_motor_controls(False)
        target_coordinates = (x, y)
        self.motor_thread.move_to_coordinates(target_coordinates)

    def move_motor_relative(self, motor, value: float) -> None:
        self.enable_motor_controls(False)
        self.motor_thread.move_relative(motor, value)

    def init_ui(self) -> None:
        """Setup all ui elements"""

        ##########################
        # 2D Plot
        ##########################

        # self.label_coorditanes = self.glw.addLabel(
        #     f"Motor position: ({dev.samx.position():.2f}, {dev.samy.position():.2f})", row=0, col=0
        # ) #TODO remove hardcoded samx and samy
        self.label_coorditanes = self.glw.addLabel(
            f"Motor position: (X, Y)", row=0, col=0
        )  # TODO remove hardcoded samx and samy
        self.plot_map = self.glw.addPlot(row=1, col=0)
        self.limit_map = pg.ImageItem()
        self.plot_map.addItem(self.limit_map)
        self.motor_map = pg.ScatterPlotItem(
            size=2, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 255)
        )
        self.plot_map.addItem(self.motor_map)
        self.plot_map.showGrid(x=True, y=True)

        ##########################
        # Motor General setting
        ##########################

        # TODO make function to update precision
        self.precision = 2  # self.spinBox_precision.value()  # Define the decimal precision

        ##########################
        # Motor movements signals
        ##########################

        self.toolButton_right.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, self.spinBox_step.value())
        )
        self.toolButton_left.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, -self.spinBox_step.value())
        )
        self.toolButton_up.clicked.connect(
            lambda: self.move_motor_relative(self.motor_y, self.spinBox_step.value())
        )
        self.toolButton_down.clicked.connect(
            lambda: self.move_motor_relative(self.motor_y, -self.spinBox_step.value())
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
        self.pushButton_go_absolute.setShortcut("Ctrl+G")
        self.pushButton_go_absolute.setToolTip("Ctrl+G")

        self.motor_thread.move_finished.connect(lambda: self.enable_motor_controls(True))

        # Stop Button
        self.pushButton_stop.clicked.connect(self.motor_thread.stop_movement)

        ##########################
        # Motor limits signals
        ##########################

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
            lambda x, y: self.update_image_map(round(x, self.precision), round(y, self.precision))
        )

        # Coordinates table
        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            self.motor_thread.retrieve_coordinates(),
            tag="Initial",
            precision=0,
        )

        # Motor connections
        self.pushButton_connecMotors.clicked.connect(
            lambda: self.connect_motor(
                self.comboBox_motor_x.currentText(), self.comboBox_motor_y.currentText()
            )
        )

        # Check if there are any motors connected
        if self.motor_x or self.motor_y is None:
            self.motorControl.setEnabled(False)
            self.motorControl_absolute.setEnabled(False)
            self.tabWidget_tables.setTabEnabled(1, False)

    def init_motor_map(self):
        # Get motor limits
        limit_x_min, limit_x_max = self.motor_thread.get_motor_limits(self.motor_x)
        limit_y_min, limit_y_max = self.motor_thread.get_motor_limits(self.motor_y)

        self.offset_x = limit_x_min
        self.offset_y = limit_y_min

        # Define the size of the image map based on the motor's limits
        map_width = limit_x_max - limit_x_min + 1
        map_height = limit_y_max - limit_y_min + 1

        # Create an empty image map
        self.background_value = 15
        self.limit_map_data = np.full(
            (map_width, map_height), self.background_value, dtype=np.float32
        )
        self.limit_map.setImage(self.limit_map_data)

        # Set the initial position on the map
        init_pos = self.motor_thread.retrieve_coordinates()
        self.motor_positions = np.array([init_pos])
        self.brushes = [pg.mkBrush(255, 255, 255, 255)]

        self.motor_map.setData(pos=self.motor_positions, brush=self.brushes)

        # Translate and scale the image item to match the motor coordinates
        self.tr = QtGui.QTransform()
        self.tr.translate(limit_x_min, limit_y_min)
        self.limit_map.setTransform(self.tr)

    def update_image_map(self, x, y):
        # Update label
        self.label_coorditanes.setText(f"Motor position: ({x:.2f}, {y:.2f})")

        # Add new point with full brightness
        new_pos = np.array([x, y])
        self.motor_positions = np.vstack((self.motor_positions, new_pos))

        # If the number of points exceeds max_points, delete the oldest points
        if len(self.motor_positions) > self.max_points:
            self.motor_positions = self.motor_positions[-self.max_points :]

        # Determine brushes based on position in the array
        self.brushes = [pg.mkBrush(50, 50, 50, 255)] * len(self.motor_positions)
        for i in range(1, min(self.num_dim_points + 1, len(self.motor_positions) + 1)):
            brightness = max(50, 255 - 20 * (i - 1))
            self.brushes[-i] = pg.mkBrush(brightness, brightness, brightness, 255)

        self.brushes[-1] = pg.mkBrush(255, 255, 255, 255)  # Newest point is always full brightness

        self.motor_map.setData(pos=self.motor_positions, brush=self.brushes)

    def update_all_motor_limits(self, x_limit: list = None, y_limit: list = None) -> None:
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
    move_finished = pyqtSignal()  # Signal to emit when the move is finished
    motors_loaded = pyqtSignal(list, list)  # Signal to emit when the motors are loaded
    motors_selected = pyqtSignal(object, object)  # Signal to emit when the motors are selected
    # progress_updated = pyqtSignal(int)  #TODO  Signal to emit progress percentage

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.motor_x, self.motor_y = None, None
        self.current_x, self.current_y = None, None

        self.motors_consumer = None

        # Get all available motors in the client
        self.all_motors = self.get_all_motors()
        self.all_motors_names = self.get_all_motors_names()
        self.retrieve_all_motors()  # send motor list to GUI

        self.connect_motors("samx", "samy")

        self.target_coordinates = None

        self.motor_x_debug = dev.samx
        # self.all_motors = self.get_all_motors()
        # self.all_motors_names = self.get_all_motors_names()

        # find index of samx in self.all_motors_names
        # self.motor_x_index = self.all_motors_names.index(self.active_devices[0])

        print(f"Motor debug: {self.motor_x_debug}")

    def motor_by_string(self, motor_x_name: str, motor_y_name: str) -> tuple:
        motor_x_index = self.all_motors_names.index(motor_x_name)
        motor_y_index = self.all_motors_names.index(motor_y_name)

        motor_x = self.all_motors[motor_x_index]
        motor_y = self.all_motors[motor_y_index]
        return motor_x, motor_y

    def connect_motors(self, motor_x_name: str, motor_y_name: str) -> None:
        self.motor_x, self.motor_y = self.motor_by_string(motor_x_name, motor_y_name)

        (self.current_x, self.current_y) = self.get_coordinates()

        if self.motors_consumer is not None:
            self.motors_consumer.shutdown()

        self.motors_consumer = client.connector.consumer(
            topics=[
                MessageEndpoints.device_readback(self.motor_x.name),
                MessageEndpoints.device_readback(self.motor_y.name),
            ],
            cb=self._device_status_callback_motors,
            parent=self,
        )

        self.motors_consumer.start()

        self.motors_selected.emit(self.motor_x, self.motor_y)

    def get_all_motors(self) -> list:
        all_motors = client.device_manager.devices.acquisition_group("motor")
        return all_motors

    def get_all_motors_names(self) -> list:
        all_motors = client.device_manager.devices.acquisition_group("motor")
        all_motors_names = [motor.name for motor in all_motors]
        return all_motors_names

    def retrieve_all_motors(self):
        self.all_motors = self.get_all_motors()
        self.all_motors_names = self.get_all_motors_names()
        self.motors_loaded.emit(self.all_motors_names, self.all_motors_names)
        print("motors sent to GUI")

        return self.all_motors, self.all_motors_names

    def get_coordinates(self) -> tuple:
        """Get current motor position"""
        x = self.motor_x.read(cached=True)["value"]  # TODO remove hardcoded samx and samy
        y = self.motor_y.read(cached=True)["value"]
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
                self.update_motor_limits(
                    self.motor_x, low_limit=x_limit[0], high_limit=x_limit[1]
                )  # TODO Remove hardcoded samx and samy

        if y_limit is not None:
            if current_position[1] < y_limit[0] or current_position[1] > y_limit[1]:
                raise ValueError("Current motor position is outside the new limits (Y)")
            else:
                self.update_motor_limits(self.motor_y, low_limit=y_limit[0], high_limit=y_limit[1])

        self.retrieve_motor_limits(self.motor_x, self.motor_y)

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
        status = scans.mv(
            self.motor_x,
            self.target_coordinates[0],
            self.motor_y,
            self.target_coordinates[1],
            relative=False,
        )

        status.wait()
        self.move_finished.emit()

    def move_motor_relative(self, motor, value: float) -> None:
        status = scans.mv(motor, value, relative=True)

        status.wait()
        self.move_finished.emit()

    def stop_movement(self):
        queue.request_scan_abortion()
        queue.request_queue_reset()

    @staticmethod
    def _device_status_callback_motors(msg, *, parent, **_kwargs) -> None:
        deviceMSG = BECMessage.DeviceMessage.loads(msg.value)
        if parent.motor_x.name in deviceMSG.content["signals"]:
            parent.current_x = deviceMSG.content["signals"][parent.motor_x.name]["value"]
        elif parent.motor_y.name in deviceMSG.content["signals"]:
            parent.current_y = deviceMSG.content["signals"][parent.motor_y.name]["value"]
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
    queue = client.queue

    app = QApplication([])
    window = MotorApp()
    window.show()
    app.exec_()
