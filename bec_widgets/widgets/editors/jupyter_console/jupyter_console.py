from bec_ipython_client.main import BECIPythonClient
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow


class BECJupyterConsole(RichJupyterWidget):  # pragma: no cover:
    def __init__(self, inprocess: bool = False):
        super().__init__()

        self.inprocess = inprocess
        self.ipyclient = None

        self.kernel_manager, self.kernel_client = self._init_kernel(inprocess=self.inprocess)
        self.set_default_style("linux")
        self._init_bec()

    def _init_kernel(self, inprocess: bool = False, kernel_name: str = "python3"):
        self.inprocess = inprocess
        if inprocess is True:
            print("starting inprocess kernel")
            kernel_manager = QtInProcessKernelManager()
        else:
            kernel_manager = QtKernelManager(kernel_name=kernel_name)
        kernel_manager.start_kernel()
        kernel_client = kernel_manager.client()
        kernel_client.start_channels()
        return kernel_manager, kernel_client

    def _init_bec(self):
        if self.inprocess is True:
            self._init_bec_inprocess()
        else:
            self._init_bec_kernel()

    def _init_bec_inprocess(self):
        self.ipyclient = BECIPythonClient()
        self.ipyclient.start()
        self.kernel_manager.kernel.shell.push(
            {
                "bec": self.ipyclient,
                "dev": self.ipyclient.device_manager.devices,
                "scans": self.ipyclient.scans,
            }
        )

    def _init_bec_kernel(self):
        self.execute(
            """
            from bec_ipython_client.main import BECIPythonClient
            bec = BECIPythonClient()
            bec.start()
            dev = bec.device_manager.devices if bec else None
            scans = bec.scans if bec else None
            """
        )

    def _cleanup_bec(self):
        if getattr(self, "ipyclient", None) is not None and self.inprocess is True:
            self.ipyclient.shutdown()
            self.ipyclient = None

    def shutdown_kernel(self):
        """
        Shutdown the Jupyter kernel and clean up resources.
        """
        self._cleanup_bec()
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()
        self.kernel_client = None
        self.kernel_manager = None

    def closeEvent(self, event):
        self.shutdown_kernel()
        event.accept()
        super().closeEvent(event)


class JupyterConsoleWindow(QMainWindow):  # pragma: no cover:
    def __init__(self, inprocess: bool = True, parent=None):
        super().__init__(parent)
        self.console = BECJupyterConsole(inprocess=inprocess)
        self.setCentralWidget(self.console)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

    def closeEvent(self, event):
        # Explicitly close the console so its own closeEvent runs
        if getattr(self, "console", None) is not None:
            self.console.close()
        event.accept()
        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    win = JupyterConsoleWindow(inprocess=True)
    win.show()

    sys.exit(app.exec_())
