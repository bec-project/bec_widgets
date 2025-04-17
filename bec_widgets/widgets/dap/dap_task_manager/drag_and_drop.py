import inspect

from bec_lib.signature_serializer import deserialize_dtype
from bec_server.data_processing.dap_framework_refactoring.dap_blocks import (
    BlockWithLotsOfArgs,
    DAPBlock,
    GradientBlock,
    SmoothBlock,
)
from pydantic.fields import FieldInfo
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QLayout,
    QRadioButton,
    QScrollArea,
)
from qtpy.QtCore import QMimeData, Qt, Signal
from qtpy.QtGui import QDrag, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.widgets.editors.scan_metadata._metadata_widgets import widget_from_type
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata
from tests.unit_tests.test_scan_metadata import metadata_widget


class DragItem(ExpandableGroupFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setContentsMargins(25, 5, 25, 5)
        self._layout = QVBoxLayout()
        self.set_layout(self._layout)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            drag.setMimeData(mime)

            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)

            drag.exec(Qt.DropAction.MoveAction)


class DragWidget(QWidget):
    """
    Generic list sorting handler.
    """

    orderChanged = Signal(list)

    def __init__(self, *args, orientation=Qt.Orientation.Vertical, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

        # Store the orientation for drag checks later.
        self.orientation = orientation

        if self.orientation == Qt.Orientation.Vertical:
            self.blayout = QVBoxLayout()
        else:
            self.blayout = QHBoxLayout()

        self.setLayout(self.blayout)

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        pos = e.position()
        widget = e.source()
        self.blayout.removeWidget(widget)

        for n in range(self.blayout.count()):
            # Get the widget at each index in turn.
            w = self.blayout.itemAt(n).widget()
            if self.orientation == Qt.Orientation.Vertical:
                # Drag drop vertically.
                drop_here = pos.y() < w.y() + w.size().height() // 2
            else:
                # Drag drop horizontally.
                drop_here = pos.x() < w.x() + w.size().width() // 2

            if drop_here:
                break

        else:
            # We aren't on the left hand/upper side of any widget,
            # so we're at the end. Increment 1 to insert after.
            n += 1

        self.blayout.insertWidget(n, widget)
        self.orderChanged.emit(self.get_item_data())

        e.accept()

    def add_item(self, item):
        self.blayout.addWidget(item)

    def get_item_data(self):
        data = []
        for n in range(self.blayout.count()):
            # Get the widget at each index in turn.
            w: "DAPBlockWidget" = self.blayout.itemAt(n).widget()
            data.append(w._title.text())
        return data


class DAPBlockWidget(BECWidget, DragItem):
    def __init__(
        self,
        parent=None,
        content: type[DAPBlock] = None,
        client=None,
        gui_id: str | None = None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            client=client,
            gui_id=gui_id,
            title=content.__name__,
            **kwargs,
        )
        self._content = content
        self.add_form(self._content)

    def add_form(self, block_type: type[DAPBlock]):
        run_signature = inspect.signature(block_type.run)
        self._title.setText(block_type.__name__)
        layout = self._contents.layout()
        if layout is None:
            return
        self._add_widgets_for_signature(layout, run_signature)

    def _add_widgets_for_signature(self, layout: QLayout, signature: inspect.Signature):
        for arg_name, arg_spec in signature.parameters.items():
            annotation: str | type = arg_spec.annotation
            if isinstance(annotation, str):
                annotation = deserialize_dtype(annotation) or annotation
            w = QWidget()
            w.setLayout(QHBoxLayout())
            w.layout().addWidget(QLabel(arg_name))
            w.layout().addWidget(
                widget_from_type(annotation)(
                    FieldInfo(
                        annotation=annotation
                    )  # FIXME this class should not be initialised directly...
                )
            )
            w.layout().addWidget(QLabel(str(annotation)))

            layout.addWidget(w)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.drag = DragWidget(orientation=Qt.Orientation.Vertical)
        for block_type in [SmoothBlock, GradientBlock, BlockWithLotsOfArgs] * 2:
            item = DAPBlockWidget(content=block_type)
            self.drag.add_item(item)

        # Print out the changed order.
        self.drag.orderChanged.connect(print)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.drag)
        layout.addStretch(1)
        container.setLayout(layout)

        self.setCentralWidget(container)


if __name__ == "__main__":
    app = QApplication([])
    w = MainWindow()
    w.show()

    app.exec()
