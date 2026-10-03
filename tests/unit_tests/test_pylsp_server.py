"""Unit tests for bec_widgets.utils.pylsp_server and bec-app's shutdown signal handlers."""

from __future__ import annotations

import signal
import sys
import threading
import types
from unittest import mock

import pytest

from bec_widgets.applications import main_app
from bec_widgets.utils import pylsp_server as pylsp_module

SIGNALS = (signal.SIGINT, signal.SIGTERM)


class FakeProvider:
    """Stand-in for qtmonaco's PyLSPProvider: takes over SIGINT/SIGTERM when constructed."""

    def __init__(self, install_handlers: bool = True):
        self.running = False
        self.stop_calls = 0
        if install_handlers:
            for signum in SIGNALS:
                signal.signal(signum, self._handle_signal)

    def _handle_signal(self, signum, frame):
        self.stop()

    def is_running(self):
        return self.running

    def stop(self):
        self.stop_calls += 1
        self.running = False


@pytest.fixture
def keep_signal_handlers():
    """Restore the test process's SIGINT/SIGTERM handlers whatever a test installs."""
    saved = {signum: signal.getsignal(signum) for signum in SIGNALS}
    yield
    for signum, handler in saved.items():
        signal.signal(signum, handler)


@pytest.fixture
def fake_provider_import(monkeypatch, keep_signal_handlers):
    """Make get_pylsp_server import a fake provider module that hijacks the handlers."""
    monkeypatch.delitem(sys.modules, pylsp_module.PYLSP_PROVIDER_MODULE, raising=False)
    created = {}

    def import_module(name):
        assert name == pylsp_module.PYLSP_PROVIDER_MODULE
        module = types.ModuleType(name)
        module.pylsp_server = created["server"] = FakeProvider()
        sys.modules[name] = module
        return module

    monkeypatch.setattr(pylsp_module.importlib, "import_module", import_module)
    yield created
    sys.modules.pop(pylsp_module.PYLSP_PROVIDER_MODULE, None)


def test_get_pylsp_server_restores_python_handlers(fake_provider_import):
    def custom_handler(signum, frame):  # pragma: no cover - never delivered
        pass

    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, custom_handler)

    server = pylsp_module.get_pylsp_server()

    assert server is fake_provider_import["server"]
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    assert signal.getsignal(signal.SIGTERM) is custom_handler


def test_get_pylsp_server_keeps_sig_dfl_terminating(fake_provider_import):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    pylsp_module.get_pylsp_server()

    assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
    # SIG_DFL would kill the process without stopping the server: stop it first, then terminate
    assert signal.getsignal(signal.SIGTERM) is pylsp_module._stop_server_then_terminate


def test_get_pylsp_server_is_idempotent_and_leaves_later_handlers_alone(fake_provider_import):
    def request_shutdown(signum, frame):  # pragma: no cover - never delivered
        pass

    first = pylsp_module.get_pylsp_server()
    signal.signal(signal.SIGTERM, request_shutdown)  # e.g. GUIServer.start()

    assert pylsp_module.get_pylsp_server() is first
    assert signal.getsignal(signal.SIGTERM) is request_shutdown


def test_get_pylsp_server_resets_handlers_left_by_an_earlier_import(
    monkeypatch, keep_signal_handlers
):
    module = types.ModuleType(pylsp_module.PYLSP_PROVIDER_MODULE)
    module.pylsp_server = FakeProvider()  # imported elsewhere, handlers already hijacked
    monkeypatch.setitem(sys.modules, pylsp_module.PYLSP_PROVIDER_MODULE, module)

    assert pylsp_module.get_pylsp_server() is module.pylsp_server
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    assert signal.getsignal(signal.SIGTERM) is pylsp_module._stop_server_then_terminate


