from __future__ import annotations

import secrets
import subprocess
import time

from bec_lib.logger import bec_logger
from louie.saferef import safe_ref
from qtpy.QtCore import QTimer, QUrl, Signal, qInstallMessageHandler
from qtpy.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty

logger = bec_logger.logger


class WebConsoleRegistry:
    """
    A registry for the WebConsole class to manage its instances.
    """

    def __init__(self):
        """
        Initialize the registry.
        """
        self._instances = {}
        self._server_process = None
        self._server_port = None
        self._token = secrets.token_hex(16)

    def register(self, instance: WebConsole):
        """
        Register an instance of WebConsole.
        """
        self._instances[instance.gui_id] = safe_ref(instance)
        self.cleanup()

        if self._server_process is None:
            # Start the ttyd server if not already running
            self.start_ttyd()

    def start_ttyd(self, use_zsh: bool | None = None):
        """
        Start the ttyd server
        ttyd -q -W -t 'theme={"background": "black"}' zsh

        Args:
            use_zsh (bool): Whether to use zsh or bash. If None, it will try to detect if zsh is available.
        """

        # First, check if ttyd is installed
        try:
            subprocess.run(["ttyd", "--version"], check=True, stdout=subprocess.PIPE)
        except FileNotFoundError:
            # pylint: disable=raise-missing-from
            raise RuntimeError("ttyd is not installed. Please install it first.")

        if use_zsh is None:
            # Check if we can use zsh
            try:
                subprocess.run(["zsh", "--version"], check=True, stdout=subprocess.PIPE)
                use_zsh = True
            except FileNotFoundError:
                use_zsh = False

        command = [
            "ttyd",
            "-p",
            "0",
            "-W",
            "-t",
            'theme={"background": "black"}',
            "-c",
            f"user:{self._token}",
        ]
        if use_zsh:
            command.append("zsh")
        else:
            command.append("bash")

        # Start the ttyd server
        self._server_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        self._wait_for_server_port()

        self._server_process.stdout.close()
        self._server_process.stderr.close()

    def _wait_for_server_port(self, timeout: float = 10):
        """
        Wait for the ttyd server to start and get the port number.

        Args:
            timeout (float): The timeout in seconds to wait for the server to start.
        """
        start_time = time.time()
        while True:
            output = self._server_process.stderr.readline()
            if output == b"" and self._server_process.poll() is not None:
                break
            if not output:
                continue

            output = output.decode("utf-8").strip()
            if "Listening on" in output:
                # Extract the port number from the output
                self._server_port = int(output.split(":")[-1])
                logger.info(f"ttyd server started on port {self._server_port}")
                break
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    "Timeout waiting for ttyd server to start. Please check if ttyd is installed and available in your PATH."
                )

    def cleanup(self):
        """
        Clean up the registry by removing any instances that are no longer valid.
        """
        for gui_id, weak_ref in list(self._instances.items()):
            if weak_ref() is None:
                del self._instances[gui_id]

        if not self._instances and self._server_process:
            # If no instances are left, terminate the server process
            self._server_process.terminate()
            self._server_process = None
            self._server_port = None
            logger.info("ttyd server terminated")

    def unregister(self, instance: WebConsole):
        """
        Unregister an instance of WebConsole.

        Args:
            instance (WebConsole): The instance to unregister.
        """
        if instance.gui_id in self._instances:
            del self._instances[instance.gui_id]

        self.cleanup()


_web_console_registry = WebConsoleRegistry()


def suppress_qt_messages(type_, context, msg):
    if context.category in ["js", "default"]:
        return
    print(msg)


qInstallMessageHandler(suppress_qt_messages)


class BECWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        logger.info(f"[JS Console] {level.name} at line {lineNumber} in {sourceID}: {message}")


class WebConsole(BECWidget, QWidget):
    """
    A simple widget to display a website
    """

    _js_callback = Signal(bool)
    initialized = Signal()

    PLUGIN = True
    ICON_NAME = "terminal"

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self._startup_cmd = "bec --nogui"
        self._is_initialized = False
        _web_console_registry.register(self)
        self._token = _web_console_registry._token
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView(self)
        self.page = BECWebEnginePage(self)
        self.page.authenticationRequired.connect(self._authenticate)
        self.browser.setPage(self.page)
        layout.addWidget(self.browser)
        self.setLayout(layout)
        self.page.setUrl(QUrl(f"http://localhost:{_web_console_registry._server_port}"))
        self._startup_timer = QTimer()
        self._startup_timer.setInterval(500)
        self._startup_timer.timeout.connect(self._check_page_ready)
        self._startup_timer.start()
        self._js_callback.connect(self._on_js_callback)

    def _check_page_ready(self):
        """
        Check if the page is ready and stop the timer if it is.
        """
        if self.page.isLoading():
            return

        self.page.runJavaScript("window.term !== undefined", self._js_callback.emit)

    def _on_js_callback(self, ready: bool):
        """
        Callback for when the JavaScript is ready.
        """
        if not ready:
            return
        self._is_initialized = True
        self._startup_timer.stop()
        if self._startup_cmd:
            self.write(self._startup_cmd)
        self.initialized.emit()

    @SafeProperty(str)
    def startup_cmd(self):
        """
        Get the startup command for the web console.
        """
        return self._startup_cmd

    @startup_cmd.setter
    def startup_cmd(self, cmd: str):
        """
        Set the startup command for the web console.
        """
        if not isinstance(cmd, str):
            raise ValueError("Startup command must be a string.")
        self._startup_cmd = cmd

    def write(self, data: str, send_return: bool = True):
        """
        Send data to the web page
        """
        self.page.runJavaScript(f"window.term.paste('{data}');")
        if send_return:
            self.send_return()

    def _authenticate(self, _, auth):
        """
        Authenticate the request with the provided username and password.
        """
        auth.setUser("user")
        auth.setPassword(self._token)

    def send_return(self):
        """
        Send return to the web page
        """
        self.page.runJavaScript(
            "document.querySelector('textarea.xterm-helper-textarea').dispatchEvent(new KeyboardEvent('keypress', {charCode: 13}))"
        )

    def send_ctrl_c(self):
        """
        Send Ctrl+C to the web page
        """
        self.page.runJavaScript(
            "document.querySelector('textarea.xterm-helper-textarea').dispatchEvent(new KeyboardEvent('keypress', {charCode: 3}))"
        )

    def set_readonly(self, readonly: bool):
        """
        Set the web console to read-only mode.
        """
        if not isinstance(readonly, bool):
            raise ValueError("Readonly must be a boolean.")
        self.setEnabled(not readonly)

    def cleanup(self):
        """
        Clean up the registry by removing any instances that are no longer valid.
        """
        self._startup_timer.stop()
        _web_console_registry.unregister(self)
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    widget = WebConsole()
    widget.show()
    sys.exit(app.exec_())
