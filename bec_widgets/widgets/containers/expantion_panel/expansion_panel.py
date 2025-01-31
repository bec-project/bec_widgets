import sys

from qtpy.QtCore import QEvent, Qt
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QPushButton,
    QLabel,
    QSizePolicy,
)

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget


class ExpansionPanel(BECWidget, QWidget):
    """
    A collapsible container widget for use in Qt Designer.
    This version avoids the traceback by deferring eventFilter installation
    until after header_frame and content_frame exist, and by checking they're
    not None before referencing them.
    """

    PLUGIN = True
    RPC = False

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        title="Panel",
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
        self.header_frame = None
        self.content_frame = None

        # Setup the main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Create the header
        self._init_header(title)

        # Create the content
        self._init_content()

        # Make sure the content is initially visible or hidden
        self.content_frame.setVisible(expanded)

        # Defer installing the event filter until everything is ready
        self.installEventFilter(self)

    def _init_header(self, title):
        """
        Create the header frame with arrow button and label.
        """
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("headerFrame")
        self.header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header_frame.setStyleSheet(
            """
            #headerFrame {
                border: 1px solid #C0C0C0;
                border-radius: 4px;
            }
            """
        )

        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(3, 2, 3, 2)
        header_layout.setSpacing(5)

        self.btn_toggle = QPushButton("▼" if self._expanded else "►", self.header_frame)
        self.btn_toggle.setFixedSize(25, 25)
        self.btn_toggle.setStyleSheet("border: none; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle)
        header_layout.addWidget(self.btn_toggle, alignment=Qt.AlignVCenter)

        self.label_title = QLabel(title, self.header_frame)
        self.label_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        header_layout.addWidget(self.label_title, alignment=Qt.AlignVCenter | Qt.AlignLeft)
        header_layout.addStretch()

        self._main_layout.addWidget(self.header_frame)

    def _init_content(self):
        """
        Create the collapsible content frame, with its own QVBoxLayout.
        """
        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("ContentFrame")
        self.content_frame.setStyleSheet(
            """
            #ContentFrame {
                border: 1px solid #C0C0C0;
                border-radius: 4px;
            }
            """
        )
        self.content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._content_layout = QVBoxLayout(self.content_frame)
        self._content_layout.setContentsMargins(5, 5, 5, 5)
        self._content_layout.setSpacing(5)

        self._main_layout.addWidget(self.content_frame)

    @SafeSlot()
    def toggle(self):
        """Collapse or expand the content area."""
        self._expanded = not self._expanded
        if self.content_frame:
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
        return self.label_title.text() if self.label_title else ""

    @title.setter
    def title(self, value: str):
        if self.label_title:
            self.label_title.setText(value)

    @SafeProperty("QColor")
    def label_color(self):
        return self.label_title.palette().color(self.label_title.foregroundRole())

    @label_color.setter
    def label_color(self, color):
        self.label_title.setStyleSheet(f"color: {color};")

    @property
    def content_layout(self) -> QVBoxLayout:
        """Return the layout of the content frame for programmatic additions."""
        return self._content_layout

    def event(self, e):
        """
        Override event() to detect when child widgets are added by Designer,
        so we can place them into the content layout if they are not the header frame
        or content frame themselves.
        """
        if e.type() == QEvent.ChildAdded:
            child_obj = e.child()
            # Only process if we have a valid child widget
            if child_obj is not None and isinstance(child_obj, QWidget):
                # Also check if we have valid references to header_frame & content_frame
                if self.header_frame is not None and self.content_frame is not None:
                    # If it's not our known frames, place it inside the content layout
                    if child_obj not in (self.header_frame, self.content_frame):
                        self._content_layout.addWidget(child_obj)
        return super().event(e)


if __name__ == "__main__":
    # Quick test if not using Designer
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QPushButton

    app = QApplication(sys.argv)

    panel = ExpansionPanel(title="Test Panel", expanded=True)
    panel.content_layout.addWidget(QPushButton("Test Button 1"))
    panel.content_layout.addWidget(QPushButton("Test Button 2"))

    container = QWidget()
    lay = QVBoxLayout(container)
    lay.addWidget(panel)
    container.resize(400, 300)
    container.show()

    sys.exit(app.exec_())
