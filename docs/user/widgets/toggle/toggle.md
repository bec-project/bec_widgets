(user.widgets.toggle)=

# Toggle Switch Widget

````{tab} Overview

The [`Toggle Switch`](/api_reference/_autosummary/bec_widgets.cli.client.ToggleSwitch) widget provides a simple, customizable toggle switch that can be used to represent binary states (e.g., on/off, true/false) within a GUI. This widget is designed to be used directly in code or added through `QtDesigner`, making it versatile for various applications where a user-friendly switch is needed.

## Key Features:
- **Binary State Representation**: Represents a simple on/off state with a smooth toggle animation.
- **Customizable Appearance**: Allows customization of track and thumb colors for both active and inactive states.
- **Smooth Animation**: Includes a smooth animation when toggling between states, enhancing user interaction.
- **QtDesigner Integration**: Can be added directly through `QtDesigner` or instantiated in code.

````

````{tab} Examples

The `Toggle Switch` widget can be integrated within a GUI application either through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and customize the `Toggle Switch` widget.

## Example 1 - Creating a Toggle Switch in Code

In this example, we demonstrate how to create a `ToggleSwitch` widget in code and customize its appearance.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.toggle_switch import ToggleSwitch

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the ToggleSwitch to the layout
        self.toggle_switch = ToggleSwitch()
        self.layout().addWidget(self.toggle_switch)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 2 - Customizing the Toggle Switch Appearance

The `ToggleSwitch` widget allows you to customize its appearance by changing the track and thumb colors for both active and inactive states. Below is an example of how to set these properties.

```python
# Set the active and inactive track and thumb colors
self.toggle_switch.active_track_color = QColor(0, 122, 204)  # Active state track color (blue)
self.toggle_switch.inactive_track_color = QColor(200, 200, 200)  # Inactive state track color (grey)
self.toggle_switch.active_thumb_color = QColor(255, 255, 255)  # Active state thumb color (white)
self.toggle_switch.inactive_thumb_color = QColor(255, 255, 255)  # Inactive state thumb color (white)
```

## Example 3 - Integrating the Toggle Switch in QtDesigner

The `ToggleSwitch` can be added as a custom widget in `QtDesigner`. Once integrated, you can configure its properties through the designer's property editor. After adding the widget to a form in QtDesigner, you can manipulate it in your PyQt/PySide application:

```python
# For instance:
self.toggle_switch.setChecked(True)
```

````