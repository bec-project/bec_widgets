(user.widgets.text_box)=
# [Text Box Widget](/api_reference/_autosummary/bec_widgets.cli.client.TextBoxWidget)
**Purpose:**

The Text Box Widget is a widget that allows you to display text within the BEC GUI. The widget can be used to display plain text or HTML text.

**Key Features:**

- set the text to display.
- automatically detects if the text is plain text or HTML text.
- set background color and font color.

**Code example:**

The following code snipped demonstrates how to create a `TextBox` widget using BEC Widgets within BEC.
```python
text_box = gui.add_dock().add_widget("TextBox")
# set the text to display
text_box.set_text("Hello, World!")
# set the background color and font color
text_box.set_color(backgroud_color="#FFF", font_color="#000")
# set the text to display as HTML
text_box.set_text("<h1>Welcome to BEC Widgets</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>")
```









