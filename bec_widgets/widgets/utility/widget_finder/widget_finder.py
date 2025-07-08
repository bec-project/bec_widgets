from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QPropertyAnimation, QRect, QSequentialAnimationGroup, Qt, QTimer
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import SafeProperty
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow
from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.waveform.waveform import Waveform


class WidgetFinderComboBox(QComboBox):

    def __init__(self, parent=None, widget_class: type[QWidget] | str | None = None):
        super().__init__(parent)
        self.widget_class = widget_class
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setMinimumWidth(200)
        # find button inside combobox
        self.find_button = QToolButton(self)
        self.find_button.setIcon(material_icon("frame_inspect"))
        self.find_button.setCursor(Qt.PointingHandCursor)
        self.find_button.setFocusPolicy(Qt.NoFocus)
        self.find_button.setToolTip("Highlight selected widget")
        self.find_button.setStyleSheet("QToolButton { border: none; padding: 0px; }")
        self.find_button.clicked.connect(self.inspect_widget)

        # refresh button inside combobox
        self.refresh_button = QToolButton(self)
        self.refresh_button.setIcon(material_icon("refresh"))
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setFocusPolicy(Qt.NoFocus)
        self.refresh_button.setToolTip("Refresh widget list")
        self.refresh_button.setStyleSheet("QToolButton { border: none; padding: 0px; }")
        self.refresh_button.clicked.connect(self.refresh_list)

        # Purple Highlighter
        self.highlighter = None

        # refresh items - delay to fetch widgets after UI is ready in next event loop
        QTimer.singleShot(0, self.refresh_list)

    def _init_highlighter(self):
        """
        Initialize the highlighter frame that will be used to highlight the inspected widget.
        """
        self.highlighter = QFrame(self, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.highlighter.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.highlighter.setStyleSheet(
            "border: 2px solid #FF00FF; border-radius: 6px; background: transparent;"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        btn_size = 16
        arrow_width = 24
        x = self.width() - arrow_width - btn_size - 2
        y = (self.height() - btn_size) // 2 - 2
        # position find_button first
        self.find_button.setFixedSize(btn_size, btn_size)
        self.find_button.move(x, y)
        # position refresh_button to the left of find_button
        refresh_x = x - btn_size - 2
        self.refresh_button.setFixedSize(btn_size, btn_size)
        self.refresh_button.move(refresh_x, y)

    def refresh_list(self):
        """
        Refresh the list of widgets in the combobox based on the specified widget class.
        """
        self.clear()
        if self.widget_class is None:
            return
        widgets = WidgetIO.find_widgets(self.widget_class, recursive=True)
        # Build display names with counts for duplicates
        name_counts: dict[str, int] = {}
        for w in widgets:
            base_name = w.objectName() or w.__class__.__name__
            count = name_counts.get(base_name, 0) + 1
            name_counts[base_name] = count
            display_name = base_name if count == 1 else f"{base_name} ({count})"
            self.addItem(display_name, w)

    def showPopup(self):
        """
        Refresh list each time the popup opens to reflect dynamic widget changes.
        """
        self.refresh_list()
        super().showPopup()

    def inspect_widget(self):
        """
        Inspect the currently selected widget in the combobox.
        """
        target = self.currentData()
        if not target:
            return
        # ensure highlighter exists, avoid calling methods on deleted C++ object
        if not getattr(self, "highlighter", None):
            self._init_highlighter()
        else:
            self.highlighter.hide()
        # draw new
        geom = target.frameGeometry()
        pos = target.mapToGlobal(target.rect().topLeft())
        self.highlighter.setGeometry(pos.x(), pos.y(), geom.width(), geom.height())
        self.highlighter.show()
        # Pulse and fade animation to draw attention
        start_rect = QRect(pos.x() - 5, pos.y() - 5, geom.width() + 10, geom.height() + 10)
        pulse = QPropertyAnimation(self.highlighter, b"geometry")
        pulse.setDuration(300)
        pulse.setStartValue(start_rect)
        pulse.setEndValue(QRect(pos.x(), pos.y(), geom.width(), geom.height()))

        fade = QPropertyAnimation(self.highlighter, b"windowOpacity")
        fade.setDuration(2000)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(self.highlighter.hide)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(pulse)
        group.addAnimation(fade)
        group.start()

    @SafeProperty(str)
    def widget_class_name(self) -> str:
        """
        Get or set the target widget class by name.
        """
        return (
            self.widget_class if isinstance(self.widget_class, str) else self.widget_class.__name__
        )

    @widget_class_name.setter
    def widget_class_name(self, name: str):
        self.widget_class = name
        self.refresh_list()

    @property
    def selected_widget(self):
        """
        The currently selected QWidget instance (or None if not found).
        """
        try:
            return self.currentData()
        except Exception:
            return None

    def cleanup(self):
        """
        Clean up the highlighter frame when the combobox is deleted.
        """
        if self.highlighter:
            self.highlighter.close()
            self.highlighter.deleteLater()
            self.highlighter = None

    def closeEvent(self, event):
        """
        Override closeEvent to clean up the highlighter frame.
        """
        self.cleanup()
        event.accept()


class InspectorMainWindow(BECMainWindow):  # pragma: no cover
    """
    A main window that includes a widget finder combobox to inspect widgets.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Widget Inspector")
        self.setMinimumSize(800, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.central_widget.layout = QGridLayout(self.central_widget)

        # Inspector box
        self.group_box_inspector = QGroupBox(self.central_widget)
        self.group_box_inspector.setTitle("Inspector")
        self.group_box_inspector.layout = QVBoxLayout(self.group_box_inspector)
        self.inspector_combobox = WidgetFinderComboBox(self.group_box_inspector, Waveform)
        self.switch_combobox = QComboBox(self.group_box_inspector)
        self.switch_combobox.addItems(["Waveform", "Image", "QPushButton"])
        self.switch_combobox.setToolTip("Switch the widget class to inspect")
        self.switch_combobox.currentTextChanged.connect(
            lambda text: setattr(self.inspector_combobox, "widget_class_name", text)
        )
        self.group_box_inspector.layout.addWidget(self.inspector_combobox)
        self.group_box_inspector.layout.addWidget(self.switch_combobox)

        # Some bec widgets to inspect
        self.wf1 = Waveform(self.central_widget)
        self.wf2 = Waveform(self.central_widget)

        self.im1 = Image(self.central_widget)
        self.im2 = Image(self.central_widget)

        # Some normal widgets to inspect
        self.group_box_widgets = QGroupBox(self.central_widget)
        self.group_box_widgets.setTitle("Widgets ")
        self.group_box_widgets.layout = QVBoxLayout(self.group_box_widgets)
        self.btn1 = QPushButton("Button 1", self.group_box_widgets)
        self.btn1.setObjectName("btn1")
        self.btn2 = QPushButton("Button 2", self.group_box_widgets)
        self.btn2.setObjectName("btn1")  # Same object name to test duplicate handling
        self.btn3 = QPushButton("Button 3", self.group_box_widgets)
        self.btn3.setObjectName("btn3")
        self.group_box_widgets.layout.addWidget(self.btn1)
        self.group_box_widgets.layout.addWidget(self.btn2)
        self.group_box_widgets.layout.addWidget(self.btn3)

        self.central_widget.layout.addWidget(self.group_box_inspector, 0, 0)
        self.central_widget.layout.addWidget(self.group_box_widgets, 1, 0)
        self.central_widget.layout.addWidget(self.wf1, 0, 1)
        self.central_widget.layout.addWidget(self.wf2, 1, 1)
        self.central_widget.layout.addWidget(self.im1, 0, 2)
        self.central_widget.layout.addWidget(self.im2, 1, 2)


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    main_window = InspectorMainWindow()
    main_window.show()
    sys.exit(app.exec())
