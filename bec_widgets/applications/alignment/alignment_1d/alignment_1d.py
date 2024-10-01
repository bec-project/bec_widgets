""" This module contains the GUI for the 1D alignment application.
It is a preliminary version of the GUI, which will be added to the main branch and steadily updated to be improved.
"""

import os
from typing import Optional

from bec_lib.device import Positioner as BECPositioner
from bec_lib.device import Signal as BECSignal
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QSize, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QPushButton, QSpinBox, QVBoxLayout, QWidget

import bec_widgets
from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.qt_utils.toolbar import WidgetAction
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.bec_progressbar.bec_progressbar import BECProgressBar
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit
from bec_widgets.widgets.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.positioner_box.positioner_box import PositionerBox
from bec_widgets.widgets.stop_button.stop_button import StopButton
from bec_widgets.widgets.toggle.toggle import ToggleSwitch
from bec_widgets.widgets.waveform.waveform_widget import BECWaveformWidget

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class Alignment1D(BECWidget, QWidget):
    """Alignment GUI to perform 1D scans"""

    # Emit a signal when a motion is ongoing
    motion_is_active = Signal(bool)

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
        self._accent_colors = get_accent_colors()
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
        # Customize the plotting widget
        self.waveform = self.ui.findChild(BECWaveformWidget, "bec_waveform_widget")
        self._customise_bec_waveform_widget()
        # Setup comboboxes for motor and signal selection
        # FIXME after changing the filtering in the combobox
        self._setup_motor_combobox()
        self._setup_signal_combobox()
        # Setup motor indicator
        self._setup_motor_indicator()
        # Connect spinboxes to scan Control
        self._setup_scan_control()
        # Setup progress bar
        self._setup_progress_bar()
        # Add actions buttons
        self._customise_buttons()
        # Customize the positioner box
        self._customize_positioner_box()
        # Hook scaninfo updates
        self.bec_dispatcher.connect_slot(self.scan_status_callback, MessageEndpoints.scan_status())

    ##############################
    ############ SLOTS ###########
    ##############################

    @Slot(dict, dict)
    def scan_status_callback(self, content: dict, _) -> None:
        """This slot allows to enable/disable the UI critical components when a scan is running"""
        if content["status"] in ["open"]:
            self.motion_is_active.emit(True)
            self.enable_ui(False)
        elif content["status"] in ["aborted", "halted", "closed"]:
            self.motion_is_active.emit(False)
            self.enable_ui(True)

    @Slot(tuple)
    def move_to_center(self, move_request: tuple) -> None:
        """Move the selected motor to the center"""
        motor = self.ui.device_combobox.currentText()
        if move_request[0] in ["center", "center1", "center2"]:
            pos = move_request[1]
        self.dev.get(motor).move(float(pos), relative=False)

    @Slot()
    def reset_progress_bar(self) -> None:
        """Reset the progress bar"""
        self.progress_bar.set_value(0)
        self.progress_bar.set_minimum(0)

    @Slot(dict, dict)
    def update_progress_bar(self, content: dict, _) -> None:
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

    @Slot()
    def clear_queue(self) -> None:
        """Clear the scan queue"""
        self.queue.request_queue_reset()

    ##############################
    ######## END OF SLOTS ########
    ##############################

    def enable_ui(self, enable: bool) -> None:
        """Enable or disable the UI components"""
        # Enable/disable motor and signal selection
        self.ui.device_combobox.setEnabled(enable)
        self.ui.device_combobox_2.setEnabled(enable)
        # Enable/disable DAP selection
        self.ui.dap_combo_box.setEnabled(enable)
        # Enable/disable Scan Button
        self.ui.scan_button.setEnabled(enable)
        # Positioner control line
        # pylint: disable=protected-access
        self.ui.positioner_box._toogle_enable_buttons(enable)
        # Disable move to buttons in LMFitDialog
        self.ui.findChild(LMFitDialog).set_actions_enabled(enable)

    def _customise_buttons(self) -> None:
        """Add action buttons for the Action Control.
        In addition, we are adding a callback to also clear the queue to the stop button
        to ensure that upon clicking the button, no scans from another client may be queued
        which would be confusing without the queue widget.
        """
        fit_dialog = self.ui.findChild(LMFitDialog)
        fit_dialog.active_action_list = ["center", "center1", "center2"]
        fit_dialog.move_action.connect(self.move_to_center)
        scan_button = self.ui.findChild(QPushButton, "scan_button")
        scan_button.setStyleSheet(
            f"""
            QPushButton:enabled {{ background-color: {self._accent_colors.success.name()};color: white; }}
            QPushButton:disabled {{ background-color: grey;color: white; }}
            """
        )
        stop_button = self.ui.findChild(StopButton)
        stop_button.button.setText("Stop and Clear Queue")
        stop_button.button.clicked.connect(self.clear_queue)

    def _customise_bec_waveform_widget(self) -> None:
        """Customise the BEC Waveform Widget, i.e. clear the toolbar, add the DAP ROI selection to the toolbar.
        We also move the scan_control widget which is fully hidden and solely used for setting up the scan parameters to the toolbar.
        """
        self.waveform.toolbar.clear()
        toggle_switch = self.ui.findChild(ToggleSwitch, "toggle_switch")
        scan_control = self.ui.scan_control
        self.waveform.toolbar.populate_toolbar(
            {
                "label": WidgetAction(label="ENABLE DAP ROI", widget=toggle_switch),
                "scan_control": WidgetAction(widget=scan_control),
            },
            self.waveform,
        )

    def _setup_motor_indicator(self) -> None:
        """Setup the arrow item"""
        self.waveform.waveform.tick_item.add_to_plot()
        positioner_box = self.ui.findChild(PositionerBox)
        positioner_box.position_update.connect(self.waveform.waveform.tick_item.set_position)
        try:
            pos = float(positioner_box.ui.readback.text())
        except ValueError:
            pos = 0
        self.waveform.waveform.tick_item.set_position(pos)

    def _setup_motor_combobox(self) -> None:
        """Setup motor selection"""
        # FIXME after changing the filtering in the combobox
        motors = [name for name in self.dev if isinstance(self.dev.get(name), BECPositioner)]
        self.ui.device_combobox.setCurrentText(motors[0])
        self.ui.device_combobox.set_device_filter("Positioner")

    def _setup_signal_combobox(self) -> None:
        """Setup signal selection"""
        # FIXME after changing the filtering in the combobox
        signals = [name for name in self.dev if isinstance(self.dev.get(name), BECSignal)]
        self.ui.device_combobox_2.setCurrentText(signals[0])
        self.ui.device_combobox_2.set_device_filter("Signal")

    def _setup_scan_control(self) -> None:
        """Setup scan control, connect spin and check boxes to the scan_control widget"""
        # Connect motor
        device_line_edit = self.ui.scan_control.arg_box.findChild(DeviceLineEdit)
        self.ui.device_combobox.currentTextChanged.connect(device_line_edit.setText)
        device_line_edit.setText(self.ui.device_combobox.currentText())
        # Connect start, stop, step, exp_time and relative check box
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
        self.ui.bec_waveform_widget.new_scan.connect(self.reset_progress_bar)
        self.bec_dispatcher.connect_slot(self.update_progress_bar, MessageEndpoints.scan_progress())

    def _customize_positioner_box(self) -> None:
        """Customize the positioner Box, i.e. remove the stop button"""
        box = self.ui.findChild(PositionerBox)
        box.ui.stop.setVisible(False)
        box.ui.position_indicator.setFixedHeight(20)


def main():
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    icon = QIcon()
    icon.addFile(
        os.path.join(MODULE_PATH, "assets", "app_icons", "alignment_1d.png"), size=QSize(48, 48)
    )
    app.setWindowIcon(icon)
    window = Alignment1D()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
