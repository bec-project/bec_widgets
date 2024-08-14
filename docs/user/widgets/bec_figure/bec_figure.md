(user.widgets.bec_figure)=
# BECFigure

````{tab} Overview

[`BECFigure`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure) is a robust framework that provides a fast, flexible plotting environment, similar to the Matplotlib figure. With BECFigure, users can dynamically change layouts, add or remove subplots, and customize their plotting environment in real-time. This flexibility makes BECFigure an ideal tool for both rapid prototyping and detailed data visualization.

- **Dynamic Layout Management**: Easily add, remove, and rearrange subplots within `BECFigure`, enabling tailored visualization setups.
- **Widget Integration**: Incorporate various specialized widgets like [`WaveformWidget`](user.widgets.waveform_widget), [`ImageWidget`](user.widgets.image_widget) , and [`MotorMapWidget`](user.widgets.motor_map) into `BECFigure`. Note that these widgets can also be used individually. For more details, please refer to the documentation for each individual widget.
- **Interactive Controls**: Provides interactive tools for zooming, panning, and adjusting plots on the fly, streamlining the data exploration process.

**Schema of the BECFigure components**

![BECFigure.png](BECFigure.png)

````

````{tab} Examples - CLI
In the following examples, we will use `BECIPythonClient` with a predefined `BECDockArea` as the `gui` object. These tutorials focus on how to work with the `BECFigure` framework, such as changing layouts, adding new elements, and accessing them. For more detailed examples of each individual component, please refer to the example sections of each individual widget: [`WaveformWidget`](user.widgets.waveform_widget), [`MotorMapWidget`](user.widgets.motor_map), [`ImageWidget`](user.widgets.image_widget).

## Example 1 - Adding subplots to BECFigure

In this example, we will demonstrate how to add different subplots to a single `BECFigure` widget.

```python
# Add a new dock with BECFigure widget
fig = gui.add_dock().add_widget('BECFigure')

# Add a WaveformWidget to the BECFigure
plt1 = fig.plot(x_name='samx', y_name='bpm4i')

# Add a second WaveformWidget to the BECFigure, specifying new=True to add it as a new subplot
plt2 = fig.plot(x_name='samx', y_name='bpm3i', new=True)

# Add a MotorMapWidget to the BECFigure
mm = fig.motor_map(motor_x='samx', motor_y='samy')

# Add an ImageWidget to the BECFigure
img = fig.image('eiger')
```
```{note}
By default, the [`.plot`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.plot), [`.image`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.image), and [`.motor_map`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.motor_map) methods always find the first widget of that type in the layout and interact with it. If you want to add a new subplot of the same type, you must either specify the coordinates of the new subplot or use the `new=True` keyword argument, as shown above when adding the second WaveformWidget. Additionally, you can directly add a subplot to a specific, unoccupied position in the layout by specifying the `row` and `col` arguments, such as `fig.plot(x_name='samx', y_name='bpm4i', row=1, col=1)`.
```

## Example 2 - Changing the layout of BECFigure

The previous example added four subplots into a single `BECFigure` widget. By default, new widgets are always added to the bottom of the BECFigure. However, you can change the layout of the BECFigure by using the [`change_layout`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.change_layout) method, specifying the number of rows and/or columns.

```python
# Change the layout of the BECFigure to have 4 columns -> 4x1 matrix layout
fig.change_layout(max_columns=4) 

# Change the layout of the BECFigure to have 2 rows -> 2x2 matrix layout
fig.change_layout(max_rows=2) 
```

## Example 3 - Accessing Subplots in BECFigure

The subplots in BECFigure can be accessed in a similar way to Matplotlib figures using the [`axes`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.axes) property. Each subplot can be accessed by its index coordinates within the layout, specified by the row and column index (starting at 0). In following example, we will access the subplots and modify their titles. The layout is a 2x2 matrix, so the subplots are indexed as follows:

```python
# Access the first subplot in the first row and first column (0, 0)
subplot1 = fig.axes(0, 0)

# Access the second subplot in the first row and second column (0, 1)
subplot2 = fig.axes(0, 1)

# Access the first subplot in the second row and first column (1, 0)
subplot3 = fig.axes(1, 0)

# Example: Set title for the first subplot
subplot1.set_title("Waveform 1")

# Example: Set title for the second subplot
subplot2.set_title("Waveform 2")

# Example: Set title for the third subplot
subplot3.set_title("Motor Map")
```

In this example, we accessed three different subplots based on their row and column positions and modified their titles.

## Example 4 - Removing Subplots from BECFigure

You may want to remove certain subplots from the `BECFigure`. This can be done using the [`remove`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.remove) method, which takes the row and column index of the subplot you want to remove. The [`remove`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.remove) method could be also called on the subplot itself.

```python

# Remove the subplot in the second row and second column (1, 1)
fig.remove(1, 1)

# Remove the subplot in the first row and first column (0, 0)
fig.remove(0, 0)

# Remove previously accessed subplot plt2 from Example 1
plt2.remove()
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst
```
````
