from __future__ import annotations

import enum
import os
import time

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QObject, QTimer, Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.ui_loader import UILoader

logger = bec_logger.logger


class ProgressSource(enum.Enum):
    """
    Enum to define the source of the progress.
    """

    SCAN_PROGRESS = "scan_progress"
    DEVICE_PROGRESS = "device_progress"


class ProgressTask(QObject):
    """
    Class to store progress information.
    Inspired by https://github.com/Textualize/rich/blob/master/rich/progress.py
    """

    def __init__(self, value: float = 0, max_value: float = 0, done: bool = False):
        super().__init__()
        self.start_time = time.time()
        self.done = done
        self.value = value
        self.max_value = max_value
        self._elapsed_time = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed_time)
        self.timer.start(100)

    def update(self, value: float, max_value: float, done: bool = False):
        """
        Update the progress.
        """
        self.max_value = max_value
        self.done = done
        self.value = value
        if done:
            self.timer.stop()

    def update_elapsed_time(self):
        """
        Update the time estimates.
        """
        self._elapsed_time += 0.1

    @property
    def percentage(self) -> float:
        """float: Get progress of task as a percentage. If a None total was set, returns 0"""
        if not self.max_value:
            return 0.0
        completed = (self.value / self.max_value) * 100.0
        completed = min(100.0, max(0.0, completed))
        return completed

    @property
    def speed(self) -> float:
        """Get the estimated speed in steps per second."""
        if self._elapsed_time == 0:
            return 0.0

        return self.value / self._elapsed_time

    @property
    def frequency(self) -> float:
        """Get the estimated frequency in steps per second."""
        return 1 / self.speed

    @property
    def time_elapsed(self) -> str:
        # format the elapsed time to a string in the format HH:MM:SS
        return self._format_time(int(self._elapsed_time))

    @property
    def remaining(self) -> float:
        """Get the estimated remaining steps."""
        if self.done:
            return 0.0
        remaining = self.max_value - self.value
        return remaining

    @property
    def time_remaining(self) -> str:
        """
        Get the estimated remaining time in the format HH:MM:SS.
        """
        if self.done or not self.speed or not self.remaining:
            return self._format_time(0)
        estimate = int(np.round(self.remaining / self.speed))

        return self._format_time(estimate)

    def _format_time(self, seconds: float) -> str:
        """
        Format the time in seconds to a string in the format HH:MM:SS.
        """
        return f"{seconds // 3600:02}:{(seconds // 60) % 60:02}:{seconds % 60:02}"


class ScanProgressBar(BECWidget, QWidget):
    """
    Widget to display a progress bar that is hooked up to the scan progress of a scan.
    If you want to manually set the progress, it is recommended to use the QProgressBar directly.
    """

    ICON_NAME = "timelapse"

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        self.get_bec_shortcuts()
        ui_file = os.path.join(os.path.dirname(__file__), "scan_progressbar.ui")
        self.ui = UILoader(self).loader(ui_file)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.ui)
        self.setLayout(self.layout)
        self.progressbar = self.ui.progressbar

        self.connect_to_queue()
        self._progress_source = None
        self.task = None
        self.scan_number = None

    def connect_to_queue(self):
        """
        Connect to the queue status signal.
        """
        self.bec_dispatcher.connect_slot(self.on_queue_update, MessageEndpoints.scan_queue_status())

    def set_progress_source(self, source: ProgressSource, device=None):
        """
        Set the source of the progress.
        """
        if self._progress_source == source:
            self.update_source_label(source, device=device)
            return
        if self._progress_source is not None:
            self.bec_dispatcher.disconnect_slot(
                self.on_progress_update,
                (
                    MessageEndpoints.scan_progress()
                    if self._progress_source == ProgressSource.SCAN_PROGRESS
                    else MessageEndpoints.device_progress(device=device)
                ),
            )
        self._progress_source = source
        self.bec_dispatcher.connect_slot(
            self.on_progress_update,
            (
                MessageEndpoints.scan_progress()
                if source == ProgressSource.SCAN_PROGRESS
                else MessageEndpoints.device_progress(device=device)
            ),
        )
        self.update_source_label(source, device=device)

    def update_source_label(self, source: ProgressSource, device=None):
        scan_text = f"Scan {self.scan_number}" if self.scan_number is not None else "Scan"
        text = scan_text if source == ProgressSource.SCAN_PROGRESS else f"Device {device}"
        logger.info(f"Set progress source to {text}")
        self.ui.source_label.setText(text)

    def on_progress_update(self, msg_content, metadata):
        """
        Update the progress bar based on the progress message.
        """
        value = msg_content["value"]
        max_value = msg_content.get("max_value", 100)
        done = msg_content.get("done", False)

        if self.task is None:
            return
        self.task.update(value, max_value, done)

        self.update_labels()

        self.progressbar.set_maximum(self.task.max_value)
        if done:
            self.progressbar.set_value(self.task.max_value)
            self.task = None
            return

        self.progressbar.set_value(self.task.value)

    @Property(bool)
    def show_elapsed_time(self):
        return self.ui.elapsed_time_label.isVisible()

    @show_elapsed_time.setter
    def show_elapsed_time(self, value):
        self.ui.elapsed_time_label.setVisible(value)

    @Property(bool)
    def show_remaining_time(self):
        return self.ui.remaining_time_label.isVisible()

    @show_remaining_time.setter
    def show_remaining_time(self, value):
        self.ui.remaining_time_label.setVisible(value)

    @Property(bool)
    def show_source_label(self):
        return self.ui.source_label.isVisible()

    @show_source_label.setter
    def show_source_label(self, value):
        self.ui.source_label.setVisible(value)

    def update_labels(self):
        """
        Update the labels based on the progress task.
        """
        if self.task is None:
            return

        self.ui.elapsed_time_label.setText(self.task.time_elapsed)
        self.ui.remaining_time_label.setText(self.task.time_remaining)

    @Slot(dict, dict)
    def on_queue_update(self, msg_content, metadata):
        """
        Update the progress bar based on the queue status.
        """
        if not "queue" in msg_content:
            return
        primary_queue_info = msg_content["queue"].get("primary", {}).get("info", [])
        if len(primary_queue_info) == 0:
            return
        scan_info = primary_queue_info[0]
        if scan_info is None:
            return
        if scan_info.get("status").lower() == "running" and self.task is None:
            self.task = ProgressTask()

        active_request_block = scan_info.get("active_request_block", {})
        if active_request_block is None:
            return

        self.scan_number = active_request_block.get("scan_number")
        report_instructions = active_request_block.get("report_instructions", [])
        if not report_instructions:
            return

        # for now, let's just use the first instruction
        instruction = report_instructions[0]

        if "scan_progress" in instruction:
            self.set_progress_source(ProgressSource.SCAN_PROGRESS)
        elif "device_progress" in instruction:
            device = instruction["device_progress"][0]
            self.set_progress_source(ProgressSource.DEVICE_PROGRESS, device=device)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    bec_logger.disabled_modules = ["bec_lib"]
    app = QApplication([])

    widget = ScanProgressBar()
    widget.show()

    app.exec_()
