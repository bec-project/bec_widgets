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

    text_box_widget.set_text("Hello World!")
    # pylint: disable=protected-access
    assert text_box_widget._text == "Hello World!"

    text_box_widget.set_color("#FFDDC1", "#123456")
    text_box_widget.set_font_size(20)
    assert (
        text_box_widget.styleSheet() == "background-color: #FFDDC1; color: #123456; font-size: 20px"
    )

    with mock.patch.object(text_box_widget, "setHtml") as mock_set_plain_text:
        text_box_widget.set_text(
            "<h1>Welcome to PyQt6</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>"
        )
        assert mock_set_plain_text.call_args == mock.call(
            "<h1>Welcome to PyQt6</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>"
        )
        # pylint: disable=protected-access
        assert (
            text_box_widget._text
            == "<h1>Welcome to PyQt6</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>"
        )
