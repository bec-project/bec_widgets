from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import cast

from bec_lib.logger import bec_logger
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import bec_widgets
from bec_widgets.applications.launch_window import LaunchWindow
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_dispatcher import BECDispatcher

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class SimpleFileLikeFromLogOutputFunc:
    def __init__(self, log_func):
        self._log_func = log_func
        self._buffer = []
        self.encoding = "utf8"

    def write(self, buffer):
        self._buffer.append(buffer)

    def flush(self):
        lines, _, remaining = "".join(self._buffer).rpartition("\n")
        if lines:
            self._log_func(lines)
        self._buffer = [remaining]

    def close(self):
        return


class GUIServer:
    """
    This class is used to start the BEC GUI and is the main entry point for launching BEC Widgets in a subprocess.
    """

    def __init__(self, args):
        self.config = args.config
        self.gui_id = args.id
        self.gui_class = args.gui_class
        self.gui_class_id = args.gui_class_id
        self.hide = args.hide
        self.app: QApplication | None = None
        self.launcher_window: LaunchWindow | None = None
        self.dispatcher: BECDispatcher | None = None

    def start(self):
        """
        Start the GUI server.
        """
        bec_logger.level = bec_logger.LOGLEVEL.INFO
        if self.hide:
            # pylint: disable=protected-access
            bec_logger._stderr_log_level = bec_logger.LOGLEVEL.ERROR
            bec_logger._update_sinks()

        with redirect_stdout(SimpleFileLikeFromLogOutputFunc(logger.info)):  # type: ignore
            with redirect_stderr(SimpleFileLikeFromLogOutputFunc(logger.error)):  # type: ignore
                self._run()

    def _get_service_config(self) -> ServiceConfig:
        if self.config:
            try:
                config = json.loads(self.config)
                service_config = ServiceConfig(config=config)
            except (json.JSONDecodeError, TypeError):
                service_config = ServiceConfig(config_path=config)
        else:
            # if no config is provided, use the default config
            service_config = ServiceConfig()
        return service_config

    def _turn_off_the_lights(self, connections: dict):
        """
        If there is only one connection remaining, it is the launcher, so we show it.
        Once the launcher is closed as the last window, we quit the application.
        """
        self.launcher_window = cast(LaunchWindow, self.launcher_window)

        remaining_connections = [
            connection
            for connection in connections.values()
            if connection.parent_id != self.launcher_window.gui_id
        ]
        if len(remaining_connections) <= 1:
            self.launcher_window.show()
            self.launcher_window.activateWindow()
            self.launcher_window.raise_()
            if self.app:
                self.app.setQuitOnLastWindowClosed(True)
        else:
            self.launcher_window.hide()
            if self.app:
                self.app.setQuitOnLastWindowClosed(False)

    def _run(self):
        """
        Run the GUI server.
        """
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("BEC")
        self.app.gui_id = self.gui_id  # type: ignore
        self.setup_bec_icon()

        service_config = self._get_service_config()
        self.dispatcher = BECDispatcher(config=service_config, gui_id=self.gui_id)
        # self.dispatcher.start_cli_server(gui_id=self.gui_id)

        self.launcher_window = LaunchWindow(gui_id=f"{self.gui_id}:launcher")
        self.launcher_window.setAttribute(Qt.WA_ShowWithoutActivating)  # type: ignore

        self.app.aboutToQuit.connect(self.shutdown)
        self.app.setQuitOnLastWindowClosed(False)

        register = RPCRegister()
        register.callbacks.append(self._turn_off_the_lights)
        register.broadcast()

        if self.gui_class:
            # If the server is started with a specific gui class, we launch it.
            # This will automatically hide the launcher.
            self.launcher_window.launch(self.gui_class, name=self.gui_class_id)

        def sigint_handler(*args):
            # display message, for people to let it terminate gracefully
            print("Caught SIGINT, exiting")
            # Widgets should be all closed.
            with RPCRegister.delayed_broadcast():
                for widget in QApplication.instance().topLevelWidgets():  # type: ignore
                    widget.close()
            if self.app:
                self.app.quit()

        signal.signal(signal.SIGINT, sigint_handler)
        signal.signal(signal.SIGTERM, sigint_handler)

        sys.exit(self.app.exec())

    def setup_bec_icon(self):
        """
        Set the BEC icon for the application
        """
        if self.app is None:
            return
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            size=QSize(48, 48),
        )
        self.app.setWindowIcon(icon)

    def shutdown(self):
        """
        Shutdown the GUI server.
        """
        if self.dispatcher:
            self.dispatcher.stop_cli_server()
            self.dispatcher.disconnect_all()


def main():
    """
    Main entry point for subprocesses that start a GUI server.
    """

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, default="test", help="The id of the server")
    parser.add_argument(
        "--gui_class",
        type=str,
        help="Name of the gui class to be rendered. Possible values: \n- BECFigure\n- BECDockArea",
    )
    parser.add_argument(
        "--gui_class_id",
        type=str,
        default="bec",
        help="The id of the gui class that is added to the QApplication",
    )
    parser.add_argument("--config", type=str, help="Config file or config string.")
    parser.add_argument("--hide", action="store_true", help="Hide on startup")

    args = parser.parse_args()

    server = GUIServer(args)
    server.start()


if __name__ == "__main__":
    # import sys

    # sys.argv = ["bec_widgets", "--gui_class", "MainWindow"]
    main()
