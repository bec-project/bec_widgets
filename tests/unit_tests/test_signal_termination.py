"""
SIGINT (Ctrl-C) and SIGTERM must keep stopping BEC Widgets processes.

``qtmonaco.pylsp_provider`` replaces both handlers at import time with one that only stops the
pylsp language server and returns, so a process that imported it (the GUI server module, the unit
suite at collection, any application with a Monaco editor such as bec-app's device manager) kept
running after Ctrl-C or ``kill``. Every scenario runs in a child process (offscreen, fake BEC
client on fakeredis) that reports READY, gets the signal and must exit within EXIT_TIMEOUT
without leaving its pylsp server behind.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

READY_TIMEOUT = 90.0
EXIT_TIMEOUT = 15.0
REPO_ROOT = Path(__file__).resolve().parents[2]

CHILD_BOOT = textwrap.dedent(r'''
    import json, os, signal, sys, time

    def report():
        """Write the READY file: pid of the pylsp server (if any) and the current handlers."""
        provider = sys.modules.get("qtmonaco.pylsp_provider")
        process = provider.pylsp_server.server_process if provider is not None else None
        info = {
            "pylsp_pid": process.pid if process is not None else None,
            "sigint": repr(signal.getsignal(signal.SIGINT)),
            "sigterm": repr(signal.getsignal(signal.SIGTERM)),
        }
        path = os.environ["SIGNAL_TEST_READY_FILE"]
        with open(path + ".tmp", "w") as f:
            json.dump(info, f)
        os.replace(path + ".tmp", path)

    def report_from_event_loop(delay_ms=500):
        from qtpy.QtCore import QTimer
        QTimer.singleShot(delay_ms, report)

    def use_fake_bec():
        """Same fake BEC client as the packaged bec_dispatcher fixture (fakeredis, DMMock devices)."""
        from unittest import mock
        from bec_widgets.tests.utils import mock_client
        from bec_widgets.utils import bec_dispatcher as dispatcher_module

        mock.patch.object(dispatcher_module, "BECClient", mock_client).start()
    ''')

# The unit suite collects test_rpc_server/test_companion_app, which import the GUI server module.
IMPORT_COMPANION_APP = """
import bec_widgets.applications.companion_app  # noqa: F401
report()
time.sleep(120)
"""

# A Python-driven process (like a test run) that created a Monaco editor; on KeyboardInterrupt
# it shuts the BEC client down like the bec_dispatcher fixture teardown does (its non-daemon threads would
# otherwise keep the interpreter alive).
MONACO_WIDGET_PYTHON_LOOP = """
use_fake_bec()
from qtpy.QtWidgets import QApplication
app = QApplication([sys.argv[0]])
from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
editor = MonacoWidget()
report()
try:
    time.sleep(120)
finally:
    dispatcher = BECDispatcher()
    dispatcher.disconnect_all()
    dispatcher.client.shutdown()
    dispatcher.stop_cli_server()
"""

# A Qt application that created a Monaco editor (bec-app device manager, plugins, designer forms).
MONACO_WIDGET_QT_LOOP = """
use_fake_bec()
from qtpy.QtWidgets import QApplication
app = QApplication([sys.argv[0]])
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
editor = MonacoWidget()
editor.show()
report_from_event_loop()
sys.exit(app.exec())
"""

# bec-app as started by its console script (its device manager view holds a Monaco editor).
BEC_APP = """
use_fake_bec()
from bec_widgets.applications import main_app
_mark = main_app.startup_profiler.mark
def mark(stage, **kwargs):
    _mark(stage, **kwargs)
    if stage == "interactive":
        report_from_event_loop()
main_app.startup_profiler.mark = mark
sys.argv = [sys.argv[0]]
main_app.main()
"""

# bec-gui-server; a Monaco editor is created after the server installed its shutdown handlers.
GUI_SERVER_WITH_MONACO = """
use_fake_bec()
from bec_widgets.applications import companion_app
_ready = companion_app.GUIServer._notify_server_ready
editors = []
def ready(self):
    _ready(self)
    from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
    editors.append(MonacoWidget())
    editors[-1].show()
    report_from_event_loop()
companion_app.GUIServer._notify_server_ready = ready
sys.argv = ["bec-gui-server", "--id", "signal_test"]
companion_app.main()
"""

# A pytest run whose collection imports the GUI server module (as tests/unit_tests does).
PYTEST_RUN_TEST_FILE = """
import os, time
import bec_widgets.applications.companion_app  # noqa: F401

def test_sleep():
    path = os.environ["SIGNAL_TEST_READY_FILE"]
    with open(path + ".tmp", "w") as f:
        f.write("{}")
    os.replace(path + ".tmp", path)
    time.sleep(120)
