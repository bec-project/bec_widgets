import re
import types

from qtpy import QtCore, QtWidgets, QtGui


class _HoverGradientFilter(QtCore.QObject):
    """Tracks hover/press state for a given widget and forces repaints."""

    def __init__(self, target):
        super().__init__(target)
        self._t = target
        target.destroyed.connect(self._on_dead)
        self._propagate_mouse_tracking(target)

    @QtCore.Slot()
    def _on_dead(self):
        """Target widget is gone → remove the filter."""
        self._t = None  # guard future calls
        self.deleteLater()

    # ensure all descendants forward move events
    def _propagate_mouse_tracking(self, w):
        for c in w.findChildren(QtWidgets.QWidget):
            c.setMouseTracking(True)
            c.installEventFilter(self)
            self._propagate_mouse_tracking(c)

    # core event handling
    def eventFilter(self, watched, ev):
        if self._t is None:  # already cleaned up
            return False
        t = self._t
        typ = ev.type()
        if typ == QtCore.QEvent.MouseMove:
            inside = t.rect().contains(t.mapFromGlobal(ev.globalPos()))
            if inside:
                p = t.mapFromGlobal(ev.globalPos())
                if p != getattr(t, "_hg_pos", QtCore.QPoint()):
                    t._hg_pos = p
                    t.update()
                t._hg_hover = True
            elif getattr(t, "_hg_hover", False):
                t._hg_hover = False
                t.update()
        elif typ == QtCore.QEvent.Enter:
            t._hg_hover, t._hg_pos = True, ev.pos()
            t.update()
        elif typ == QtCore.QEvent.Leave:
            t._hg_hover = False
            t.update()
        elif typ == QtCore.QEvent.MouseButtonPress:
            t._hg_pressed = True
            t.update()
        elif typ == QtCore.QEvent.MouseButtonRelease:
            t._hg_pressed = False
            t.update()
        return super().eventFilter(watched, ev)


# ─────────────────────────── painter helper ─────────────────────────────
def _draw_hover_gradient(widget, painter, path):
    if not getattr(widget, "_hg_hover", False) or widget._hg_pos.x() < 0:
        return

    pressed = getattr(widget, "_hg_pressed", False)
    cols = getattr(widget, "_hg_cols", [QtGui.QColor("#ffffff")])
    accent = cols[0]

    r = max(widget.width(), widget.height()) * (0.6 if pressed else 0.9)
    grad = QtGui.QRadialGradient(widget._hg_pos, r)

    centre = QtGui.QColor(accent)
    centre.setAlpha(180 if pressed else 110)
    grad.setColorAt(0.0, centre)

    edge = cols[1] if len(cols) > 1 else QtCore.Qt.transparent
    grad.setColorAt(1.0, edge)

    painter.fillPath(path, grad)


# ─────────────────────────── public API  ────────────────────────────────
def enable_hover_gradient(frame: QtWidgets.QFrame, colours=None):
    """
    Inject a radial hover-gradient ‘glow’ into *any* QFrame instance.

    Parameters
    ----------
    frame : QFrame
        The widget to enhance.
    colours : str | list[str] | None
        One colour → accent→transparent. Two colours → accent→edge.
    """
    if getattr(frame, "_hg_enabled", False):  # hover gradient injected attribute
        return  # already done

    # normalise colours
    if colours is None:
        colours = ["#ffffff"]
    if isinstance(colours, str):
        colours = [colours]

    # state variables stored directly on the frame
    frame._hg_enabled = True
    frame._hg_cols = [QtGui.QColor(c) for c in colours]
    frame._hg_hover = False
    frame._hg_pressed = False
    frame._hg_pos = QtCore.QPoint(-1, -1)

    # 1) patch paintEvent
    orig_paint = frame.paintEvent

    def patched_paint(self, ev):
        orig_paint(ev)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rad = 0  # default radius

        m = re.search(r"border-radius\s*:\s*([0-9]+)", self.styleSheet())
        if m:
            rad = int(m.group(1))

        path = QtGui.QPainterPath()
        if rad > 0:
            path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), rad, rad)
        else:
            path.addRect(self.rect().adjusted(0, 0, -1, -1))

        _draw_hover_gradient(self, painter, path)
        painter.end()

    frame.paintEvent = types.MethodType(patched_paint, frame)
    frame._hg_orig_paint = orig_paint

    # 2) install tracking filter
    filt = _HoverGradientFilter(frame)
    frame._hg_filter = filt
    frame.installEventFilter(filt)

    frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    frame.setMouseTracking(True)
