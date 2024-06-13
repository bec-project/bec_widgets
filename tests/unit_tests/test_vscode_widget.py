import os
import shlex
import subprocess
from unittest import mock

import pytest

from bec_widgets.widgets.vscode.vscode import VSCodeEditor

from .client_mocks import mocked_client


@pytest.fixture
def vscode_widget(qtbot, mocked_client):
    with mock.patch("bec_widgets.widgets.vscode.vscode.subprocess.Popen") as mock_popen:
        widget = VSCodeEditor(client=mocked_client)
        yield widget


def test_vscode_widget(qtbot, vscode_widget):
    assert vscode_widget.process is not None
    assert vscode_widget._url == "http://127.0.0.1:7000?tkn=bec"


def test_start_server(qtbot, mocked_client):

    with mock.patch("bec_widgets.widgets.vscode.vscode.subprocess.Popen") as mock_popen:
        mock_process = mock.Mock()
        mock_process.stdout.fileno.return_value = 1
        mock_process.poll.return_value = None
        mock_process.stdout.read.return_value = (
            f"available at http://{VSCodeEditor.host}:{VSCodeEditor.port}?tkn={VSCodeEditor.token}"
        )
        mock_popen.return_value = mock_process

        widget = VSCodeEditor(client=mocked_client)

        mock_popen.assert_called_once_with(
            shlex.split(
                f"code serve-web --port {widget.port} --connection-token={widget.token} --accept-server-license-terms"
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )


def test_close_event(qtbot, vscode_widget):
    with mock.patch("bec_widgets.widgets.vscode.vscode.os.killpg") as mock_killpg:
        with mock.patch("bec_widgets.widgets.vscode.vscode.os.getpgid") as mock_getpgid:
            with mock.patch(
                "bec_widgets.widgets.website.website.WebsiteWidget.closeEvent"
            ) as mock_close_event:
                mock_getpgid.return_value = 123
                vscode_widget.process = mock.Mock()
                vscode_widget.process.pid = 123
                vscode_widget.closeEvent(None)
                mock_killpg.assert_called_once_with(123, 15)
                vscode_widget.process.wait.assert_called_once()
                mock_close_event.assert_called_once()
