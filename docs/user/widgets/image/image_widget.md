(user.widgets.image_widget)=

# Image widget

````{tab} Overview

The Image widget is a versatile tool designed for visualizing both 1D and 2D data, such as camera images or waveform data, in real-time. Directly integrated with the `BEC` framework, it can display live data streams from connected detectors or other data sources within the current `BEC` session. The widget provides advanced customization options for color maps and scale bars, allowing users to tailor the visualization to their specific needs.

## Key Features:
- **Flexible Integration**: The widget can be integrated into [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`.
- **Live Data Visualization**: Real-time plotting of both 1D and 2D data from detectors or other data sources, provided that a data stream is available in the BEC session.
- **Support for Multiple Monitor Types**: The Image widget supports different monitor types (`'1d'` and `'2d'`), allowing visualization of various data dimensions. It can automatically determine the best way to visualise the data based on the shape of the data source.
- **Customizable Color Maps and Scale Bars**: Users can customize the appearance of images with various color maps and adjust scale bars to better interpret the visualized data.
- **Real-time Image Processing**: Apply real-time image processing techniques directly within the widget to enhance the quality or analyze specific aspects of the data, such as rotation, logarithmic scaling, and Fast Fourier Transform (FFT).
- **Data Export**: Export visualized data to various formats such as PNG, TIFF, or H5 for further analysis or reporting.
- **Interactive Controls**: Offers interactive controls for zooming, panning, and adjusting the visual properties of the images on the fly.

![Image 2D](./image.gif)
````

````{tab} Examples - CLI

`ImageWidget` can be embedded in [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`. The command-line API is the same for all cases.

## Example 1 - Visualizing 2D Image Data from a Detector

In this example, we demonstrate how to add an `ImageWidget` to a [`BECDockArea`](user.widgets.bec_dock_area) to visualize live 2D image data from a connected camera detector.

```python
# Add a new dock with BECFigure widget
dock_area = gui.new()
img_widget = dock_area.new().new(gui.available_widgets.Image)

# Add an ImageWidget to the BECFigure for a 2D detector
img_widget.image(monitor='eiger', monitor_type='2d')
img_widget.title = "Camera Image - Eiger Detector"
```

## Example 2 - Visualizing 1D Waveform Data from a Detector

This example demonstrates how to set up the Image widget to visualize 1D waveform data from a detector, such as a line detector or a spectrometer. The widget will stack incoming 1D data arrays to construct a 2D image.

```python
# Add a new dock with BECFigure widget
dock_area = gui.new()
img_widget = dock_area.new().new(gui.available_widgets.Image)

# Add an ImageWidget to the BECFigure for a 2D detector
img_widget.image(monitor='waveform', monitor_type='1d')
img_widget.title = "Line Detector Data"

# Optional: Set the color map and value range
img_widget.colormap = "plasma"
img_widget.vrange= [0, 100]
```

## Example 3 - Real-time Image Processing

The `Image` provides real-time image processing capabilities, such as rotating, scaling, applying logarithmic scaling, and performing FFT on the displayed images. The following example demonstrates how to apply these transformations to an image.

```python
# Rotate the image by 90 degrees (1,2,3,4 are multiplied by 90 degrees)
img_widget.rotation = 1

# Transpose the image
img_widget.transpose = True

# Apply FFT to the image
img_widget.fft = True

# Set logarithmic scaling for the image display
img_widget.log = True

# Set autorange for the image color map
img_widget.autorange = True
img_widget.autorange_mode = 'mean'# or 'max' 
```
<!-- 
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
``` -->


````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.Image.rst
```
````
