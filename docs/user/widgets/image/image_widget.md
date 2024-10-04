(user.widgets.image_widget)=

# Image Widget

````{tab} Overview

The Image Widget is a versatile tool designed for visualizing both 1D and 2D data, such as camera images or waveform data, in real-time. Directly integrated with the `BEC` framework, it can display live data streams from connected detectors or other data sources within the current `BEC` session. The widget provides advanced customization options for color maps and scale bars, allowing users to tailor the visualization to their specific needs.

## Key Features:
- **Flexible Integration**: The widget can be integrated into both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.
- **Live Data Visualization**: Real-time plotting of both 1D and 2D data from detectors or other data sources, provided that a data stream is available in the BEC session.
- **Support for Multiple Monitor Types**: The Image Widget supports different monitor types (`'1d'` and `'2d'`), allowing visualization of various data dimensions.
- **Customizable Color Maps and Scale Bars**: Users can customize the appearance of images with various color maps and adjust scale bars to better interpret the visualized data.
- **Real-time Image Processing**: Apply real-time image processing techniques directly within the widget to enhance the quality or analyze specific aspects of the data, such as rotation, logarithmic scaling, and Fast Fourier Transform (FFT).
- **Data Export**: Export visualized data to various formats such as PNG, TIFF, or H5 for further analysis or reporting.
- **Interactive Controls**: Offers interactive controls for zooming, panning, and adjusting the visual properties of the images on the fly.

## Monitor Types

The Image Widget can handle different types of data, specified by the `monitor_type` parameter:

- **1D Monitor (`monitor_type='1d'`)**: Used for visualizing 1D waveform data. The widget collects incoming 1D data arrays and constructs a 2D image by stacking them, adjusting for varying lengths if necessary.
- **2D Monitor (`monitor_type='2d'`)**: Used for visualizing 2D image data directly from detectors like cameras.

By specifying the appropriate `monitor_type`, you can configure the Image Widget to handle data from different detectors and sources.

![Image 2D](./image_plot.gif)
````

````{tab} Examples - CLI

`ImageWidget` can be embedded in both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. The command-line API is the same for all cases.

## Example 1 - Visualizing 2D Image Data from a Detector

In this example, we demonstrate how to add an `ImageWidget` to a [`BECFigure`](user.widgets.bec_figure) to visualize live 2D image data from a connected camera detector.

```python
# Add a new dock with BECFigure widget
fig = gui.add_dock().add_widget('BECFigure')

# Add an ImageWidget to the BECFigure for a 2D detector
img_widget = fig.image(monitor='eiger', monitor_type='2d')
img_widget.set_title("Camera Image - Eiger Detector")
```

## Example 2 - Visualizing 1D Waveform Data from a Detector

This example demonstrates how to set up the Image Widget to visualize 1D waveform data from a detector, such as a line detector or a spectrometer. The widget will stack incoming 1D data arrays to construct a 2D image.

```python
# Add an ImageWidget to the BECFigure for a 1D detector
img_widget = fig.image(monitor='line_detector', monitor_type='1d')
img_widget.set_title("Line Detector Data")

# Optional: Set the color map and value range
img_widget.set_colormap("plasma")
img_widget.set_vrange(vmin=0, vmax=100)
```

## Example 3 - Adding Image Widget as a Dock in BECDockArea

Adding an `ImageWidget` into a [`BECDockArea`](user.widgets.bec_dock_area) is similar to adding any other widget. The widget has the same API as the one in [`BECFigure`](user.widgets.bec_figure); however, as an independent widget outside of `BECFigure`, it has its own toolbar, allowing users to configure the widget without needing CLI commands.

```python
# Add an ImageWidget to the BECDockArea for a 2D detector
img_widget = gui.add_dock().add_widget('BECImageWidget')

# Visualize live data from a camera with a specified value range
img_widget.image(monitor='eiger', monitor_type='2d')
img_widget.set_vrange(vmin=0, vmax=100)
```

## Example 4 - Customizing Image Display

This example demonstrates how to customize the color map and scale bar for an image being visualized in an `ImageWidget`.

```python
# Set the color map and adjust the value range
img_widget.set_colormap("viridis")
img_widget.set_vrange(vmin=10, vmax=200)
```

## Example 5 - Real-time Image Processing

The `ImageWidget` provides real-time image processing capabilities, such as rotating, scaling, applying logarithmic scaling, and performing FFT on the displayed images. The following example demonstrates how to apply these transformations to an image.

```python
# Rotate the image by 90 degrees
img_widget.set_rotation(deg_90=1)

# Transpose the image
img_widget.set_transpose(enable=True)

# Apply FFT to the image
img_widget.set_fft(enable=True)

# Set logarithmic scaling for the image display
img_widget.set_log(enable=True)
```

## Example 6 - Setting Up for Different Detectors

The Image Widget can be configured for different detectors by specifying the correct monitor name and monitor type. Here's how to set it up for various detectors:

### For a 2D Camera Detector (e.g., 'eiger')

```python
# For a 2D camera detector
img_widget = fig.image(monitor='eiger', monitor_type='2d')
img_widget.set_title("Eiger Camera Image")
```

### For a 1D Line Detector (e.g., 'waveform')

```python
# For a 1D line detector
img_widget = fig.image(monitor='waveform', monitor_type='1d')
img_widget.set_title("Line Detector Data")
```

```{note}
Since the Image Widget does not have prior information about the shape of incoming data, it is essential to specify the correct `monitor_type` when setting up the widget. This ensures that the data is processed and displayed correctly.
```


````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECImageWidget.rst
```
````
