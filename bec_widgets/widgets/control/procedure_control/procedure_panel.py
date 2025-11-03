from bec_widgets.widgets.containers.dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.control.procedure_control.procedure_control import ProcedureControl
from bec_widgets.widgets.control.procedure_control.procedure_logs import ProcedureLogs


class ProcedurePanel(DockAreaWidget):

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.procedure_control = ProcedureControl(parent=self)
        self.procedure_control.setObjectName("Procedure Queue Control")
        self.procedure_logs = ProcedureLogs(parent=self)
        self.procedure_logs.setObjectName("Procedure Logs")

        _dock_kwargs = {"closable": False, "movable": False, "floatable": False}
        self.new(self.procedure_control, **_dock_kwargs)
        self.new(self.procedure_logs, where="bottom", **_dock_kwargs)

        self.procedure_control.queue_selected.connect(self.procedure_logs.set_queue)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = ProcedurePanel()
    widget.show()
    sys.exit(app.exec())
