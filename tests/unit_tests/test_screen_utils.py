from qtpy.QtCore import QRect
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.screen_utils import (
    apply_centered_size,
    centered_geometry,
    main_app_size_for_screen,
)


def test_centered_geometry_returns_expected_tuple():
    available = QRect(100, 50, 800, 600)
    result = centered_geometry(available, 400, 300)
    assert result == (300, 200, 400, 300)


def test_main_app_size_for_screen_respects_16_9_and_screen_caps():
    available = QRect(0, 0, 1920, 1080)
    width, height = main_app_size_for_screen(available)
    assert (width, height) == (1728, 972)

    narrow = QRect(0, 0, 1000, 800)
    width, height = main_app_size_for_screen(narrow)
    assert (width, height) == (900, 506)


def test_apply_centered_size_uses_provided_geometry(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    available = QRect(10, 20, 600, 400)
    apply_centered_size(widget, 200, 100, available=available)

    geometry = widget.geometry()
    assert geometry.x() == 210
    assert geometry.y() == 170
    assert geometry.width() == 200
    assert geometry.height() == 100
