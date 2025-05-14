import pytest

from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget


@pytest.fixture
def monaco_widget(qtbot):
    widget = MonacoWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_monaco_widget_set_text(monaco_widget: MonacoWidget, qtbot):
    """
    Test that the MonacoWidget can set text correctly.
    """
    test_text = "Hello, Monaco!"
    monaco_widget.set_text(test_text)
    qtbot.waitUntil(lambda: monaco_widget.get_text() == test_text, timeout=1000)
    assert monaco_widget.get_text() == test_text


def test_monaco_widget_readonly(monaco_widget: MonacoWidget, qtbot):
    """
    Test that the MonacoWidget can be set to read-only mode.
    """
    monaco_widget.set_text("Initial text")
    qtbot.waitUntil(lambda: monaco_widget.get_text() == "Initial text", timeout=1000)
    monaco_widget.set_readonly(True)

    with pytest.raises(ValueError):
        monaco_widget.set_text("This should not change")

    monaco_widget.set_readonly(False)  # Set back to editable
    qtbot.wait(100)
    monaco_widget.set_text("Attempting to change text")
    qtbot.waitUntil(lambda: monaco_widget.get_text() == "Attempting to change text", timeout=1000)
    assert monaco_widget.get_text() == "Attempting to change text"
