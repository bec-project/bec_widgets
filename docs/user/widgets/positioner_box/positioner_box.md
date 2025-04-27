(user.widgets.positioner_box)=

# Positioner Box Widget

````{tab} Overview

The [`PositionerBox`](/api_reference/_autosummary/bec_widgets.cli.client.PositionerBox) widget provides a graphical user interface to control a positioner device within the BEC environment. This widget allows users to interact with a positioner by setting setpoints, tweaking the motor position, and stopping motion. The device selection can be done via a small button under the device label, through `BEC Designer`, or by using the command line interface (CLI). This flexibility makes the `PositionerBox` an essential tool for tasks involving precise position control.

## Key Features:
- **Device Selection**: Easily select a positioner device by clicking the button under the device label or by configuring the widget in `BEC Designer`.
- **Setpoint Control**: Directly set the positioner’s target setpoint and issue movement commands.
- **Tweak Controls**: Adjust the motor position incrementally using the tweak left/right buttons.
- **Real-Time Feedback**: Monitor the device’s current position and status, with live updates on whether the device is moving or idle.
- **Flexible Integration**: Can be integrated into a GUI through `BECDockArea` or used as a standalone component in `BEC Designer`.
````

````{tab} Examples

The `PositionerBox` widget can be integrated within a GUI application either through direct code instantiation or by using `BEC Designer`. Below are examples demonstrating how to create and use the `PositionerBox` widget.

## Example 1 - Creating a PositionerBox in Code

In this example, we demonstrate how to create a `PositionerBox` widget in code and configure it for a specific device.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.positioner_box import PositionerBox

class MyGui(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the PositionerBox to the layout
        self.positioner_box = PositionerBox(parent=self, device="motor1")
        self.layout().addWidget(self.positioner_box)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 2 - Selecting a Device via GUI

Users can select the positioner device by clicking the button under the device label, which opens a dialog for device selection.

## Example 3 - Customizing PositionerBox in BEC Designer

The `PositionerBox` widget can be added to a GUI through `BEC Designer`. Once integrated, you can configure the default device and customize the widget’s appearance and behavior directly within the designer.

```python
# After adding the widget to a form in BEC Designer, you can configure the device:
self.positioner_box.set_positioner("motor2")
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.PositionerBox.rst
```
````