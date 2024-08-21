(user.widgets.device_browser)=

# Device Browser

````{tab} Overview

The `Device Browser` widget provides a user-friendly interface for browsing through all available devices in the current BEC session. As it supports drag functionality, users can easily drag and drop device into other widgets or applications. 

```{note}
The `Device Browser` widget is currently under development. Other widgets may not support drag and drop functionality yet.
```

## Key Features:
- **Device Search**: Allows users to search for devices using regular expressions.
- **Drag and Drop**: Supports drag and drop functionality for easy transfer of devices to other widgets or applications.

```{figure} ./device_browser.png
```
````

````{tab} Examples

In this example, we demonstrate how to add a `DeviceBrowser` widget to a `BECDockArea` to visualize the progress of a task.

```python
# Add a new dock with a DeviceBrowser widget
browser = gui.add_dock().add_widget("DeviceBrowser")
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.DeviceBrowser.rst
```
````
