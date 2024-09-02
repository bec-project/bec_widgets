(user.widgets.dap_combo_box)=

# DAP Combobox

````{tab} Overview

The [`DAP ComboBox`](/api_reference/_autosummary/bec_widgets.widgets.dap_combo_box.dap_combo_box.DAPComboBox) is a widget that extends the functionality of a standard `QComboBox` to allow the user to select a DAP process from a list of DAP processes. 
The widget provides a set of signals and slots to allow the user to interact with the selection of a DAP process, including a signal to send a signal that can be hooked up to the `add_dap(str, str, str)` slot of the [`add_dap`](/api_reference/_autosummary/bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.rst#bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.add_dap) from the BECWaveformWidget to add a DAP process.

## Key Features:
- **Select DAP model**: Selection of all active DAP models from BEC.
- **Signal/Slot Interaction**: Signals to add DAP process to BECWaveformWidget.
```{figure} /assets/widget_screenshots/dap_combo_box.png
---
name: lmfit_dialog
---
LMFit Dialog
```
````
````{tab} Summary of Signals
The following signals are emitted by the `DAP ComboBox` widget:
- `add_dap_model(str, str, str)` : Signal to add a DAP model to the BECWaveformWidget
- `update_x_axis(str)` : Signal to emit the current x axis
- `update_y_axis(str)` : Signal to emit the current y axis
- `update_fit_model(str)` : Signal to emit the current fit model
````
````{tab} Summary of Slots
The following slots are available for the `DAP ComboBox` widget:
- `select_x_axis(str)` : Slot to select the current x axis, emits the `update_x_axis` signal
- `select_y_axis(str)` : Slot to select the current y axis, emits the `update_y_axis` signal
- `select_fit(str)` : Slot to select the current fit model, emits the `update_fit_model` signal. If x and y axis are set, it will also emit the `add_dap_model` signal.
````
````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.widgets.dap_combo_box.dap_combo_box.DAPCombobox.rst
```
````









