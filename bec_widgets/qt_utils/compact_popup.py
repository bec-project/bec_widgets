from types import SimpleNamespace

from bec_qthemes import material_icon
from qtpy.QtCore import Property, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_accent_colors


class LedLabel(QLabel):
    success_led = "color: white;border-radius: 10;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:1, y2:1, stop:0 %s, stop:1 %s);"
    emergency_led = "color: white;border-radius: 10;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:0.92, y2:0.988636, stop:0 %s, stop:1 %s);"
    warning_led = "color: white;border-radius: 10;background-color: qlineargradient(spread:pad, x1:0.232, y1:0.272, x2:0.98, y2:0.959773, stop:0 %s, stop:1 %s);"
    default_led = "color: white;border-radius: 10;background-color: qlineargradient(spread:pad, x1:0.04, y1:0.0565909, x2:0.799, y2:0.795, stop:0 %s, stop:1 %s);"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.palette = get_accent_colors()
        if self.palette is None:
            # no theme!
            self.palette = SimpleNamespace(
                default=QColor("blue"),
                success=QColor("green"),
                warning=QColor("orange"),
                emergency=QColor("red"),
            )
        self.setState("default")
        self.setFixedSize(20, 20)

    def setState(self, state: str):
        match state:
            case "success":
                r, g, b, a = self.palette.success.getRgb()
                self.setStyleSheet(
                    LedLabel.success_led
                    % (
                        f"rgba({r},{g},{b},{a})",
                        f"rgba({int(r*0.8)},{int(g*0.8)},{int(b*0.8)},{a})",
                    )
                )
            case "default":
                r, g, b, a = self.palette.default.getRgb()
                self.setStyleSheet(
                    LedLabel.default_led
                    % (
                        f"rgba({r},{g},{b},{a})",
                        f"rgba({int(r*0.8)},{int(g*0.8)},{int(b*0.8)},{a})",
                    )
                )
            case "warning":
                r, g, b, a = self.palette.warning.getRgb()
                self.setStyleSheet(
                    LedLabel.warning_led
                    % (
                        f"rgba({r},{g},{b},{a})",
                        f"rgba({int(r*0.8)},{int(g*0.8)},{int(b*0.8)},{a})",
                    )
                )
            case "emergency":
                r, g, b, a = self.palette.emergency.getRgb()
                self.setStyleSheet(
                    LedLabel.emergency_led
                    % (
                        f"rgba({r},{g},{b},{a})",
                        f"rgba({int(r*0.8)},{int(g*0.8)},{int(b*0.8)},{a})",
                    )
                )
            case unknown_state:
                raise ValueError(
                    f"Unknown state {repr(unknown_state)}, must be one of default, success, warning or emergency"
                )


class PopupDialog(QDialog):
    def __init__(self, content_widget):
        self.parent = content_widget.parent()
        self.content_widget = content_widget

        super().__init__(self.parent)

        self.setAttribute(Qt.WA_DeleteOnClose)

        self.content_widget.setParent(self)
        QVBoxLayout(self)
        self.layout().addWidget(self.content_widget)
        self.content_widget.setVisible(True)

    def closeEvent(self, event):
        self.content_widget.setVisible(False)
        self.content_widget.setParent(self.parent)


class CompactPopupWidget(QWidget):
    """Container widget, that can display its content or have a compact form,
    in this case clicking on a small button pops the contained widget up.

    In the compact form, a LED-like indicator shows a status indicator.
    """

    def __init__(self, parent=None, layout=QVBoxLayout):
        super().__init__(parent)

        self._popup_window = None

        QVBoxLayout(self)
        self.compact_view = QWidget(self)
        self.compact_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        QHBoxLayout(self.compact_view)
        self.compact_view.layout().setSpacing(0)
        self.compact_view.layout().setContentsMargins(0, 0, 0, 0)
        self.compact_label = QLabel(self.compact_view)
        self.compact_status = LedLabel(self.compact_view)
        self.compact_show_popup = QPushButton(self.compact_view)
        self.compact_show_popup.setFlat(True)
        self.compact_show_popup.setIcon(
            material_icon(icon_name="pan_zoom", size=(10, 10), convert_to_pixmap=False)
        )
        self.compact_view.layout().addWidget(self.compact_label)
        self.compact_view.layout().addWidget(self.compact_status)
        self.compact_view.layout().addWidget(self.compact_show_popup)
        self.compact_view.setVisible(False)
        self.layout().addWidget(self.compact_view)
        self.container = QWidget(self)
        self.layout().addWidget(self.container)
        self.container.setVisible(True)
        layout(self.container)
        self.layout = self.container.layout()

        self.compact_show_popup.clicked.connect(self.show_popup)

    def set_global_state(self, state: str):
        """Set the LED-indicator state

        The LED indicator represents the 'global' state. State can be one of the
        following: "default", "success", "warning", "emergency"
        """
        self.compact_status.setState(state)

    def show_popup(self):
        """Display the contained widgets in a popup dialog"""
        self._popup_window = PopupDialog(self.container)
        self._popup_window.show()

    def setSizePolicy(self, size_policy1, size_policy2=None):
        # setting size policy on the compact popup widget will set
        # the policy for the container, and for itself
        if size_policy2 is None:
            # assuming first form: setSizePolicy(QSizePolicy)
            self.container.setSizePolicy(size_policy1)
            QWidget.setSizePolicy(self, size_policy1)
        else:
            self.container.setSizePolicy(size_policy1, size_policy2)
            QWidget.setSizePolicy(self, size_policy1, size_policy2)

    def addWidget(self, widget):
        """Add a widget to the popup container

        The popup container corresponds to the "full view" (not compact)
        The widget is reparented to the container, and added to the container layout
        """
        widget.setParent(self.container)
        self.container.layout().addWidget(widget)

    @Property(bool)
    def compact(self):
        return self.compact_view.isVisible()

    @compact.setter
    def compact(self, set_compact: bool):
        """Sets the compact form

        If set_compact is True, the compact view is displayed ; otherwise,
        the full view is displayed. This is handled by toggling visibility of
        the container widget or the compact view widget.
        """
        if set_compact:
            self.compact_view.setVisible(True)
            self.container.setVisible(False)
            QWidget.setSizePolicy(self, QSizePolicy.Fixed, QSizePolicy.Fixed)
        else:
            self.compact_view.setVisible(False)
            self.container.setVisible(True)
            QWidget.setSizePolicy(self, self.container.sizePolicy())
        if self.parentWidget():
            self.parentWidget().adjustSize()
        else:
            self.adjustSize()

    @Property(str)
    def label(self):
        return self.compact_label.text()

    @label.setter
    def label(self, compact_label_text: str):
        """Set the label text associated to the compact view"""
        self.compact_label.setText(compact_label_text)

    @Property(str)
    def tooltip(self):
        return self.compact_label.toolTip()

    @tooltip.setter
    def tooltip(self, tooltip: str):
        """Set the tooltip text associated to the compact view"""
        self.compact_label.setToolTip(tooltip)
        self.compact_status.setToolTip(tooltip)

    def closeEvent(self, event):
        # Called by Qt, on closing - since the children widgets can be
        # BECWidgets, it is good to explicitely call 'close' on them,
        # to ensure proper resources cleanup
        for child in self.container.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            child.close()
