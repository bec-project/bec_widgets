(user.widgets.device_input)=

# Device Input Widgets

````{tab} Overview

The `Device Input Widgets` consist of two primary widgets: `DeviceLineEdit` and `DeviceComboBox`. Both widgets are designed to facilitate the selection of devices within the BEC environment, allowing users to filter, search, and select devices dynamically. These widgets are highly customizable and can be integrated into a GUI either through direct code instantiation or by using `QtDesigner`.

## DeviceLineEdit
The `DeviceLineEdit` widget provides a line edit interface with autocomplete functionality for device names, making it easier for users to quickly search and select devices.

## DeviceComboBox
The `DeviceComboBox` widget offers a dropdown interface for device selection, providing a more visual way to browse through available devices.

## Key Features:
- **Device Filtering**: Both widgets allow users to filter devices by their class names, ensuring that only relevant devices are shown.
- **Default Device Setting**: Users can set a default device to be pre-selected when the widget is initialized.
- **Real-Time Autocomplete (LineEdit)**: The `DeviceLineEdit` widget supports real-time autocomplete, helping users find devices faster.
- **Dropdown Selection (ComboBox)**: The `DeviceComboBox` widget displays devices in a dropdown list, making selection straightforward.
- **QtDesigner Integration**: Both widgets can be added as custom widgets in `QtDesigner` or instantiated directly in code.

````

````{tab} Examples

Both `DeviceLineEdit` and `DeviceComboBox` can be integrated within a GUI application through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and use these widgets.


## Example 1 - Creating a DeviceLineEdit in Code

In this example, we demonstrate how to create a `DeviceLineEdit` widget in code and customize its behavior.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.device_line_edit import DeviceLineEdit

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the DeviceLineEdit to the layout
        self.device_line_edit = DeviceLineEdit(device_filter="Motor")
        self.layout().addWidget(self.device_line_edit)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 2 - Creating a DeviceComboBox in Code

Similarly, here is an example of creating a `DeviceComboBox` widget in code and customizing its behavior.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.device_combo_box import DeviceComboBox

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the DeviceComboBox to the layout
        self.device_combo_box = DeviceComboBox(device_filter="Motor")
        self.layout().addWidget(self.device_combo_box)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 3 - Setting Default Device

Both `DeviceLineEdit` and `DeviceComboBox` allow you to set a default device that will be selected when the widget is initialized.

```python
# Set default device for DeviceLineEdit
self.device_line_edit.set_default_device("motor1")

# Set default device for DeviceComboBox
self.device_combo_box.set_default_device("motor2")
```
````

````{tab} API - ComboBox
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.DeviceComboBox.rst
```
````

````{tab} API - LineEdit
```{eval-rst}
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.DeviceLineEdit.rst
```
````
