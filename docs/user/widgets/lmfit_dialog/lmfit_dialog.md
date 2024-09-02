(user.widgets.lmfit_dialog)=

# LMFit Dialog

````{tab} Overview

The [`LMFit Dialog`](/api_reference/_autosummary/bec_widgets.widgets.lmfit_dialog.lmfit_dialog.LMFitDialog) is a widget that is developed to be used together with the [`BECWaveformWidget`](/api_reference/_autosummary/bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget). The `BECWaveformWidget` allows user to submit a fit request to BEC's [DAP server](https://bec.readthedocs.io/en/latest/developer/getting_started/architecture.html) choosing from a selection of [LMFit models](https://lmfit.github.io/lmfit-py/builtin_models.html#) to fit monitored data sources. The `LMFit Dialog` provides an interface to monitor these fits, including statistics and fit parameters in real time. 
Within the `BECWaveformWidget`, the dialog is accessible via the toolbar and will be automatically linked to the current waveform widget. For a more customised use, we can embed the `LMFit Dialog` in a larger GUI using the *BEC Designer*. In this case, one has to connect the [`update_summary_tree`](/api_reference/_autosummary/bec_widgets.widgets.lmfit_dialog.lmfit_dialog.LMFitDialog.rst#bec_widgets.widgets.lmfit_dialog.lmfit_dialog.LMFitDialog.update_summary_tree) slot of the LMFit Dialog to the [`dap_summary_update`](/api_reference/_autosummary/bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.rst#bec_widgets.widgets.waveform.waveform_widget.BECWaveformWidget.dap_summary_update) signal of the BECWaveformWidget to ensure its functionality. 


## Key Features:
- **Fit Summary**: Display updates on LMFit DAP processes and fit statistics.
- **Fit Parameter**: Display current fit parameter.
- **BECWaveformWidget Integration**: Directly connect to BECWaveformWidget to display fit statistics and parameters.
```{figure} /assets/widget_screenshots/lmfit_dialog.png
---
name: lmfit_dialog
---
LMFit Dialog
```
````
````{tab} Connect in BEC Designer
The `LMFit Dialog` widget can be connected to a `BECWaveformWidget` to display fit statistics and parameters from the LMFit DAP process hooked up to the waveform widget. You can use the signal/slot editor from the BEC Designer to connect the `dap_summary_update` signal of the BECWaveformWidget to the `update_summary_tree` slot of the LMFit Dialog. 

```{figure} /assets/widget_screenshots/lmfit_dialog_connect.png
````
````{tab} Connect in Python
It is also possible to directly connect the `dap_summary_update` signal of the BECWaveformWidget to the `update_summary_tree` slot of the LMFit Dialog in Python.

```python
waveform = BECWaveformWidget(...)
lmfit_dialog = LMFitDialog(...)
waveform.dap_summary_update.connect(lmfit_dialog.update_summary_tree)

```
````
````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.LMFitDialog.rst
```
````









