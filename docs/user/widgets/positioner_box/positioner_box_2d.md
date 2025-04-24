(user.widgets.positioner_box_2d)=

# Positioner Box 2D Widget

````{tab} Overview

The [`PositionerBox2D`](/api_reference/_autosummary/bec_widgets.cli.client.PositionerBox2D) widget is very similar to the [`PositionerBox`](/user/widgets/positioner_box/positioner_box) but allows controlling two positioners at the same time, in a horizontal and vertical orientation respectively. It is intended primarily for controlling axes which have a perpendicular relationship like that. In other cases, it may be better to use a `PositionerGroup` instead. 

The `PositionerBox2D` has the same features as the standard `PositionerBox`, but additionally, step buttons which move the positioner by the selected step size, and tweak buttons which move by a tenth of the selected step size.

````

````{tab} Examples

The `PositionerBox2D` widget can be integrated within a GUI application either through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and use the `PositionerBox2D` widget.

## Example 1 - Creating a PositionerBox in Code

In this example, we demonstrate how to create a `PositionerBox2D` widget in code and configure it for a specific device.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.positioner_box import PositionerBox2D

class MyGui(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the PositionerBox to the layout
        self.positioner_box_2d = PositionerBox(parent=self, device_hor="horizontal_motor", device_ver="vertical_motor")
        self.layout().addWidget(self.positioner_box_2d)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 2 - Selecting a Device via GUI

Users can select the positioner device by clicking the button under the device label, which opens a dialog for device selection.

## Example 3 - Customizing PositionerBox in QtDesigner

The `PositionerBox2D` widget can be added to a GUI through `QtDesigner`. Once integrated, you can configure the default device and customize the widget’s appearance and behavior directly within the designer.

```python
# After adding the widget to a form in QtDesigner, you can configure the device:
self.positioner_box.set_positioner_hor("samx")
self.positioner_box.set_positioner_verr("samy")
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.PositionerBox2D.rst
```
````