(user.widgets.heatmap_widget)=

# Heatmap widget

````{tab} Overview

The Heatmap widget is a specialized plotting tool designed for visualizing 2D grid data with color mapping for the z-axis. It excels at displaying data from grid scans or arbitrary step scans, automatically interpolating scattered data points into a coherent 2D image. Directly integrated with the `BEC` framework, it can display live data streams from scanning experiments within the current `BEC` session.

## Key Features:
- **Flexible Integration**: The widget can be integrated into [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`.
- **Live Grid Scan Visualization**: Real-time plotting of grid scan data with automatic positioning and color mapping based on scan parameters.
- **Dual Scan Support**: Handles both structured grid scans (with pre-allocated grids) and unstructured step scans (with interpolation).
- **Intelligent Data Interpolation**: For arbitrary step scans, the widget automatically interpolates scattered (x, y, z) data points into a smooth 2D heatmap using various interpolation methods.
- **Oversampling**: Supports oversampling to enhance the appearance of the heatmap, allowing for smoother transitions and better visual representation of data. Especially useful the for nearest-neighbor interpolation.
- **Customizable Color Maps**: Wide variety of color maps available for data visualization, with support for both simple and full color bars.
- **Real-time Image Processing**: Apply real-time processing techniques such as FFT and logarithmic scaling to enhance data visualization.
- **Interactive Controls**: Comprehensive toolbar with settings for heatmap configuration, crosshair tools, mouse interaction, and data export capabilities.


```{figure} ./heatmap_grid_scan.gif
:width: 60%

Real-time heatmap visualization of a 2D grid scan showing motor positions and detector intensity
```

```{figure} ./heatmap_fermat_scan.gif
:width: 80%

Real-time heatmap visualization of an (not path-optimized) scan following Fermat's spiral pattern. On the left, the heatmap widget is shown with the oversampling option set to 10 and the interpolation method set to nearest neighbor. On the right, the scatter waveform widget is shown with the same data.
```


````

````{tab} Examples - CLI

`HeatmapWidget` can be embedded in [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`. The command-line API is the same for all cases.

## Example 1 - Visualizing Grid Scan Data

In this example, we demonstrate how to add a `HeatmapWidget` to visualize live data from a 2D grid scan with motor positions and detector readout.

```python
# Add a new dock with HeatmapWidget
dock_area = gui.new()
heatmap_widget = dock_area.new().new(gui.available_widgets.Heatmap)

# Plot a heatmap with x and y motor positions and z detector signal
heatmap_widget.plot(
    x_name='samx',  # X-axis motor
    y_name='samy',  # Y-axis motor  
    z_name='bpm4i', # Z-axis detector signal
    color_map='plasma'
)
heatmap_widget.title = "Grid Scan - Sample Position vs BPM Intensity"
```

## Example 2 - Step Scan with Custom Entries

This example shows how to visualize data from an arbitrary step scan by specifying custom data entries for each axis.

```python
# Add a new dock with HeatmapWidget
dock_area = gui.new()
heatmap_widget = dock_area.new().new(gui.available_widgets.Heatmap)

# Plot heatmap with specific data entries
heatmap_widget.plot(
    x_name='motor1',
    y_name='motor2', 
    z_name='detector1',
    x_entry='RBV',      # Use readback value for x
    y_entry='RBV',      # Use readback value for y
    z_entry='value',    # Use main value for z
    color_map='viridis',
    reload=True         # Force reload of data
)
```

## Example 3 - Real-time Processing and Customization

The `Heatmap` widget provides real-time processing capabilities and extensive customization options for enhanced data visualization.

```python
# Configure heatmap appearance and processing
heatmap_widget.color_map = 'plasma'
heatmap_widget.lock_aspect_ratio = True

# Apply real-time processing
heatmap_widget.fft = True           # Apply FFT to the data
heatmap_widget.log = True           # Use logarithmic scaling

# Configure color bar and range
heatmap_widget.enable_full_colorbar = True
heatmap_widget.v_min = 0
heatmap_widget.v_max = 1000

```

````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.widgets.plots.heatmap.heatmap.Heatmap.rst
```
````
