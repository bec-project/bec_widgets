# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring

import qdarktheme
from qtpy.QtWidgets import QApplication
from qtpy.QtWidgets import QVBoxLayout
from qtpy.QtWidgets import (
    QWidget,
    QSplitter,
)
from qtpy.QtCore import Qt

from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.widgets import (
    MotorControlAbsolute,
    MotorControlRelative,
    MotorControlSelection,
    MotorThread,
    MotorMap,
)

CONFIG_DEFAULT = {
    "motor_control": {
        "motor_x": "samx",
        "motor_y": "samy",
        "step_size_x": 3,
        "step_size_y": 50,
        "precision": 4,
        "step_x_y_same": False,
        "move_with_arrows": False,
    },
    "plot_settings": {
        "colormap": "Greys",
        "scatter_size": 5,
        "max_points": 1000,
        "num_dim_points": 100,
        "precision": 2,
        "num_columns": 1,
        "background_value": 25,
    },
    "motors": [
        {
            "plot_name": "Motor Map",
            "x_label": "Motor X",
            "y_label": "Motor Y",
            "signals": {
                "x": [{"name": "samx", "entry": "samx"}],
                "y": [{"name": "samy", "entry": "samy"}],
            },
        },
    ],
}


class MotorControlMap(QWidget):
    def __init__(self, parent=None, client=None, config=None):
        super().__init__(parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.config = config

        # Widgets
        self.motor_control_panel = MotorControlPanel(client=self.client, config=self.config)
        # Create MotorMap
        self.motion_map = MotorMap(client=self.client, config=self.config)

        # Create the splitter and add MotorMap and MotorControlPanel
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.motion_map)
        splitter.addWidget(self.motor_control_panel)

        # Set the main layout
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        self.setLayout(layout)


class MotorControlPanel(QWidget):
    def __init__(self, parent=None, client=None, config=None):
        super().__init__(parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.config = config

        self.motor_thread = MotorThread(client=self.client)

        self.selection_widget = MotorControlSelection(
            client=self.client, config=self.config, motor_thread=self.motor_thread
        )
        self.relative_widget = MotorControlRelative(
            client=self.client, config=self.config, motor_thread=self.motor_thread
        )
        self.absolute_widget = MotorControlAbsolute(
            client=self.client, config=self.config, motor_thread=self.motor_thread
        )

        layout = QVBoxLayout(self)

        layout.addWidget(self.selection_widget)
        layout.addWidget(self.relative_widget)
        layout.addWidget(self.absolute_widget)

        # Connecting signals and slots
        self.selection_widget.selected_motors_signal.connect(self.relative_widget.change_motors)
        self.selection_widget.selected_motors_signal.connect(self.absolute_widget.change_motors)

        # Set the window to a fixed size based on its contents
        self.layout().setSizeConstraint(layout.SetFixedSize)


class MotorControlPanelAbsolute(QWidget):
    def __init__(self, parent=None, client=None, config=None):
        super().__init__(parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.config = config

        self.motor_thread = MotorThread(client=self.client)

        self.selection_widget = MotorControlSelection(
            client=client, config=config, motor_thread=self.motor_thread
        )
        self.absolute_widget = MotorControlAbsolute(
            client=client, config=config, motor_thread=self.motor_thread
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.selection_widget)
        layout.addWidget(self.absolute_widget)

        # Connecting signals and slots
        self.selection_widget.selected_motors_signal.connect(self.absolute_widget.change_motors)

        # Set the window to a fixed size based on its contents
        self.layout().setSizeConstraint(layout.SetFixedSize)


class MotorControlPanelRelative(QWidget):
    def __init__(self, parent=None, client=None, config=None):
        super().__init__(parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.config = config

        self.motor_thread = MotorThread(client=self.client)

        self.selection_widget = MotorControlSelection(
            client=client, config=config, motor_thread=self.motor_thread
        )
        self.relative_widget = MotorControlRelative(
            client=client, config=config, motor_thread=self.motor_thread
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.selection_widget)
        layout.addWidget(self.relative_widget)

        # Connecting signals and slots
        self.selection_widget.selected_motors_signal.connect(self.relative_widget.change_motors)

        # Set the window to a fixed size based on its contents
        self.layout().setSizeConstraint(layout.SetFixedSize)


if __name__ == "__main__":
    bec_dispatcher = BECDispatcher()
    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    qdarktheme.setup_theme("auto")

    motor_control = MotorControlMap(client=client, config=CONFIG_DEFAULT)
    # motor_control = MotorControlPanel(client=client, config=CONFIG_DEFAULT)
    # motor_control = MotorControlPanelRelative(client=client, config=CONFIG_DEFAULT)
    # motor_control = MotorControlPanelAbsolute(client=client, config=CONFIG_DEFAULT)
    window = motor_control
    window.show()
    app.exec()
