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

```{grid-item-card}  BEC Figure
:link: user.widgets.bec_figure
:link-type: ref
:img-top: /assets/widget_screenshots/figure.png

Display 1D and 2D data.
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

```{grid-item-card} Service Buttons
:link: user.widgets.buttons
:link-type: ref
:img-top: /assets/widget_screenshots/buttons.png

Various service buttons.
```

```{grid-item-card} Device Input Widgets
:link: user.widgets.device_input
:link-type: ref
:img-top: /assets/widget_screenshots/device_inputs.png

Choose individual device from current session.
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

```{grid-item-card} Position Indicator
:link: user.widgets.position_indicator
:link-type: ref
:img-top: /assets/widget_screenshots/position_indicator.png

Display position of motor withing its limits.
```
````

```{toctree}
---
maxdepth: 1
hidden: true
---

dock_area/bec_dock_area.md
bec_figure/bec_figure.md
waveform/waveform_widget.md
image/image_widget.md
motor_map/motor_map.md
scan_control/scan_control.md
progress_bar/ring_progress_bar.md
bec_status_box/bec_status_box.md
queue/queue.md
buttons/buttons.md
device_browser/device_browser.md
positioner_box/positioner_box.md
text_box/text_box.md
website/website.md
toggle/toggle.md
spinner/spinner.md
device_input/device_input.md
position_indicator/position_indicator.md

```