"""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - pid reused by another user's process
        return True
    return True


def _child_env(tmp_path: Path) -> dict:
    env = dict(os.environ)
    env.update(
        SIGNAL_TEST_READY_FILE=str(tmp_path / "ready.json"),
        BECWIDGETS_PROFILE_DIR=str(tmp_path / "profiles"),
        QT_QPA_PLATFORM="offscreen",
        BEC_WIDGETS_OPENGL="0",
        QTWEBENGINE_DISABLE_SANDBOX="1",
        QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu",
        OPHYD_CONTROL_LAYER="dummy",
    )
    return env


def _signal_child(cmd: list[str], tmp_path: Path, sig: signal.Signals, cwd: Path) -> dict:
    """
    Start ``cmd``, wait for its READY file, send ``sig`` and wait for the exit.

    Returns:
        dict: ``returncode`` (None if the child survived EXIT_TIMEOUT and was SIGKILLed),
        ``seconds`` until the exit, ``pylsp_leaked`` and the child's READY info.
    """
    ready_file = tmp_path / "ready.json"
    log_file = tmp_path / "child.log"
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=_child_env(tmp_path), stdout=log, stderr=subprocess.STDOUT
        )
    pylsp_pid = None
    try:
        deadline = time.monotonic() + READY_TIMEOUT
        while not ready_file.exists():
            if proc.poll() is not None or time.monotonic() > deadline:
                pytest.fail(f"child not ready (rc={proc.poll()}):\n{log_file.read_text()[-3000:]}")
            time.sleep(0.1)
        info = json.loads(ready_file.read_text())
        pylsp_pid = info.get("pylsp_pid")
        start = time.monotonic()
        proc.send_signal(sig)
        try:
            returncode = proc.wait(timeout=EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            returncode = None
        seconds = time.monotonic() - start
        pylsp_leaked = False
        if pylsp_pid is not None and returncode is not None:
            time.sleep(0.5)
            pylsp_leaked = _pid_alive(pylsp_pid)
        return {
            "returncode": returncode,
            "seconds": seconds,
            "pylsp_leaked": pylsp_leaked,
            "info": info,
            "log": log_file.read_text()[-3000:],
        }
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if pylsp_pid is not None and _pid_alive(pylsp_pid):
            os.kill(pylsp_pid, signal.SIGKILL)


def _python_child(script: str) -> list[str]:
    return [sys.executable, "-c", CHILD_BOOT + textwrap.dedent(script)]


def _assert_exited(result: dict, sig: signal.Signals, expected_returncodes: tuple[int, ...]):
    assert result["returncode"] is not None, (
        f"process ignored {sig.name} for {EXIT_TIMEOUT:.0f}s "
        f"(handlers at READY: {result['info']})\n{result['log']}"
    )
    assert result["returncode"] in expected_returncodes, result["log"]
    assert not result["pylsp_leaked"], "pylsp language server outlived its process"


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=lambda s: s.name)
def test_importing_companion_app_keeps_process_killable(tmp_path, sig):
    result = _signal_child(_python_child(IMPORT_COMPANION_APP), tmp_path, sig, REPO_ROOT)
    _assert_exited(result, sig, (-sig,))


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=lambda s: s.name)
def test_monaco_widget_keeps_python_process_killable(tmp_path, sig):
    result = _signal_child(_python_child(MONACO_WIDGET_PYTHON_LOOP), tmp_path, sig, REPO_ROOT)
    assert result["info"]["pylsp_pid"] is not None, "Monaco editor did not start pylsp"
    _assert_exited(result, sig, (-sig,))


def test_monaco_widget_qt_application_terminates_on_sigterm(tmp_path):
    result = _signal_child(
        _python_child(MONACO_WIDGET_QT_LOOP), tmp_path, signal.SIGTERM, REPO_ROOT
    )
    assert result["info"]["pylsp_pid"] is not None, "Monaco editor did not start pylsp"
    _assert_exited(result, signal.SIGTERM, (-signal.SIGTERM,))


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=lambda s: s.name)
def test_bec_app_quits_on_signal(tmp_path, sig):
    result = _signal_child(_python_child(BEC_APP), tmp_path, sig, REPO_ROOT)
    assert result["info"]["pylsp_pid"] is not None, "bec-app did not create a Monaco editor"
    _assert_exited(result, sig, (0,))


def test_gui_server_with_monaco_still_shuts_down_on_sigterm(tmp_path):
    result = _signal_child(
        _python_child(GUI_SERVER_WITH_MONACO), tmp_path, signal.SIGTERM, REPO_ROOT
    )
    assert result["info"]["pylsp_pid"] is not None, "Monaco editor did not start pylsp"
    _assert_exited(result, signal.SIGTERM, (0,))


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=lambda s: s.name)
def test_pytest_run_importing_companion_app_stops_on_signal(tmp_path, sig):
    test_dir = tmp_path / "suite"
    test_dir.mkdir()
    (test_dir / "test_sleep.py").write_text(textwrap.dedent(PYTEST_RUN_TEST_FILE))
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_sleep.py"]
    result = _signal_child(cmd, tmp_path, sig, test_dir)
    # SIGINT: pytest reports the KeyboardInterrupt and exits with ExitCode.INTERRUPTED (2)
    _assert_exited(result, sig, (-signal.SIGTERM,) if sig == signal.SIGTERM else (2,))
