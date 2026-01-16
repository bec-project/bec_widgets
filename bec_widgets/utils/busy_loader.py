from __future__ import annotations

from bec_lib.logger import bec_logger
from qtpy.QtCore import QEvent, QObject, Qt, QTimer, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeProperty

logger = bec_logger.logger


class _OverlayEventFilter(QObject):
    """Keeps the overlay sized and stacked over its target widget."""

    def __init__(self, target: QWidget, overlay: QWidget):
        super().__init__(target)
        self._target = target
        self._overlay = overlay

    def eventFilter(self, obj, event):
        if not hasattr(self, " _target") or self._target is None:
            return False
        if not hasattr(self, "_overlay") or self._overlay is None:
            return False
        if obj is self._target and event.type() in (
            QEvent.Resize,
            QEvent.Show,
            QEvent.LayoutRequest,
            QEvent.Move,
        ):
            self._overlay.setGeometry(self._target.rect())
            self._overlay.raise_()
        return False


class BusyLoaderOverlay(QWidget):
    """
    A semi-transparent scrim with centered text and an animated spinner.
    Call show()/hide() directly, or use via `install_busy_loader(...)`.

    Args:
        parent(QWidget): The parent widget to overlay.
        text(str): Initial text to display.
        opacity(float): Overlay opacity (0..1).

    Returns:
        BusyLoaderOverlay: The overlay instance.
    """

    foreground_color_changed = Signal(QColor)
    scrim_color_changed = Signal(QColor)

    def __init__(self, parent: QWidget, opacity: float = 0.35, **kwargs):
        super().__init__(parent=parent, **kwargs)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._opacity = opacity
        self._scrim_color = QColor(128, 128, 128, 110)
        self._label_color = QColor(240, 240, 240)
        self._filter: QObject | None = None

        # Set Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        self.setLayout(layout)

        # Custom widget placeholder
        self._custom_widget: QWidget | None = None

        # Add a frame around the content
        self._frame = QFrame(self)
        self._frame.setObjectName("busyFrame")
        self._frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._frame.lower()

        # Defaults
        self._update_palette()

        # Start hidden; interactions beneath are blocked while visible
        self.hide()

    @SafeProperty(QColor, notify=scrim_color_changed)
    def scrim_color(self) -> QColor:
        """
        The overlay scrim color.
        """
        return self._scrim_color

    @scrim_color.setter
    def scrim_color(self, value: QColor):
        if not isinstance(value, QColor):
            raise TypeError("scrim_color must be a QColor")
        self._scrim_color = value
        self.update()

    @SafeProperty(QColor, notify=foreground_color_changed)
    def foreground_color(self) -> QColor:
        """
        The overlay foreground color (text, spinner).
        """
        return self._label_color

    @foreground_color.setter
    def foreground_color(self, value: QColor):
        if not isinstance(value, QColor):
            try:
                color = QColor(value)
                if not color.isValid():
                    raise ValueError(f"Invalid color: {value}")
            except Exception:
                # pylint: disable=raise-missing-from
                raise ValueError(f"Color {value} is invalid, cannot be converted to QColor")
        self._label_color = value
        self.update()

    def set_filter(self, filt: _OverlayEventFilter):
        """
        Set an event filter to keep the overlay sized and stacked over its target.

        Args:
            filt(QObject): The event filter instance.
        """
        self._filter = filt
        target = filt._target
        if self.parent() != target:
            logger.warning(f"Overlay parent {self.parent()} does not match filter target {target}")
        target.installEventFilter(self._filter)

    ######################
    ### Public methods ###
    ######################

    def set_widget(self, widget: QWidget):
        """
        Set a custom widget as an overlay for the busy overlay.

        Args:
            widget(QWidget): The custom widget to display.
        """
        lay = self.layout()
        if lay is None:
            return
        self._custom_widget = widget
        lay.addWidget(widget, 0, Qt.AlignHCenter)

    def set_opacity(self, opacity: float):
        """
        Set the overlay opacity. Only values between 0.0 and 1.0 are accepted. If a
        value outside this range is provided, it will be clamped.

        Args:
            opacity(float): The opacity value between 0.0 (fully transparent) and 1.0 (fully opaque).
        """
        self._opacity = max(0.0, min(1.0, float(opacity)))
        # Re-apply alpha using the current theme color
        base = self.scrim_color
        base.setAlpha(int(255 * self._opacity))
        self.scrim_color = base
        self._update_palette()

    ##########################
    ### Internal methods ###
    ##########################

    def _update_palette(self):
        """
        Update colors from the current application theme.
        """
        _app = QApplication.instance()
        if hasattr(_app, "theme"):
            theme = _app.theme  # type: ignore[attr-defined]
            _bg = theme.color("BORDER")
            _fg = theme.color("FG")
        else:
            # Fallback neutrals
            _bg = QColor(30, 30, 30)
            _fg = QColor(230, 230, 230)

        # Semi-transparent scrim derived from bg
        base = _bg if isinstance(_bg, QColor) else QColor(str(_bg))
        base.setAlpha(int(255 * max(0.0, min(1.0, getattr(self, "_opacity", 0.35)))))
        self.scrim_color = base
        fg = _fg if isinstance(_fg, QColor) else QColor(str(_fg))
        self.foreground_color = fg

        # Set the frame style with updated foreground colors
        r, g, b, a = base.getRgb()
        self._frame.setStyleSheet(
            f"#busyFrame {{ border: 2px dashed {self.foreground_color.name()}; border-radius: 9px; background-color: rgba({r}, {g}, {b}, {a}); }}"
        )
        self.update()

    #############################
    ### Custom Event Handlers ###
    #############################

    def showEvent(self, e):
        # Call showEvent on custom widget if present
        if self._custom_widget is not None:
            self._custom_widget.showEvent(e)
        super().showEvent(e)

    def hideEvent(self, e):
        # Call hideEvent on custom widget if present
        if self._custom_widget is not None:
            self._custom_widget.hideEvent(e)
        super().hideEvent(e)

    def resizeEvent(self, e):
        # Call resizeEvent on custom widget if present
        if self._custom_widget is not None:
            self._custom_widget.resizeEvent(e)
        super().resizeEvent(e)
        r = self.rect().adjusted(10, 10, -10, -10)
        self._frame.setGeometry(r)

    # TODO should we have this cleanup here?
    def cleanup(self):
        """Cleanup resources used by the overlay."""
        if self._custom_widget is not None:
            if hasattr(self._custom_widget, "cleanup"):
                self._custom_widget.cleanup()


