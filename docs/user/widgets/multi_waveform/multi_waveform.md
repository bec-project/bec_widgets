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
- **Flexible Integration**: Can be integrated into [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.

````

````{tab} Examples - CLI

`BECMultiWaveform` can be embedded in [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. The command-line API is consistent across these contexts.

## Example 1 - Using BECMultiWaveformWidget in BECDockArea

You can add `BECMultiWaveformWidget` directly to a `BECDockArea`. This widget includes its own toolbar and controls for interacting with the multi waveform plot.

```python
# Add a new MultiWaveform  to the BECDockArea
dock_area = gui.new()
multi_waveform_widget = dock_area.new().new(gui.available_widgets.MultiWaveform)

# Set the monitor from the command line
multi_waveform_widget.plot('waveform')

# Optionally, adjust settings
multi_waveform_widget.opacity = 60
```

## Example 2 - Customizing the Multi Waveform Plot

You can customize various aspects of the plot, such as the colormap, opacity, and curve limit.

```python
# Change the colormap to 'viridis'
multi_waveform_widget.color_palette = 'viridis'

# Adjust the opacity of the curves to 70%
multi_waveform_widget.opacity = 60

# Limit the number of curves displayed to 50
multi_waveform_widget.max_trace = 10

# Enable buffer flush when the curve limit is reached
multi_waveform_widget.flush_buffer = True
```

## Example 3 - Highlighting Curves

You can highlight specific curves to emphasize important data.

```python
# Disable automatic highlighting of the last curve
multi_waveform.highlight_last_curve = False

# Highlight the third curve (indexing starts from 0)
multi_waveform.highlighted_index = 2

# Re-enable automatic highlighting of the last curve
multi_waveform.highlight_last_curve = True
```

<!-- ## Example 4 - Exporting Data

You can export the data from the multi waveform plot for further analysis.

```python
# Get all the data as a dictionary
data = multi_waveform.get_all_data(output='dict')

# Or get the data as a pandas DataFrame (if pandas is installed)
data_df = multi_waveform.get_all_data(output='pandas')

# Export the plot to Matplotlib for further customization
multi_waveform.export_to_matplotlib()
``` -->
````

````{tab} API


````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.MultiWaveform.rst
```
````