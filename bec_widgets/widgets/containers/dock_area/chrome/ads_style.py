"""Qt-ADS behaviour flags and the stylesheet layer of the improved dock area chrome.

The dock framework stays Qt-ADS. This module only changes how it behaves and looks:

* the per-group X (which closed every tab of a group at once) is gone; every tab has its own X,
* double-clicking a title no longer pops the widget out (double-click renames instead),
* the tabs menu only shows when tabs overflow,
* splitter gutters are visible and highlight on hover,
* the focused group and the active tab are marked with the accent colour,
* drop overlays use the theme's accent instead of Qt-ADS' default blue.
"""

from __future__ import annotations

import os

from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QWidget

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets.utils.quick.host import ThemeTokens

CHROME_ENV = "BEC_DOCK_CHROME"
CHROME_MODES = ("qwidget", "qml", "legacy")

_FLAG_SNAPSHOT: dict | None = None


def chrome_mode() -> str:
    """Return the selected dock chrome: ``qwidget`` (default), ``qml`` or ``legacy``.

    Set ``BEC_DOCK_CHROME=qml`` to use the QML gallery and empty state, or ``legacy`` to get the
    dock area exactly as it was before.
    """
    mode = os.environ.get(CHROME_ENV, "qwidget").strip().lower()
    return mode if mode in CHROME_MODES else "qwidget"


def _modern_flags() -> dict:
    flag = QtAds.CDockManager.eConfigFlag
    return {
        flag.DockAreaHasCloseButton: False,
        flag.DockAreaCloseButtonClosesTab: True,
        flag.AllTabsHaveCloseButton: True,
        flag.DoubleClickUndocksWidget: False,
        flag.DockAreaDynamicTabsMenuButtonVisibility: True,
        flag.MiddleMouseButtonClosesTab: True,
        flag.FloatingContainerHasWidgetTitle: True,
        flag.FocusHighlighting: True,
    }


def configure_ads_flags(modern: bool) -> None:
    """Set the global Qt-ADS config flags. Must run before a ``CDockManager`` is created.

    Args:
        modern(bool): True for the improved behaviour, False to restore the flags found on the
            first call (the legacy behaviour).
    """
    global _FLAG_SNAPSHOT  # pylint: disable=global-statement
    manager = QtAds.CDockManager
    if _FLAG_SNAPSHOT is None:
        _FLAG_SNAPSHOT = {
            key: manager.testConfigFlag(key) for key in _modern_flags()  # type: ignore[arg-type]
        }
    target = _modern_flags() if modern else _FLAG_SNAPSHOT
    for key, value in target.items():
        manager.setConfigFlag(key, value)


def _rgba(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(alpha * 255)})"


def _line(color: str, horizontal_handle: bool) -> str:
    """A 2 px line centred in a splitter handle, drawn with a hard-stop gradient."""
    axis = "x1:0, y1:0, x2:1, y2:0" if horizontal_handle else "x1:0, y1:0, x2:0, y2:1"
    return (
        f"qlineargradient({axis}, stop:0 transparent, stop:0.37 transparent,"
        f" stop:0.38 {color}, stop:0.62 {color}, stop:0.63 transparent, stop:1 transparent)"
    )


def dock_chrome_qss(tokens: ThemeTokens) -> str:
    """Stylesheet applied on top of the application theme to the dock manager.

    Args:
        tokens(ThemeTokens): Resolved colours of the active theme.
    """
    grip = _rgba(tokens.fg, 0.16)
    grip_hover = tokens.primary.name()
    overlay_colors = " ".join(
        (
            f"Frame={tokens.primary.name()}",
            f"WindowBackground={tokens.card.name()}",
            f"Overlay={_rgba(tokens.primary, 0.3)}",
            f"Arrow={tokens.fg.name()}",
            f"Shadow={_rgba(QColor('black'), 0.25)}",
        )
    )
    return f"""
    ads--CDockSplitter::handle:horizontal {{ background: {_line(grip, True)}; }}
    ads--CDockSplitter::handle:vertical {{ background: {_line(grip, False)}; }}
    ads--CDockSplitter::handle:horizontal:hover {{ background: {_line(grip_hover, True)}; }}
    ads--CDockSplitter::handle:vertical:hover {{ background: {_line(grip_hover, False)}; }}
    ads--CDockSplitter::handle:pressed {{ background: {_rgba(tokens.primary, 0.55)}; }}

    ads--CDockAreaWidget[focused="true"] {{ border: 1px solid {_rgba(tokens.primary, 0.7)}; }}

    ads--CDockWidgetTab {{ padding: 2px 4px; }}
    ads--CDockWidgetTab QLabel {{ color: {tokens.fg_muted.name()}; }}
    ads--CDockWidgetTab:hover QLabel {{ color: {tokens.fg.name()}; }}
    ads--CDockWidgetTab[activeTab="true"] QLabel {{ color: {tokens.fg.name()}; font-weight: 600; }}
    ads--CDockWidgetTab[activeTab="true"] {{ border-bottom: 2px solid {tokens.fg_subtle.name()}; }}
    ads--CDockWidgetTab[focused="true"] {{ border-bottom: 2px solid {tokens.primary.name()}; }}

    ads--CDockOverlayCross {{ qproperty-iconColors: "{overlay_colors}"; }}
    """


def apply_dock_chrome_style(manager: QWidget, enabled: bool) -> None:
    """Apply (or clear) the chrome stylesheet and drop-overlay colours on a dock manager.

    Args:
        manager(QWidget): The ``CDockManager``.
        enabled(bool): False clears the layer and keeps only the application theme.
    """
    if not enabled:
        manager.setStyleSheet("")
        return
    tokens = ThemeTokens()
    manager.setStyleSheet(dock_chrome_qss(tokens))
    for name in ("dockAreaOverlay", "containerOverlay"):
        overlay = getattr(manager, name, lambda: None)()
        if overlay is None:
            continue
        palette = overlay.palette()
        palette.setColor(QPalette.ColorRole.Highlight, tokens.primary)
        overlay.setPalette(palette)