def install_busy_loader(
    target: QWidget, start_loading: bool = False, opacity: float = 0.35
) -> BusyLoaderOverlay:
    """
    Attach a BusyLoaderOverlay to `target` and keep it sized and stacked.

    Args:
        target(QWidget): The widget to overlay.
        start_loading(bool): If True, show the overlay immediately.
        opacity(float): Overlay opacity (0..1).

    Returns:
        BusyLoaderOverlay: The overlay instance.
    """
    overlay = BusyLoaderOverlay(parent=target, opacity=opacity)
    overlay.setGeometry(target.rect())
    overlay.set_filter(_OverlayEventFilter(target, overlay))
    if start_loading:
        overlay.show()
    return overlay


# --------------------------
# Launchable demo
# --------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

    class DemoWidget(BECWidget, QWidget):  # pragma: no cover
        def __init__(self, parent=None, start_busy: bool = False):
            super().__init__(parent=parent, theme_update=True, start_busy=start_busy)

            self._title = QLabel("Demo Content", self)
            self._title.setAlignment(Qt.AlignCenter)
            self._title.setFrameStyle(QFrame.Panel | QFrame.Sunken)
            lay = QVBoxLayout(self)
            lay.addWidget(self._title)
            waveform = Waveform(self)
            waveform.plot([1, 2, 3, 4, 5])
            lay.addWidget(waveform, 1)

            QTimer.singleShot(5000, self._ready)

        def _ready(self):
            self._title.setText("Ready ✓")
            self.set_busy(False)

    class DemoWindow(QMainWindow):  # pragma: no cover
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Busy Loader — BECWidget demo")

            left = DemoWidget(start_busy=True)
            right = DemoWidget()

            btn_on = QPushButton("Right → Loading")
            btn_off = QPushButton("Right → Ready")
            btn_text = QPushButton("Set custom text")
            btn_on.clicked.connect(lambda: right.set_busy(True))
            btn_off.clicked.connect(lambda: right.set_busy(False))

            panel = QWidget()
            prow = QVBoxLayout(panel)
            prow.addWidget(btn_on)
            prow.addWidget(btn_off)
            prow.addWidget(btn_text)
            prow.addStretch(1)

            central = QWidget()
            row = QHBoxLayout(central)
            row.setContentsMargins(12, 12, 12, 12)
            row.setSpacing(12)
            row.addWidget(left, 1)
            row.addWidget(right, 1)
            row.addWidget(panel, 0)

            self.setCentralWidget(central)
            self.resize(900, 420)

    app = QApplication(sys.argv)
    apply_theme("light")
    w = DemoWindow()
    w.show()
    sys.exit(app.exec())
