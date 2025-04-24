(user.widgets.scatter_waveform_widget)=

# Scatter Waveform Widget

````{tab} Overview
The 2D scatter plot widget is designed for more complex data visualization. It employs a false color map to represent a third dimension (z-axis), making it an ideal tool for visualizing multidimensional data sets.

## Key Features:
- **Real-Time Data Visualization**: Display 2D scatter plots with a third dimension represented by color.
- **Flexible Integration**: Can be integrated into [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.

````

````{tab} Examples - CLI

`ScatterWaveform` widget can be embedded in [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. The command-line API is consistent across these contexts.

## Example

```python
# Add a new dock_area, a new dock and a BECWaveForm to the dock
plt = gui.new().new().new(gui.available_widgets.ScatterWaveform)
plt.plot(x_name='samx', y_name='samy', z_name='bpm4i')

```

![Scatter 2D](./scatter_2D.gif)


```{note}
The ScatterWaveform widget only plots the data points if both x and y axis motors are moving. Or more generally, if all signals are of readout type *monitored*.
```
````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ScatterWaveform.rst
```
````
