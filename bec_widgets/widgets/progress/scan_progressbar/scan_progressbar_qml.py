"""Scan progress bar rendered with QML (QQuickWidget) on top of ScanProgressModel."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.progress.scan_progressbar.qml_support import create_quick_widget
from bec_widgets.widgets.progress.scan_progressbar.scan_progress_model import ScanProgressModel

QML_FILE = Path(__file__).parent / "qml" / "ScanProgress.qml"


class ScanProgressBarQml(BECWidget, QWidget):
    """
    Scan progress bar with a state chip, smooth bar and time estimate, drawn in QML.

    Same public API as ``ScanProgressBar``: ``progress_started``/``progress_finished`` signals,
    ``one_line_design`` and the ``show_*`` properties.
    """

    ICON_NAME = "timelapse"
    PLUGIN = False
    RPC = False
    progress_started = Signal()
    progress_finished = Signal()

    def __init__(
        self, parent=None, client=None, config=None, gui_id=None, one_line_design=False, **kwargs
    ):
        kwargs.pop("enable_dynamic_stylesheet", None)
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self.get_bec_shortcuts()
        self.model = ScanProgressModel(self.bec_dispatcher, parent=self)
        self.model.progress_started.connect(self.progress_started)
        self.model.progress_finished.connect(self.progress_finished)
        self.model.changed.connect(self._update_tooltip)

        self.view = create_quick_widget(self, QML_FILE, {"progressModel": self.model})
        # the view's root item must be destroyed before the model it binds to
        self.model.setParent(self.view)
        self.view.rootObject().setProperty("compact", bool(one_line_design))
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22 if one_line_design else 58)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_tooltip()

    @property
    def progress_tracker(self):
        """The underlying BECProgressTracker."""
        return self.model.tracker

    @SafeSlot()
    def _update_tooltip(self):
        self.view.setToolTip(self.model.toolTip)

    def _root_flag(self, name: str) -> bool:
        return bool(self.view.rootObject().property(name))

    @SafeProperty(bool)
    def show_elapsed_time(self):
        return self._root_flag("showElapsed")

    @show_elapsed_time.setter
    def show_elapsed_time(self, value):
        self.view.rootObject().setProperty("showElapsed", bool(value))

    @SafeProperty(bool)
    def show_remaining_time(self):
        return self._root_flag("showRemaining")

    @show_remaining_time.setter
    def show_remaining_time(self, value):
        self.view.rootObject().setProperty("showRemaining", bool(value))

    @SafeProperty(bool)
    def show_source_label(self):
        return self._root_flag("showSource")

    @show_source_label.setter
    def show_source_label(self, value):
        self.view.rootObject().setProperty("showSource", bool(value))

    def update_labels(self):
        """Kept for API compatibility; the view updates itself from the model."""
        self.model._tick()

    def cleanup(self):
        self.model.cleanup()
        self.view.setSource("")  # release QML objects before the context goes away
        self.view.close()
        self.view.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    widget = ScanProgressBarQml()
    widget.show()
    app.exec_()
