(user.widgets.buttons_appearance)=

# Appearance Buttons

`````{tab} Overview
This section consolidates various buttons designed to manage the appearance of the BEC GUI, allowing users to easily switch themes, select colors, and choose colormaps.

## Dark Mode Button

The `Dark Mode Button` is a toggle control that allows users to switch between light and dark themes in the BEC GUI. It provides a convenient way to adjust the interface's appearance based on user preferences or environmental conditions.

````{grid} 2
:gutter: 2

```{grid-item-card} Dark Mode
:img-top:  ./dark_mode_enabled.png
```

```{grid-item-card} Light Mode
:img-top:  ./dark_mode_disabled.png
```
````

**Key Features:**
- **Theme Switching**: Enables users to switch between light and dark themes with a single click.
- **Configurable from BECDesigner**: The defaults for the dark mode can be set in the BECDesigner, allowing users to customize the startup appearance of the GUI.

## Color Button

The `Color Button` is a user interface element that provides a dialog to select colors. This button, adapted from `pyqtgraph`, is a simple yet powerful tool to integrate color selection functionality into the BEC GUIs.

**Key Features:**
- **Color Selection**: Opens a dialog for selecting colors, returning the selected color in both RGBA and HEX formats.

## Colormap Selector

The `Colormap Selector` is a specialized combobox that allows users to select a colormap. It includes a preview of the colormap, making it easier for users to choose the appropriate one for their needs.

**Key Features:**
- **Colormap Selection**: Provides a dropdown to select from all available colormaps in `pyqtgraph`.
- **Visual Preview**: Displays a small preview of the colormap next to its name, enhancing usability.

## Colormap Button

The `Colormap Button` is a custom widget that displays the current colormap and, upon clicking, shows a nested menu for selecting a different colormap. It integrates the `ColorMapMenu` from `pyqtgraph`, providing an intuitive and interactive way for users to choose colormaps within the GUI.

**Key Features:**
- **Current Colormap Display**: Shows the name and a gradient icon of the current colormap directly on the button.
- **Nested Menu Selection**: Offers a nested menu with categorized colormaps, making it easy to find and select the desired colormap.
- **Signal Emission**: Emits a signal when the colormap changes, providing the new colormap name as a string.
- **Qt Designer Integration**: Exposes properties and signals to be used within Qt Designer, allowing for customization within the designer interface.
- **Resizable and Styled**: Features adjustable size policies and styles to match the look and feel of standard `QPushButton` widgets, including rounded edges.
`````

````{tab} Examples

Integrating these buttons into a BEC GUI layout is straightforward. The following examples demonstrate how to embed these buttons within a custom GUI layout using `QtWidgets`.

## Example 1 - Adding a Dark Mode Button

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import DarkModeButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the DarkModeButton to the layout
        self.dark_mode_button = DarkModeButton()
        self.layout().addWidget(self.dark_mode_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

## Example 2 - Adding a Color Button

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import ColorButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the ColorButton to the layout
        self.color_button = ColorButton()
        self.layout().addWidget(self.color_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

## Example 3 - Adding a Colormap Selector

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import ColormapSelector

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the ColormapSelector to the layout
        self.colormap_selector = ColormapSelector()
        self.layout().addWidget(self.colormap_selector)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

## Example 4 - Adding a Colormap Button

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import ColormapButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the ColormapButton to the layout
        self.colormap_button = ColormapButton()
        self.layout().addWidget(self.colormap_button)

        # Connect the signal to handle colormap changes
        self.colormap_button.colormap_changed_signal.connect(self.on_colormap_changed)

    def on_colormap_changed(self, colormap_name):
        print(f"Selected colormap: {colormap_name}")

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.DarkModeButton.rst
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ColorButton.rst
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ColormapSelector.rst
```
````