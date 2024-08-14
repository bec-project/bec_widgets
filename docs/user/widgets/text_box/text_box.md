(user.widgets.text_box)=

# Text Box Widget

````{tab} Overview

The [`Text Box Widget`](/api_reference/_autosummary/bec_widgets.cli.client.TextBox) is a versatile widget that allows users to display text within the BEC GUI. It supports both plain text and HTML, making it useful for displaying simple messages or more complex formatted content. This widget is particularly suited for integrating textual content directly into the user interface, whether as a standalone message box or as part of a larger application interface.

## Key Features:
- **Text Display**: Display either plain text or HTML content, with automatic detection of the format.
- **Customizable Appearance**: Set the background and font colors to match the design of your application.
- **Font Size Adjustment**: Customize the font size of the displayed text for better readability.

````

````{tab} Examples - CLI

The `TextBox` widget can be integrated within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `QtDesigner`. The following examples demonstrate how to create and customize the `TextBox` widget in various scenarios.

## Example 1 - Adding Text Box Widget to BECDockArea

In this example, we demonstrate how to add a `TextBox` widget to a `BECDockArea` and set the text to be displayed.

```python
# Add a new dock with a TextBox widget
text_box = gui.add_dock().add_widget("TextBox")

# Set the text to display
text_box.set_text("Hello, World!")
```

## Example 2 - Displaying HTML Content

The `TextBox` widget can automatically detect and render HTML content. This example shows how to display formatted HTML text.

```python
# Set the text to display as HTML
text_box.set_text("<h1>Welcome to BEC Widgets</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>")
```

## Example 3 - Customizing Appearance

The `TextBox` widget allows you to customize the background and font colors to fit your application's design. Below is an example of how to set these properties.

```python
# Set the background color to white and the font color to black
text_box.set_color(background_color="#FFF", font_color="#000")
```

## Example 4 - Adjusting Font Size

To improve readability or fit more text within the widget, you can adjust the font size.

```python
# Set the font size to 14 pixels
text_box.set_font_size(14)
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.TextBox.rst
```
````