def test_get_pylsp_server_outside_main_thread_does_not_touch_signals(
    monkeypatch, keep_signal_handlers
):
    module = types.ModuleType(pylsp_module.PYLSP_PROVIDER_MODULE)
    module.pylsp_server = FakeProvider()
    monkeypatch.setitem(sys.modules, pylsp_module.PYLSP_PROVIDER_MODULE, module)
    result = {}
    thread = threading.Thread(target=lambda: result.update(server=pylsp_module.get_pylsp_server()))
    thread.start()
    thread.join()

    assert result["server"] is module.pylsp_server
    assert signal.getsignal(signal.SIGTERM) == module.pylsp_server._handle_signal


def test_stop_pylsp_server_never_imports_qtmonaco(monkeypatch):
    monkeypatch.delitem(sys.modules, pylsp_module.PYLSP_PROVIDER_MODULE, raising=False)
    with mock.patch.object(pylsp_module.importlib, "import_module") as import_module:
        pylsp_module.stop_pylsp_server()
    import_module.assert_not_called()
    assert pylsp_module.PYLSP_PROVIDER_MODULE not in sys.modules


@pytest.mark.parametrize("running", [True, False])
def test_stop_pylsp_server_stops_only_a_running_server(monkeypatch, running):
    module = types.ModuleType(pylsp_module.PYLSP_PROVIDER_MODULE)
    module.pylsp_server = FakeProvider(install_handlers=False)
    module.pylsp_server.running = running
    monkeypatch.setitem(sys.modules, pylsp_module.PYLSP_PROVIDER_MODULE, module)

    pylsp_module.stop_pylsp_server()

    assert module.pylsp_server.stop_calls == int(running)


def test_stop_server_then_terminate_reraises_with_default_action(monkeypatch):
    calls = []
    monkeypatch.setattr(pylsp_module, "stop_pylsp_server", lambda: calls.append("stop"))
    monkeypatch.setattr(
        pylsp_module.signal, "signal", lambda signum, handler: calls.append((signum, handler))
    )
    monkeypatch.setattr(pylsp_module.signal, "raise_signal", lambda signum: calls.append(signum))

    pylsp_module._stop_server_then_terminate(signal.SIGTERM, None)

    assert calls == ["stop", (signal.SIGTERM, signal.SIG_DFL), signal.SIGTERM]


@pytest.fixture
def captured_handlers(monkeypatch):
    """Capture the handlers bec-app installs instead of installing them in the test process."""
    handlers = {}
    monkeypatch.setattr(
        main_app.signal, "signal", lambda signum, handler: handlers.__setitem__(signum, handler)
    )
    return handlers


def test_bec_app_signal_handlers_close_windows_and_quit(qtbot, captured_handlers):
    app = mock.MagicMock()
    window = mock.MagicMock()
    app.topLevelWidgets.return_value = [window]

    main_app.install_shutdown_signal_handlers(app)
    assert set(captured_handlers) == {signal.SIGINT, signal.SIGTERM}

    captured_handlers[signal.SIGTERM](signal.SIGTERM, None)
    app.quit.assert_not_called()  # deferred to the event loop, not run inside the handler
    qtbot.waitUntil(lambda: app.quit.called, timeout=1000)
    window.close.assert_called_once()


def test_bec_app_second_signal_terminates_immediately(qtbot, captured_handlers, monkeypatch):
    calls = []
    monkeypatch.setattr(main_app, "stop_pylsp_server", lambda: calls.append("stop"))
    monkeypatch.setattr(main_app.signal, "raise_signal", lambda signum: calls.append(signum))
    app = mock.MagicMock()
    app.topLevelWidgets.return_value = []

    main_app.install_shutdown_signal_handlers(app)
    captured_handlers[signal.SIGINT](signal.SIGINT, None)
    captured_handlers[signal.SIGINT](signal.SIGINT, None)

    assert calls == ["stop", signal.SIGINT]
    assert captured_handlers[signal.SIGINT] is signal.SIG_DFL
    qtbot.waitUntil(lambda: app.quit.called, timeout=1000)
