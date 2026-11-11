"""
Qt bridge for DataAPI subscriptions.

Wraps a :class:`bec_lib.data_api.Subscription` in a ``QObject``: columnar
:class:`~bec_lib.data_api.SubscriptionUpdate` snapshots arriving on
dispatcher/worker threads are marshalled onto the Qt thread via a queued
signal, stale-scan payloads are dropped, and the subscription is closed with
the widget. This is the one-line integration point for plotting widgets —
no per-widget signal bridges, rate-limit proxies or health checks needed.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from bec_lib.data_api import (
    CorrelationMode,
    ScanTarget,
    SourceKey,
    Subscription,
    SubscriptionUpdate,
    UpdateReason,
)
from qtpy.QtCore import QObject, Qt, Signal

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient


class QtDataSubscription(QObject):
    """One DataAPI subscription delivered on the Qt thread."""

    #: Emitted on the Qt thread with each SubscriptionUpdate.
    updated = Signal(object)
    #: Emitted on the Qt thread with the bulk-load fraction (0..1) while the
    #: backend reads history data.
    progress = Signal(float)

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
        sources: list[SourceKey] | None = None,
        scan: str | None = ScanTarget.LIVE,
        parent: QObject | None = None,
        min_emit_interval: float = 0.1,
        max_points: int | None = None,
        size_limit_bytes: int | None = None,
        force_source: str | None = None,
        devices: list[str] | None = None,
        correlation: CorrelationMode | str = CorrelationMode.ORDINAL,
        **options: Any,
    ):
        """
        Subscribe to data for the given sources.

        Args:
            client (BECClient): The widget's BEC client.
            sources (list[SourceKey] | None): (device, entry) pairs; they are
                partitioned into correlation groups by the backend and each
                group emits its own updates.
            scan (str | None): ``ScanTarget.LIVE`` to follow the active scan, a
                concrete (possibly finished) scan id, or ``None`` for
                scan-less device streams (readback, configuration,
                preview signals).
            parent (QObject | None): Qt parent; closing follows the parent's
                destruction.
            min_emit_interval (float): Backend emission coalescing interval.
            max_points (int | None): Per-source retention cap; oldest points
                are dropped beyond it. Recommended for endless device-stream
                subscriptions (``scan=None``).
            size_limit_bytes (int | None): Withhold the load when the backend
                can estimate the payload up front (history scans) and the
                estimate exceeds this limit. Nothing is read; the bridge
                reports :attr:`size_gated` with :attr:`estimated_bytes` and
                waits for :meth:`confirm_size`.
            force_source (str | None): Pin the subscription to one data
                source (``"redis"``, ``"file"``, …); see
                :meth:`bec_lib.data_api.DataAPI.subscribe`.
            devices (list[str] | None): Shorthand for hub signals,
                ``devices=["samx", "samy"]`` is ``sources=[("samx", "samx"),
                ("samy", "samy")]``. Exclusive with ``sources``.
            correlation (CorrelationMode | str): ``CorrelationMode.ORDINAL`` (default) or,
                for scan-less streams, ``CorrelationMode.CONTINUOUS``: every source forms one
                sample-and-hold group whose updates carry equal-length,
                already paired columns (the (x, y) trail of a motor map).

        Raises:
            ValueError: If a concrete scan id cannot be served, or the
                arguments contradict each other.
            CorrelationGroupError: If the source list is empty.
        """
        super().__init__(parent)
        self._closed = False
        # Latest undelivered update per correlation group: a slow GUI thread sees
        # the newest state, never a backlog of superseded snapshots.
        self._pending: dict[Any, SubscriptionUpdate] = {}
        self._pending_lock = threading.Lock()
        # Explicitly queued: the backend delivers the initial backfill
        # SYNCHRONOUSLY inside subscribe() when called on the Qt thread; an
        # auto-connection would then invoke _filter before _subscription is
        # assigned and before the widget had a chance to connect `updated`.
        self._raw.connect(self._filter, Qt.QueuedConnection)
        self._raw_progress.connect(self._emit_progress, Qt.QueuedConnection)
        self._api = client.data_api
        self._subscription: Subscription = self._api.subscribe(
            sources=sources,
            scan=scan,
            callback=self._deliver,
            min_emit_interval=min_emit_interval,
            max_points=max_points,
            size_limit_bytes=size_limit_bytes,
            progress_callback=self._deliver_progress,
            force_source=force_source,
            devices=devices,
            correlation=correlation,
            **options,
        )
        self.destroyed.connect(lambda: self.close())

    # --- api-thread side -----------------------------------------------------

    def _deliver(self, update: SubscriptionUpdate) -> None:
        if self._closed:
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
        if not self._closed:
            self._raw_progress.emit(float(fraction))

    # --- qt-thread side ------------------------------------------------------

    def _emit_progress(self, fraction: float) -> None:
        if not self._closed and not self._api.closed:
            self.progress.emit(fraction)

    def _filter(self, group: Any) -> None:
        with self._pending_lock:
            update = self._pending.pop(group, None)
        if update is None:
            return
        if self._closed or self._api.closed:
            return
        if update.generation != self._subscription.generation:
            return  # source/path rebind within the same scan, while this was queued
        current = self._subscription.scan_id
        if current is not None and update.scan_id != current:
            # A payload queued before a rebind; the bound scan's own emission
            # follows.
            return
        self.updated.emit(update)

    # --- public --------------------------------------------------------------

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

    def set_min_emit_interval(self, seconds: float) -> None:
        """
        Change the backend coalescing interval of the live subscription.

        Args:
            seconds (float): New interval in seconds; 0 disables coalescing.
        """
        self._subscription.set_min_emit_interval(seconds)

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
        """Close the underlying subscription (idempotent)."""
        if self._closed:
            return
        self._closed = True
        self._subscription.close()
