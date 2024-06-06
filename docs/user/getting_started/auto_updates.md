(user.auto_updates)=
# Auto updates
BEC Widgets provides a simple way to update the entire GUI configuration based on events. These events can be of different types, such as a new scan being started or completed, a button being pressed, a device reporting an error or the existence of a specific metadata key. This allows the users to streamline the experience of the GUI and to focus on the data and the analysis, rather than on the GUI itself.

The default auto update only takes control over a single `BECFigure` widget, which is automatically added to the GUI instance. The update instance is accessible via the `bec.gui.auto_updates` object. The user can disable / enable the auto updates by setting the `enabled` attribute of the `bec.gui.auto_updates` object, e.g. 

```python
bec.gui.auto_updates.enabled = False
```

Without further customization, the auto update will automatically update the `BECFigure` widget based on the currently performed scan. The behaviour is determined by the `handler` method of the `AutoUpdate` class: 

````{dropdown} Auto Updates Handler
:icon: code-square
:animate: fade-in-slide-down
:open: 
```{literalinclude} ../../../bec_widgets/cli/auto_updates.py
:pyobject: AutoUpdates.handler
```
````

As shown, the default handler switches between different scan names and updates the `BECFigure` widget accordingly. If the scan is a line scan, the `simple_line_scan` update method is executed. 

````{dropdown} Auto Updates Simple Line Scan
:icon: code-square
:animate: fade-in-slide-down
:open: 
```{literalinclude} ../../../bec_widgets/cli/auto_updates.py
:pyobject: AutoUpdates.simple_line_scan
```
````

As it can be seen from the above snippet, the update method gets the default figure by calling the `get_default_figure` method. If the figure is not found, maybe because the user has deleted or closed it, no update is performed. If the figure is found, the scan info is used to extract the first reported device for the x axis and the first device of the monitored devices for the y axis. The y axis can also be set by the user using the `selected_device` attribute:

```python
bec.gui.auto_updates.selected_device = 'bpm4i'
```


````{dropdown} Auto Updates Code
:icon: code-square
:animate: fade-in-slide-down
```{literalinclude} ../../../bec_widgets/cli/auto_updates.py
```
````

## Custom Auto Updates
The beamline can customize their default behaviour through customized auto update classes. This can be achieved by modifying the class located in the beamline plugin repository: `<beamline_plugin>/bec_widgets/auto_updates.py`. The class should inherit from the `AutoUpdates` class and overwrite the `handler` method. 

```python
from bec_widgets.cli.auto_updates import AutoUpdates, ScanInfo


class PlotUpdate(AutoUpdates):
    create_default_dock = True
    enabled = True

    # def simple_line_scan(self, info: ScanInfo) -> None:
    #     """
    #     Simple line scan.
    #     """
    #     fig = self.get_default_figure()
    #     if not fig:
    #         return
    #     dev_x = info.scan_report_devices[0]
    #     dev_y = self.get_selected_device(info.monitored_devices, self.gui.selected_device)
    #     if not dev_y:
    #         return
    #     fig.clear_all()
    #     plt = fig.plot(x_name=dev_x, y_name=dev_y)
    #     plt.set(title=f"Custom Plot {info.scan_number}", x_label=dev_x, y_label=dev_y)

    def handler(self, info: ScanInfo) -> None:
        # EXAMPLES:
        # if info.scan_name == "line_scan" and info.scan_report_devices:
        #     self.simple_line_scan(info)
        #     return
        # if info.scan_name == "grid_scan" and info.scan_report_devices:
        #     self.run_grid_scan_update(info)
        #     return
        super().handler(info)
```