(user.widgets.scan_control)=

# Scan Control

**Purpose:**

The `ScanControl` widget is designed to generate a graphical user interface (GUI) to control various scan operations
based on the scan's signature and `gui_config`. The widget is used to control the scan operations, such as starting,
stopping, and pausing the scan. The widget also provides a graphical representation of the scan progress and the scan
status. The widget is designed to be used in conjunction with the `ScanServer` and `ScanBundler` services from the BEC
core services.

By default the widget supports only the scans which have defined `gui_config` and are inhereted from these scan classes:

- [ScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.ScanBase.html)
- [SyncFlyScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.SyncFlyScanBase.html)
- [AsyncFlyScanBase](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_server.scan_server.scans.AsyncFlyScanBase.html)

**Key Features:**

- Automatically generates a control interface based on scan signatures and `gui_config`.
- Supports adding and removing argument bundles dynamically.
- Provides a visual representation of scan parameters grouped by functionality.
- Integrates start and stop controls for executing and halting scans.

**Example of Use:**

**Code example:**
The following code snipped demonstrates how to create a `ScanControl` widget using BEC Widgets within `BECIPythonClient`

![ScanControl](./scan_control.gif)

```python
scan_control = gui.add_dock().add_widget("ScanControl")
```