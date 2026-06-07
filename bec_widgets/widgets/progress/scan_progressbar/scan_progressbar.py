from __future__ import annotations

import os

from bec_lib.logger import bec_logger
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import ProgressState
from bec_widgets.widgets.progress.progress_backend import BECProgressTracker, ProgressSnapshot

logger = bec_logger.logger

BEC_STATUS_TO_PROGRESS_STATE = {
    "open": ProgressState.NORMAL,
    "paused": ProgressState.PAUSED,
    "aborted": ProgressState.WARNING,
    "halted": ProgressState.INTERRUPTED,
    "closed": ProgressState.COMPLETED,
    "user_completed": ProgressState.COMPLETED,
}


class ScanProgressBar(BECWidget, QWidget):
    """
    Widget to display a progress bar that is hooked up to the scan progress of a scan.
    If you want to manually set the progress, it is recommended to use the BECProgressbar or QProgressbar directly.
    """

    ICON_NAME = "timelapse"
    PLUGIN = True
    progress_started = Signal()
    progress_finished = Signal()

    def __init__(
        self,
        parent=None,
        client=None,
        config=None,
        gui_id=None,
        one_line_design=False,
        enable_dynamic_stylesheet: bool = True,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)

        self.get_bec_shortcuts()
        ui_file = os.path.join(
            os.path.dirname(__file__),
            "scan_progressbar_one_line.ui" if one_line_design else "scan_progressbar.ui",
        )
        self.ui = UILoader(self).loader(ui_file)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.ui)
        self.setLayout(self.layout)
        self.progressbar = self.ui.progressbar
        self.progressbar.enable_dynamic_stylesheet = enable_dynamic_stylesheet
        self._show_elapsed_time = self.ui.elapsed_time_label.isVisible()
        self._show_remaining_time = self.ui.remaining_time_label.isVisible()
        self._show_source_label = self.ui.source_label.isVisible()

        self.progress_tracker = BECProgressTracker(self.bec_dispatcher, parent=self)
        self.progress_tracker.progress_started.connect(self._on_progress_started)
        self.progress_tracker.progress_updated.connect(self._on_progress_snapshot)
        self.progress_tracker.progress_finished.connect(
            lambda _snapshot: self.progress_finished.emit()
        )
        self.progress_tracker.start()

    def update_source_label(self):
        scan_number = self.progress_tracker.scan_number
        scan_text = f"Scan {scan_number}" if scan_number is not None else "Scan"
        if self.ui.source_label.text() == scan_text:
            return
        logger.info(f"Set progress source to {scan_text}")
        self.ui.source_label.setText(scan_text)

    def _on_progress_started(self, _snapshot: ProgressSnapshot):
        if self.progress_tracker.task is not None:
            self.progress_tracker.task.timer.timeout.connect(self.update_labels)
        self.progress_started.emit()

    def _on_progress_snapshot(self, snapshot: ProgressSnapshot):
        self.update_labels()
        if snapshot.is_new_scan and self.progress_tracker.task is None:
            self.ui.elapsed_time_label.setText("00:00:00")
            self.ui.remaining_time_label.setText("00:00:00")
        self.update_source_label()
        self.progressbar.set_maximum(snapshot.max_value)
        self.progressbar.set_value(snapshot.value)
        self.progressbar.state = BEC_STATUS_TO_PROGRESS_STATE.get(
            snapshot.status.lower(), ProgressState.NORMAL
        )

    @SafeProperty(bool)
    def show_elapsed_time(self):
        return self._show_elapsed_time

    @show_elapsed_time.setter
    def show_elapsed_time(self, value):
        self._show_elapsed_time = value
        self.ui.elapsed_time_label.setVisible(value)
        if hasattr(self.ui, "dash"):
            self.ui.dash.setVisible(value)

    @SafeProperty(bool)
    def show_remaining_time(self):
        return self._show_remaining_time

    @show_remaining_time.setter
    def show_remaining_time(self, value):
        self._show_remaining_time = value
        self.ui.remaining_time_label.setVisible(value)
        if hasattr(self.ui, "dash"):
            self.ui.dash.setVisible(value)

    @SafeProperty(bool)
    def show_source_label(self):
        return self._show_source_label

    @show_source_label.setter
    def show_source_label(self, value):
        self._show_source_label = value
        self.ui.source_label.setVisible(value)

    def update_labels(self):
        """
        Update the labels based on the progress task.
        """
        task = self.progress_tracker.task
        if task is None:
            return

        self.ui.elapsed_time_label.setText(task.time_elapsed)
        self.ui.remaining_time_label.setText(task.time_remaining)

    def cleanup(self):
        self.progress_tracker.cleanup()
        self.progressbar.close()
        self.progressbar.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    from qtpy.QtWidgets import QApplication

    bec_logger.disabled_modules = ["bec_lib"]
    app = QApplication([])

    widget = ScanProgressBar()
    widget.show()

    app.exec_()
