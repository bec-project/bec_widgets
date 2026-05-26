from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QObject, QTimer, Signal


@dataclass(frozen=True)
class ProgressSnapshot:
    value: float
    max_value: float
    done: bool
    status: Literal["open", "paused", "aborted", "halted", "closed", "user_completed"]
    scan_id: str | None = None
    scan_number: int | None = None
    rid: str | None = None
    is_new_scan: bool = False


class ProgressTask(QObject):
    """
    Class to store progress information.
    Inspired by https://github.com/Textualize/rich/blob/master/rich/progress.py
    """

    def __init__(
        self, parent: QObject | None, value: float = 0, max_value: float = 0, done: bool = False
    ):
        super().__init__(parent=parent)
        self.start_time = time.monotonic()
        self.done = done
        self.value = value
        self.max_value = max_value
        self._elapsed_time = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed_time)
        self.timer.start(1000)

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
        Update the time estimates. This is called every second by a QTimer.
        """
        self._elapsed_time = max(0.0, time.monotonic() - self.start_time)

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
        if self.speed == 0:
            return 0.0
        return 1 / self.speed

    @property
    def time_elapsed(self) -> str:
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

    @staticmethod
    def _format_time(seconds: float) -> str:
        """
        Format the time in seconds to a string in the format HH:MM:SS.
        """
        return f"{seconds // 3600:02}:{(seconds // 60) % 60:02}:{seconds % 60:02}"


class BECProgressTracker(QObject):
    """
    Shared backend for BEC scan progress messages.
    """

    progress_started = Signal(object)
    progress_updated = Signal(object)
    progress_finished = Signal(object)
    progress_cleared = Signal()

    def __init__(self, bec_dispatcher, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.bec_dispatcher = bec_dispatcher
        self._connected = False
        self.task: ProgressTask | None = None
        self.scan_number: int | None = None
        self._active_scan_id: str | None = None
        self._active_rid: str | None = None

    def start(self) -> None:
        if self._connected:
            return
        self.bec_dispatcher.connect_slot(
            self.process_progress_message, MessageEndpoints.scan_progress()
        )
        self._connected = True

    def _start_task(self, scan_id: str | None, rid: str | None = None) -> None:
        if self.task is not None:
            self.task.timer.stop()
            self.task.deleteLater()
        self.task = ProgressTask(parent=self)
        self._active_scan_id = scan_id
        self._active_rid = rid
        self.progress_started.emit(
            ProgressSnapshot(
                value=0,
                max_value=100,
                done=False,
                status="open",
                scan_id=self._active_scan_id,
                scan_number=self.scan_number,
                rid=self._active_rid,
            )
        )

    def clear_task(self, *, emit_finished: bool = True) -> None:
        if self.task is None:
            self._active_scan_id = None
            self._active_rid = None
            self.progress_cleared.emit()
            return
        self.task.timer.stop()
        self.task.deleteLater()
        self.task = None
        self._active_scan_id = None
        self._active_rid = None
        self.progress_cleared.emit()
        if emit_finished:
            self.progress_finished.emit(
                ProgressSnapshot(
                    value=0,
                    max_value=100,
                    done=True,
                    status="open",
                    scan_id=self._active_scan_id,
                    scan_number=self.scan_number,
                    rid=self._active_rid,
                )
            )

    def process_progress_message(
        self, msg_content: dict, metadata: dict
    ) -> ProgressSnapshot | None:
        done = msg_content.get("done", False)
        value = msg_content.get("value", 0)
        max_value = msg_content.get("max_value", 100)
        status: Literal["open", "paused", "aborted", "halted", "closed", "user_completed"] = (
            metadata.get("status", "open")
        )
        scan_id = metadata.get("scan_id") or metadata.get("RID")
        rid = metadata.get("RID")
        scan_number = metadata.get("scan_number")
        if scan_number is not None:
            self.scan_number = scan_number
        is_new_scan = False
        previous_scan_id = self._active_scan_id
        previous_rid = self._active_rid
        identity_changed = (
            (scan_id is not None and scan_id != previous_scan_id)
            or (rid is not None and rid != previous_rid)
            or (previous_scan_id is None and previous_rid is None)
        )

        if self.task is None:
            self._start_task(scan_id, rid=rid)
            is_new_scan = identity_changed
        elif scan_id is not None and scan_id != self._active_scan_id:
            self._start_task(scan_id, rid=rid)
            is_new_scan = True
        elif rid is not None and rid != self._active_rid:
            self._start_task(scan_id or self._active_scan_id, rid=rid)
            is_new_scan = True

        if self.task is None:
            return None

        self.task.update(value, max_value, done)
        snapshot = ProgressSnapshot(
            value=value,
            max_value=max_value,
            done=done,
            status=status,
            scan_id=self._active_scan_id,
            scan_number=self.scan_number,
            rid=self._active_rid,
            is_new_scan=is_new_scan,
        )
        self.progress_updated.emit(snapshot)
        if done:
            self.clear_task()
        return snapshot

    def cleanup(self) -> None:
        self.clear_task(emit_finished=False)
        if self._connected:
            self.bec_dispatcher.disconnect_slot(
                self.process_progress_message, MessageEndpoints.scan_progress()
            )
            self._connected = False
