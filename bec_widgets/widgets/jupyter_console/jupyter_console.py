from bec_ipython_client.main import BECIPythonClient
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtWidgets import QApplication


class BECJupyterConsole(RichJupyterWidget):  # pragma: no cover:
    def __init__(self, parent=None, inprocess=True):
        super().__init__(parent=parent)

        self.inprocess = inprocess

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
        self.client = BECIPythonClient()
        self.client.start()

        self.kernel_manager.kernel.shell.push(
            {
                "bec": self.client,
                "dev": self.client.device_manager.devices,
                "scans": self.client.scans,
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

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


# if __name__ == "__main__":  # pragma: no cover
#     import sys
#
#     app = QApplication(sys.argv)
#     win = BECJupyterConsole(inprocess=True)
#     win.show()
#     sys.exit(app.exec_())
