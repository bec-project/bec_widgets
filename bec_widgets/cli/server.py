from __future__ import annotations

import argparse
import json
import signal
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import cast

from bec_lib.logger import bec_logger
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication

from bec_widgets.applications.launch_window import LaunchWindow
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_qapp import BECApplication

logger = bec_logger.logger


class SimpleFileLikeFromLogOutputFunc:
    def __init__(self, log_func):
        self._log_func = log_func
        self._buffer = []

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
    Class that starts the GUI server.
    """

    def __init__(self, args):
        self.config = args.config
        self.gui_id = args.id
        self.gui_class = args.gui_class
        self.gui_class_id = args.gui_class_id
        self.hide = args.hide
        self.app: BECApplication | None = None
        self.launcher_window: LaunchWindow | None = None

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
        self.app = cast(BECApplication, self.app)
        self.launcher_window = cast(LaunchWindow, self.launcher_window)

        if len(connections) <= 1:
            self.launcher_window.show()
            self.launcher_window.activateWindow()
            self.launcher_window.raise_()
            self.app.setQuitOnLastWindowClosed(True)
        else:
            self.launcher_window.hide()
            self.app.setQuitOnLastWindowClosed(False)

    def _run(self):
        """
        Run the GUI server.
        """
        service_config = self._get_service_config()
        self.app = BECApplication(sys.argv, config=service_config, gui_id=self.gui_id)
        self.app.setQuitOnLastWindowClosed(False)

        self.launcher_window = LaunchWindow(gui_id=f"{self.gui_id}:launcher")
        self.launcher_window.setAttribute(Qt.WA_ShowWithoutActivating)  # type: ignore

        RPCRegister().callbacks.append(self._turn_off_the_lights)

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
            self.app.quit()

        # gui.bec.close()
        # win.shutdown()
        signal.signal(signal.SIGINT, sigint_handler)
        signal.signal(signal.SIGTERM, sigint_handler)

        sys.exit(self.app.exec())


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
    import sys

    sys.argv = ["bec_widgets", "--gui_class", "MainWindow"]
    main()
