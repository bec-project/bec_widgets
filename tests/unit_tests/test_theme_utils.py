from unittest import mock

from qtpy.QtCore import QSize
from qtpy.QtGui import QColor, QIcon
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.theme_utils import crisp_icon, crisp_pixmap, css, theme_colors


def test_crisp_icons_render_at_the_device_pixel_ratio(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    with mock.patch.object(host, "devicePixelRatioF", return_value=2.0):
        pixmap = crisp_pixmap("delete", 18, QColor("red"), widget=host)
        icon = crisp_icon("delete", 18, QColor("red"), widget=host)
    assert pixmap.size() == QSize(36, 36)
    assert pixmap.devicePixelRatio() == 2.0
    assert QSize(36, 36) in icon.availableSizes(QIcon.Mode.Normal)
    normal = icon.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Normal).toImage()
    disabled = icon.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Disabled).toImage()
    assert normal.size() == QSize(36, 36)
    assert normal != disabled


def test_theme_colors_and_css(qtbot):
    colors = theme_colors()
    for key in ("fg", "muted", "bg", "card", "border", "primary", "on_primary", "ok", "bad"):
        assert isinstance(colors[key], QColor)
    assert colors["muted"].alphaF() < 1
    assert css(QColor(10, 20, 30)) == "rgba(10, 20, 30, 255)"
    assert css(QColor(10, 20, 30), 0.5) == "rgba(10, 20, 30, 128)"
