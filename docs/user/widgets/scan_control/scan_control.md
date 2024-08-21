(user.widgets.scan_control)=

# Scan Control Widget

````{tab} Overview

The [`Scan Control`](/api_reference/_autosummary/bec_widgets.cli.client.ScanControl) widget provides a graphical user interface (GUI) to manage various scan operations in a BEC environment. It is designed to interact with the BEC server, enabling users to start and stop scans. The widget automatically creates the necessary input form based on the scan's signature and gui_config, making it highly adaptable to different scanning processes.

## Key Features:
- **Automatic Interface Generation**: Automatically generates a control interface based on scan signatures and `gui_config`.
- **Dynamic Argument Bundling**: Supports the dynamic addition and removal of argument bundles such as positioners controls.
- **Visual Parameter Grouping**: Provides a visual representation of scan parameters, grouped by their functionality.
- **Integrated Scan Controls**: Includes start abd stop controls for managing scan execution.

```{note}
By default, this widget supports scans that are derived from the following base classes and have a defined `gui_config`:
- [ScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.ScanBase.html)
- [SyncFlyScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.SyncFlyScanBase.html)
- [AsyncFlyScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.AsyncFlyScanBase.html)
```

```{hint}
The full procedure how to design `gui_config` for your custom scan class is described in the [Scan GUI Configuration](https://bec.readthedocs.io/en/latest/developer/scans/scan_gui_config.html) tutorial.
```

````

````{tab} Examples

The `ScanControl` widget can be integrated within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `QtDesigner`. Below are examples demonstrating how to create and use the `ScanControl` widget.

## Example 1 - Adding Scan Control Widget to BECDockArea

In this example, we demonstrate how to add a `ScanControl` widget to a `BECDockArea`, enabling the user to control scan operations directly from the GUI.

```python
# Add a new dock with a ScanControl widget
scan_control = gui.add_dock().add_widget("ScanControl")
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ScanControl.rst
```
````