import os
import shlex
import subprocess
from unittest import mock

import pytest

from bec_widgets.widgets.editors.vscode.vscode import VSCodeEditor

from .client_mocks import mocked_client


@pytest.fixture
def vscode_widget(qtbot, mocked_client):
    with mock.patch("bec_widgets.widgets.editors.vscode.vscode.subprocess.Popen") as mock_popen:
        widget = VSCodeEditor(client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget


def test_vscode_widget(qtbot, vscode_widget):
    assert vscode_widget.process is not None
    assert vscode_widget._url == f"http://127.0.0.1:{vscode_widget.port}?tkn=bec"


def test_start_server(qtbot, mocked_client):
    with mock.patch("bec_widgets.widgets.editors.vscode.vscode.os.killpg") as mock_killpg:
        with mock.patch("bec_widgets.widgets.editors.vscode.vscode.os.getpgid") as mock_getpgid:
            with mock.patch(
                "bec_widgets.widgets.editors.vscode.vscode.subprocess.Popen"
            ) as mock_popen:
                with mock.patch(
                    "bec_widgets.widgets.editors.vscode.vscode.select.select"
                ) as mock_select:
                    with mock.patch(
                        "bec_widgets.widgets.editors.vscode.vscode.get_free_port"
                    ) as mock_get_free_port:
                        mock_get_free_port.return_value = 12345
                        mock_process = mock.Mock()
                        mock_process.stdout.fileno.return_value = 1
                        mock_process.poll.return_value = None
                        mock_process.stdout.read.return_value = f"available at http://{VSCodeEditor.host}:{12345}?tkn={VSCodeEditor.token}"
                        mock_popen.return_value = mock_process
                        mock_select.return_value = [[mock_process.stdout], [], []]

                        widget = VSCodeEditor(client=mocked_client)
                        widget.close()
                        widget.deleteLater()

                    assert (
                        mock.call(
                            shlex.split(
                                f"code serve-web --port {widget.port} --connection-token={widget.token} --accept-server-license-terms"
                            ),
                            text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            preexec_fn=os.setsid,
                            env=mock.ANY,
                        )
                        in mock_popen.mock_calls
                    )


@pytest.fixture
def patched_vscode_process(qtbot, vscode_widget):
    with mock.patch("bec_widgets.widgets.editors.vscode.vscode.os.killpg") as mock_killpg:
        mock_killpg.reset_mock()
        with mock.patch("bec_widgets.widgets.editors.vscode.vscode.os.getpgid") as mock_getpgid:
            mock_getpgid.return_value = 123
            vscode_widget.process = mock.Mock()
            yield vscode_widget, mock_killpg


def test_vscode_cleanup(qtbot, patched_vscode_process):
    vscode_patched, mock_killpg = patched_vscode_process
    vscode_patched.process.pid = 123
    vscode_patched.process.poll.return_value = None
    vscode_patched.cleanup_vscode()
    mock_killpg.assert_called_once_with(123, 15)
    vscode_patched.process.wait.assert_called_once()


def test_close_event_on_terminated_code(qtbot, patched_vscode_process):
    vscode_patched, mock_killpg = patched_vscode_process
    vscode_patched.process.pid = 123
    vscode_patched.process.poll.return_value = 0
    vscode_patched.cleanup_vscode()
    mock_killpg.assert_not_called()
    vscode_patched.process.wait.assert_not_called()
