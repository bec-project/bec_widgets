"""
Runs the reads of :mod:`h5_reader` off the GUI thread and hands the results back to it.

A widget asks for a read with :meth:`H5Service.request` and gets the result in a callback
on the GUI thread. Requests are grouped in channels: a newer request on a channel replaces
the older ones, so quickly changing selections never queue up stale reads.
"""

from __future__ import annotations

import itertools
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, Qt, Signal

from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5ReadError, file_summary

logger = bec_logger.logger

#: Threads that read. Two keep a slow read from holding back the tree.
WORKER_THREADS = 2
#: Longest time :meth:`H5Service.cleanup` waits for running reads.
SHUTDOWN_SECONDS = 2.0


class ReadContext:
    """Handed to a read so that it can be cancelled and can report how far it is."""

    def __init__(self, request_id: int, report: Callable[[int, float], None]):
        self._request_id = request_id
        self._report = report
        self._cancelled = threading.Event()
        self._last_report = 0.0

    def cancel(self) -> None:
        """Mark the read as no longer wanted."""
        self._cancelled.set()

    def cancelled(self) -> bool:
        """
        Whether the read is no longer wanted.

        Returns:
            bool: True once the request was replaced or the service was closed.
        """
        return self._cancelled.is_set()

    def progress(self, fraction: float) -> None:
        """
        Report the fraction read so far. Reports closer than 50 ms apart are dropped.

        Args:
            fraction (float): Between 0 and 1.
        """
        now = time.monotonic()
        if fraction < 1.0 and now - self._last_report < 0.05:
            return
        self._last_report = now
        self._report(self._request_id, float(fraction))


@dataclass
class _Request:
    request_id: int
    channel: str
    file_path: str
    read: Callable[[ReadContext], Any]
    on_done: Callable[[Any], None]
    on_error: Callable[[H5ReadError], None] | None
    on_progress: Callable[[float], None] | None
    context: ReadContext = field(repr=False, default=None)  # type: ignore[assignment]


