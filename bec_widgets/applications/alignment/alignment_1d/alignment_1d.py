""" This module contains the GUI for the 1D alignment application.
#TODO at this stage it is a preliminary version of the GUI, which will be added to the main branch although it is not yet fully functional.
It is a work in progress and will be updated in the future.
"""

import os
from typing import Optional

from bec_lib.device import Positioner, Signal
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QSpinBox, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.qt_utils.toolbar import WidgetAction
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.bec_progressbar.bec_progressbar import BECProgressBar
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit
from bec_widgets.widgets.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.positioner_box.positioner_control_line import PositionerControlLine
from bec_widgets.widgets.toggle.toggle import ToggleSwitch
from bec_widgets.widgets.waveform.waveform_widget import BECWaveformWidget


class Alignment1D(BECWidget, QWidget):
    """GUI for 1D alignment"""

    motion_is_active = pyqtSignal(bool)

    def __init__(
        self, parent: Optional[QWidget] = None, client=None, gui_id: Optional[str] = None
    ) -> None:
        """Initialise the widget

        Args:
            parent: Parent widget.
            config: Configuration of the widget.
            client: BEC client object.
            gui_id: GUI ID.
        """
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)
        self.get_bec_shortcuts()
        self.ui_file = "alignment_1d.ui"
        self.ui = None
        self.progress_bar = None
        self.waveform = None
        self.init_ui()

    def init_ui(self):
        """Initialise the UI from QT Designer file"""

        current_path = os.path.dirname(__file__)
        self.ui = UILoader(self).loader(os.path.join(current_path, self.ui_file))
        layout = QVBoxLayout(self)
        layout.addWidget(self.ui)
        self.setLayout(layout)
        self.waveform = self.ui.findChild(BECWaveformWidget, "bec_waveform_widget")
        # Customize the plotting widget
        self._customise_bec_waveform_widget()
        # Setup filters for comboboxes
        self._setup_motor_combobox()
        self._setup_signal_combobox()
        # Setup arrow item
        self._setup_arrow_item()
        # Setup Scan Control
        self._setup_scan_control()
        # Setup progress bar
        self._setup_progress_bar()
        # Add actions buttons
        self._add_action_buttons()
        # Hook scaninfo updates
        self.bec_dispatcher.connect_slot(self._scan_status_callback, MessageEndpoints.scan_status())

    ##############################
    ############ SLOTS ###########
    ##############################

    @Slot(dict, dict)
    def _scan_status_callback(self, content: dict, metadata: dict) -> None:
        """This slot allows to enable/disable the UI critical components when a scan is running"""
        if content["status"] in ["running", "open"]:
            self.motion_is_active.emit(True)
            self._enable_ui(False)
        elif content["status"] in ["aborted", "halted", "closed"]:
            self.motion_is_active.emit(False)
            self._enable_ui(True)

    @Slot(float)
    def move_to_center(self, pos: float) -> None:
        """Move the selected motor to the center"""
        motor = self.ui.device_combobox.currentText()
        self.dev[motor].move(float(pos), relative=False)

    @Slot()
    def _reset_progress_bar(self) -> None:
        """Reset the progress bar"""
        self.progress_bar.set_value(0)
        self.progress_bar.set_minimum(0)

    @Slot(dict, dict)
    def _update_progress_bar(self, content: dict, metadata: dict) -> None:
        """Hook to update the progress bar

        Args:
            content: Content of the scan progress message.
            metadata: Metadata of the message.
        """
        if content["max_value"] == 0:
            self.progress_bar.set_value(0)
            return
        self.progress_bar.set_maximum(content["max_value"])
        self.progress_bar.set_value(content["value"])

    ##############################
    ######## END OF SLOTS ########
    ##############################

    def _enable_ui(self, enable: bool) -> None:
        """Enable or disable the UI components"""
        # Device selection comboboxes
        self.ui.device_combobox.setEnabled(enable)
        self.ui.device_combobox_2.setEnabled(enable)
        self.ui.dap_combo_box.setEnabled(enable)
        # Scan button
        self.ui.scan_button.setEnabled(enable)
        # Positioner control line
        # pylint: disable=protected-access
        self.ui.positioner_control_line._toogle_enable_buttons(enable)
        # Send report to scilog
        self.ui.button_send_summary_scilog.setEnabled(enable)
        # Disable move to buttons in LMFitDialog
        self.ui.findChild(LMFitDialog).set_enable_move_to_buttons(enable)

    def _add_action_buttons(self) -> None:
        """Add action buttons for the Action Control"""
        fit_dialog = self.ui.findChild(LMFitDialog)
        fit_dialog.update_activated_button_list(["center", "center1", "center2"])
        fit_dialog.move_to_position.connect(self.move_to_center)

    def _customise_bec_waveform_widget(self) -> None:
        """Customise the BEC Waveform Widget, i.e. hide toolbar buttons except roi selection"""
        for button in self.waveform.toolbar.widgets.values():
            if getattr(button, "action", None) is not None:
                button.action.setVisible(False)
        self.waveform.toolbar.widgets["roi_select"].action.setVisible(True)
        toggle_switch = self.ui.findChild(ToggleSwitch, "toggle_switch")
        scan_control = self.ui.scan_control
        self.waveform.toolbar.populate_toolbar(
            {
                "label": WidgetAction(label="Enable DAP ROI", widget=toggle_switch),
                "scan_control": WidgetAction(widget=scan_control),
            },
            self.waveform,
        )

    def _setup_arrow_item(self) -> None:
        """Setup the arrow item"""
        self.waveform.waveform.motor_pos_tick.add_to_plot()
        positioner_line = self.ui.findChild(PositionerControlLine)
        positioner_line.position_update.connect(self.waveform.waveform.motor_pos_tick.set_position)
        try:
            pos = float(positioner_line.ui.readback.text())
        except ValueError:
            pos = 0
        self.waveform.waveform.motor_pos_tick.set_position(pos)

    def _setup_motor_combobox(self) -> None:
        """Setup motor selection"""
        # FIXME after changing the filtering in the combobox
        motors = [name for name in self.dev if isinstance(self.dev.get(name), Positioner)]
        self.ui.device_combobox.setCurrentText(motors[0])
        self.ui.device_combobox.set_device_filter("Positioner")

    def _setup_signal_combobox(self) -> None:
        """Setup signal selection"""
        # FIXME after changing the filtering in the combobox
        signals = [name for name in self.dev if isinstance(self.dev.get(name), Signal)]
        self.ui.device_combobox_2.setCurrentText(signals[0])
        self.ui.device_combobox_2.set_device_filter("Signal")

    def _setup_scan_control(self) -> None:
        """Setup scan control, connect spin and check boxes to the scan_control widget"""
        device_line_edit = self.ui.scan_control.arg_box.findChild(DeviceLineEdit)
        self.ui.device_combobox.currentTextChanged.connect(device_line_edit.setText)
        device_line_edit.setText(self.ui.device_combobox.currentText())
        spin_boxes = self.ui.scan_control.arg_box.findChildren(QDoubleSpinBox)
        start = self.ui.findChild(QDoubleSpinBox, "linescan_start")
        start.valueChanged.connect(spin_boxes[0].setValue)
        stop = self.ui.findChild(QDoubleSpinBox, "linescan_stop")
        stop.valueChanged.connect(spin_boxes[1].setValue)
        step = self.ui.findChild(QSpinBox, "linescan_step")
        step.valueChanged.connect(
            self.ui.scan_control.kwarg_boxes[0].findChildren(QSpinBox)[0].setValue
        )
        exp_time = self.ui.findChild(QDoubleSpinBox, "linescan_exp_time")
        exp_time.valueChanged.connect(
            self.ui.scan_control.kwarg_boxes[1].findChildren(QDoubleSpinBox)[0].setValue
        )
        relative = self.ui.findChild(QCheckBox, "linescan_relative")
        relative.toggled.connect(
            self.ui.scan_control.kwarg_boxes[0].findChildren(QCheckBox)[0].setChecked
        )

    def _setup_progress_bar(self) -> None:
        """Setup progress bar"""
        # FIXME once the BECScanProgressBar is implemented
        self.progress_bar = self.ui.findChild(BECProgressBar, "bec_progress_bar")
        self.progress_bar.set_value(0)
        self.ui.bec_waveform_widget.new_scan.connect(self._reset_progress_bar)
        self.bec_dispatcher.connect_slot(
            self._update_progress_bar, MessageEndpoints.scan_progress()
        )


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = Alignment1D()
    window.show()
    sys.exit(app.exec_())
