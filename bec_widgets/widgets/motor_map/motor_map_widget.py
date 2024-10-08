from __future__ import annotations

import sys

from bec_lib.device import ReadoutPriority
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.toolbar import DeviceSelectionAction, MaterialIconAction, ModularToolBar
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.motor_map.motor_map import MotorMapConfig
from bec_widgets.widgets.motor_map.motor_map_dialog.motor_map_settings import MotorMapSettings


class BECMotorMapWidget(BECWidget, QWidget):
    ICON_NAME = "my_location"
    USER_ACCESS = [
        "change_motors",
        "set_max_points",
        "set_precision",
        "set_num_dim_points",
        "set_background_value",
        "set_scatter_size",
        "get_data",
        "reset_history",
        "export",
    ]

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
                "motor_x": DeviceSelectionAction(
                    "Motor X:", DeviceComboBox(device_filter=[BECDeviceFilter.POSITIONER])
                ),
                "motor_y": DeviceSelectionAction(
                    "Motor Y:", DeviceComboBox(device_filter=[BECDeviceFilter.POSITIONER])
                ),
                "connect": MaterialIconAction(icon_name="link", tooltip="Connect Motors"),
                "history": MaterialIconAction(icon_name="history", tooltip="Reset Trace History"),
                "config": MaterialIconAction(
                    icon_name="settings", tooltip="Open Configuration Dialog"
                ),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.fig)

        self.map = self.fig.motor_map()
        self.map.apply_config(config)

        self._hook_actions()

        self.config = config

    def _hook_actions(self):
        self.toolbar.widgets["connect"].action.triggered.connect(self._action_motors)
        self.toolbar.widgets["config"].action.triggered.connect(self.show_settings)
        self.toolbar.widgets["history"].action.triggered.connect(self.reset_history)

        if self.map.motor_x is None and self.map.motor_y is None:
            self._enable_actions(False)

    def _enable_actions(self, enable: bool):
        self.toolbar.widgets["config"].action.setEnabled(enable)
        self.toolbar.widgets["history"].action.setEnabled(enable)

    def _action_motors(self):
        toolbar_x = self.toolbar.widgets["motor_x"].device_combobox
        toolbar_y = self.toolbar.widgets["motor_y"].device_combobox
        motor_x = toolbar_x.currentText()
        motor_y = toolbar_y.currentText()
        self.change_motors(motor_x, motor_y, None, None, True)
        toolbar_x.setStyleSheet("QComboBox {{ background-color: " "; }}")
        toolbar_y.setStyleSheet("QComboBox {{ background-color: " "; }}")

    def show_settings(self) -> None:
        dialog = SettingsDialog(
            self, settings_widget=MotorMapSettings(), window_title="Motor Map Settings"
        )
        dialog.exec()

    ###################################
    # User Access Methods from MotorMap
    ###################################

    def change_motors(
        self,
        motor_x: str,
        motor_y: str,
        motor_x_entry: str = None,
        motor_y_entry: str = None,
        validate_bec: bool = True,
    ) -> None:
        """
        Change the active motors for the plot.

        Args:
            motor_x(str): Motor name for the X axis.
            motor_y(str): Motor name for the Y axis.
            motor_x_entry(str): Motor entry for the X axis.
            motor_y_entry(str): Motor entry for the Y axis.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
        """
        self.map.change_motors(motor_x, motor_y, motor_x_entry, motor_y_entry, validate_bec)
        if self.map.motor_x is not None and self.map.motor_y is not None:
            self._enable_actions(True)
        toolbar_x = self.toolbar.widgets["motor_x"].device_combobox
        toolbar_y = self.toolbar.widgets["motor_y"].device_combobox

        if toolbar_x.currentText() != motor_x:
            toolbar_x.setCurrentText(motor_x)
            toolbar_x.setStyleSheet("QComboBox {{ background-color: " "; }}")
        if toolbar_y.currentText() != motor_y:
            toolbar_y.setCurrentText(motor_y)
            toolbar_y.setStyleSheet("QComboBox {{ background-color: " "; }}")

    def get_data(self) -> dict:
        """
        Get the data of the motor map.

        Returns:
            dict: Data of the motor map.
        """
        return self.map.get_data()

    def reset_history(self) -> None:
        """
        Reset the history of the motor map.
        """
        self.map.reset_history()

    def set_color(self, color: str | tuple):
        """
        Set the color of the motor map.

        Args:
            color(str, tuple): Color to set.
        """
        self.map.set_color(color)

    def set_max_points(self, max_points: int) -> None:
        """
        Set the maximum number of points to display on the motor map.

        Args:
            max_points(int): Maximum number of points to display.
        """
        self.map.set_max_points(max_points)

    def set_precision(self, precision: int) -> None:
        """
        Set the precision of the motor map.

        Args:
            precision(int): Precision to set.
        """
        self.map.set_precision(precision)

    def set_num_dim_points(self, num_dim_points: int) -> None:
        """
        Set the number of points to display on the motor map.

        Args:
            num_dim_points(int): Number of points to display.
        """
        self.map.set_num_dim_points(num_dim_points)

    def set_background_value(self, background_value: int) -> None:
        """
        Set the background value of the motor map.

        Args:
            background_value(int): Background value of the motor map.
        """
        self.map.set_background_value(background_value)

    def set_scatter_size(self, scatter_size: int) -> None:
        """
        Set the scatter size of the motor map.

        Args:
            scatter_size(int): Scatter size of the motor map.
        """
        self.map.set_scatter_size(scatter_size)

    def export(self):
        """
        Show the export dialog for the motor map.
        """
        self.map.export()

    def cleanup(self):
        self.fig.cleanup()
        self.toolbar.widgets["motor_x"].device_combobox.cleanup()
        self.toolbar.widgets["motor_y"].device_combobox.cleanup()
        return super().cleanup()


def main():  # pragma: no cover
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECMotorMapWidget()
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
