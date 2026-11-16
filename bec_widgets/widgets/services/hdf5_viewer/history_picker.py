"""
A compact picker of history curves for a plot: the scans of the HDF5 viewer on the left and
the signals of the selected scan on the right, with a Y button each.

It does not import the Waveform, so the Waveform can import it lazily without a cycle.
"""

from __future__ import annotations

from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry, ScanList
from bec_widgets.widgets.services.hdf5_viewer.signal_list import SignalList, SourceKey
from bec_widgets.widgets.services.hdf5_viewer.style import mute
from bec_widgets.widgets.services.scan_history_browser.components.scan_history_view import (
    BECHistoryManager,
)

logger = bec_logger.logger


class HistoryPicker(QWidget):
    """
    Pick history curves for a plot. Pressing Y on a signal adds that signal of the selected
    scan to the plot as a history curve, pressing it again takes it off. The Y buttons show
    what the plot holds of the selected scan.

    Args:
        plot: The plot, a Waveform.
        parent (QWidget | None): Parent widget.
    """

    def __init__(self, plot, parent: QWidget | None = None):
        super().__init__(parent)
        self._plot = plot
        self._entry: ScanEntry | None = None
        self.scan_list = ScanList(self, pinnable=False)
        self.signal_list = SignalList(self, picker=True)
        self.note = QLabel(self)
        self.note.setWordWrap(True)
        mute(self.note)
        self.note.setContentsMargins(6, 2, 6, 2)
        self.note.setText("Pick a scan, then press Y on a signal to add it to the plot.")

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.scan_list)
        splitter.addWidget(self.signal_list)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([260, 340])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.note)

        self.history_manager = BECHistoryManager(parent=self, client=plot.client)
        self.history_manager.scan_history_refreshed.connect(self._on_history_refreshed)
        self.history_manager.scan_history_updated.connect(self._on_history_updated)
        self.scan_list.scan_selected.connect(self._on_scan_selected)
        self.signal_list.y_toggled.connect(self._on_y_toggled)
        try:
            self.history_manager.refresh_scan_history()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"History picker: the scan history could not be read: {exc}")

    ################################################################################
    # Scans
    ################################################################################

    @SafeSlot(list)
    def _on_history_refreshed(self, history: list) -> None:
        self.scan_list.set_entries([ScanEntry.from_history(msg) for msg in history])

    @SafeSlot(dict)
    def _on_history_updated(self, msg: dict) -> None:
        self.scan_list.add_entry(ScanEntry.from_history(msg))

    def _on_scan_selected(self, entry: ScanEntry | None) -> None:
        self._entry = entry
        self.signal_list.set_scan(entry)
        self.sync()

    ################################################################################
    # The plot
    ################################################################################

    def held(self) -> dict[SourceKey, object]:
        """
        The history curves the plot holds of the selected scan.

        Returns:
            dict[SourceKey, Curve]: Curve by (device, entry).
        """
        if self._entry is None:
            return {}
        held = {}
        for curve in self._plot.curves:
            config = curve.config
            if (
                config.source == "history"
                and config.signal is not None
                and config.scan_id == self._entry.scan_id
            ):
                held[(config.signal.device, config.signal.signal)] = curve
        return held

    def sync(self) -> None:
        """Show on the Y buttons what the plot holds of the selected scan, in its colours."""
        held = self.held()
        self.signal_list.set_colors(
            {key: curve.config.color for key, curve in held.items()}, "#2a78d6"
        )
        self.signal_list.set_y_signals(list(held))

    def _on_y_toggled(self, key: SourceKey, on: bool) -> None:
        entry = self._entry
        if entry is None:
            return
        device, signal = key
        held = self.held()
        try:
            if on and key not in held:
                self._plot.plot(
                    device_y=device,
                    signal_y=signal,
                    scan_id=entry.scan_id,
                    _override_slot_params={"popup_error": False, "raise_error": True},
                )
                self.note.setText(f"Added {device} of scan {entry.scan_number} to the plot.")
            elif not on and key in held:
                self._plot.remove_curve(held[key].name())
                self.note.setText(f"Took {device} of scan {entry.scan_number} off the plot.")
        except Exception as exc:  # pylint: disable=broad-except
            self.note.setText(f"{device} could not be added: {exc}")
        self.sync()

    def cleanup(self) -> None:
        """Release the history subscription and stop the timers."""
        self.history_manager.cleanup()
        self.scan_list.cleanup()
