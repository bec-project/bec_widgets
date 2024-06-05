(user.widgets.spiral_progress_bar)=
# [Spiral Progress Bar](/api_reference/_autosummary/bec_widgets.cli.client.SpiralProgressBar)
**Purpose** The Spiral Progress Bar widget is a circular progress bar that can be used to visualize the progress of a task. The widget is designed to be used in applications where the progress of a task is represented as a percentage. The Spiral Progress Bar widget is a part of the BEC Widgets library and can be controlled directly using its API, or hooked up to the progress of a device readback or scan.

**Key Features:**

- circular progress bar to show updates on the progress of a task.
- hooks to update the progress bar from a device readback or scan.
- multiple progress rings to show different tasks in parallel.

**Example of Use:**
![SpiralProgressBar](./progress_bar.gif)

**Code example**
The following code snipped demonstrates how to create a 2D scatter plot using BEC Widgets within BEC.
```python
# adds a new dock with a spiral progress bar
progress = gui.add_dock().add_widget("SpiralProgressBar")
# customize the size of the ring
progress.set_line_width(20)
```