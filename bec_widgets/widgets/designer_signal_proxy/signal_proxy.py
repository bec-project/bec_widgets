from collections import defaultdict

from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_widget import BECWidget


class DesignerSignalProxy(BECWidget, QWidget):
    output = Signal((str,), (int,), (float,), (bool,), (list,), (dict,), (object,), (type(None),))

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QWidget.__init__(self, parent)

        self.storage = defaultdict()
        self.input_objects = ["BECWaveformWidget", "DeviceComboBox"]

    @Slot()
    @Slot(str)
    @Slot(int)
    @Slot(float)
    @Slot(bool)
    @Slot(list)
    @Slot(dict)
    @Slot(object)
    @Slot(type(None))
    def input(self, *args):
        sender_name = self.sender().__class__.__name__
        print(f"Input signal received from {sender_name}: {args}")
        self.storage[sender_name] = args
        self._check_for_all_signals()

    def _check_for_all_signals(self):
        for obj in self.input_objects:
            if obj not in self.storage:
                return
        out = self._perform_aggregation()
        print(f"Output signal emitted: {out}")
        self.output.emit([self.storage[obj] for obj in self.input_objects])

        self.storage.clear()

    def _perform_aggregation(self):
        return [self.storage[obj] for obj in self.input_objects]


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = DesignerSignalProxy()
    widget.show()
    sys.exit(app.exec_())
