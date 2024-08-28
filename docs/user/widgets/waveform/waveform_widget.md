(user.widgets.waveform_widget)=

# Waveform Widget

````{tab} Overview

The Waveform Widget is used to display 1D detector signals. The widget is directly integrated with the `BEC` framework and can display real-time data from detectors loaded in the current `BEC` session as well as custom data from users.

## Key Features:
- **Flexible Integration**: The widget can be integrated into both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.
- **Data Visualization**: Real-time plotting of positioner versus detector values from the BEC session, as well as static plotting of custom data.
- **Real-time Data Processing**: Add real-time Data Processing Pipeline (DAP) to the real-time acquisition.
- **Data Export**: Export data to CSV, H5, and other formats.
- **Customizable Visual Elements**: Customize visual elements such as line color and style.
- **Interactive Controls**: Interactive controls for zooming and panning through the data.

![Waveform 1D](./w1D.gif)
````

````{tab} Examples - CLI

`WaveformWidget` can be embedded in both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. However, the command-line API is the same for all cases.

## Example 1 - Adding Waveform Widget to BECFigure

In this example, we will demonstrate how to add two different `WaveformWidgets` into a single [`BECFigure`](user.widgets.bec_figure) widget.

```python
# Add new dock with BECFigure widget
fig = gui.add_dock().add_widget('BECFigure')

# Add two WaveformWidgets to the BECFigure
plt1 = fig.plot(x_name='samx', y_name='bpm4i')
plt2 = fig.plot(x_name='samx', y_name='bpm3i')
```

## Example 2 - Adding Waveform Widget as a dock with BECDockArea

Adding `WaveformWidget` into a [`BECDockArea`](user.widgets.bec_dock_area) is similar to adding any other widget. The widget has the same API as the one in BECFigure; however, as an independent widget outside BECFigure, it has its own toolbar, allowing users to configure the widget without needing CLI commands.

```python
# Add new WaveformWidgets to the BECDockArea
plt1 = gui.add_dock().add_widget('BECWaveformWidget')
plt2 = gui.add_dock().add_widget('BECWaveformWidget')

# Add signals to the WaveformWidget
plt1.plot(x_name='samx', y_name='bpm4i')
plt2.plot(x_name='samx', y_name='bpm3i')
```

## Example 3 - Adding Waveform Widget with curves
```python
# adds a new dock, a new BECFigure and a BECWaveForm to the dock
plt = gui.add_dock().add_widget('BECFigure').plot(x_name='samx', y_name='bpm4i')

# add a second curve to the same plot 
plt.plot(x_name='samx', y_name='bpm3i')

# set axis labels
plt.set_title("Gauss plots vs. samx")
plt.set_x_label("Motor X")
plt.set_y_label("Gauss Signal (A.U.")
```

```{note}
The return value of the simulated devices *bpm4i* and *bpm3i* may not be Gaussian signals, but they can be easily configured with the code snippet below. For more details, please check the documentation for the [simulation](https://bec.readthedocs.io/en/latest/developer/devices/bec_sim.html).
```

```python
# bpm4i uses GaussianModel and samx as a reference; default settings
dev.bpm4i.sim.select_sim_model("GaussianModel")

# bpm3i uses StepModel and samx as a reference; default settings
dev.bpm3i.sim.select_sim_model("StepModel")
```
## Example 4 - Adding Data Processing Pipeline Curve with LMFit Models

In addition to the scan curve, you can also add a second curve that fits the signal using a specified model from [LMFit](https://lmfit.github.io/lmfit-py/builtin_models.html). The following code snippet demonstrates how to create a 1D waveform curve with an attached DAP process, or how to add a DAP process to an existing curve using the BEC CLI. Please note that for this example, both devices were set as Gaussian signals.

```python
# Add a new dock, a new BECFigure, and a BECWaveForm to the dock with a GaussianModel DAP
plt = gui.add_dock().add_widget('BECFigure').plot(x_name='samx', y_name='bpm4i', dap="GaussianModel")

# Add a second curve to the same plot without DAP
plt.plot(x_name='samx', y_name='bpm3a')

# Add DAP to the second curve
plt.add_dap(x_name='samx', y_name='bpm3a', dap="GaussianModel")

```

To get the parameters of the fit, you need to retrieve the curve objects and call the `dap_params` property.

```python
# Get the curve object by name from the legend
dap_bpm4i = plt.get_curve("bpm4i-bpm4i-GaussianModel")
dap_bpm3a = plt.get_curve("bpm3a-bpm3a-GaussianModel")

# Get the parameters of the fit
print(dap_bpm4i.dap_params)
# Output
{'amplitude': 197.399639720862,
 'center': 5.013486095404885,
 'sigma': 0.9820868875739888}

print(dap_bpm3a.dap_params)
# Output
{'amplitude': 698.3072786185278,
 'center': 0.9702840866173836,
 'sigma': 1.97139754785518}
```

![Waveform 1D_DAP](./bec_figure_dap.gif)

## Example 5 - 2D Waveform Scatter Plot

The 2D scatter plot widget is designed for more complex data visualization. It employs a false color map to represent a third dimension (z-axis), making it an ideal tool for visualizing multidimensional data sets.

```python
# adds a new dock, a new BECFigure and a BECWaveForm to the dock
plt = gui.add_dock().add_widget('BECFigure').add_plot(x_name='samx', y_name='samy', z_name='bpm4i')
```

![Scatter 2D](./scatter_2D.gif)

````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECWaveform.rst
```
````