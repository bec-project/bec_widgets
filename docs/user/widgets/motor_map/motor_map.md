(user.widgets.motor_map)=

# Motor Map Widget

````{tab} Overview

The Motor Map Widget is a specialized tool for tracking and visualizing the positions of motors in real-time. This widget is crucial for applications requiring precise alignment and movement tracking during scans. It provides an intuitive way to monitor motor trajectories, ensuring accurate positioning throughout the scanning process.

## Key Features:
- **Flexible Integration**: The widget can be integrated into both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`.
- **Real-time Motor Position Visualization**: Tracks motor positions in real-time and visually represents motor trajectories.
- **Customizable Visual Elements**: The appearance of all widget components is fully customizable, including scatter size and background values.
- **Interactive Controls**: Interactive controls for zooming, panning, and adjusting the visual properties of motor trajectories on the fly.

![MotorMap](./motor.gif)
````

````{tab} Examples CLI
`MotorMapWidget` can be embedded in both [`BECFigure`](user.widgets.bec_figure) and [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BECDesigner`. However, the command-line API is the same for all cases.

## Example 1 - Adding Motor Map Widget to BECFigure

In this example, we will demonstrate how to add two different `MotorMapWidgets` into a single [`BECFigure`](user.widgets.bec_figure) widget.

```python
# Add new dock with BECFigure widget
fig = gui.add_dock().add_widget('BECFigure')

# Add two WaveformWidgets to the BECFigure
mm1 = fig.motor_map(motor_x='samx', motor_y='samy')
mm2 = fig.motor_map(motor_x='aptrx', motor_y='aptry',new=True)
```

## Example 2 - Adding Motor Map Widget as a Dock in BECDockArea

Adding `MotorMapWidget` into a [`BECDockArea`](user.widgets.bec_dock_area) is similar to adding any other widget. The widget has the same API as the one in BECFigure; however, as an independent widget outside BECFigure, it has its own toolbar, allowing users to configure the widget without needing CLI commands.

```python
# Add new MotorMaps to the BECDockArea
mm1 = gui.add_dock().add_widget('BECMotorMapWidget')
mm2 = gui.add_dock().add_widget('BECMotorMapWidget')

# Add signals to the MotorMaps
mm1.change_motors(motor_x='samx', motor_y='samy')
mm2.change_motors(motor_x='aptrx', motor_y='aptry')
```

## Example 3 - Customizing Motor Map Display

The `MotorMapWidget` allows customization of its visual elements to better suit the needs of your application. Below is an example of how to adjust the scatter size, set background values, and limit the number of points displayed from the position buffer.

```python
# Set scatter size
mm1.set_scatter_size(scatter_size=5)

# Set background value
mm1.set_background_value(background_value=0)

# Limit the number of points displayed and saved in the position buffer
mm1.set_max_points(max_points=500)
```

## Example 4 - Changing Motors and Resetting History

You can dynamically change the motors being tracked and reset the history of the motor trajectories during the session.

```python
# Reset the history of motor movements
mm1.reset_history()

# Change the motors being tracked
mm1.change_motors(motor_x='aptrx', motor_y='aptry')
```
````

````{tab} API
```{eval-rst}  
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECMotorMap.rst
```
````
