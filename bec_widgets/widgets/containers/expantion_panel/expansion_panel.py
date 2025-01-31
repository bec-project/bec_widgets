import sys

from PySide6.QtWidgets import QSizePolicy
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QToolBox,
    QColorDialog,
)
from qtpy.QtCore import Qt

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import set_theme


class ExpansionPanel(BECWidget, QWidget):
    PLUGIN = True
    RPC = False

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        title="Panel",
        color: str | None = "#C0C0C0",
        expanded=False,
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, gui_id=gui_id, config=config)
        QWidget.__init__(self, parent=parent)

        self.setObjectName("ExpansionPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Properties
        self._expanded = expanded

        # Main vertical layout: header + content
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Header
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("headerFrame")
        self.header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header_frame.setStyleSheet(
            """
                #headerFrame {
                    border: 1px solid #C0C0C0;
                    border-radius: 5;
                }
            """
        )  # TODO think about the colors of the header frame and rounding the corners

        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(3, 2, 3, 2)
        header_layout.setSpacing(3)

        # Toggle button (arrow)
        self.btn_toggle = QPushButton("▼" if expanded else "►", self.header_frame)
        self.btn_toggle.setFixedSize(25, 25)
        self.btn_toggle.setStyleSheet("border: none; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle)
        header_layout.addWidget(self.btn_toggle, alignment=Qt.AlignVCenter)

        # Title label
        self.label_title = QLabel(title, self.header_frame)
        self.label_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        header_layout.addWidget(self.label_title, alignment=Qt.AlignVCenter | Qt.AlignLeft)

        # Spacer stretch
        header_layout.addStretch()

        self._main_layout.addWidget(self.header_frame)

        # Content area
        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("ContentFrame")
        self.content_frame.setStyleSheet(
            """
                #ContentFrame {
                    border: 1px solid #C0C0C0;
                    border-radius: 5;
                }
            """
        )
        self.content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._content_layout = QVBoxLayout(self.content_frame)
        self._content_layout.setContentsMargins(5, 5, 5, 5)
        self._content_layout.setSpacing(5)

        self._main_layout.addWidget(self.content_frame)

        self.content_frame.setVisible(expanded)

    @SafeSlot()
    def toggle(self):
        """Collapse or expand the content area."""
        self._expanded = not self._expanded
        self.content_frame.setVisible(self._expanded)
        self.btn_toggle.setText("▼" if self._expanded else "►")

    @SafeProperty(bool)
    def expanded(self) -> bool:
        return self._expanded

    @expanded.setter
    def expanded(self, value: bool):
        if value != self._expanded:
            self.toggle()

    @SafeProperty(str)
    def title(self):
        return self.label_title.text()

    @title.setter
    def title(self, value: str):
        self.label_title.setText(value)

    @SafeProperty("QColor")
    def label_color(self):
        return self.label_title.palette().color(self.label_title.foregroundRole())

    @label_color.setter
    def label_color(self, color):
        self.label_title.setStyleSheet(f"color: {color};")

    @property
    def content_layout(self) -> QVBoxLayout:
        """
        Return the layout of the content frame,
        so you can add sub-widgets at any time.
        """
        return self._content_layout


class DemoApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)

        self.panel1 = ExpansionPanel(title="Panel 1", expanded=False)
        self.layout.addWidget(self.panel1)
        btn1 = QPushButton("Button 1")
        self.panel1._content_layout.addWidget(btn1)

        self.panel2 = ExpansionPanel(title="Panel 2", color="#FF0000")
        self.layout.addWidget(self.panel2)

        self.panel3 = ExpansionPanel(title="Panel 3", color="#00FF00", expanded=False)
        self.layout.addWidget(self.panel3)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_theme("dark")
    panel = DemoApp()
    panel.show()
    sys.exit(app.exec_())
