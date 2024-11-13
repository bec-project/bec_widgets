import pytest

from bec_widgets.widgets.editors.text_box.text_box import DEFAULT_TEXT, TextBox

from .client_mocks import mocked_client


@pytest.fixture
def text_box_widget(qtbot, mocked_client):
    widget = TextBox(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_textbox_widget(text_box_widget):
    """Test the TextBox widget."""
    # Test default
    assert text_box_widget.config.text == DEFAULT_TEXT
    # Test set text
    text = "Hello World!"
    text_box_widget.set_plain_text(text)
    assert text_box_widget.plain_text == text
    # Test set HTML text
    text = "<h1>Welcome to PyQt6</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>"
    text_box_widget.set_html_text(text)
    assert (
        text_box_widget.plain_text
        == "Welcome to PyQt6\nThis is an example of displaying HTML text."
    )
