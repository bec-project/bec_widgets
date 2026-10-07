"""This custom class is a thin wrapper around the SignalProxy class to allow signal calls to be blocked.
Unblocking the proxy needs to be done through the slot unblock_proxy. The most likely use case for this class is
when the callback function is potentially initiating a slower progress, i.e. requesting a data analysis routine to
analyse data. Requesting a new fit may lead to request piling up and an overall slow done of performance. This proxy
will allow you to decide by yourself when to unblock and execute the callback again."""

from pyqtgraph import SignalProxy
from qtpy.QtCore import QTimer, Signal

from bec_widgets.utils.error_popups import SafeSlot


def cleanup_signal_proxy(proxy: SignalProxy) -> None:
    """
    Stop a pyqtgraph SignalProxy for good, so nothing is delivered to its slot afterwards.

    pg.SignalProxy.disconnect() only detaches the source signal and blocks the proxy. An
    emission that is already queued keeps the repeating delivery timer running, because flush()
    returns before stopping the timer once the proxy is blocked. This also stops that timer and
    drops the queued arguments. Calling it again is a no-op.

    Args:
        proxy(SignalProxy): The proxy to stop.
    """
    # Called explicitly: on subclasses of SignalProxy, PySide6 resolves proxy.disconnect
    # to the built-in QObject.disconnect instead of SignalProxy.disconnect.
    SignalProxy.disconnect(proxy)
    proxy.timer.stop()
    proxy.args = None


class BECSignalProxy(SignalProxy):
    """
    Thin wrapper around the SignalProxy class to allow signal calls to be blocked,
    but arguments still being stored.

    Args:
        *args: Arguments to pass to the SignalProxy class.
        rateLimit (int): The rateLimit of the proxy.
        timeout (float): The number of seconds after which the proxy automatically
                         unblocks if still blocked. Default is 10.0 seconds.
        **kwargs: Keyword arguments to pass to the SignalProxy class.

    Example:
        >>> proxy = BECSignalProxy(signal, rate_limit=25, slot=callback)
    """

    is_blocked = Signal(bool)

    def __init__(self, *args, rateLimit=25, timeout=10.0, **kwargs):
        super().__init__(*args, rateLimit=rateLimit, **kwargs)
        self._blocking = False
        self._pending = False
        self._cleaned_up = False
        self.old_args = None
        self.new_args = None

        # Store timeout value (in seconds)
        self._timeout = timeout

        # Create a single-shot timer for auto-unblocking
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout_unblock)

    @property
    def blocked(self):
        """Returns if the proxy is blocked"""
        return self._blocking

    @blocked.setter
    def blocked(self, value: bool):
        self._blocking = value
        self.is_blocked.emit(value)

    def signalReceived(self, *args):
        """Receive signal, store the args and call signalReceived from the parent class if not blocked"""
        if self._cleaned_up:
            return
        self.new_args = args
        if self.blocked is True:
            self._pending = True
            return
        self.blocked = True
        self.old_args = args
        super().signalReceived(*args)

        self._timer.start(int(self._timeout * 1000))

    @SafeSlot()
    def unblock_proxy(self):
        """
        Unblock the proxy and replay emissions that arrived while it was blocked.
        """
        if self._cleaned_up:
            return
        if self.blocked:
            self._timer.stop()
            self.blocked = False
            if self._pending:
                self._pending = False
                if self.new_args == () or self.new_args != self.old_args:
                    self.signalReceived(*self.new_args)

    @SafeSlot()
    def _timeout_unblock(self):
        """
        Internal method called by the QTimer upon timeout. Unblocks the proxy
        automatically if it is still blocked.
        """
        if self.blocked:
            self.unblock_proxy()

    def cleanup(self):
        """
        Cleanup the proxy so that nothing is delivered to the slot afterwards.

        Stops the pg.SignalProxy part (see cleanup_signal_proxy), drops any pending emission
        and stops and deletes the auto-unblock timer. Calling it again is a no-op.
        """
        if self._cleaned_up:
            return
        self._cleaned_up = True
        cleanup_signal_proxy(self)
        self._pending = False
        self.old_args = None
        self.new_args = None
        self._timer.stop()
        self._timer.timeout.disconnect(self._timeout_unblock)
        self._timer.deleteLater()
