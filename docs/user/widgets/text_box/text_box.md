(user.widgets.text_box)=

# Text Box Widget

````{tab} Overview

The [`Text Box Widget`](/api_reference/_autosummary/bec_widgets.cli.client.TextBox) is a versatile widget that allows users to display text within the BEC GUI. It supports both plain text and HTML, making it useful for displaying simple messages or more complex formatted content. This widget is particularly suited for integrating textual content directly into the user interface, whether as a standalone message box or as part of a larger application interface.

## Key Features:
- **Text Display**: Display either plain text or HTML content, with automatic detection of the format.
- **Automatic styling**: The widget automatically adheres to BEC's style guides. No need to worry about background colors, font sizes, or other appearance settings.

## BEC Designer Properties
```{figure} ../../../assets/widget_screenshots/text_box_properties.png
```

````

````{tab} Examples - CLI

The `TextBox` widget can be integrated within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `QtDesigner`. The following examples demonstrate how to create and customize the `TextBox` widget in various scenarios.

## Example 1 - Adding Text Box Widget to BECDockArea

In this example, we demonstrate how to add a `TextBox` widget to a `BECDockArea` and set the text to be displayed.

```python
# Add a new dock with a TextBox widget
text_box = gui.bec.new().new(widget=gui.available_widgets.TextBox)

# Set the text to display
text_box.set_plain_text("Hello, World!")
```

## Example 2 - Displaying HTML Content

The `TextBox` widget can also render HTML content. This example shows how to display formatted HTML text.

```python
# Set the text to display as HTML
text_box.set_html_text("<h1>Welcome to BEC Widgets</h1><p>This is an example of displaying <strong>HTML</strong> text.</p>")
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.TextBox.rst
```
````









