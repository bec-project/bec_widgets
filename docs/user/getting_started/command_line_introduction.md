(user.command_line_introduction)=
# Command Line Introduction
In order to use BEC Widgets as a plotting tool for BEC, it needs to be [installed](#user.installation) in the same python environment as the BECIpythonClient. If that is the case, it will automatically launch a GUI and assign the control of the GUI to the `gui` object in the client. The GUI backend will also be automatically connect to the BEC server, giving access to all information on the server and allowing the user to visualize the data in real-time.

## BECDockArea
The `gui` object represents the top level of hierarchy in BEC Widgets. It is a [`BECDockArea`](/api_reference/_autosummary/bec_widgets.cli.client.BECDockArea) based on the [pyqtgraph.dockarea](https://pyqtgraph.readthedocs.io/en/latest/api_reference/dockarea.html). The GUI can be further composed of multiple [`BECDock`](/api_reference/_autosummary/bec_widgets.cli.client.BECDock)s that can be detached and attached to the main area. These docks allow users to freely arrange and customize the widgets they add to the gui, giving them the necessary freedom to design the user interface they desire.

## Widgets
Widgets are the building blocks of the BEC Widgets framework. They are the visual components that allow users to interact with the data and control the behavior of the application. Each dock can contain multiple widgets, although we recommend using a direct mapping of a single widget to a dock. We currently support two type of widgets:
- [`BECFigure`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure): A widget that can be used to visualize data from BEC. It is automatically connected to the BEC server and can be used to plot data from BEC.
- [`SpiralProgressBar`](/api_reference/_autosummary/bec_widgets.cli.client.SpiralProgressBar): A custom widget that can be used to show progress in a spiral shape.

**BECFigure**
The [`BECFigure`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure) widget is one of the core widgets developed for BEC and designed to be flexible and can be used to visualize different types of data. It can be used to visualize [1D Waveform](user.widgets.waveform_1d), [2D Scatter Plot](user.widgets.scatter_2d), [Motor Position Map](user.widgets.motor_map) and 2D image data. As mentioned before, starting the BECIPythonClient will automatically launch a `gui` with a single dock area and a BECFigure widget attached to it. This widget is accessible via the `fig` object from the client directly. We also provide two methods [`plot()`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.plot), [`image()`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.image) and [`motor_map()`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.motor_map) as shortcuts to add a plot, image or motor map to the BECFigure.

**Waveform Plot** 
 The [`BECWaveForm`](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform) is a widget that can be used to visualize 1D waveform data, i.e. to plot data of a monitor against a motor position. The method [`plot()`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure.rst#bec_widgets.cli.client.BECFigure.plot) of BECFigure adds a BECWaveForm widget to the figure, and returns the plot object. 

```python
plt = fig.add_plot('samx', 'bpm4i')
```
Here, we assign the plot to the object `plt`. We can now use this object to further customize the plot, e.g. changing the title ([`set_title()`](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform.rst#bec_widgets.cli.client.BECWaveform.set_title)), axis labels ([`set_x_label()`](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform.rst#bec_widgets.cli.client.BECWaveform.set_x_label)) or limits ([`set_x_lim()`](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform.rst#bec_widgets.cli.client.BECWaveform.set_x_lim)). We invite you to explore the API of the BECWaveForm in the [documentation](user.widgets.waveform_1d) or directly in the command line.

**Scatter Plot**
The [`BECWaveForm`](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveForm) widget can also be used to visualize 2D scatter plots. More details on setting up the scatter plot are available in the widget documentation of the [scatter plot](user.widgets.scatter_2d).

**Motor Map**
The [`BECMotorMap`](/api_reference/_autosummary/bec_widgets.cli.client.BECMotorMap) widget can be used to visualize the position of motors. It's focused on tracking and visualizing the position of motors, crucial for precise alignment and movement tracking during scans. More details on setting up the motor map are available in the widget documentation of the [motor map](user.widgets.motor_map).

**Image Plot**
The [`BECImageItem`](/api_reference/_autosummary/bec_widgets.cli.client.BECImageItem) widget can be used to visualize 2D image data for example a camera. More details on setting up the image plot are available in the widget documentation of the [image plot](user.widgets.image)

### Useful Commands
We recommend users to explore the API of the widgets by themselves since we assume that the user interface is supposed to be intuitive and self-explanatory. We appreciate feedback from user in order to constantly improve the experience and allow easy access to the gui, widgets and their functionality. We recommend checking the [API documentation](user.api_reference), but also by using BEC Widgets, exploring the available functions and check their dockstrings.
```python
gui.add_dock? # shows the dockstring of the add_dock method
```

In addition, we list below a few useful commands that can be used to interface with the widgets:

```python
gui.panels # returns a dictionary of all docks in the gui
gui.add_dock() # adds a new dock to the gui

dock = gui.panels['dock_2']
dock.add_widget_bec('BECFigure') # adds a new widget of BECFigure to the dock
dock.widget_list # returns a list of all widgets in the dock

figure = dock.widget_list[0] # assigns the created BECFigure to figure
plt = figure.add_plot('samx', 'bpm4i') # adds a BECWaveForm plot to the figure
plt.curves # returns a list of all curves in the plot
```

We note that commands can also be chained. For example, `gui.add_dock().add_widget_bec('BECFigure')` will add a new dock to the gui and add a new widget of `BECFigure` to the dock. 

## Composing a larger GUI
The example given above introduces BEC Widgets with its different components, and provides an overview of how to interact with the widgets. Nevertheless, another power aspect of BEC Widgets lies in the ability to compose a larger GUI with multiple docks and widgets. This section aims to provide a tutorial like guide on how to compose a more complex GUI that (A) live-plots a 1D waveform, (B) plots data from a camera, and (C) tracks the positions of two motors.
Let's assume BEC was just started and the `gui` object is available in the client. A single dock is already attached together with a BEC Figure. Let's add the 1D waveform to this dock, change the color of the line to white and add the title *1D Waveform* to the plot.

```python
plt = fig.add_plot('samx', 'bpm4i')
plt.curves[0].set_color(color="white")
plt.set_title('1D Waveform')
```

Next, we add 2 new docks to the gui, one to plot the data of a camera and one to track the positions of two motors. 
```ipython
cam_widget= gui.add_dock(name="cam_dock").add_widget_bec('BECFigure').image("eiger")
motor_widget = gui.add_dock(name="mot_dock").add_widget_bec('BECFigure').motor_map("samx", "samy")
```
Note, we chain commands here which is possible since the `add_dock` and `add_widget_bec` methods return the dock and the widget respectively. We can now further customize the widgets by changing the title, axis labels, etc.

```python
cam_widget.set_title("Camera Image Eiger")
cam_widget.set_vrange(vmin=0, vmax=100)
```
As a final step, we can now add also a SpiralProgressBar to a new dock, and perform a grid_scan with the motors *samx* and *samy*.
As you see in the example below, all docks are arranged below each other. This is the default behavior of the `add_dock` method. However, the docks can be freely arranged by drag and drop as desired by the user. We invite you to explore this by yourself following the example in the video, and build your custom GUI with BEC Widgets.

```python
prog_bar = gui.add_dock(name="prog_dock").add_widget_bec('SpiralProgressBar')
prog_bar.set_line_widths(15)
scans.grid_scan(dev.samy, -2, 2, 10, dev.samx, -5, 5, 10, exp_time=0.1, relative=False)
```

![gui_complex_gui](./gui_complex_gui.gif)

