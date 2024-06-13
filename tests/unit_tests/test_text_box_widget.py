import re
from unittest import mock

import pytest

from bec_widgets.widgets.text_box.text_box import TextBox

from .client_mocks import mocked_client


@pytest.fixture
def text_box_widget(qtbot, mocked_client):
    widget = TextBox(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_textbox_widget(text_box_widget):
    """Test the TextBox widget."""
    text = "Hello World!"
    text_box_widget.set_text(text)
    assert text_box_widget.toPlainText() == text

    text_box_widget.set_color("#FFDDC1", "#123456")
    text_box_widget.set_font_size(20)
    assert (
        text_box_widget.styleSheet() == "background-color: #FFDDC1; color: #123456; font-size: 20px"
    )
    text_box_widget.set_color("white", "blue")
    text_box_widget.set_font_size(14)
    assert text_box_widget.styleSheet() == "background-color: white; color: blue; font-size: 14px"
    text = "<h1>Welcome to PyQt6</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>"
    with mock.patch.object(text_box_widget, "setHtml") as mocked_set_html:
        text_box_widget.set_text(text)
        assert mocked_set_html.call_count == 1
        assert mocked_set_html.call_args == mock.call(text)


def test_textbox_change_theme(text_box_widget):
    """Test change theme functionaility"""
    # Default is dark theme
    text_box_widget.change_theme()
    assert text_box_widget.config.theme == "light"
    assert (
        text_box_widget.styleSheet()
        == f"background-color: #FFF; color: #000; font-size: {text_box_widget.config.font_size}px"
    )
    text_box_widget.change_theme()
    assert text_box_widget.config.theme == "dark"
    assert (
        text_box_widget.styleSheet()
        == f"background-color: #000; color: #FFF; font-size: {text_box_widget.config.font_size}px"
    )
