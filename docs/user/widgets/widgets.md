(user.widgets)=
# Widgets

BEC Widgets offers a range of tools designed to make data visualization in beamline experiments easier and more
interactive. These widgets help users better understand their data by providing clear, intuitive displays that enhance
the overall experience.

## Widget Containers

Serves as containers to organise and display other widgets.

````{grid} 3
:gutter: 2

```{grid-item-card}  BEC Dock Area
:link: user.widgets.bec_dock_area
:link-type: ref
:img-top: /assets/widget_screenshots/dock_area.png

Quickly build dynamic GUI.

```
````

## Plotting Widgets

Plotting widgets are used to display data in a graphical format.

````{grid} 3
:gutter: 2

```{grid-item-card}  Waveform Widget
:link: user.widgets.waveform_widget
:link-type: ref
:img-top: /assets/widget_screenshots/waveform_widget.png

Display 1D detector signals.
```

```{grid-item-card}  Multi Waveform Widget
:link: user.widgets.multi_waveform_widget
:link-type: ref
:img-top: /assets/widget_screenshots/multi_waveform.png

Display multiple 1D waveforms.
```

```{grid-item-card}  Scatter Waveform Widget
:link: user.widgets.scatter_waveform_widget
:link-type: ref
:img-top: /assets/widget_screenshots/scatter_waveform.png

Display a 1D waveforms with a third device on the z-axis.
```

```{grid-item-card}  Image Widget
:link: user.widgets.image_widget
:link-type: ref
:img-top: /assets/widget_screenshots/image_widget.png

Display signal from 2D detector.
```

```{grid-item-card}  Motor Map Widget
:link: user.widgets.motor_map
:link-type: ref
:img-top: /assets/widget_screenshots/motor_map_widget.png

Track position for motors.
```

````

## Device Control Widgets

Control and monitor devices/scan in the BEC environment.

````{grid} 3
:gutter: 2

```{grid-item-card}  Scan Control Widget
:link: user.widgets.scan_control
:link-type: ref
:img-top: /assets/widget_screenshots/scan_controller.png

Launch scans.
```

```{grid-item-card}  Device Browser
:link: user.widgets.device_browser
:link-type: ref
:img-top: /assets/widget_screenshots/device_browser.png

Find and drag devices.
```

```{grid-item-card}  Positioner Box
:link: user.widgets.positioner_box
:link-type: ref
:img-top: /assets/widget_screenshots/device_box.png

Control individual device.
```

```{grid-item-card}  Positioner Box 2D
:link: user.widgets.positioner_box_2d
:link-type: ref
:img-top: /assets/widget_screenshots/positioner_box_2d.png

Control two individual devices on perpendicular axes.
```

```{grid-item-card} Ring Progress Bar 
:link: user.widgets.ring_progress_bar
:link-type: ref
:img-top: /assets/widget_screenshots/ring_progress_bar.png

Nested progress bar.
```

````

## BEC Service Widgets

Visualise the status of BEC services.

````{grid} 3
:gutter: 2

```{grid-item-card} BEC Status Box
:link: user.widgets.bec_status_box
:link-type: ref
:img-top: /assets/widget_screenshots/status_box.png

Display status of BEC services.
```

```{grid-item-card} BEC Queue Table 
:link: user.widgets.bec_queue
:link-type: ref
:img-top: /assets/widget_screenshots/queue.png

Display current scan queue.
```
````

## BEC Utility Widgets

Various utility widgets to enhance user experience.

````{grid} 3
:gutter: 2

```{grid-item-card} Buttons Appearance
:link: user.widgets.buttons_appearance
:link-type: ref
:img-top: /assets/widget_screenshots/buttons.png

Various buttons which manage the appearance of the BEC GUI.
```

```{grid-item-card} Buttons Queue
:link: user.widgets.buttons_queue
:link-type: ref
:img-top: /assets/widget_screenshots/buttons_queue.png

Various buttons which manage the control of the BEC Queue.
```

```{grid-item-card} Device Input Widgets
:link: user.widgets.device_input
:link-type: ref
:img-top: /assets/widget_screenshots/device_inputs.png

Choose individual device from current session.
```

```{grid-item-card} Signal Input Widgets
:link: user.widgets.signal_input
:link-type: ref
:img-top: /assets/widget_screenshots/signal_inputs.png

Choose individual signals available for a selected device.
```

```{grid-item-card} Text Box Widget
:link: user.widgets.text_box
:link-type: ref
:img-top: /assets/widget_screenshots/text_box.png

Display custom text or HTML content.
```

```{grid-item-card} Website Widget
:link: user.widgets.website
:link-type: ref
:img-top: /assets/widget_screenshots/website.png

Display website content.
```

```{grid-item-card} Toogle Widget
:link: user.widgets.toggle
:link-type: ref
:img-top: /assets/widget_screenshots/toggle.png

Angular like toggle switch.
```

```{grid-item-card} Spinner 
:link: user.widgets.spinner
:link-type: ref
:img-top: /assets/widget_screenshots/spinner.gif

Display spinner widget for loading or device movement.
```

```{grid-item-card} BEC Progressbar 
:link: user.widgets.bec_progressbar
:link-type: ref
:img-top: /assets/widget_screenshots/bec_progressbar.png

Modern progress bar for BEC.
```

```{grid-item-card} Position Indicator
:link: user.widgets.position_indicator
:link-type: ref
:img-top: /assets/widget_screenshots/position_indicator.png

Display position of motor withing its limits.
```

```{grid-item-card} LMFit Dialog
:link: user.widgets.lmfit_dialog
:link-type: ref
:img-top: /assets/widget_screenshots/lmfit_dialog.png

Display DAP summaries of LMFit models in a window.
```

```{grid-item-card} DAP ComboBox
:link: user.widgets.dap_combo_box
:link-type: ref
:img-top: /assets/widget_screenshots/dap_combo_box.png

Select DAP model from a list of DAP processes.
```

```{grid-item-card} Log panel widget
:link: user.widgets.log_panel
:link-type: ref
:img-top: /user/widgets/log_panel/logpanel.png

Show and filter logs from the BEC Redis server.
```
````

```{toctree}
---
maxdepth: 1
hidden: true
---

dock_area/bec_dock_area.md
waveform/waveform_widget.md
scatter_waveform/scatter_waveform.md
multi_waveform/multi_waveform.md
image/image_widget.md
motor_map/motor_map.md
scan_control/scan_control.md
progress_bar/ring_progress_bar.md
bec_status_box/bec_status_box.md
queue/queue.md
buttons_appearance/buttons_appearance.md
buttons_queue/button_queue.md
device_browser/device_browser.md
positioner_box/positioner_box.md
positioner_box/positioner_box_2d.md
text_box/text_box.md
website/website.md
toggle/toggle.md
spinner/spinner.md
bec_progressbar/bec_progressbar.md
device_input/device_input.md
signal_input/signal_input.md
position_indicator/position_indicator.md
lmfit_dialog/lmfit_dialog.md
dap_combo_box/dap_combo_box.md
games/games.md
log_panel/log_panel.md

```