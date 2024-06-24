(user.widgets.spiral_progress_bar)=
# [Ring Progress Bar](/api_reference/_autosummary/bec_widgets.cli.client.RingProgressBar)

**Purpose:**

The ring Progress Bar widget is a circular progress bar that can be used to visualize the progress of a task. The
widget is designed to be used in applications where the progress of a task is represented as a percentage. The Spiral
Progress Bar widget is a part of the BEC Widgets library and can be controlled directly using its API, or hooked up to
the progress of a device readback or scan.

**Key Features:**

- circular progress bar to show updates on the progress of a task.
- hooks to update the progress bar from a device readback or scan.
- multiple progress rings to show different tasks in parallel.

**Example of Use:**
![RingProgressBar](./progress_bar.gif)

**Code example:**

The following code snipped demonstrates how to create a `RingProgressBar` using BEC Widgets within BEC.
```python
# adds a new dock with a ring progress bar
progress = gui.add_dock().add_widget("RingProgressBar")
# customize the size of the ring
progress.set_line_width(20)
```

By default, the Ring Progress Bar widget will display a single ring. To add more rings, use the add_ring method:

```python
# adds a new dock with a ring progress bar
progress.add_ring()
```

To access rings and specify their properties, you can use `progress.rings` with an index specifying the ring index (
starting from 0):

```python
progress.rings[0].set_line_width(20)  # set the width of the first ring
progress.rings[1].set_line_width(10)  # set the width of the second ring
```

By default, the `RingProgressBar` widget is set with `progress.enable_auto_update(True)`, which will automatically
update the bars in the widget. To manually set updates for each progress bar, use the set_update method. Note that
manually updating a ring will disable the automatic update for the whole widget:

```python
progress.rings[0].set_update("scan")  # set the update of the first ring to be an overall scan progress
progress.rings[1].set_update("device",
                             "samx")  # set the update of the second ring to be a device readback (in this case, samx)
```

