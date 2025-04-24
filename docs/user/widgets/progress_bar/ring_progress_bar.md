(user.widgets.ring_progress_bar)=

# Ring Progress Bar

````{tab} Overview

The [`Ring Progress Bar`](/api_reference/_autosummary/bec_widgets.cli.client.RingProgressBar) widget is a circular progress bar designed to visualize the progress of tasks in a clear and intuitive manner. This widget is particularly useful in applications where task progress needs to be represented as a percentage. The `Ring Progress Bar` can be controlled directly via its API or can be hooked up to track the progress of a device readback or scan, providing real-time visual feedback.

## Key Features:
- **Circular Progress Visualization**: Displays a circular progress bar to represent task completion.
- **Device and Scan Integration**: Hooks into device readbacks or scans to automatically update the progress bar based on real-time data.
- **Multiple Rings**: Supports multiple progress rings within the same widget to track different tasks in parallel.
- **Customizable Visual Elements**: Allows customization of colors, line widths, and other visual elements for each progress ring.

![RingProgressBar](./progress_bar.gif)

````

````{tab} Example

## Example 1 - Adding Ring Progress Bar to BECDockArea

In this example, we demonstrate how to add a `RingProgressBar` widget to a `BECDockArea` to visualize the progress of a task.

```python
# Add a new dock with a RingProgressBar widget
dock_area = gui.new('my_new_dock_area') # Create a new dock area
progress = dock_area.new().new(gui.available_widgets.RingProgressBar)

# Customize the size of the progress ring
progress.set_line_widths(20)
```

## Example 2 - Adding Multiple Rings to Track Parallel Tasks

By default, the `RingProgressBar` widget displays a single ring. You can add additional rings to track multiple tasks simultaneously.

```python
# Add a second ring to the RingProgressBar
progress.add_ring()

# Customize the rings
progress.rings[0].set_line_widths(20)  # Set the width of the first ring
progress.rings[1].set_line_widths(10)  # Set the width of the second ring
```

## Example 3 - Integrating with Device Readback and Scans

The `RingProgressBar` can automatically update based on the progress of scans or device readbacks. This example shows how to set up the progress rings to reflect these updates.

```python
# Set the first ring to update based on scan progress
progress.rings[0].set_update("scan")

# Set the second ring to update based on a device readback (e.g., samx)
progress.rings[1].set_update("device", "samx")
```

## Example 4 - Customizing Visual Elements of the Rings

The `RingProgressBar` widget offers various customization options, such as changing colors, line widths, and the gap between rings.

```python
# Set the color of the first ring to blue
progress.rings[0].set_color("blue")

# Set the background color of the second ring
progress.rings[1].set_background("gray")

# Adjust the gap between the rings
progress.set_gap(5)

# Set the diameter of the progress bar
progress.set_diameter(150)
```

## Example 5 - Manual Updates and Precision Control

While the `RingProgressBar` supports automatic updates, you can also manually control the progress and set the precision for each ring.

```python
# Disable automatic updates and manually set the progress value
progress.enable_auto_updates(False)
progress.rings[0].set_value(75)  # Set the first ring to 75%

# Set precision for the progress display
progress.set_precision(2)  # Display progress with two decimal places


# Setting multiple rigns with different values
progress.set_number_of_bars(3)

# Set the values of the rings to 50, 75, and 25 from outer to inner ring
progress.set_value([50, 75, 25])
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.RingProgressBar.rst
```
````

