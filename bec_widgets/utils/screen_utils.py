from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtCore import QRect


def available_screen_geometry(*, widget: QWidget | None = None) -> QRect | None:
    """
    Get the available geometry of the screen associated with the given widget or application.

    Args:
        widget(QWidget | None): The widget to get the screen from.
    Returns:
        QRect | None: The available geometry of the screen, or None if no screen is found.
    """
    screen = widget.screen() if widget is not None else None
    if screen is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return None
    return screen.availableGeometry()


def centered_geometry(available: "QRect", width: int, height: int) -> tuple[int, int, int, int]:
    """
    Calculate centered geometry within the available rectangle.

    Args:
        available(QRect): The available rectangle to center within.
        width(int): The desired width.
        height(int): The desired height.

    Returns:
        tuple[int, int, int, int]: The (x, y, width, height) of the centered geometry.
    """
    x = available.x() + (available.width() - width) // 2
    y = available.y() + (available.height() - height) // 2
    return x, y, width, height


def centered_geometry_for_app(width: int, height: int) -> tuple[int, int, int, int] | None:
    available = available_screen_geometry()
    if available is None:
        return None
    return centered_geometry(available, width, height)


def scaled_centered_geometry_for_window(
    window: QWidget, *, width_ratio: float = 0.8, height_ratio: float = 0.8
) -> tuple[int, int, int, int] | None:
    available = available_screen_geometry(widget=window)
    if available is None:
        return None
    width = int(available.width() * width_ratio)
    height = int(available.height() * height_ratio)
    return centered_geometry(available, width, height)


def apply_window_geometry(
    window: QWidget,
    geometry: tuple[int, int, int, int] | None,
    *,
    width_ratio: float = 0.8,
    height_ratio: float = 0.8,
) -> None:
    if geometry is not None:
        window.setGeometry(*geometry)
        return
    default_geometry = scaled_centered_geometry_for_window(
        window, width_ratio=width_ratio, height_ratio=height_ratio
    )
    if default_geometry is not None:
        window.setGeometry(*default_geometry)
    else:
        window.resize(window.minimumSizeHint())


def main_app_size_for_screen(available: "QRect") -> tuple[int, int]:
    height = int(available.height() * 0.9)
    width = int(height * (16 / 9))
    if width > available.width() * 0.9:
        width = int(available.width() * 0.9)
        height = int(width / (16 / 9))
    return width, height


def apply_centered_size(
    window: QWidget, width: int, height: int, *, available: "QRect" | None = None
) -> None:
    if available is None:
        available = available_screen_geometry(widget=window)
    if available is None:
        window.resize(width, height)
        return
    window.setGeometry(*centered_geometry(available, width, height))
