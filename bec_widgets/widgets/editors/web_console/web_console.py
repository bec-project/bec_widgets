from __future__ import annotations

import json
import secrets
import subprocess
import time

from bec_lib.logger import bec_logger
from louie.saferef import safe_ref
from pydantic import BaseModel
from qtpy.QtCore import QTimer, QUrl, Signal, qInstallMessageHandler
from qtpy.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from qtpy.QtWidgets import QApplication, QPushButton, QTabWidget, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty

logger = bec_logger.logger


class PageOwnerInfo(BaseModel):
    owner_gui_id: str | None = None
    widget_ids: list[str] = []
    page: QWebEnginePage | None = None
    initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}


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
        self._page_registry: dict[str, PageOwnerInfo] = {}

    def register(self, instance: WebConsole):
        """
        Register an instance of WebConsole.
        """
        self._instances[instance.gui_id] = safe_ref(instance)
        self.cleanup()

        if instance._unique_id:
            self._register_page(instance)

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

        if instance._unique_id:
            self._unregister_page(instance._unique_id, instance.gui_id)

        self.cleanup()

    def _register_page(self, instance: WebConsole):
        """
        Register a page in the registry. Please note that this does not transfer ownership;
        it simply records which widget currently owns the page.
        Use transfer_page_ownership to change ownership.

        Args:
            instance (WebConsole): The instance to register.
        """

        unique_id = instance._unique_id
        gui_id = instance.gui_id

        if unique_id is None:
            return

        if unique_id not in self._page_registry:
            page = BECWebEnginePage()
            page.authenticationRequired.connect(instance._authenticate)
            self._page_registry[unique_id] = PageOwnerInfo(
                owner_gui_id=gui_id, widget_ids=[gui_id], page=page
            )
            return

        if gui_id not in self._page_registry[unique_id].widget_ids:
            self._page_registry[unique_id].widget_ids.append(gui_id)

    def _unregister_page(self, unique_id: str, gui_id: str):
        """
        Unregister a page from the registry.

        Args:
            unique_id (str): The unique identifier for the page.
            gui_id (str): The GUI ID of the widget.
        """
        if unique_id not in self._page_registry:
            return
        page_info = self._page_registry[unique_id]
        if gui_id in page_info.widget_ids:
            page_info.widget_ids.remove(gui_id)
        if page_info.owner_gui_id == gui_id:
            page_info.owner_gui_id = None
        if not page_info.widget_ids:
            if page_info.page:
                page_info.page.deleteLater()
            del self._page_registry[unique_id]

        logger.info(f"Unregistered page {unique_id} for {gui_id}")

    def get_page_info(self, unique_id: str) -> PageOwnerInfo | None:
        """
        Get a page from the registry.

        Args:
            unique_id (str): The unique identifier for the page.

        Returns:
            PageOwnerInfo | None: The page info if found, None otherwise.
        """
        if unique_id not in self._page_registry:
            return None
        return self._page_registry[unique_id]

    def take_page_ownership(self, unique_id: str, new_owner_gui_id: str) -> QWebEnginePage | None:
        """
        Transfer ownership of a page to a new owner.

        Args:
            unique_id (str): The unique identifier for the page.
            new_owner_gui_id (str): The GUI ID of the new owner.

        Returns:
            QWebEnginePage | None: The page if ownership transfer was successful, None otherwise.
        """
        if unique_id not in self._page_registry:
            logger.warning(f"Page {unique_id} not found in registry")
            return None

        page_info = self._page_registry[unique_id]
        page_info.owner_gui_id = new_owner_gui_id

        logger.info(f"Transferred ownership of page {unique_id} to {new_owner_gui_id}")
        return page_info.page

    def yield_ownership(self, gui_id: str) -> bool:
        """
        Yield ownership of a page without destroying it. The page remains in the
        registry with no owner, available for another widget to claim.

        Args:
            gui_id (str): The GUI ID of the widget yielding ownership.

        Returns:
            bool: True if ownership was yielded, False otherwise.
        """
        if gui_id not in self._instances:
            return False

        instance = self._instances[gui_id]()
        if instance is None:
            return False

        unique_id = instance._unique_id
        if instance is None:
            return False

        if unique_id not in self._page_registry:
            return False

        page_owner_info = self._page_registry[unique_id]
        if page_owner_info.owner_gui_id != gui_id:
            return False

        page_owner_info.owner_gui_id = None
        return True


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

    def __init__(
        self,
        parent=None,
        config=None,
        client=None,
        gui_id=None,
        startup_cmd: str | None = "bec --nogui",
        unique_id: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self._startup_cmd = startup_cmd
        self._is_initialized = False
        self._unique_id = unique_id
        self.page = None  # Will be set in _set_up_page

        self._set_up_page()

        self._startup_timer = QTimer()
        self._startup_timer.setInterval(500)
        self._startup_timer.timeout.connect(self._check_page_ready)
        self._startup_timer.start()
        self._js_callback.connect(self._on_js_callback)

    def _set_up_page(self):
        """
        Set up the web page and UI elements.
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView(self)

        layout.addWidget(self.browser)
        self.setLayout(layout)

        _web_console_registry.register(self)
        self._token = _web_console_registry._token

        # If no unique_id is provided, create a new page
        if not self._unique_id:
            self.page = BECWebEnginePage(self)
            self.page.authenticationRequired.connect(self._authenticate)
            self.page.setUrl(QUrl(f"http://localhost:{_web_console_registry._server_port}"))
            self.browser.setPage(self.page)
            return

        # Try to get the page from the registry
        page_info = _web_console_registry.get_page_info(self._unique_id)
        if page_info and page_info.page:
            self.page = page_info.page
            if not page_info.owner_gui_id or page_info.owner_gui_id == self.gui_id:
                self.browser.setPage(self.page)
            # Only set URL if this is a newly created page (no URL set yet)
            if self.page.url().isEmpty():
                self.page.setUrl(QUrl(f"http://localhost:{_web_console_registry._server_port}"))

    def _check_page_ready(self):
        """
        Check if the page is ready and stop the timer if it is.
        """
        if not self.page or self.page.isLoading():
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
            if self._unique_id:
                page_info = _web_console_registry.get_page_info(self._unique_id)
                if page_info is None:
                    return
                if not page_info.initialized:
                    page_info.initialized = True
                    self.write(self._startup_cmd)
            else:
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

        Args:
            data (str): The data to send.
            send_return (bool): Whether to send a return after the data.
        """
        cmd = f"window.term.paste({json.dumps(data)});"
        self.page.runJavaScript(cmd)
        if send_return:
            self.send_return()

    def take_page_ownership(self, unique_id: str | None = None):
        """
        Take ownership of a web page from the registry. This will transfer the page
        from its current owner (if any) to this widget.

        Args:
            unique_id (str): The unique identifier of the page to take ownership of.
                           If None, uses this widget's unique_id.
        """
        if unique_id is None:
            unique_id = self._unique_id

        if not unique_id:
            logger.warning("Cannot take page ownership without a unique_id")
            return

        # Get the page from registry
        page = _web_console_registry.take_page_ownership(unique_id, self.gui_id)

        if not page:
            logger.warning(f"Page {unique_id} not found in registry")
            return

        self.page = page
        self.browser.setPage(page)
        self.browser.setVisible(True)
        logger.info(f"Widget {self.gui_id} took ownership of page {unique_id}")

    def _on_ownership_lost(self):
        """
        Called when this widget loses ownership of its page.
        Shows the retake button and hides the browser.
        """
        # self._retake_button.setVisible(True)
        self.browser.setVisible(False)
        logger.info(f"Widget {self.gui_id} lost ownership of page {self._unique_id}")

    def _on_retake_button_clicked(self):
        """
        Called when the retake ownership button is clicked.
        """
        if self._unique_id:
            self.take_page_ownership(self._unique_id)
        else:
            logger.warning("Cannot retake ownership without a unique_id")

    def yield_ownership(self):
        """
        Yield ownership of the page. The page remains in the registry with no owner,
        available for another widget to claim. This is automatically called when the
        widget becomes hidden.
        """
        if not self._unique_id:
            return
        success = _web_console_registry.yield_ownership(self.gui_id)
        if success:
            self._on_ownership_lost()
            logger.info(f"Widget {self.gui_id} yielded ownership of page {self._unique_id}")

    def has_ownership(self) -> bool:
        """
        Check if this widget currently has ownership of a page.

        Returns:
            bool: True if this widget owns a page, False otherwise.
        """
        if not self._unique_id:
            return False
        page_info = _web_console_registry.get_page_info(self._unique_id)
        if page_info is None:
            return False
        return page_info.owner_gui_id == self.gui_id

    def hideEvent(self, event):
        """
        Called when the widget is hidden. Automatically yields ownership.
        """
        if self.has_ownership():
            self.yield_ownership()
        super().hideEvent(event)

    def showEvent(self, event):
        """
        Called when the widget is shown. Updates UI state based on ownership.
        """
        super().showEvent(event)
        if self._unique_id and not self.has_ownership():
            # If the page does not have an owner, take ownership
            page_info = _web_console_registry.get_page_info(self._unique_id)
            if page_info is not None and page_info.owner_gui_id is None:
                self.take_page_ownership(self._unique_id)
                return
            # We have a unique_id but no ownership, show the retake button
            # self._retake_button.setVisible(True)
            self.browser.setVisible(False)

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

    from qtpy.QtCore import QTimer

    app = QApplication(sys.argv)
    widget = QTabWidget()

    # Create two consoles with different unique_ids
    web_console1 = WebConsole(startup_cmd="bec --nogui", unique_id="console1")
    web_console2 = WebConsole(startup_cmd="htop")
    web_console3 = WebConsole(startup_cmd="bec --nogui", unique_id="console1")
    widget.addTab(web_console1, "Console 1")
    widget.addTab(web_console2, "Console 2")
    widget.addTab(web_console3, "Console 3 -- mirror of Console 1")
    widget.show()

    # Demonstrate page sharing:
    # After initialization, web_console2 can take ownership of console1's page:
    # web_console2.take_page_ownership("console1")

    widget.resize(800, 600)

    def _close_cons1():
        web_console2.close()
        web_console2.deleteLater()

    # QTimer.singleShot(3000, _close_cons1)

    sys.exit(app.exec_())
