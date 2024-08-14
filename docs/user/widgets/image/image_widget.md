(user.widgets.image_widget)=

# Image Widget

````{tab} Overview

The Image Widget is a versatile tool designed for visualizing 2D image data, such as camera images, in real-time. Directly integrated with the `BEC` framework, it can display live data streams from connected cameras or other image sources within the current `BEC` session. The widget provides advanced customization options for color maps and scale bars, allowing users to tailor the visualization to their specific needs.

## Key Features:
- **Flexible Integration**: The widget can be integrated into both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.
- **Live Data Visualization**: Real-time plotting of 2D image data from cameras or other image sources, provided that a data stream is available in the BEC session.
- **Customizable Color Maps and Scale Bars**: Users can customize the appearance of images with various color maps and adjust scale bars to better interpret the visualized data.
- **Real-time Image Processing**: Apply real-time image processing techniques directly within the widget to enhance the quality or analyze specific aspects of the images such as rotation, log scaling, and FFT.
- **Data Export**: Export visualized image data to various formats such as PNG, TIFF, or H5 for further analysis or reporting.
- **Interactive Controls**: Offers interactive controls for zooming, panning, and adjusting the visual properties of the images on the fly.

![Image 2D](./image_plot.gif)
````

````{tab} Examples - CLI

`ImageWidget` can be embedded in both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. However, the command-line API is the same for all cases.

## Example 1 - Adding Image Widget to BECFigure

In this example, we demonstrate how to add an `ImageWidget` to a [`BECFigure`](user.widgets.bec_figure) to visualize live data from a connected camera.

```python
# Add a new dock with BECFigure widget
fig = gui.add_dock().add_widget('BECFigure')

# Add an ImageWidget to the BECFigure
img_widget = fig.image(source='eiger')
img_widget.set_title("Camera Image Eiger")
```

## Example 2 - Adding Image Widget as a Dock in BECDockArea

Adding `ImageWidget` into a [`BECDockArea`](user.widgets.bec_dock_area) is similar to adding any other widget. The widget has the same API as the one in [`BECFigure`](user.widgets.bec_figure); however, as an independent widget outside [`BECFigure`](user.widgets.bec_figure), it has its own toolbar, allowing users to configure the widget without needing CLI commands.

```python
# Add an ImageWidget to the BECDockArea
img_widget = gui.add_dock().add_widget('BECImageWidget')

# Visualize live data from a camera with range from 0 to 100
img_widget.image(source='eiger')
img_widget.set_vrange(vmin=0, vmax=100)
```

## Example 3 - Customizing Image Display

This example demonstrates how to customize the color map and scale bar for an image being visualized in an `ImageWidget`.

```python
# Set the color map and adjust the scale bar range
img_widget.set_colormap("viridis")
img_widget.set_vrange(vmin=10, vmax=200)
```

## Example 4 - Real-time Image Processing

The `ImageWidget` provides real-time image processing capabilities, such as rotating, scaling, and applying FFT to the displayed images. The following example demonstrates how to rotate an image by 90 degrees, transpose it, and apply FFT.

```python
# Rotate the image by 90 degrees
img_widget.set_rotation(deg_90=1)

# Transpose the image
img_widget.set_transpose(enable=True)

# Apply FFT to the image
img_widget.set_fft(enable=True)

# Set the logarithmic scale for the image display
img_widget.set_log(enable=True)
```

````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECImageWidget.rst
```
````
