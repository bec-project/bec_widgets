import signal
import subprocess
from contextlib import contextmanager
from unittest import mock

import pytest

from bec_widgets.cli.client import BECDockArea
from bec_widgets.cli.client_utils import (
    GRACEFUL_SERVER_SHUTDOWN_RPC_TIMEOUT,
    OUTPUT_READER_STOP_EVENT_ATTR,
    BECGuiClient,
    _join_process_output_thread,
    _start_plot_process,
    check_gui_display_available,
)
from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCResponseTimeoutError, rpc_timeout


@pytest.fixture
def cli_dock_area():
    dock_area = BECDockArea(gui_id="test")
    with mock.patch.object(dock_area, "_run_rpc") as mock_rpc_call:
        with mock.patch.object(dock_area, "_gui_is_alive", return_value=True):
            yield dock_area, mock_rpc_call


def test_rpc_call_new_dock(cli_dock_area):
    dock_area, mock_rpc_call = cli_dock_area
    dock_area.new(name="test")
    mock_rpc_call.assert_called_with("new", name="test")


@pytest.mark.parametrize(
    "config, call_config",
    [
        (None, None),
        ("/path/to/config.yml", "/path/to/config.yml"),
        ({"key": "value"}, '{"key": "value"}'),
    ],
)
def test_client_utils_start_plot_process(config, call_config):
    with mock.patch("bec_widgets.cli.client_utils.subprocess.Popen") as mock_popen:
        _start_plot_process("gui_id", "bec", config, gui_class="AdvancedDockArea")
        command = [
            "bec-gui-server",
            "--id",
            "gui_id",
            "--gui_class",
            "AdvancedDockArea",
            "--gui_class_id",
            "bec",
            "--hide",
        ]
        if call_config:
            command.extend(["--config", call_config])
        mock_popen.assert_called_once_with(
            command,
            text=True,
            start_new_session=True,
            stdout=mock.ANY,
            stderr=mock.ANY,
            env=mock.ANY,
        )


def test_client_utils_passes_client_config_to_server(bec_dispatcher):
    """
    Test that the client config is passed to the server. This ensures that
    changes to the client config (either through config files or plugins) are
    reflected in the server.
    """

    @contextmanager
    def bec_client_mixin():
        mixin = BECGuiClient()
        mixin._client = bec_dispatcher.client
        mixin._gui_id = "gui_id"
        mixin._gui_is_alive = mock.MagicMock()
        mixin._gui_is_alive.side_effect = [False, False, True]

        try:
            yield mixin
        finally:
            mixin.kill_server()

    with bec_client_mixin() as mixin:
        with mock.patch("bec_widgets.cli.client_utils._start_plot_process") as mock_start_plot:
            mock_start_plot.return_value = [mock.MagicMock(), mock.MagicMock()]
            mixin._start_server(
                wait=False
            )  # the started event will not be set, wait=True would block forever
            mock_start_plot.assert_called_once_with(
                "gui_id",
                gui_class_id="bec",
                config=mixin._client._service_config.config,
                logger=mock.ANY,
            )


def test_check_gui_display_available_reports_missing_display_for_ssh_session():
    with mock.patch.dict(
        "bec_widgets.cli.client_utils.os.environ", {"SSH_CONNECTION": "1"}, clear=True
    ):
        available, message = check_gui_display_available()

    assert available is False
    assert message is not None
    assert "SSH session" in message
    assert "ssh -X" in message


def test_client_utils_start_server_returns_when_no_display(bec_dispatcher):
    gui = BECGuiClient()
    gui._client = bec_dispatcher.client
    gui._gui_id = "gui_id"
    gui._gui_is_alive = mock.MagicMock(return_value=False)

    with (
        mock.patch(
            "bec_widgets.cli.client_utils.check_gui_display_available",
            return_value=(False, "No display available"),
        ),
        mock.patch("bec_widgets.cli.client_utils._start_plot_process") as mock_start_plot,
        mock.patch("bec_widgets.cli.client_utils.logger") as mock_logger,
    ):
        gui._start_server(wait=False)

    mock_start_plot.assert_not_called()
    mock_logger.error.assert_called_once_with("No display available")


@contextmanager
def _no_wait_for_server(_client):
    yield


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_client_utils_apply_theme_explicit(theme):
    gui = BECGuiClient()
    launcher = mock.MagicMock()

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                gui.change_theme(theme)

    launcher._run_rpc.assert_called_once_with("change_theme", theme=theme)


