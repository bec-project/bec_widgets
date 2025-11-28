from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.utility.logpanel.logpanel import LogPanel


class DiagnosticWidget(DockAreaWidget):

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, variant="compact", **kwargs)

        logs_dock_kwargs = {
            "closable": False,
            "floatable": False,
            "movable": False,
            "return_dock": True,
            "show_settings_action": False,
            "title_buttons": {"float": False, "close": False, "menu": False},
        }

        self.device_logs = LogPanel(show_toolbar=False, service_filter={"DeviceServer"})
        self.device_logs.setObjectName("Device Server logs")
        self.device_logs_dock = self.new(self.device_logs, **logs_dock_kwargs)

        self.scihub_logs = LogPanel(show_toolbar=False, service_filter={"SciHub"})
        self.scihub_logs.setObjectName("SciHub logs")
        self.scihub_logs_dock = self.new(
            self.scihub_logs, relative_to=self.device_logs_dock, where="right", **logs_dock_kwargs
        )

        self.service_status = BECStatusBox()
        self.service_status.setObjectName("Service Status")
        self.service_status_dock = self.new(
            self.service_status,
            relative_to=self.scihub_logs_dock,
            where="right",
            **logs_dock_kwargs,
        )

        self.scan_logs = LogPanel(show_toolbar=False, service_filter={"ScanServer"})
        self.scan_logs.setObjectName("Scan Server logs")
        self.scan_logs_dock = self.new(
            self.scan_logs, relative_to=self.device_logs_dock, where="bottom", **logs_dock_kwargs
        )

        self.dap_logs = LogPanel(show_toolbar=False, service_filter={"DAPServer"})
        self.dap_logs.setObjectName("DAP Server logs")
        self.dap_logs_dock = self.new(
            self.dap_logs, relative_to=self.scan_logs_dock, where="bottom", **logs_dock_kwargs
        )

        self.scanbundler_logs = LogPanel(show_toolbar=False, service_filter={"ScanBundler"})
        self.scanbundler_logs.setObjectName("ScanBundler logs")
        self.scanbundler_logs_dock = self.new(
            self.scanbundler_logs,
            relative_to=self.scihub_logs_dock,
            where="bottom",
            **logs_dock_kwargs,
        )

        self.filewriter_logs = LogPanel(show_toolbar=False, service_filter={"FileWriter"})
        self.filewriter_logs.setObjectName("FileWriter logs")
        self.filewriter_logs_dock = self.new(
            self.filewriter_logs,
            relative_to=self.scanbundler_logs_dock,
            where="bottom",
            **logs_dock_kwargs,
        )


class DiagnosticView(ViewBase):
    """
    A view for users to write scripts and macros and execute them within the application.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        id: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent=parent, content=content, id=id, title=title)
        self.developer_widget = DiagnosticWidget(parent=self)
        self.set_content(self.developer_widget)
