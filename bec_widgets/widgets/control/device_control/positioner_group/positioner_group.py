""" Module for a PositionerGroup widget to control a positioner device."""

from __future__ import annotations

from bec_lib.device import Positioner
from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize, Signal
from qtpy.QtWidgets import QGridLayout, QGroupBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox

logger = bec_logger.logger


class PositionerGroupBox(QGroupBox):
    PLUGIN = True
    position_update = Signal(float)

    def __init__(self, parent, dev_name):
        super().__init__(parent)

        self.device_name = dev_name

        QVBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.widget = PositionerBox(self, dev_name)
        self.widget.compact_view = True
        self.widget.expand_popup = False
        self.layout().addWidget(self.widget)
        self.widget.position_update.connect(self._on_position_update)
        self.widget.expand.connect(self._on_expand)
        self.setTitle(self.device_name)
        self.widget.force_update_readback()

    def _on_expand(self, expand):
        if expand:
            self.setTitle("")
            self.setFlat(True)
        else:
            self.setTitle(self.device_name)
            self.setFlat(False)

    def _on_position_update(self, pos: float):
        self.position_update.emit(pos)
        self.widget.label = f"%.{self.widget.dev[self.widget.device].precision}f" % pos

    def close(self):
        self.widget.close()
        super().close()


class PositionerGroup(BECWidget, QWidget):
    """Simple Widget to control a positioner in box form"""

    ICON_NAME = "grid_view"
    USER_ACCESS = ["set_positioners"]

    # Signal emitted to inform listeners about a position update of the first positioner
    position_update = Signal(float)
    # Signal emitted to inform listeners about (positioner, pos) updates
    device_position_update = Signal(str, float)

    def __init__(self, parent=None, **kwargs):
        """Initialize the widget.

        Args:
            parent: The parent widget.
        """
        super().__init__(**kwargs)
        QWidget.__init__(self, parent)

        self.get_bec_shortcuts()

        QGridLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self._device_widgets = {}
        self._grid_ncols = 2

    def minimumSizeHint(self):
        return QSize(300, 30)

    @SafeSlot(str)
    def set_positioners(self, device_names: str):
        """Redraw grid with positioners from device_names string

        Device names must be separated by space
        """
        devs = device_names.split()
        for dev_name in devs:
            if not self._check_device_is_valid(dev_name):
                raise ValueError(f"{dev_name} is not a valid Positioner")
        for i, existing_widget in enumerate(self._device_widgets.values()):
            self.layout().removeWidget(existing_widget)
            existing_widget.position_update.disconnect(self._on_position_update)
            if i == 0:
                existing_widget.position_update.disconnect(self.position_update)
        for i, dev_name in enumerate(devs):
            widget = self._device_widgets.get(dev_name)
            if widget is None:
                widget = PositionerGroupBox(self, dev_name)
                self._device_widgets[dev_name] = widget
                widget.position_update.connect(self._on_position_update)
                if i == 0:
                    # only emit 'position_update' for the first positioner in grid
                    widget.position_update.connect(self.position_update)
            self.layout().addWidget(widget, i // self._grid_ncols, i % self._grid_ncols)
        to_remove = set(self._device_widgets) - set(devs)
        for dev_name in to_remove:
            self._device_widgets[dev_name].close()
            del self._device_widgets[dev_name]

    def _check_device_is_valid(self, device: str):
        """Check if the device is a positioner

        Args:
            device (str): The device name
        """
        if device not in self.dev:
            logger.info(f"Device {device} not found in the device list")
            return False
        if not isinstance(self.dev[device], Positioner):
            logger.info(f"Device {device} is not a positioner")
            return False
        return True

    def _on_position_update(self, pos: float):
        widget = self.sender()
        self.device_position_update.emit(widget.title(), pos)

    @SafeProperty(str)
    def devices_list(self):
        """Device names string separated by space"""
        return " ".join(self._device_widgets)

    @devices_list.setter
    def devices_list(self, device_names: str):
        """Set devices list from device names string separated by space"""
        devs = device_names.split()
        for dev_name in devs:
            if not self._check_device_is_valid(dev_name):
                return
        self.set_positioners(device_names)

    @SafeProperty(int)
    def grid_max_cols(self):
        """Max number of columns for widgets grid"""
        return self._grid_ncols

    @grid_max_cols.setter
    def grid_max_cols(self, ncols: int):
        """Set max number of columns for widgets grid"""
        self._grid_ncols = ncols
        self.set_positioners(self.devices_list)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    widget = PositionerGroup()
    widget.grid_max_cols = 3
    widget.set_positioners("samx samy samz")

    widget.show()
    sys.exit(app.exec_())