@pytest.mark.parametrize("current_theme, expected_theme", [("light", "dark"), ("dark", "light")])
def test_client_utils_apply_theme_toggles_when_none(current_theme, expected_theme):
    gui = BECGuiClient()
    launcher = mock.MagicMock()
    launcher._run_rpc.side_effect = [current_theme, None]

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                gui.change_theme(None)

    assert launcher._run_rpc.call_args_list == [
        mock.call("fetch_theme"),
        mock.call("change_theme", theme=expected_theme),
    ]


def test_client_utils_new_passes_startup_profile():
    gui = BECGuiClient()
    launcher = mock.MagicMock()

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                gui.new(startup_profile="saved_profile")

    launcher._run_rpc.assert_called_once_with(
        "system.launch_dock_area", name=None, geometry=None, startup_profile="saved_profile"
    )


def test_client_utils_new_defaults_to_empty_startup_profile():
    gui = BECGuiClient()
    launcher = mock.MagicMock()

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                gui.new()

    launcher._run_rpc.assert_called_once_with(
        "system.launch_dock_area", name=None, geometry=None, startup_profile=None
    )


def test_client_utils_new_rejects_legacy_profile_kwargs():
    gui = BECGuiClient()
    with pytest.raises(TypeError, match="startup_profile"):
        gui.new(profile="saved_profile")


def test_client_utils_new_falls_back_when_system_rpc_not_supported():
    gui = BECGuiClient()
    launcher = mock.MagicMock()
    launcher._run_rpc.side_effect = [
        ValueError("Unknown system RPC method: system.launch_dock_area"),
        "fallback_widget",
    ]

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                result = gui.new(startup_profile="restore")

    assert result == "fallback_widget"
    assert launcher._run_rpc.call_args_list == [
        mock.call("system.launch_dock_area", name=None, geometry=None, startup_profile="restore"),
        mock.call(
            "launch", launch_script="dock_area", name=None, geometry=None, startup_profile="restore"
        ),
    ]


def test_client_utils_new_reraises_unexpected_system_rpc_error():
    gui = BECGuiClient()
    launcher = mock.MagicMock()
    launcher._run_rpc.side_effect = ValueError("Some other RPC error")

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with mock.patch.object(gui, "_check_if_server_is_alive", return_value=True):
                with pytest.raises(ValueError, match="Some other RPC error"):
                    gui.new(startup_profile="restore")


def test_client_utils_new_starts_server_when_not_alive():
    gui = BECGuiClient()
    launcher = mock.MagicMock()

    with mock.patch.object(
        BECGuiClient, "launcher", new_callable=mock.PropertyMock
    ) as launcher_prop:
        launcher_prop.return_value = launcher
        with mock.patch("bec_widgets.cli.client_utils.wait_for_server", _no_wait_for_server):
            with (
                mock.patch.object(gui, "_check_if_server_is_alive", return_value=False),
                mock.patch.object(gui, "show") as mock_start,
            ):
                gui.new(wait=False, startup_profile=None)

    mock_start.assert_called_once_with(wait=True)


def test_client_utils_delete_uses_container_proxy():
    gui = BECGuiClient()
    widget = mock.MagicMock()
    widget._gui_id = "widget-id"

    with (
        mock.patch.object(BECGuiClient, "windows", new_callable=mock.PropertyMock) as windows_prop,
        mock.patch.dict(
            gui._server_registry, {"widget-id": {"container_proxy": "container-id"}}, clear=True
        ),
    ):
        windows_prop.return_value = {"dock": widget}
        gui.delete("dock")

    widget._run_rpc.assert_called_once_with("close", gui_id="container-id")


def test_client_utils_delete_falls_back_to_direct_close():
    gui = BECGuiClient()
    widget = mock.MagicMock()
    widget._gui_id = "widget-id"

    with (
        mock.patch.object(BECGuiClient, "windows", new_callable=mock.PropertyMock) as windows_prop,
        mock.patch.dict(gui._server_registry, {"widget-id": {"container_proxy": None}}, clear=True),
    ):
        windows_prop.return_value = {"dock": widget}
        gui.delete("dock")

    widget._run_rpc.assert_called_once_with("close")


