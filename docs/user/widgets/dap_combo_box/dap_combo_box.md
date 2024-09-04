(user.widgets.dap_combo_box)=

# DAP Combobox

````{tab} Overview

The [`DAPComboBox`](/api_reference/_autosummary/bec_widgets.widgets.dap_combo_box.dap_combo_box.DAPComboBox) is a widget that extends the functionality of a standard `QComboBox` to allow the user to select a DAP process from all available DAP models.
One of its signals `new_dap_config` is designed to be connected to the [`add_dap(str, str, str)`](/api_reference/_autosummary/bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.rst#bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.add_dap) slot from the BECWaveformWidget to add a DAP process.

## Key Features:
- **Select DAP model**: Select one of the available DAP models.
- **Signal/Slot Interaction**: Signal and slots to configure the fit_model, x_axis, and y_axis, and to add a DAP model to the BECWaveformWidget.
```{figure} /assets/widget_screenshots/dap_combo_box.png
---
name: lmfit_dialog
---
LMFit Dialog
```
````
````{tab} Summary of Signals
The following signals are emitted by the `DAP ComboBox` widget:
- `new_dap_config(str, str, str)` : Signal to add a DAP model to the BECWaveformWidget
- `x_axis_updated(str)` : Signal to emit the current x axis
- `y_axis_updated(str)` : Signal to emit the current y axis
- `fit_model_updated(str)` : Signal to emit the current fit model
````
````{tab} Summary of Slots
The following slots are available for the `DAP ComboBox` widget:
- `select_x_axis(str)` : Slot to select the current x axis, emits the `x_axis_updated` signal
- `select_y_axis(str)` : Slot to select the current y axis, emits the `x_axis_updated` signal
- `select_fit_model(str)` : Slot to select the current fit model, emits the `fit_model_updated` signal. If x and y axis are set, it will also emit the `new_dap_config` signal.
````
````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.widgets.dap_combo_box.dap_combo_box.DAPCombobox.rst
```
````









