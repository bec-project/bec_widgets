import os
import select
import shlex
import signal
import socket
import subprocess
from typing import Literal

from pydantic import BaseModel
from qtpy.QtCore import Signal, Slot

from bec_widgets.widgets.editors.website.website import WebsiteWidget


class VSCodeInstructionMessage(BaseModel):
    command: Literal["open", "write", "close", "zenMode", "save", "new", "setCursor"]
    content: str = ""


def get_free_port():
    """
    Get a free port on the local machine.

    Returns:
        int: The free port number
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class VSCodeEditor(WebsiteWidget):
    """
    A widget to display the VSCode editor.
    """

    file_saved = Signal(str)

    token = "bec"
    host = "127.0.0.1"

    PLUGIN = True
    USER_ACCESS = []
    ICON_NAME = "developer_mode_tv"

    def __init__(self, parent=None, config=None, client=None, gui_id=None):

        self.process = None
        self.port = get_free_port()
        self._url = f"http://{self.host}:{self.port}?tkn={self.token}"
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)
        self.start_server()
        self.bec_dispatcher.connect_slot(self.on_vscode_event, f"vscode-events/{self.gui_id}")

    def start_server(self):
        """
        Start the server.

        This method starts the server for the VSCode editor in a subprocess.
        """

        env = os.environ.copy()
        env["BEC_Widgets_GUIID"] = self.gui_id
        env["BEC_REDIS_HOST"] = self.client.connector.host
        cmd = shlex.split(
            f"code serve-web --port {self.port} --connection-token={self.token} --accept-server-license-terms"
        )
        self.process = subprocess.Popen(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            env=env,
        )

        os.set_blocking(self.process.stdout.fileno(), False)
        while self.process.poll() is None:
            readylist, _, _ = select.select([self.process.stdout], [], [], 1)
            if self.process.stdout in readylist:
                output = self.process.stdout.read(1024)
                if output and f"available at {self._url}" in output:
                    break
        self.set_url(self._url)
        self.wait_until_loaded()

    @Slot(str)
    def open_file(self, file_path: str):
        """
        Open a file in the VSCode editor.

        Args:
            file_path: The file path to open
        """
        msg = VSCodeInstructionMessage(command="open", content=f"file://{file_path}")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot(dict, dict)
    def on_vscode_event(self, content, _metadata):
        """
        Handle the VSCode event. VSCode events are received as RawMessages.

        Args:
            content: The content of the event
            metadata: The metadata of the event
        """

        # the message also contains the content but I think is fine for now to just emit the file path
        if not isinstance(content["data"], dict):
            return
        if "uri" not in content["data"]:
            return
        if not content["data"]["uri"].startswith("file://"):
            return
        file_path = content["data"]["uri"].split("file://")[1]
        self.file_saved.emit(file_path)

    @Slot()
    def save_file(self):
        """
        Save the file in the VSCode editor.
        """
        msg = VSCodeInstructionMessage(command="save")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot()
    def new_file(self):
        """
        Create a new file in the VSCode editor.
        """
        msg = VSCodeInstructionMessage(command="new")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot()
    def close_file(self):
        """
        Close the file in the VSCode editor.
        """
        msg = VSCodeInstructionMessage(command="close")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot(str)
    def write_file(self, content: str):
        """
        Write content to the file in the VSCode editor.

        Args:
            content: The content to write
        """
        msg = VSCodeInstructionMessage(command="write", content=content)
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot()
    def zen_mode(self):
        """
        Toggle the Zen mode in the VSCode editor.
        """
        msg = VSCodeInstructionMessage(command="zenMode")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    @Slot(int, int)
    def set_cursor(self, line: int, column: int):
        """
        Set the cursor in the VSCode editor.

        Args:
            line: The line number
            column: The column number
        """
        msg = VSCodeInstructionMessage(command="setCursor", content=f"{line},{column}")
        self.client.connector.raw_send(f"vscode-instructions/{self.gui_id}", msg.model_dump_json())

    def cleanup_vscode(self):
        """
        Cleanup the VSCode editor.
        """
        if not self.process or self.process.poll() is not None:
            return
        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        self.process.wait()

    def cleanup(self):
        """
        Cleanup the widget. This method is called from the dock area when the widget is removed.
        """
        self.bec_dispatcher.disconnect_slot(self.on_vscode_event, f"vscode-events/{self.gui_id}")
        self.cleanup_vscode()
        return super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = VSCodeEditor(gui_id="unknown")
    widget.show()
    app.exec_()
    widget.bec_dispatcher.disconnect_all()
    widget.client.shutdown()
