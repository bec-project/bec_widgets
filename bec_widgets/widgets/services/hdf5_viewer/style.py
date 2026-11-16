"""Colours the HDF5 viewer shares with the other BEC widgets (scan queue, status box)."""

from __future__ import annotations

import functools
import math
import sys

from qtpy.QtCore import QLocale, QPointF, QRect, QRectF, Qt
from qtpy.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPalette,
    QPen,
)
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_queue.queue_ui import (
    BADGE_ALPHA,
    BADGE_PADDING,
    BADGE_RADIUS,
    GROUP_TITLE_FONT_PX,
    GROUP_TITLE_LETTER_SPACING,
    ROW_HOVER_ALPHA,
    ROW_SELECTED_ALPHA,
)

#: Corner radius of the rounded background of a row of the file tree and the signal list, as
#: on the rows of the scan list but for their lower rows.
LIST_ROW_RADIUS = 4
#: Width of the ring of the selected row and the gap inside it.
LIST_RING_WIDTH = 1.5
LIST_RING_GAP = 1.0

#: Widgets drawn in the muted colour carry this property, so a theme change can find them.
MUTED_PROPERTY = "hdf5_viewer_muted"


#: How much of the text colour secondary text has on a row tinted for the curves it leads to:
#: more than on a plain row, so that it keeps 4.5:1 or more on every part of the tint.
DIM_ON_TINT_ALPHA = 0.78


def muted_color(alpha: float | None = None) -> QColor:
    """
    The colour of secondary text: the text colour of the theme at 62 %, as in the scan queue,
    laid over the background so that it can also be used where alpha is not blended.

    Args:
        alpha (float | None): How much of the text colour, instead of the theme's 62 %; e.g.
            :data:`DIM_ON_TINT_ALPHA` for secondary text on a tinted row.

    Returns:
        QColor: An opaque colour.
    """
    colors = theme_colors()
    fg, bg = colors["fg"], colors["bg"]
    if alpha is None:
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


def control_key_name() -> str:
    """
    Name of the key that Qt reports as ``Qt.KeyboardModifier.ControlModifier``: Ctrl on Linux,
    the main platform, and the Command key (⌘) on macOS.

    Returns:
        str: ``"Ctrl"``, or ``"⌘"`` on macOS.
    """
    return "⌘" if sys.platform == "darwin" else "Ctrl"


def count_text(count: int, locale: QLocale | None = None) -> str:
    """
    A count as the scan panel shows it, with the group separator of the user's locale, so
    that 5213 reads 5,213 with an English locale and the same in every place.

    Args:
        count (int): The count.
        locale (QLocale | None): The locale; the user's by default.

    Returns:
        str: The count in words of digits, e.g. ``"5,213"``.
    """
    return (locale or QLocale()).toString(int(count))


#: The header of a group of signals, in the lettering of the scan list's day header, on a
#: faint band of the text colour laid over the list's background.
HEAD_BAND_ALPHA = 0.05
#: The title of a header: the text colour at this strength over the band.
HEAD_TITLE_ALPHA = 0.7
#: Height of the band: the count pill and its margins, as the scan list's day header.
HEAD_BAND_HEIGHT = 2 * BADGE_RADIUS + 6
#: Room above a header that follows rows, more than there is between rows.
HEAD_GAP = 8
#: Least contrast of the text of a header against its band.
HEAD_MIN_CONTRAST = 4.5


def blend(color: QColor, base: QColor, alpha: float) -> QColor:
    """
    A colour at ``alpha`` laid over an opaque one.

    Args:
        color (QColor): The colour on top.
        base (QColor): The colour below.
        alpha (float): Strength of the colour on top, 0 to 1.

    Returns:
        QColor: An opaque colour.
    """
    return QColor(
        round(color.red() * alpha + base.red() * (1 - alpha)),
        round(color.green() * alpha + base.green() * (1 - alpha)),
        round(color.blue() * alpha + base.blue() * (1 - alpha)),
    )


