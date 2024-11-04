(user.widgets.multi_waveform_widget)=

# Multi Waveform Widget

````{tab} Overview
The Multi Waveform Widget is designed to display multiple 1D detector signals over time. It is ideal for visualizing real-time streaming data from a monitor in the BEC framework, where each new data set is added as a new curve on the plot. This allows users to observe historical changes and trends in the signal.

## Key Features:
- **Real-Time Data Visualization**: Display multiple 1D signals from a monitor in real-time, with each new data set represented as a new curve.
- **Curve Management**: Control the number of curves displayed, set limits on the number of curves, and manage the buffer with options to flush old data.
- **Interactive Controls**: Highlight specific curves, adjust opacity, and interact with the plot using zoom and pan tools.
- **Customizable Appearance**: Customize the colormap, curve opacity, and highlight settings to enhance data visualization.
- **Data Export**: Export the displayed data for further analysis, including exporting to Matplotlib for advanced plotting.
- **Flexible Integration**: Can be integrated into both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.

````

````{tab} Examples - CLI

`BECMultiWaveform` can be embedded in both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. The command-line API is consistent across these contexts.

## Example 1 - Adding Multi Waveform to BECFigure

In this example, we demonstrate how to add a `MultiWaveform` plot to a `BECFigure` widget and connect it to a monitor.

```python
# Add a new dock and BECFigure to the GUI
fig = gui.add_dock().add_widget('BECFigure')

# Add a MultiWaveform plot to the figure and set the monitor
multi_waveform = fig.multi_waveform(monitor='waveform1d')

# Optionally, set plot properties
multi_waveform.set_title("Real-Time Multi Waveform")
multi_waveform.set_x_label("Time (s)")
multi_waveform.set_y_label("Amplitude")
```

## Example 2 - Using BECMultiWaveformWidget in BECDockArea

You can add `BECMultiWaveformWidget` directly to a `BECDockArea`. This widget includes its own toolbar and controls for interacting with the multi waveform plot.

```python
# Add a new BECMultiWaveformWidget to the BECDockArea
multi_waveform_widget = gui.add_dock().add_widget('BECMultiWaveformWidget')

# Set the monitor from the command line
multi_waveform_widget.set_monitor('waveform1d')

# Optionally, adjust settings
multi_waveform_widget.set_opacity(60)
multi_waveform_widget.set_curve_limit(100)
```

## Example 3 - Customizing the Multi Waveform Plot

You can customize various aspects of the plot, such as the colormap, opacity, and curve limit.

```python
# Change the colormap to 'viridis'
multi_waveform.set_colormap('viridis')

# Adjust the opacity of the curves to 70%
multi_waveform.set_opacity(70)

# Limit the number of curves displayed to 50
multi_waveform.set_curve_limit(50)

# Enable buffer flush when the curve limit is reached
multi_waveform.set_curve_limit(50, flush_buffer=True)
```

## Example 4 - Highlighting Curves

You can highlight specific curves to emphasize important data.

```python
# Disable automatic highlighting of the last curve
multi_waveform.set_highlight_last_curve(False)

# Highlight the third curve (indexing starts from 0)
multi_waveform.set_curve_highlight(2)

# Re-enable automatic highlighting of the last curve
multi_waveform.set_highlight_last_curve(True)
```

## Example 5 - Exporting Data

You can export the data from the multi waveform plot for further analysis.

```python
# Get all the data as a dictionary
data = multi_waveform.get_all_data(output='dict')

# Or get the data as a pandas DataFrame (if pandas is installed)
data_df = multi_waveform.get_all_data(output='pandas')

# Export the plot to Matplotlib for further customization
multi_waveform.export_to_matplotlib()
```
````

````{tab} API

```{eval-rst}
.. autoclass:: bec_widgets.widgets.figure.plots.multi_waveform.multi_waveform.BECMultiWaveform
   :members:
   :inherited-members:
```
```