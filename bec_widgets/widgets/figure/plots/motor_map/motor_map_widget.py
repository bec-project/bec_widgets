import os

from qtpy.QtCore import QSize, Slot
from qtpy.QtGui import QAction, QIcon
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils import BECConnector
from bec_widgets.widgets.device_inputs import DeviceComboBox
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.motor_map.motor_map import MotorMapConfig
from bec_widgets.widgets.toolbar import ModularToolBar
from bec_widgets.widgets.toolbar.toolbar import ToolBarAction


class SettingsAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        icon = QIcon()
        icon.addFile(os.path.join(current_path, "assets", "settings.svg"), size=QSize(20, 20))
        action = QAction(icon, "Config", target)
        action.triggered.connect(lambda: print(target.config_dict))
        toolbar.addAction(action)


class DeviceSelectionAction(ToolBarAction):
    def __init__(self, label: str):
        self.label = label
        self.device_combobox = DeviceComboBox(device_filter="Positioner")

    def add_to_toolbar(self, toolbar, target):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        label = QLabel(f"{self.label}")

        layout.addWidget(label)
        layout.addWidget(self.device_combobox)
        toolbar.addWidget(widget)


class ConnectAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        icon = QIcon()
        icon.addFile(os.path.join(current_path, "assets", "connection.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Connect Motors", target)
        toolbar.addAction(self.action)


class BECMotorMapWidget(BECConnector, QWidget):
    USER_ACCESS = []

    def __init__(
        self,
        parent: QWidget | None = None,
        config: MotorMapConfig | None = None,
        client=None,
        gui_id: str | None = None,
    ) -> None:
        if config is None:
            config = MotorMapConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = MotorMapConfig(**config)
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.fig = BECFigure()
        self.toolbar = ModularToolBar(
            actions={
                "motor_x": DeviceSelectionAction("Motor X:"),
                "motor_y": DeviceSelectionAction("Motor Y:"),
                "connect": ConnectAction(),
                "config": SettingsAction(),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.fig)

        self.map = self.fig.motor_map()
        self.map.apply_config(config)

        self.config = config

        self._hook_actions()

    def _hook_actions(self):
        self.toolbar.widgets["connect"].action.triggered.connect(self.pass_motors)

    def pass_motors(self):
        motor_x = self.toolbar.widgets["motor_x"].device_combobox.currentText()
        motor_y = self.toolbar.widgets["motor_y"].device_combobox.currentText()
        self.change_motors(motor_x, motor_y)

    @Slot(str, str)
    def change_motors(self, motor_x, motor_y):
        self.map.change_motors(motor_x, motor_y)

    def set(self, **kwargs):
        self.map.set(**kwargs)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECMotorMapWidget()
    widget.show()
    sys.exit(app.exec_())
