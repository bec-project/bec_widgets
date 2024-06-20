(user.widgets.text_box)=
# [BEC Status Box](/api_reference/_autosummary/bec_widgets.cli.client.BECStatusBox)
**Purpose:**

The BECStatusBox Widget is a widget that allows you to monitor the status/health of the all running BEC processes. The widget generates the view automatically and updates the status of the processes in real-time. The top level indicates the overall state of the BEC core services (DeviceServer, ScanServer, SciHub, ScanBundler and FileWriter), but you can also see the status of each individual process by opening the collapsed view. In the collapsed view, you can double click on each process to get a popup window with live updates of the metrics for each process in real-time.

**Key Features:**

- monitor the state of individual BEC services.
- automatically track BEC services, i.e. additional clients connecting.
- live-updates of the metrics for each process.

**Example of Use:**
![BECStatus](./bec_status_box.gif)

**Code example:**

The following code snipped demonstrates how to create a `BECStatusBox` widget using BEC Widgets within BEC.
```python
bec_status_box = gui.add_dock().add_widget("BECStatusBox")
```









