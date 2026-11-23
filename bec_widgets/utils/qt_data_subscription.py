"""
Qt bridge for DataAPI subscriptions.

Wraps a :class:`bec_lib.data_api.Subscription` in a ``QObject``: columnar
:class:`~bec_lib.data_api.SubscriptionUpdate` snapshots arriving on
dispatcher/worker threads are marshalled onto the Qt thread via a queued
signal, stale-scan payloads are dropped, and the widget's slot is called with what is
left. Widgets do not create it themselves: ``BECDispatcher.connect_data_subscription``
does, and the dispatcher holds it and closes it with its owner, exactly as it does for
the slots of Redis topics.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from bec_lib.data_api import (
    DEFAULT_UPDATE_RATE,
    ScanTarget,
    SourceKey,
    Subscription,
    SubscriptionUpdate,
    UpdateReason,
)
from qtpy.QtCore import Qt, Signal

from bec_widgets.utils.qt_owned_callback import QtOwnedCallback

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient


class QtDataSubscription(QtOwnedCallback):
    """
    One DataAPI subscription delivered to a slot on the Qt thread.

    The slot and its owner are held as :class:`QtOwnedCallback` describes, with the same
    checks before every delivery as for the slots of Redis topics.
    """

    #: Carries a correlation-group key; the update itself waits in ``_pending``.
    _raw = Signal(object)
    _raw_progress = Signal(float)

    #: Which reason survives when a queued update is superseded (higher wins).
    _REASON_RANK = {
        UpdateReason.LIVE: 0,
        UpdateReason.BACKFILL: 1,
        UpdateReason.HISTORY: 2,
        UpdateReason.REBIND: 3,
    }

    def __init__(
        self,
        client: BECClient,
        slot: Callable[[SubscriptionUpdate], Any],
        sources: list[SourceKey] | None = None,
        scan: str | None = ScanTarget.LIVE,
        owner: object | None = None,
        progress_slot: Callable[[float], Any] | None = None,
        update_rate: float | None = DEFAULT_UPDATE_RATE,
        max_buffer_size: int | None = None,
        size_limit_bytes: int | None = None,
        force_source: str | None = None,
        devices: list[str] | None = None,
        pair_sources: bool = False,
        **options: Any,
    ):
        """
        Subscribe to data for the given sources. Use
        ``BECDispatcher.connect_data_subscription`` instead of calling this directly.

        Args:
            client (BECClient): The BEC client.
            slot (Callable): Called on the Qt thread with each ``SubscriptionUpdate``.
            sources (list[SourceKey] | None): (device, entry) pairs; they are
                partitioned into correlation groups by the backend and each
                group emits its own updates.
            scan (str | None): ``ScanTarget.LIVE`` to follow the active scan, a
                concrete (possibly finished) scan id, or ``None`` for
                scan-less device streams (readback, configuration,
                preview signals).
            owner (object | None): Lifetime anchor for a slot that is not a bound method.
            progress_slot (Callable | None): Called on the Qt thread with the fraction
                (0..1) of a stored scan that is loaded. It belongs to the same owner.
            update_rate (float | None): Most live updates a second, in Hz; faster updates
                are coalesced in the backend. ``None`` delivers every update.
            max_buffer_size (int | None): Most points kept per source; the oldest
                are dropped beyond it. Recommended for endless device-stream
                subscriptions (``scan=None``).
            size_limit_bytes (int | None): Withhold the load when the backend
                can estimate the payload up front (history scans) and the
                estimate exceeds this limit. Nothing is read; the subscription
                reports :attr:`size_gated` with :attr:`estimated_bytes` and
                waits for :meth:`confirm_size`.
            force_source (str | None): Pin the subscription to one data
                source (``"redis"``, ``"file"``, …); see
                :meth:`bec_lib.data_api.DataAPI.subscribe`.
            devices (list[str] | None): Shorthand for hub signals,
                ``devices=["samx", "samy"]`` is ``sources=[("samx", "samx"),
                ("samy", "samy")]``. Exclusive with ``sources``.
            pair_sources (bool): Only for scan-less streams (``scan=None``). False
                (default): every source is its own stream. True: all sources form one
                sample-and-hold group whose updates carry equal-length,
                already paired columns (the (x, y) trail of a motor map).

        Raises:
            ValueError: If a concrete scan id cannot be served, or the
                arguments contradict each other.
            CorrelationGroupError: If the source list is empty.
        """
        super().__init__(slot, owner)
        self._progress = None if progress_slot is None else QtOwnedCallback(progress_slot, owner)
        # Latest undelivered update per correlation group: a slow GUI thread sees
        # the newest state, never a backlog of superseded snapshots.
        self._pending: dict[Any, SubscriptionUpdate] = {}
        self._pending_lock = threading.Lock()
        # Explicitly queued: the backend delivers the initial backfill
        # SYNCHRONOUSLY inside subscribe() when called on the Qt thread; an
        # auto-connection would then invoke _filter before _subscription is
        # assigned.
        self._raw.connect(self._filter, Qt.QueuedConnection)
        self._raw_progress.connect(self._emit_progress, Qt.QueuedConnection)
        self._api = client.data_api
        self._subscription: Subscription = self._api.subscribe(
            sources=sources,
            scan=scan,
            callback=self._deliver,
            update_rate=update_rate,
            max_buffer_size=max_buffer_size,
            size_limit_bytes=size_limit_bytes,
            progress_callback=self._deliver_progress,
            force_source=force_source,
            devices=devices,
            pair_sources=pair_sources,
            **options,
        )

    # --- api-thread side -----------------------------------------------------

    def _deliver(self, update: SubscriptionUpdate) -> None:
        if not self._active:
            return
        group = update.metadata.get("group")
        with self._pending_lock:
            previous = self._pending.get(group)
            if previous is not None and previous.generation == update.generation:
                # Keep the transition a superseded update announced (e.g. "rebind").
                if self._REASON_RANK[previous.reason] > self._REASON_RANK[update.reason]:
                    update = replace(update, reason=previous.reason)
            self._pending[group] = update
        if previous is None:
            self._raw.emit(group)

    def _deliver_progress(self, fraction: float) -> None:
        if self._active:
            self._raw_progress.emit(float(fraction))

    # --- qt-thread side ------------------------------------------------------

    def _emit_progress(self, fraction: float) -> None:
        callback = None if self._progress is None else self._progress.live_callback()
        if callback is not None and self._active and not self._api.closed:
            callback(fraction)

    def _filter(self, group: Any) -> None:
        with self._pending_lock:
            update = self._pending.pop(group, None)
        if update is None:
            return
        callback = self.live_callback()
        if callback is None or self._api.closed:
            return
        if update.generation != self._subscription.generation:
            return  # source/path rebind within the same scan, while this was queued
        current = self._subscription.scan_id
        if current is not None and update.scan_id != current:
            # A payload queued before a rebind; the bound scan's own emission
            # follows.
            return
        callback(update)

    # --- public --------------------------------------------------------------

    @property
    def closed(self) -> bool:
        """Whether the subscription was closed; nothing is delivered any more."""
        return not self._active

    @property
    def groups(self) -> dict:
        """Correlation groups of the current binding (label -> sources)."""
        return self._subscription.groups

    @property
    def routes(self) -> dict:
        """The data source serving each bound source."""
        return self._subscription.routes

    @property
    def unbound_sources(self) -> list:
        """Declared sources that are not delivering."""
        return self._subscription.unbound_sources

    def request_view(
        self, source: SourceKey, start: int, stop: int, max_points: int = 4000
    ) -> bool:
        """
        Ask for the rows ``start:stop`` of a source that is held as an overview.

        Args:
            source (SourceKey): The (device, entry) source.
            start (int): First row wanted.
            stop (int): One past the last row wanted.
            max_points (int): Upper bound of the points for these rows.

        Returns:
            bool: Whether the request was taken; the rows arrive in a later update.
        """
        if not self._active:
            return False
        return self._subscription.request_view(source, start, stop, max_points)

    def set_update_rate(self, update_rate: float | None) -> None:
        """
        Change how often the live subscription delivers updates.

        Args:
            update_rate (float | None): Most live updates a second, in Hz; ``None``
                delivers every update.
        """
        self._subscription.set_update_rate(update_rate)

    @property
    def scan_id(self) -> str | None:
        """The currently bound scan id."""
        return self._subscription.scan_id

    @property
    def sources(self) -> list[SourceKey]:
        """The declared source set."""
        return self._subscription.sources

    @property
    def healthy(self) -> bool:
        """Whether every declared source is currently delivering."""
        return not self._subscription.unbound_sources

    @property
    def size_gated(self) -> bool:
        """Whether delivery is withheld pending :meth:`confirm_size`."""
        return bool(self._subscription.size_gated)

    @property
    def estimated_bytes(self) -> int | None:
        """Estimated payload size of the bound scan, if the backend knows it."""
        return self._subscription.estimated_bytes

    def confirm_size(self) -> None:
        """
        Release a load withheld by ``size_limit_bytes``.

        Returns immediately: the file read runs on the backend's worker
        thread and the data arrives later through :attr:`updated`.
        """
        self._subscription.confirm_size()

    def set_sources(self, sources: list[SourceKey]) -> None:
        """Atomically replace the source set."""
        self._subscription.set_sources(sources)

    def close(self) -> None:
        """
        Close the DataAPI subscription and delete this object (idempotent).

        Widgets call ``BECDispatcher.disconnect_data_subscription``, which also makes the
        dispatcher forget it.
        """
        if not self._active:
            return
        self.invalidate()
        if self._progress is not None:
            self._progress.invalidate()
        self._subscription.close()
        # On the GUI thread's next turn: no data thread is inside this object any more.
        self.deleteLater()
