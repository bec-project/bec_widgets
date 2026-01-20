(user.widgets.ring_progress_bar)=

# Ring Progress Bar

````{tab} Overview

The `RingProgressBar` widget is a circular progress bar designed to visualize the progress of tasks in a clear and intuitive manner. This widget is particularly useful in applications where task progress needs to be represented as a percentage. The `Ring Progress Bar` can be controlled directly via its API or can be hooked up to track the progress of a device readback or scan, providing real-time visual feedback.

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
dock_area = gui.new() # Create a new dock area
progress = dock_area.new(gui.available_widgets.RingProgressBar)

# Add a ring to the RingProgressBar
progress.add_ring()
ring = progress.rings[0]
ring.set_value(50)  # Set the progress value to 50
```

## Example 2 - Adding Multiple Rings to Track Parallel Tasks

By default, the `RingProgressBar` widget displays a single ring. You can add additional rings to track multiple tasks simultaneously.

```python
# Add a second ring to the RingProgressBar
progress.add_ring()

# Customize the rings
progress.rings[1].set_value(30)  # Set the second ring to 30
```

## Example 3 - Integrating with Device Readback and Scans

The `RingProgressBar` can automatically update based on the progress of scans or device readbacks. This example shows how to set up the progress rings to reflect these updates.

```python
# Set the first ring to update based on scan progress
progress.rings[0].set_update("scan")

# Set the second ring to update based on a device readback (e.g., samx)
progress.rings[1].set_update("device", "samx")
```

````

````{tab} API
```{eval-rst} 
.. autoclass:: bec_widgets.cli.client.RingProgressBar
   :members:
   :show-inheritance:
```
````

