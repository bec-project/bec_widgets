import pytest
from qtpy.QtCore import Qt

from bec_widgets.qt_utils.palette_viewer import PaletteViewer
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


@pytest.fixture
def palette_viewer(qtbot):
    widget = PaletteViewer()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_palette_viewer_renders_palette_and_accents(qtbot, palette_viewer):
    assert palette_viewer.frame_layout.count() == 28
    palette_viewer.clear_palette()
    assert palette_viewer.frame_layout.count() == 0
    palette_viewer.update_palette()
    assert palette_viewer.frame_layout.count() == 28


def test_palette_viewer_updates_on_theme_change(qtbot, palette_viewer):
    light_window_text_color = palette_viewer.frame_layout.itemAt(1).itemAt(0).widget().text()
    assert "(windowText)" in light_window_text_color
    light_hex_color = light_window_text_color.split(" ")[0]

    button = palette_viewer.findChild(DarkModeButton)
    qtbot.mouseClick(button.mode_button, Qt.MouseButton.LeftButton)
    qtbot.wait(100)

    dark_window_text_color = palette_viewer.frame_layout.itemAt(1).itemAt(0).widget().text()
    assert "(windowText)" in dark_window_text_color
    dark_hex_color = dark_window_text_color.split(" ")[0]

    assert light_hex_color != dark_hex_color
