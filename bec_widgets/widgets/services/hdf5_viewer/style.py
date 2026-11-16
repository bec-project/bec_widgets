"""Colours the HDF5 viewer shares with the other BEC widgets (scan queue, status box)."""

from __future__ import annotations

from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone

#: Widgets drawn in the muted colour carry this property, so a theme change can find them.
MUTED_PROPERTY = "hdf5_viewer_muted"


def muted_color() -> QColor:
    """
    The colour of secondary text: the text colour of the theme at 62 %, as in the scan queue,
    laid over the background so that it can also be used where alpha is not blended.

    Returns:
        QColor: An opaque colour.
    """
    colors = theme_colors()
    fg, bg = colors["fg"], colors["bg"]
    alpha = colors["muted"].alphaF()
    return QColor(
        round(fg.red() * alpha + bg.red() * (1 - alpha)),
        round(fg.green() * alpha + bg.green() * (1 - alpha)),
        round(fg.blue() * alpha + bg.blue() * (1 - alpha)),
    )


def mute(widget: QWidget) -> None:
    """
    Draw a widget's text in the muted colour, now and after every change of the theme.

    Args:
        widget (QWidget): The widget, usually a label.
    """
    widget.setProperty(MUTED_PROPERTY, True)
    _apply(widget)


def remute(root: QWidget) -> None:
    """
    Apply the muted colour of the current theme again to every muted widget below ``root``.

    Args:
        root (QWidget): The widget whose children are refreshed.
    """
    for widget in root.findChildren(QWidget):
        if widget.property(MUTED_PROPERTY):
            _apply(widget)


def _apply(widget: QWidget) -> None:
    color = muted_color()
    palette = widget.palette()
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
        palette.setColor(role, color)
    widget.setPalette(palette)


def tone_color(tone: Tone) -> QColor:
    """
    The colour of a tone, as the chips of the scan queue and the status box use it.

    Args:
        tone (Tone): The tone.

    Returns:
        QColor: The colour.
    """
    colors = theme_colors()
    return QColor(
        {
            Tone.RUN: colors["run"],
            Tone.OK: colors["ok"],
            Tone.WARN: colors["warn"],
            Tone.BAD: colors["bad"],
            Tone.ACCENT: colors["primary"],
        }.get(tone, colors["muted"])
    )