def contrast(first: QColor, second: QColor) -> float:
    """
    The WCAG contrast ratio of two opaque colours.

    Args:
        first (QColor): One colour.
        second (QColor): The other.

    Returns:
        float: 1 to 21.
    """

    def luminance(color: QColor) -> float:
        def channel(value: int) -> float:
            value /= 255
            return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(color.red())
            + 0.7152 * channel(color.green())
            + 0.0722 * channel(color.blue())
        )

    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable(ink: QColor, back: QColor, ratio: float = HEAD_MIN_CONTRAST) -> QColor:
    """
    A colour of the same hue as ``ink`` that reads on ``back``: darker on a light background,
    lighter on a dark one, as little as it takes.

    Args:
        ink (QColor): The wanted colour.
        back (QColor): The opaque background.
        ratio (float): The least contrast.

    Returns:
        QColor: ``ink`` itself when it reads, else the nearest shade that does.
    """
    toward = QColor("#000000" if back.lightnessF() > 0.5 else "#ffffff")
    for step in range(21):
        color = blend(toward, ink, step / 20)
        if contrast(color, back) >= ratio:
            return color
    return toward


def head_colors(base: QColor) -> dict[str, QColor]:
    """
    The colours of a group header drawn on a list of the given background.

    Args:
        base (QColor): The opaque background of the list.

    Returns:
        dict[str, QColor]: ``band``, ``title``, ``rule``, ``badge`` (the pill), ``count`` and
        ``mark`` (the fold mark).
    """
    colors = theme_colors()
    band = blend(colors["fg"], base, HEAD_BAND_ALPHA)
    title = readable(blend(colors["fg"], band, HEAD_TITLE_ALPHA), band)
    badge = blend(colors["primary"], band, BADGE_ALPHA)
    return {
        "band": band,
        "title": title,
        "rule": QColor(colors["border"]),
        "badge": badge,
        "count": readable(colors["primary"], badge),
        "mark": title,
    }


def head_title_font(base: QFont) -> QFont:
    """The lettering of a group header: the scan list's day header."""
    font = QFont(base)
    font.setPixelSize(GROUP_TITLE_FONT_PX)
    font.setBold(True)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, GROUP_TITLE_LETTER_SPACING)
    return font


