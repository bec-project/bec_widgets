"""This custom class is a thin wrapper around the SignalProxy class to allow signal calls to be blocked.
Unblocking the proxy needs to be done through the slot unblock_proxy. The most likely use case for this class is
when the callback function is potentially initiating a slower progress, i.e. requesting a data analysis routine to
analyse data. Requesting a new fit may lead to request piling up and an overall slow done of performance. This proxy
will allow you to decide by yourself when to unblock and execute the callback again."""

from pyqtgraph import SignalProxy
from qtpy.QtCore import QTimer, Signal

from bec_widgets.utils.error_popups import SafeSlot


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
        self.new_args = args
        if self.blocked is True:
            return
        self.blocked = True
        self.old_args = args
        super().signalReceived(*args)

        self._timer.start(int(self._timeout * 1000))

    @SafeSlot()
    def unblock_proxy(self):
        """Unblock the proxy, and call the signalReceived method in case there was an update of the args."""
        if self.blocked:
            self._timer.stop()
            self.blocked = False
            if self.new_args != self.old_args:
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
        Cleanup the proxy by stopping the timer and disconnecting the timeout signal.
        """
        self._timer.stop()
        self._timer.timeout.disconnect(self._timeout_unblock)
        self._timer.deleteLater()
