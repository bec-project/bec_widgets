(user.widgets.bec_queue)=

# BEC Queue Widget

````{tab} Overview

The [`BEC Queue Widget`](/api_reference/_autosummary/bec_widgets.cli.client.BECQueue) provides a real-time display and control of the BEC scan queue, allowing users to monitor, manage, and control the status of ongoing and pending scans. The widget automatically updates to reflect the current state of the scan queue, displaying critical information such as scan numbers, types, and statuses. Additionally, it provides control options to stop individual scans, stop the entire queue, resume, and reset the queue, making it a powerful tool for managing scan operations in the BEC environment.

## Key Features:
- **Real-Time Queue Monitoring**: Displays the current state of the BEC scan queue, with automatic updates as the queue changes.
- **Detailed Scan Information**: Provides a clear view of scan numbers, types, and statuses, helping users track the progress and state of each scan.
- **Queue Control**: Allows users to stop specific scans, stop the entire queue, resume paused scans, and reset the queue.
- **Interactive Table Layout**: The queue is presented in a table format, with customizable columns that stretch to fit the available space.
- **Flexible Integration**: The widget can be integrated into both [`BECDockArea`](user.widgets.bec_dock_area) and used as an individual component in your application through `QtDesigner`.

````

````{tab} Examples

The `BEC Queue Widget` can be embedded within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `QtDesigner`. Below are examples demonstrating how to create and use the `BEC Queue Widget`.

## Example 1 - Adding BEC Queue Widget to BECDockArea

In this example, we demonstrate how to add a `BECQueue` widget to a `BECDockArea`, allowing users to monitor the BEC scan queue directly from the GUI.

```python
# Add a new dock with a BECQueue widget
bec_queue = gui.add_dock().add_widget("BECQueue")
```

```{hint}
The `BECQueue` widget automatically updates as the scan queue changes, providing real-time feedback on the status of each scan.
Once the widget is added, it will automatically display the current scan queue
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.BECQueue.rst
```
````