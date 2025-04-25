(user.widgets.signal_input)=

# Signal Input Widgets

````{tab} Overview
The `Signal Input Widgets` consist of two primary widgets: `SignalLineEdit` and `SignalComboBox`. Both widgets are designed to facilitate the selection of the available signals for a selected device within the current BEC session. These widgets allow users to filter, search, and select signals dynamically. The widgets can either be integrated into a GUI through direct code instantiation or by using `QtDesigner`. 

## SignalLineEdit
The `SignalLineEdit` widget provides a line edit interface with autocomplete functionality for the available of signals associated with the selected device. This widget is ideal for users who prefer to type in the signal name directly. If no device is selected, the autocomplete will be empty. In addition, the widget will display a red border around the line edit if the input signal is invalid.

## SignalComboBox
The `SignalComboBox` widget offers a dropdown interface for choosing a signal from the available signals of a device. It will further categorise the signals according to its `kind`: `hinted`, `normal` and `config`. For more information about `kind`, please check the [ophyd documentation](https://nsls-ii.github.io/ophyd/signals.html#kind). This widget is ideal for users who prefer to select signals from a list.

## Key Features:
- **Signal Filtering**: Both widgets allow users to filter devices by signal types(`kind`). No selected filter will show all signals.
- **Real-Time Autocomplete (LineEdit)**: The `SignalLineEdit` widget supports real-time autocomplete, helping users find devices faster.
- **Real-Time Input Validation (LineEdit)**: User input is validated in real-time with a red border around the `SignalLineEdit` indicating an invalid input. 
- **Dropdown Selection (SignalComboBox)**: The `SignalComboBox` widget displays the sorted signals of the device 
- **QtDesigner Integration**: Both widgets can be added as custom widgets in `QtDesigner` or instantiated directly in code.

## Screenshot

```{figure} /assets/widget_screenshots/signal_inputs.png
```

````

````{tab} Examples

Both `SignalLineEdit` and `SignalComboBox` can be integrated within a GUI application through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and use these widgets.


## Example 1 - Creating a SignalLineEdit in Code

In this example, we demonstrate how to create a `SignalLineEdit` widget in code and customize its behavior. 
We will select `samx`, which is a motor in the BEC simulation device config, and filter the signals to `normal` and `hinted`.
Note, not specifying signal_filter will include all signals.

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.control.device_input.signal_line_edit.signal_line_edit import SignalLineEdit
from ophyd import Kind

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget
        # Create and add the SignalLineEdit to the layout
        self.signal_line_edit = SignalLineEdit(device="samx", signal_filter=[Kind.normal, Kind.hinted])
        self.layout().addWidget(self.signal_line_edit)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()
app.exec_()
```

## Example 2 - Creating a SignalComboBox in Code

A 

```python
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from ophyd import Kind

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget
        # Create and add the SignalComboBox to the layout
        self.signal_combobox = SignalComboBox(device="samx",  signal_filter=[Kind.normal, Kind.hinted])
        self.layout().addWidget(self.signal_combobox)

# Example of how this custom GUI might be used:
app = QApplication([])
my_gui = MyGui()
my_gui.show()   
app.exec_()
```

## Example 3 - Setting Default Device

Both `SignalLineEdit` and `SignalComboBox` allow you to set a default device that will be selected when the widget is initialized.

```python
# Set default device for DeviceLineEdit
self.signal_line_edit.set_device("motor1")

# Set default device for DeviceComboBox
self.signal_combobox.set_device("motor2")
```
````
````{tab} BEC Designer
Both widgets are also available as plugins for the BEC Designer. We have included Qt properties for both widgets, allowing customization of filtering and default device settings directly from the designer. In addition to the common signals and slots for `SignalLineEdit` and `SignalComboBox`, the following slots are available:
- `set_device(str)` to set the default device
- `set_signal(str)` to set the default signal
- `update_signals_from_filters()` to refresh the devices list based on the current filters

The following Qt properties are also included:
```{figure} ./signal_input_qproperties.png
```

````

````{tab} API - ComboBox
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.control.device_input.signal_combobox.SignalComboBox.rst
```
````

````{tab} API - LineEdit
```{eval-rst}
.. include:: /api_reference/_autosummary/bec_widgets.control.device_input.signal_line_edit.SignalLineEdit.rst
```
````