def test_client_utils_gui_client_set_rpc_timeout():
    gui = BECGuiClient()
    assert gui._rpc_timeout == 60

    gui.set_rpc_timeout(10)
    assert gui._rpc_timeout == 10


def test_client_utils_kill_server_waits_for_process_before_joining_output_thread():
    gui = BECGuiClient()
    gui._client = mock.MagicMock()
    gui._process = mock.MagicMock(pid=123, stdout=None, stderr=None)
    gui._process.poll.return_value = None
    order = []
    gui._process.wait.side_effect = lambda timeout: order.append("wait")
    gui._process_output_processing_thread = mock.MagicMock()
    gui._process_output_processing_thread.join.side_effect = lambda timeout: order.append("join")
    gui._process_output_processing_thread.is_alive.return_value = False

    with (
        mock.patch.object(gui, "_request_server_shutdown", return_value=False),
        mock.patch("bec_widgets.cli.client_utils.os.getpgid", return_value=123),
        mock.patch("bec_widgets.cli.client_utils.os.killpg") as killpg,
    ):
        gui.kill_server()

    killpg.assert_called_once_with(123, signal.SIGTERM)
    assert order == ["wait", "join"]
    assert gui._process is None
    assert gui._process_output_processing_thread is None


def test_client_utils_kill_server_requests_graceful_shutdown_before_signal():
    gui = BECGuiClient()
    gui._client = mock.MagicMock()
    process = mock.MagicMock(stdout=None, stderr=None)
    process.poll.return_value = None
    gui._process = process
    gui._process_output_processing_thread = mock.MagicMock()
    gui._process_output_processing_thread.is_alive.return_value = False
    launcher = mock.MagicMock()

    with (
        mock.patch.object(
            BECGuiClient, "launcher", new_callable=mock.PropertyMock
        ) as launcher_prop,
        mock.patch("bec_widgets.cli.client_utils.os.killpg") as killpg,
    ):
        launcher_prop.return_value = launcher
        gui.kill_server()

    launcher._run_rpc.assert_called_once_with(
        "system.shutdown", wait_for_rpc_response=True, timeout=GRACEFUL_SERVER_SHUTDOWN_RPC_TIMEOUT
    )
    process.wait.assert_called_once_with(timeout=5)
    killpg.assert_not_called()
    assert gui._process is None
    assert gui._process_output_processing_thread is None


def test_client_utils_kill_server_kills_process_group_after_timeout():
    gui = BECGuiClient()
    gui._client = mock.MagicMock()
    process = mock.MagicMock(pid=123, stdout=None, stderr=None, args=["bec-gui-server"])
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired(cmd="bec-gui-server", timeout=10), None]
    gui._process = process

    with (
        mock.patch.object(gui, "_request_server_shutdown", return_value=False),
        mock.patch("bec_widgets.cli.client_utils.os.getpgid", return_value=123),
        mock.patch("bec_widgets.cli.client_utils.os.killpg") as killpg,
        mock.patch("bec_widgets.cli.client_utils.subprocess.run") as run,
    ):
        run.return_value.stdout = "PID PPID PGID STAT COMMAND\n123 1 123 S bec-gui-server"
        gui.kill_server()

    assert killpg.call_args_list == [mock.call(123, signal.SIGTERM), mock.call(123, signal.SIGKILL)]
    assert process.wait.call_args_list == [mock.call(timeout=10), mock.call(timeout=10)]
    run.assert_called_once_with(
        ["ps", "-o", "pid,ppid,pgid,stat,command", "-g", "123"],
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )


def test_join_process_output_thread_signals_reader_before_closing_streams():
    process = mock.MagicMock(pid=123, args=["bec-gui-server"])
    process.stdout = mock.MagicMock()
    process.stderr = mock.MagicMock()
    thread = mock.MagicMock()
    stop_event = mock.MagicMock()
    setattr(thread, OUTPUT_READER_STOP_EVENT_ATTR, stop_event)
    thread.is_alive.side_effect = [True, False]
    logger = mock.MagicMock()

    _join_process_output_thread(process, thread, logger)

    assert thread.join.call_args_list == [mock.call(timeout=2), mock.call(timeout=2)]
    stop_event.set.assert_called_once_with()
    process.stdout.close.assert_called_once_with()
    process.stderr.close.assert_called_once_with()
