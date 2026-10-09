"""
Signal-safe access to qtmonaco's shared PyLSP language server.

``qtmonaco.pylsp_provider`` creates its ``pylsp_server`` singleton at import time, and the
singleton's constructor replaces the process's SIGINT and SIGTERM handlers with one that only
stops the language server and returns. A process that imports the module (directly, or by
creating its first ``qtmonaco.Monaco`` editor) therefore ignores Ctrl-C and ``kill`` for the rest
of its life. Import the provider only through :func:`get_pylsp_server`, and stop the server with
:func:`stop_pylsp_server`, which never imports qtmonaco just to find out that nothing runs.
"""

from __future__ import annotations

import importlib
import signal
import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from qtmonaco.pylsp_provider import PyLSPProvider

PYLSP_PROVIDER_MODULE = "qtmonaco.pylsp_provider"

# The signals qtmonaco takes over, with the disposition a Python process starts with.
_DEFAULT_HANDLERS = {signal.SIGINT: signal.default_int_handler, signal.SIGTERM: signal.SIG_DFL}


def get_pylsp_server() -> PyLSPProvider:
    """
    Return qtmonaco's shared PyLSP provider without letting it take over SIGINT and SIGTERM.

    The provider module is imported on the first call; right after the import, the handlers it
    installed are replaced by the ones the process had before. A signal whose previous
    disposition was ``SIG_DFL`` (SIGTERM, usually) gets a handler that stops the language server
    and then terminates the process exactly like ``SIG_DFL`` would have, so a ``kill`` does not
    leave an orphaned pylsp process behind. Python handlers (``default_int_handler``, the GUI
    server's ``request_shutdown``, ...) and ``SIG_IGN`` are restored as they were; their exit
    paths stop the server through ``atexit`` or :func:`stop_pylsp_server`.

    Call it from the main thread before creating a ``qtmonaco.Monaco`` editor. If another
    component imported the provider first, the handlers it left behind are reset to the
    interpreter defaults (with the same stop-then-terminate treatment for SIGTERM).

    Returns:
        PyLSPProvider: The process-wide provider (``qtmonaco.pylsp_provider.pylsp_server``).
    """
    module = sys.modules.get(PYLSP_PROVIDER_MODULE)
    previous = {}
    if module is None:
        previous = {signum: signal.getsignal(signum) for signum in _DEFAULT_HANDLERS}
        module = importlib.import_module(PYLSP_PROVIDER_MODULE)
    server = module.pylsp_server
    _replace_provider_signal_handlers(server, previous)
    return server


def stop_pylsp_server() -> None:
    """
    Stop qtmonaco's PyLSP server if this process started it.

    Does nothing (and imports nothing) when no Monaco editor was ever created in this process.
    """
    module = sys.modules.get(PYLSP_PROVIDER_MODULE)
    if module is None:
        return
    server = module.pylsp_server
    if server.is_running():
        server.stop()


def _replace_provider_signal_handlers(server: PyLSPProvider, previous: dict) -> None:
    """Swap the provider's own SIGINT/SIGTERM handlers for the process's previous ones."""
    if threading.current_thread() is not threading.main_thread():
        # signal.signal() only works in the main thread; qtmonaco's own import fails there too.
        return
    # pylint: disable=protected-access
    provider_handler = server._handle_signal
    for signum, default in _DEFAULT_HANDLERS.items():
        if signal.getsignal(signum) != provider_handler:
            continue  # already replaced, e.g. by the GUI server's own shutdown handler
        handler = previous.get(signum)
        if handler is None:  # not installed from Python, or the provider was imported elsewhere
            handler = default
        if handler is signal.SIG_DFL:
            handler = _stop_server_then_terminate
        signal.signal(signum, handler)


def _stop_server_then_terminate(signum: int, _frame) -> None:
    """Stop the language server, then let the signal terminate the process like SIG_DFL."""
    try:
        stop_pylsp_server()
    finally:
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)
