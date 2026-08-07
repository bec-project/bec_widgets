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

from typing import TYPE_CHECKING

from bec_lib.data_api import DataAPI, SourceKey, SubscriptionUpdate
from qtpy.QtCore import QObject, Qt, Signal

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient


class QtDataSubscription(QObject):
    """One DataAPI subscription delivered on the Qt thread."""

    #: Emitted on the Qt thread with each SubscriptionUpdate.
    updated = Signal(object)

    _raw = Signal(object)

    def __init__(
        self,
        client: BECClient,
        sources: list[SourceKey],
        scan: str = "live",
        parent: QObject | None = None,
        min_emit_interval: float = 0.1,
    ):
        """
        Subscribe to data for the given sources.

        Args:
            client (BECClient): The widget's BEC client.
            sources (list[SourceKey]): (device, entry) pairs forming one
                correlation group.
            scan (str): ``"live"`` to follow the active scan, or a concrete
                (possibly finished) scan id.
            parent (QObject | None): Qt parent; closing follows the parent's
                destruction.
            min_emit_interval (float): Backend emission coalescing interval.

        Raises:
            ValueError: If a concrete scan id cannot be served.
            CorrelationGroupError: If the sources do not form one group.
        """
        super().__init__(parent)
        self._closed = False
        self._subscription = None
        # Explicitly queued: the backend delivers the initial backfill
        # SYNCHRONOUSLY inside subscribe() when called on the Qt thread; an
        # auto-connection would then invoke _filter before _subscription is
        # assigned and before the widget had a chance to connect `updated`.
        self._raw.connect(self._filter, Qt.QueuedConnection)
        self._api = DataAPI(client)
        self._subscription = self._api.subscribe(
            sources=sources, scan=scan, callback=self._deliver, min_emit_interval=min_emit_interval
        )
        self.destroyed.connect(lambda: self.close())

    # --- api-thread side -----------------------------------------------------

    def _deliver(self, update: SubscriptionUpdate) -> None:
        if not self._closed:
            self._raw.emit(update)

    # --- qt-thread side ------------------------------------------------------

    def _filter(self, update: SubscriptionUpdate) -> None:
        if self._closed or self._subscription is None:
            return
        current = self._subscription.scan_id
        if current is not None and update.scan_id != current:
            # A payload queued before a rebind; the bound scan's own emission
            # follows.
            return
        self.updated.emit(update)

    # --- public --------------------------------------------------------------

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

    def set_sources(self, sources: list[SourceKey]) -> None:
        """Atomically replace the source set."""
        self._subscription.set_sources(sources)

    def close(self) -> None:
        """Close the underlying subscription (idempotent)."""
        if self._closed:
            return
        self._closed = True
        self._subscription.close()