class H5Service(QObject):
    """Serves file reads for the widgets of the HDF5 viewer without blocking the window."""

    #: Emitted with True when the first read starts and with False when the last one ends.
    busy_changed = Signal(bool)
    #: Emitted with a file path when more bytes of that file were read.
    bytes_read_changed = Signal(str)

    _finished = Signal(int, object, object)
    _progressed = Signal(int, float)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._ids = itertools.count(1)
        self._requests: dict[int, _Request] = {}
        self._latest: dict[str, int] = {}
        self._queue: queue.Queue[_Request | None] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._closed = False
        self._bytes_read: dict[str, int] = {}
        self._reads_while_busy: set[str] = set()
        self._finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._progressed.connect(self._deliver_progress, Qt.ConnectionType.QueuedConnection)

    ################################################################################
    # Requests
    ################################################################################

    def request(
        self,
        channel: str,
        file_path: str,
        read: Callable[[ReadContext], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[H5ReadError], None] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> int:
        """
        Run ``read`` on a worker thread and call ``on_done`` with its result on the GUI thread.

        A file that looks like it is still being written is not read: the request fails
        with an error of kind ``busy`` unless :meth:`allow_busy_file` was called for it.

        Args:
            channel (str): Requests of one channel replace each other; only the result of the
                newest one is delivered.
            file_path (str): The file the read opens.
            read (Callable[[ReadContext], Any]): The read. Runs on a worker thread.
            on_done (Callable[[Any], None]): Receives the result on the GUI thread.
            on_error (Callable[[H5ReadError], None] | None): Receives the error of a failed
                read on the GUI thread.
            on_progress (Callable[[float], None] | None): Receives the fraction read so far.

        Returns:
            int: Identifier of the request.
        """
        request_id = next(self._ids)
        if self._closed:
            return request_id
        self.cancel(channel)
        request = _Request(request_id, channel, file_path, read, on_done, on_error, on_progress)
        request.context = ReadContext(request_id, self._progressed.emit)
        was_idle = not self._requests
        self._requests[request_id] = request
        self._latest[channel] = request_id
        self._ensure_threads()
        self._queue.put(request)
        if was_idle:
            self.busy_changed.emit(True)
        return request_id

    def cancel(self, channel: str) -> None:
        """
        Drop the pending request of a channel. Its callbacks are not called.

        Args:
            channel (str): The channel to clear.
        """
        request_id = self._latest.pop(channel, None)
        request = self._requests.pop(request_id, None) if request_id is not None else None
        if request is None:
            return
        request.context.cancel()
        if not self._requests:
            self.busy_changed.emit(False)

    def has_pending(self, prefix: str = "") -> bool:
        """
        Whether a channel whose name starts with ``prefix`` waits for a read.

        Args:
            prefix (str): Start of the channel names. Empty for all channels.

        Returns:
            bool: True while such a read is pending.
        """
        return any(name.startswith(prefix) for name in self._latest)

    def cancel_all(self, prefix: str = "") -> None:
        """
        Drop the pending requests of every channel whose name starts with ``prefix``.

        Args:
            prefix (str): Start of the channel names. Empty for all channels.
        """
        for channel in [name for name in self._latest if name.startswith(prefix)]:
            self.cancel(channel)

    def allow_busy_file(self, file_path: str, allowed: bool = True) -> None:
        """
        Let the next reads open a file although it looks like it is still being written.

        Args:
            file_path (str): Path of the file.
            allowed (bool): False takes the permission back.
        """
        if allowed:
            self._reads_while_busy.add(file_path)
        else:
            self._reads_while_busy.discard(file_path)

    def bytes_read(self, file_path: str) -> int:
        """
        Bytes of dataset values read from a file so far.

        Args:
            file_path (str): Path of the file.

        Returns:
            int: Number of bytes.
        """
        return self._bytes_read.get(file_path, 0)

    ################################################################################
    # Worker side
    ################################################################################

    def _ensure_threads(self) -> None:
        if self._threads:
            return
        for index in range(WORKER_THREADS):
            thread = threading.Thread(
                target=self._work, name=f"hdf5-viewer-read-{index}", daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def _work(self) -> None:
        while True:
            request = self._queue.get()
            if request is None:
                return
            if request.context.cancelled():
                continue
            result, error = None, None
            try:
                if (
                    request.file_path
                    and request.file_path not in self._reads_while_busy
                    and file_summary(request.file_path).busy
                ):
                    raise H5ReadError("The file is still being written", "busy", request.file_path)
                result = request.read(request.context)
            except H5ReadError as exc:
                error = exc
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"HDF5 viewer: reading {request.file_path} failed: {exc}")
                error = H5ReadError(str(exc), "unreadable", request.file_path)
            if request.context.cancelled():
                continue
            try:
                self._finished.emit(request.request_id, result, error)
            except RuntimeError:
                # The service was deleted while the read ran.
                return

    ################################################################################
    # GUI side
    ################################################################################

    def _deliver(self, request_id: int, result: Any, error: H5ReadError | None) -> None:
        request = self._requests.pop(request_id, None)
        if request is None:
            return
        if self._latest.get(request.channel) == request_id:
            del self._latest[request.channel]
        if not self._requests:
            self.busy_changed.emit(False)
        if error is not None:
            if request.on_error is not None and error.kind != "cancelled":
                request.on_error(error)
            return
        count = getattr(result, "bytes_read", 0)
        if count and request.file_path:
            self._bytes_read[request.file_path] = self.bytes_read(request.file_path) + count
            self.bytes_read_changed.emit(request.file_path)
        request.on_done(result)

    def _deliver_progress(self, request_id: int, fraction: float) -> None:
        request = self._requests.get(request_id)
        if request is not None and request.on_progress is not None:
            request.on_progress(fraction)

    def cleanup(self) -> None:
        """Cancel every read and stop the worker threads."""
        if self._closed:
            return
        self._closed = True
        for request in self._requests.values():
            request.context.cancel()
        self._requests.clear()
        self._latest.clear()
        for _ in self._threads:
            self._queue.put(None)
        deadline = time.monotonic() + SHUTDOWN_SECONDS
        for thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        self._threads.clear()