def paint_group_head(
    painter: QPainter,
    rect: QRect,
    title: str,
    count: int,
    base: QColor,
    font: QFont,
    *,
    gap: int = 0,
    rule: bool = False,
    open_: bool | None = None,
    padding: int = 6,
) -> None:
    """
    Paint the header of a group of a list: an uppercase title and its count in a pill, on a
    faint band across the row, with a hairline on top and a fold mark where they apply.

    Args:
        painter (QPainter): The painter.
        rect (QRect): The row, across the whole list.
        title (str): The group's name, as it is written; it is shown in capitals.
        count (int): How many are in the group.
        base (QColor): The opaque background of the list.
        font (QFont): The font of the list's rows.
        gap (int): Room left free above the band.
        rule (bool): Whether a hairline separates the band from the rows above.
        open_ (bool | None): Whether the group is open, for its fold mark; None for a group
            that does not fold.
        padding (int): Room at the left and the right of the band's content.
    """
    colors = head_colors(base)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    band = QRect(rect.left(), rect.top() + gap, rect.width(), rect.height() - gap)
    painter.fillRect(band, colors["band"])
    if rule:
        painter.setPen(QPen(colors["rule"], 1))
        painter.drawLine(band.left(), band.top(), band.right(), band.top())
    left, right = band.left() + padding, band.right() - padding
    if open_ is not None:
        # A chevron at the right: down when the group is open, right when it is closed.
        size = 4.0
        centre = QPointF(right - size, band.center().y() + 0.5)
        if open_:
            points = [
                centre + QPointF(-size, -size / 2),
                centre + QPointF(0, size / 2),
                centre + QPointF(size, -size / 2),
            ]
        else:
            points = [
                centre + QPointF(-size / 2, -size),
                centre + QPointF(size / 2, 0),
                centre + QPointF(-size / 2, size),
            ]
        pen = QPen(colors["mark"], 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(points)
        right -= int(2 * size) + padding
    title_font = head_title_font(font)
    badge_font = QFont(font)
    badge_font.setWeight(QFont.Weight.DemiBold)
    text = count_text(count)
    badge_width = max(
        2 * BADGE_RADIUS, QFontMetrics(badge_font).horizontalAdvance(text) + 2 * BADGE_PADDING
    )
    metrics = QFontMetrics(title_font)
    room = max(0, right - left - badge_width - 8)
    shown = metrics.elidedText(title.upper(), Qt.TextElideMode.ElideRight, room)
    painter.setFont(title_font)
    painter.setPen(colors["title"])
    painter.drawText(
        QRect(left, band.top(), room, band.height()),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        shown,
    )
    pill = QRectF(
        left + metrics.horizontalAdvance(shown) + 8,
        band.center().y() + 1 - BADGE_RADIUS,
        badge_width,
        2 * BADGE_RADIUS,
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colors["badge"])
    painter.drawRoundedRect(pill, BADGE_RADIUS, BADGE_RADIUS)
    painter.setFont(badge_font)
    painter.setPen(colors["count"])
    painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


#: Shades of a scan's colour for its curves in a comparison: the scan's own and then others of
#: its hue; with more curves they repeat.
SHADE_STEPS = 4
#: Least contrast of a curve against the plot's background.
CURVE_MIN_CONTRAST = 3.0
#: The lightness (OKLCH) shades keep within: not so dark on a light plot, nor so light on a
#: dark one, that they lose their hue.
SHADE_LIGHTNESS = {"light": (0.40, 1.0), "dark": (0.0, 0.86)}


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _gam(v: float) -> float:
    v = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return v


def oklch_of(color: QColor) -> tuple[float, float, float]:
    """OKLCH lightness (0 to 1), chroma and hue (radians) of an sRGB colour."""
    r, g, b = (_lin(c) for c in (color.red(), color.green(), color.blue()))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.atan2(bb, a)


def _rgb_of(L: float, C: float, h: float) -> tuple:  # pylint: disable=invalid-name
    a, b = C * math.cos(h), C * math.sin(h)
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def color_of_oklch(L: float, C: float, h: float) -> QColor:  # pylint: disable=invalid-name
    """The sRGB colour of an OKLCH one; the chroma is lowered as far as sRGB needs."""
    lo, hi = 0.0, C
    rgb = _rgb_of(L, C, h)
    if not all(-1e-6 <= v <= 1 + 1e-6 for v in rgb):
        for _ in range(24):
            mid = (lo + hi) / 2
            if all(-1e-6 <= v <= 1 + 1e-6 for v in _rgb_of(L, mid, h)):
                lo = mid
            else:
                hi = mid
        rgb = _rgb_of(L, lo, h)
    return QColor(*(round(min(1, max(0, _gam(min(1, max(0, v))))) * 255) for v in rgb))


def scan_shades(base: QColor | str, backs: tuple[QColor, ...]) -> list[QColor]:
    """
    Shades of one scan's colour for its curves, see :func:`_scan_shades`; worked out once per
    colour and theme.
    """
    names = _scan_shade_names(QColor(base).name(), tuple(QColor(back).name() for back in backs))
    return [QColor(name) for name in names]


@functools.lru_cache(maxsize=64)
def _scan_shade_names(base: str, backs: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(color.name() for color in _scan_shades(QColor(base), tuple(map(QColor, backs))))


def _scan_shades(base: QColor | str, backs: tuple[QColor, ...]) -> list[QColor]:
    """
    Shades of one scan's colour for its curves: the colour itself first, then others of its
    hue in even lightness steps, each readable on the plot.

    Args:
        base (QColor | str): The scan's colour.
        backs (tuple[QColor, ...]): The plot's backgrounds of the theme, all light or all dark.

    Returns:
        list[QColor]: :data:`SHADE_STEPS` colours, the base first, the others from the one
        that differs most to the one that differs least.
    """
    base = QColor(base)
    lightness, chroma, hue = oklch_of(base)
    dark = all(back.lightnessF() < 0.5 for back in backs)
    low, high = SHADE_LIGHTNESS["dark" if dark else "light"]

    def fits(value: float) -> bool:
        color = color_of_oklch(value, chroma, hue)
        return all(contrast(color, back) >= CURVE_MIN_CONTRAST for back in backs)

    readable_l = [step / 200 for step in range(201) if low <= step / 200 <= high]
    readable_l = [value for value in readable_l if fits(value)]
    if not readable_l:
        return [base] * SHADE_STEPS
    low, high = readable_l[0], readable_l[-1]
    if low <= lightness <= high:
        # Even steps through the scan's own colour: a grid of a quarter of the room fits four
        # or five steps, the one farthest from the colour goes.
        step = (high - low) / SHADE_STEPS
        first = lightness - math.floor((lightness - low) / step + 1e-9) * step
        targets = [first + k * step for k in range(SHADE_STEPS + 1)]
        targets = [value for value in targets if value <= high + 1e-9]
        targets = sorted(targets, key=lambda value: abs(value - lightness))[1:SHADE_STEPS]
    else:
        # A colour too light or too dark to read: even steps through the readable room, the
        # one nearest to the colour left out.
        targets = [low + (high - low) * k / (SHADE_STEPS - 1) for k in range(SHADE_STEPS)]
        targets.remove(min(targets, key=lambda value: abs(value - lightness)))
    targets.sort(key=lambda value: -abs(value - lightness))
    return [base] + [color_of_oklch(value, chroma, hue) for value in targets]


def mix_colors(colors: list[QColor]) -> QColor:
    """
    The mean of some colours, to pick black or white text for a row painted in all of them.

    Args:
        colors (list[QColor]): At least one colour.

    Returns:
        QColor: Their mean in RGB.
    """
    count = len(colors)
    return QColor.fromRgbF(
        sum(c.redF() for c in colors) / count,
        sum(c.greenF() for c in colors) / count,
        sum(c.blueF() for c in colors) / count,
    )


#: How much of the colours of its curves tints a row that only leads to them, by theme: the
#: colours told apart at a glance, the text of the theme at 7:1 or more on every part of it.
LEAD_TINT_DARK = 0.30
LEAD_TINT_LIGHT = 0.25


def lead_tint() -> float:
    """The strength of the tint of a row that leads to curves, for the current theme."""
    return LEAD_TINT_DARK if QColor(theme_colors()["bg"]).lightnessF() < 0.5 else LEAD_TINT_LIGHT


def paint_list_row(
    painter: QPainter,
    row: QRectF,
    fills: list[QColor],
    selected: bool,
    hovered: bool,
    strength: float = 1.0,
) -> None:
    """
    Paint the background of a row of a list as the scan list paints its rows: the colour of
    what is on the plot (several side by side, as a gradient), a ring and a tint for the
    selected row, a shade under the pointer.

    Args:
        painter (QPainter): The painter of the list's viewport.
        row (QRectF): The row, across the list.
        fills (list[QColor]): The colours the row is on the plot in; empty for none.
        selected (bool): Whether the row is selected.
        hovered (bool): Whether the pointer is on the row.
        strength (float): How much of the colours covers the background: 1 for a solid fill
            (the row is on the plot), less for a tint (the row only leads to what is).
    """
    if not fills and not selected and not hovered:
        return
    colors = theme_colors()
    if strength < 1.0:
        fills = [QColor(color) for color in fills]
        for color in fills:
            color.setAlphaF(strength)
    fill = None
    if len(fills) == 1:
        fill = QBrush(fills[0])
    elif fills:
        gradient = QLinearGradient(row.left(), 0, row.right(), 0)
        for position, color in enumerate(fills):
            gradient.setColorAt(position / (len(fills) - 1), color)
        fill = QBrush(gradient)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    body = QRectF(row).adjusted(0, 1, 0, -1)
    radius = LIST_ROW_RADIUS
    if selected:
        half = LIST_RING_WIDTH / 2
        painter.setPen(QPen(colors["primary"], LIST_RING_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body.adjusted(half, half, -half, -half), radius, radius)
        inset = LIST_RING_WIDTH + LIST_RING_GAP
        body = body.adjusted(inset, inset, -inset, -inset)
        radius = max(1.0, radius - inset)
    painter.setPen(Qt.PenStyle.NoPen)
    if fill is not None:
        painter.setBrush(fill)
        painter.drawRoundedRect(body, radius, radius)
    elif selected:
        tint = QColor(colors["primary"])
        tint.setAlphaF(ROW_SELECTED_ALPHA)
        painter.setBrush(tint)
        painter.drawRoundedRect(body, radius, radius)
    if hovered:
        shade = QColor(colors["fg"])
        shade.setAlphaF(ROW_HOVER_ALPHA)
        painter.setBrush(shade)
        painter.drawRoundedRect(body, radius, radius)
    painter.restore()
