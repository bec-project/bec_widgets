(user.widgets.position_indicator)=

# Position Indicator Widget

````{tab} Overview

The [`PositionIndicator`](/api_reference/_autosummary/bec_widgets.cli.client.PositionIndicator) widget is a simple yet effective tool for visually indicating the position of a motor within its set limits. This widget is particularly useful in applications where it is important to provide a visual cue of the motor's current position relative to its minimum and maximum values. The `PositionIndicator` can be easily integrated into your GUI application either through direct code instantiation or by using `QtDesigner`.

## Key Features:
- **Position Visualization**: Displays the current position of a motor on a linear scale, showing its location relative to the defined limits.
- **Customizable Range**: The widget allows you to set the minimum and maximum range, adapting to different motor configurations.
- **Real-Time Updates**: Responds to real-time updates, allowing the position indicator to move dynamically as the motor's position changes.
- **QtDesigner Integration**: Can be added directly in code or through `QtDesigner`, making it adaptable to various use cases.

````

````{tab} Examples

The `PositionIndicator` widget can be embedded within a GUI application through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and use the `PositionIndicator` widget.

## Example 1 - Creating a Position Indicator in Code

In this example, we demonstrate how to create a `PositionIndicator` widget in code and connect it to a slider to simulate position updates.

```python
from qtpy.QtWidgets import QApplication, QSlider, QVBoxLayout, QWidget
from bec_widgets.widgets.position_indicator import PositionIndicator

app = QApplication([])

# Create the PositionIndicator widget
position_indicator = PositionIndicator()

# Create a slider to simulate position changes
slider = QSlider(Qt.Horizontal)
slider.valueChanged.connect(lambda value: position_indicator.on_position_update(value / 100))

# Create a layout and add the widgets
layout = QVBoxLayout()
layout.addWidget(position_indicator)
layout.addWidget(slider)

# Set up the main widget
widget = QWidget()
widget.setLayout(layout)
widget.show()

app.exec_()
```

## Example 2 - Setting the Range for the Position Indicator

You can set the minimum and maximum range for the position indicator to reflect the actual limits of the motor.

```python
# Set the range for the position indicator
position_indicator.set_range(min_value=0, max_value=200)
```

## Example 3 - Integrating the Position Indicator in QtDesigner

The `PositionIndicator` can be added to your GUI layout using `QtDesigner`. Once added, you can connect it to the motor's position updates using the `on_position_update` slot.

```python
# Example: Updating the position in a QtDesigner-based application
self.position_indicator.on_position_update(new_position_value)
```

````