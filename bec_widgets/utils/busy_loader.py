from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtGui import QColor, QFont
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

from bec_widgets import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget


class _OverlayEventFilter(QObject):
    """Keeps the overlay sized and stacked over its target widget."""

    def __init__(self, target: QWidget, overlay: QWidget):
        super().__init__(target)
        self._target = target
        self._overlay = overlay

    def eventFilter(self, obj, event):
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

    def __init__(self, parent: QWidget, text: str = "Loading…", opacity: float = 0.85, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._opacity = opacity

        self._label = QLabel(text, self)
        self._label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        f = QFont(self._label.font())
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self._label.setFont(f)

        self._spinner = SpinnerWidget(self)
        self._spinner.setFixedSize(42, 42)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(10)
        lay.addStretch(1)
        lay.addWidget(self._spinner, 0, Qt.AlignHCenter)
        lay.addWidget(self._label, 0, Qt.AlignHCenter)
        lay.addStretch(1)

        self._frame = QFrame(self)
        self._frame.setObjectName("busyFrame")
        self._frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._frame.lower()

        # Defaults
        self._scrim_color = QColor(0, 0, 0, 110)
        self._label_color = QColor(240, 240, 240)
        self.update_palette()

        # Start hidden; interactions beneath are blocked while visible
        self.hide()

    # --- API ---
    def set_text(self, text: str):
        """
        Update the overlay text.

        Args:
            text(str): The text to display on the overlay.
        """
        self._label.setText(text)

    def set_opacity(self, opacity: float):
        """
        Set overlay opacity (0..1).

        Args:
            opacity(float): The opacity value between 0.0 (fully transparent) and 1.0 (fully opaque).
        """
        self._opacity = max(0.0, min(1.0, float(opacity)))
        # Re-apply alpha using the current theme color
        if isinstance(self._scrim_color, QColor):
            base = QColor(self._scrim_color)
            base.setAlpha(int(255 * self._opacity))
            self._scrim_color = base
        self.update()

    def update_palette(self):
        """
        Update colors from the current application theme.
        """
        app = QApplication.instance()
        if hasattr(app, "theme"):
            theme = app.theme  # type: ignore[attr-defined]
            self._bg = theme.color("BORDER")
            self._fg = theme.color("FG")
            self._primary = theme.color("PRIMARY")
        else:
            # Fallback neutrals
            self._bg = QColor(30, 30, 30)
            self._fg = QColor(230, 230, 230)
        # Semi-transparent scrim derived from bg
        self._scrim_color = QColor(self._bg)
        self._scrim_color.setAlpha(int(255 * max(0.0, min(1.0, getattr(self, "_opacity", 0.35)))))
        self._spinner.update()
        fg_hex = self._fg.name() if isinstance(self._fg, QColor) else str(self._fg)
        self._label.setStyleSheet(f"color: {fg_hex};")
        self._frame.setStyleSheet(
            f"#busyFrame {{ border: 2px dashed {fg_hex}; border-radius: 9px; background-color: rgba(128, 128, 128, 110); }}"
        )
        self.update()

    # --- QWidget overrides ---
    def showEvent(self, e):
        self._spinner.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._spinner.stop()
        super().hideEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        r = self.rect().adjusted(10, 10, -10, -10)
        self._frame.setGeometry(r)

    def paintEvent(self, e):
        super().paintEvent(e)


def install_busy_loader(
    target: QWidget, text: str = "Loading…", start_loading: bool = False, opacity: float = 0.35
) -> BusyLoaderOverlay:
    """
    Attach a BusyLoaderOverlay to `target` and keep it sized and stacked.

    Args:
        target(QWidget): The widget to overlay.
        text(str): Initial text to display.
        start_loading(bool): If True, show the overlay immediately.
        opacity(float): Overlay opacity (0..1).

    Returns:
        BusyLoaderOverlay: The overlay instance.
    """
    overlay = BusyLoaderOverlay(target, text=text, opacity=opacity)
    overlay.setGeometry(target.rect())
    filt = _OverlayEventFilter(target, overlay)
    overlay._filter = filt  # type: ignore[attr-defined]
    target.installEventFilter(filt)
    if start_loading:
        overlay.show()
    return overlay


# --------------------------
# Launchable demo
# --------------------------
class DemoWidget(BECWidget, QWidget):  # pragma: no cover
    def __init__(self, parent=None):
        super().__init__(
            parent=parent, theme_update=True, start_busy=True, busy_text="Demo: Initializing…"
        )

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


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Busy Loader — BECWidget demo")

        left = DemoWidget()
        right = DemoWidget()

        btn_on = QPushButton("Right → Loading")
        btn_off = QPushButton("Right → Ready")
        btn_text = QPushButton("Set custom text")
        btn_on.clicked.connect(lambda: right.set_busy(True, "Fetching data…"))
        btn_off.clicked.connect(lambda: right.set_busy(False))
        btn_text.clicked.connect(lambda: right.set_busy_text("Almost there…"))

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


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    apply_theme("light")
    w = DemoWindow()
    w.show()
    sys.exit(app.exec())
