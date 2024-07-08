import os
import select
import shlex
import signal
import subprocess
import sys

from bec_widgets.widgets.website.website import WebsiteWidget


class VSCodeEditor(WebsiteWidget):
    """
    A widget to display the VSCode editor.
    """

    token = "bec"
    host = "127.0.0.1"
    port = 7000

    USER_ACCESS = []

    def __init__(self, parent=None, config=None, client=None, gui_id=None):

        self.process = None
        self._url = f"http://{self.host}:{self.port}?tkn={self.token}"
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)
        self.start_server()

    def start_server(self):
        """
        Start the server.

        This method starts the server for the VSCode editor in a subprocess.
        """

        cmd = shlex.split(
            f"code serve-web --port {self.port} --connection-token={self.token} --accept-server-license-terms"
        )
        self.process = subprocess.Popen(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, preexec_fn=os.setsid
        )

        os.set_blocking(self.process.stdout.fileno(), False)
        while self.process.poll() is None:
            readylist, _, _ = select.select([self.process.stdout], [], [], 1)
            if self.process.stdout in readylist:
                output = self.process.stdout.read(1024)
                if output and f"available at {self._url}" in output:
                    break
        self.set_url(self._url)

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
        self.cleanup_vscode()
        return super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = VSCodeEditor()
    widget.show()
    app.exec_()
    widget.bec_dispatcher.disconnect_all()
    widget.client.shutdown()
