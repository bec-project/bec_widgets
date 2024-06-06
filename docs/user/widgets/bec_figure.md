(user.widgets.bec_figure)=
# BECFigure
[`BECFigure`](/api_reference/_autosummary/bec_widgets.cli.client.BECFigure) is a widget that provides a graphical user interface for creating and managing plots. It is a versatile tool that allows users to create a wide range of plots, from simple 1D waveforms to complex 2D scatter plots. BECFigure is designed to be user-friendly and interactive, enabling users to customize plots and visualize data in real-time.
In the following, we describe 4 different type of widgets thaat are available in BECFigure. 

(user.widgets.waveform_1d)=
## [1D Waveform Widget](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform)

**Purpose:** This widget provides a straightforward visualization of 1D data. It is particularly useful for plotting positioner movements against detector readings, enabling users to observe correlations and patterns in a simple, linear format.

**Key Features:**
- Real-time plotting of positioner versus detector values.
- Interactive controls for zooming and panning through the data.
- Customizable visual elements such as line color and style.

**Example of Use:**
![Waveform 1D](./w1D.gif)

**Code example**
The following code snipped demonstrates how to create a 1D waveform plot using BEC Widgets within BEC. More details about BEC Widgets in BEC can be found in the getting started section within the [introduction to the command line.](user.command_line_introduction)
```python
# adds a new dock, a new BECFigure and a BECWaveForm to the dock
plt = gui.add_dock().add_widget('BECFigure').plot('samx', 'bpm4i')
# add a second curve to the same plot 
plt.plot(x_name='samx', y_name='bpm3i')
plt.set_title("Gauss plots vs. samx")
plt.set_x_label("Motor X")
plt.set_y_label("Gauss Signal (A.U.")
```
Note, the return value of the simulated devices *bpm4i* and *bpm3i* may not be gaussian signals, but they can be easily configured with the code snippet below. For more details please check the documentation of the [simulation](https://bec.readthedocs.io/en/latest/developer/devices/bec_sim.html).
```python
# bpm4i uses GaussianModel and samx as a reference; default settings
dev.bpm4i.sim.select_sim_model("GaussianModel")
# bpm3i uses StepModel and samx as a reference; default settings
dev.bpm3i.sim.select_sim_model("StepModel")
```

(user.widgets.scatter_2d)=
## [2D Scatter Plot](/api_reference/_autosummary/bec_widgets.cli.client.BECWaveform)

**Purpose:** The 2D scatter plot widget is designed for more complex data visualization. It employs a false color map to represent a third dimension (z-axis), making it an ideal tool for visualizing multidimensional data sets.

**Key Features:**

- 2D scatter plot with color-coded data points based on a third variable (two positioners for x/y vs. one detector for colormap).
- Interactive false color map for enhanced data interpretation.
- Tools for selecting and inspecting specific data points.

**Example of Use:**
![Waveform 1D](./scatter_2D.gif)

**Code example**
The following code snipped demonstrates how to create a 2D scatter plot using BEC Widgets within BEC.
```python
# adds a new dock, a new BECFigure and a BECWaveForm to the dock
plt = gui.add_dock().add_widget('BECFigure').add_plot(x_name='samx', y_name='samy', z_name='bpm4i')
```

(user.widgets.motor_map)=
## [Motor Position Map](/api_reference/_autosummary/bec_widgets.cli.client.BECMotorMap)

**Purpose:** A specialized component derived from the Motor Alignment Tool. It's focused on tracking and visualizing the position of motors, crucial for precise alignment and movement tracking during scans.

**Key Features:**
- Real-time tracking of motor positions.
- Visual representation of motor trajectories, aiding in alignment tasks.

**Example of Use:**
![Waveform 1D](./motor.gif)

**Code example**
The following code snipped demonstrates how to create a motor map using BEC Widgets within BEC.
```python
# add a motor map to the gui
mot_map = gui.add_dock().add_widget('BECFigure').motor_map('samx', 'samy')
# change the number of points displayed
```

(user.widgets.image_2d)=
## [Image Plot](/api_reference/_autosummary/bec_widgets.cli.client.BECImageItem)

**Purpose:** A versatile widget for visualizing 2D image data, such as camera images. It provides a detailed representation of image data, with an attached color and scale bar to dynamically adjust the image display.

**Key Features:**
- Live-plotting of 2D image data from cameras (*if data stream is available in BEC*).
- Color maps and scale bars for customizing image display.
**Example of Use:**
![Image 2D](./image_plot.gif)

**Code example**
The following code snipped demonstrates how to create a motor map using BEC Widgets within BEC.
```python
# add a camera view for the eiger camera to the gui
cam_widget = gui.add_dock().add_widget('BECFigure').image('eiger')
# set the title of the camera view
cam_widget.set_title("Camera Image Eiger")
# change the color map range, e.g. from 0 to 100, per default it is autoscaling
# Note, the simulation has hot pixels on the detector
cam_widget.set_vrange(vmin=0, vmax=100)
```
