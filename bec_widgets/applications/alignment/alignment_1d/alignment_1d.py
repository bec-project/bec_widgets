""" This module contains the GUI for the 1D alignment application.
It is a preliminary version of the GUI, which will be added to the main branch and steadily updated to be improved.
"""

import os
from typing import Optional

from bec_lib.device import Signal as BECSignal
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import bec_widgets
from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.control.device_control.positioner_group import PositionerGroup
from bec_widgets.widgets.dap.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.plots.waveform import BECWaveformWidget
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import BECProgressBar

MODULE_PATH = os.path.dirname(bec_widgets.__file__)
logger = bec_logger.logger


class Alignment1D:
    """Alignment GUI to perform 1D scans"""

    def __init__(self, client=None, gui_id: Optional[str] = None) -> None:
        """Initialization

        Args:
            config: Configuration of the application.
            client: BEC client object.
            gui_id: GUI ID.
        """
        self.bec_dispatcher = BECDispatcher(client=client)
        self.client = self.bec_dispatcher.client if client is None else client
        QApplication.instance().aboutToQuit.connect(self.close)
        self.dev = self.client.device_manager.devices

        self._accent_colors = get_accent_colors()
        self.ui_file = "alignment_1d.ui"
        self.ui = None
        self.progress_bar = None
        self.waveform = None
        self.init_ui()

    def init_ui(self):
        """Initialise the UI from QT Designer file"""
        current_path = os.path.dirname(__file__)
        self.ui = UILoader(None).loader(os.path.join(current_path, self.ui_file))
        # Customize the plotting widget
        self.waveform = self.ui.findChild(BECWaveformWidget, "bec_waveform_widget")
        self._customise_bec_waveform_widget()
        # Setup comboboxes for motor and signal selection
        # FIXME after changing the filtering in the combobox
        self._setup_signal_combobox()
        # Setup motor indicator
        self._setup_motor_indicator()
        # Setup progress bar
        self._setup_progress_bar()
        # Add actions buttons
        self._customise_buttons()
        # Hook scaninfo updates
        self.bec_dispatcher.connect_slot(self.scan_status_callback, MessageEndpoints.scan_status())

    def show(self):
        return self.ui.show()

    ##############################
    ############ SLOTS ###########
    ##############################

    @Slot(dict, dict)
    def scan_status_callback(self, content: dict, _) -> None:
        """This slot allows to enable/disable the UI critical components when a scan is running"""
        if content["status"] in ["open"]:
            self.enable_ui(False)
        elif content["status"] in ["aborted", "halted", "closed"]:
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
        self.ui.device_combobox_2.setEnabled(enable)
        # Enable/disable DAP selection
        self.ui.dap_combo_box.setEnabled(enable)
        # Enable/disable Scan Button
        # self.ui.scan_button.setEnabled(enable)
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
        stop_button = self.ui.findChild(StopButton)
        stop_button.button.setText("Stop and Clear Queue")
        stop_button.button.clicked.connect(self.clear_queue)

    def _customise_bec_waveform_widget(self) -> None:
        """Customise the BEC Waveform Widget, i.e. clear the toolbar"""
        self.waveform.toolbar.clear()

    def _setup_motor_indicator(self) -> None:
        """Setup the arrow item"""
        self.waveform.waveform.tick_item.add_to_plot()
        positioner_box = self.ui.findChild(PositionerGroup)
        positioner_box.position_update.connect(self.waveform.waveform.tick_item.set_position)
        self.waveform.waveform.tick_item.set_position(0)

    def _setup_signal_combobox(self) -> None:
        """Setup signal selection"""
        # FIXME after changing the filtering in the combobox
        signals = [name for name in self.dev if isinstance(self.dev.get(name), BECSignal)]
        self.ui.device_combobox_2.setCurrentText(signals[0])
        self.ui.device_combobox_2.set_device_filter("Signal")

    def _setup_progress_bar(self) -> None:
        """Setup progress bar"""
        # FIXME once the BECScanProgressBar is implemented
        self.progress_bar = self.ui.findChild(BECProgressBar, "bec_progress_bar")
        self.progress_bar.set_value(0)
        self.ui.bec_waveform_widget.new_scan.connect(self.reset_progress_bar)
        self.bec_dispatcher.connect_slot(self.update_progress_bar, MessageEndpoints.scan_progress())

    def close(self):
        logger.info("Disconnecting", repr(self.bec_dispatcher))
        self.bec_dispatcher.disconnect_all()
        logger.info("Shutting down BEC Client", repr(self.client))
        self.client.shutdown()


def main():
    import sys

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
