"""
The safeguards every dispatcher-held callback shares.

Threads that are not the GUI thread (the Redis connector, the DataAPI) emit on a Qt object
of the dispatcher, never on a widget. That object holds the widget's callback, and it must
neither keep the widget alive nor call into a widget that is gone. Both rules live here,
once, for the slots of Redis topics (``QtThreadSafeCallback``) and for DataAPI
subscriptions (``QtDataSubscription``).
"""

from __future__ import annotations

from collections.abc import Callable

import louie
import shiboken6
from qtpy.QtCore import QObject


class QtOwnedCallback(QObject):
    """
    A callback together with the object whose lifetime it is bound to.

    Bound methods are held only through weak references: the dispatcher must never keep
    the owning widget alive. Non-method callables (lambdas, partials, module functions)
    have no owning object whose lifetime could be tracked, so they are kept alive by the
    wrapper itself; pass ``owner`` to bind their lifetime to a widget.
    Create the wrapper on the GUI thread: it has no Qt parent and is held by the
    dispatcher, so it does not die together with a widget while another thread emits on it.
    """

    def __init__(self, cb: Callable, owner: object | None = None):
        """
        Args:
            cb (Callable): The callback to hold.
            owner (object, optional): Lifetime anchor for non-method callables. Ignored for
                bound methods (their ``__self__`` is the owner). Defaults to None.
        """
        super().__init__()
        if hasattr(cb, "__self__"):
            # Bound method: the owner is the method's instance; hold NO strong reference
            # anywhere so the dispatcher can never keep a widget alive.
            self.cb_owner = louie.saferef.safe_ref(cb.__self__)
            self._strong_cb = None
        else:
            # No trackable owner on the callable itself: keep it alive explicitly,
            # released together with this wrapper (disconnect_owner / dead-slot sweep
            # when owner is given, an explicit disconnect otherwise).
            self.cb_owner = louie.saferef.safe_ref(owner) if owner is not None else None
            self._strong_cb = cb
        self.cb_ref = louie.saferef.safe_ref(cb)
        self._active = True

    @property
    def cb(self) -> Callable | None:
        """The wrapped callback, or None if it has been garbage collected."""
        return self.cb_ref()

    @property
    def owner(self) -> object | None:
        """The object the callback belongs to, or None if there is none (any more)."""
        return self.cb_owner() if self.cb_owner is not None else None

    def is_dead(self) -> bool:
        """
        Whether the callback or its owner no longer exists, without any close event having
        been delivered: garbage collected, or a Qt object destroyed together with a parent
        while a Python reference lingers. Such wrappers are released by the dispatcher's
        sweep.
        """
        if self.cb is None:
            return True
        owner = self.owner
        if self.cb_owner is not None and owner is None:
            return True
        return isinstance(owner, QObject) and not shiboken6.isValid(owner)

    def invalidate(self) -> None:
        """Suppress pending deliveries and release any strongly held callback."""
        self._active = False
        self._strong_cb = None

    def live_callback(self) -> Callable | None:
        """
        The callback, if a delivery may still happen. GUI thread.

        Resolved at delivery time, never earlier: a queued delivery can outlive the
        receiver. The caller holds the returned callback, and with it the receiver, alive
        while it runs.

        Returns:
            Callable | None: The callback, or None when the wrapper was invalidated, the
                owner was garbage collected, its Qt object was destroyed, or it is a
                widget in or after cleanup.
        """
        if not self._active:
            return None
        owner = self.owner
        if self.cb_owner is not None and owner is None:
            return None
        if isinstance(owner, QObject) and not shiboken6.isValid(owner):
            return None
        if owner is not None and getattr(owner, "_destroyed", False):
            return None
        return self.cb_ref()
