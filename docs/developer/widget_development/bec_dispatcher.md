(developer.widget_development.bec_dispatcher)=

# BECDispatcher

## Overview

The [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
is a powerful tool that
simplifies the process of connecting Qt slots to message updates from the BEC server. It enables real-time communication
between your widget and the BEC server by listening to specific message channels and triggering callbacks when new data
is received.

This tool is especially useful for creating widgets that need to respond to dynamic data, such as device readbacks or
scan updates. By
using [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher),
you
can create callback functions that react to incoming messages and update your widget's state or perform other tasks
based on the data received.

## How It Works

When you create a widget that needs to respond to updates from the BEC server, you can use
the [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
to
connect specific Qt slots (callback functions) to message endpoints. These endpoints are defined within the BEC system
and represent specific channels of information (
e.g., [`device readback`](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_lib.endpoints.MessageEndpoints.html#bec_lib.endpoints.MessageEndpoints.device_readback),
[`scan_segment`](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_lib.endpoints.MessageEndpoints.html#bec_lib.endpoints.MessageEndpoints.scan_segment),
etc.).

### Step-by-Step Guide

1. **Create a Callback Function**: Define a function within your widget that will handle the data received from the BEC
   server. This function should usually accept two parameters: `msg_content` (the message content) and `metadata` (
   additional
   information about the message).

    ```python
    # Example for a callback function that updates a widget display based on motor readback data
   from qtpy.QtCore import Slot
   
    @Slot(dict, dict)
    def on_device_readback(self, msg_content, metadata):
        # Process the incoming data
        new_value = msg_content["signals"]['motor_x']["value"]
        # Update the widget's display or perform another action
        self.update_display(new_value)
    ```

2. **Connect the Slot to an Endpoint**: Use
   the [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
   to connect your callback function to a specific
   endpoint. The endpoint represents the type of data or message you're interested in.

    ```python
   from bec_lib.endpoints import MessageEndpoints
   
    self.bec_dispatcher.connect_slot(self.on_device_readback, MessageEndpoints.device_readback("motor_x"))
    ```

3. **Handle Incoming Data**: Your callback function will be triggered automatically whenever a new message is received
   on the connected endpoint. Use the data in `msg_content` to update your widget or perform other actions.

4. **Clean Up Connections**: If your widget is being destroyed or you no longer need to listen for updates, make sure to
   disconnect your slots from
   the [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
   to avoid memory or thread leaks.

    ```python
    self.bec_dispatcher.disconnect_slot(self.on_device_readback, MessageEndpoints.device_readback("motor_x"))
    ```

### Example: Motor Map Widget

The [`BECMotorMap`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.widgets.figure.plots.motor_map.motor_map.BECMotorMap.html#bec-widgets-widgets-figure-plots-motor-map-motor-map-becmotormap)
widget is a great example of
how [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
can be used to handle real-time data updates. This
widget listens for updates on specific motor positions and dynamically updates the motor map display.

Here's a breakdown of
how [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
is used in
the [`BECMotorMap`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.widgets.figure.plots.motor_map.motor_map.BECMotorMap.html#bec-widgets-widgets-figure-plots-motor-map-motor-map-becmotormap)
widget:

1. **Connecting to Motor Readbacks**:
   The widget connects to
   the [`device readback`](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_lib.endpoints.MessageEndpoints.html#bec_lib.endpoints.MessageEndpoints.device_readback)
   endpoints using
   the [`connect_slot`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher.connect_slot)
   method
   of [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher).
   This allows
   the widget to receive real-time updates about the motor positions.

```{literalinclude} ../../../bec_widgets/widgets/figure/plots/motor_map/motor_map.py
:language: python
:pyobject: BECMotorMap._connect_motor_to_slots
:dedent: 4
```

2. **Handling Readback Data**:
   The `on_device_readback` slot is called whenever new data is received from the motor readback. This slot processes
   the data and updates the motor map plot accordingly.

```{literalinclude} ../../../bec_widgets/widgets/figure/plots/motor_map/motor_map.py
:language: python
:pyobject: BECMotorMap.on_device_readback
:dedent: 4
```

3. **Updating the Plot**:
   The motor map plot is updated in response to the new data, providing a real-time visualization of the motor's
   position.

```{literalinclude} ../../../bec_widgets/widgets/figure/plots/motor_map/motor_map.py
:language: python
:pyobject: BECMotorMap._update_plot
:dedent: 4
```

4. **Disconnecting When No Longer Needed**:
   The widget ensures that connections are properly cleaned up when no longer needed.

```{literalinclude} ../../../bec_widgets/widgets/figure/plots/motor_map/motor_map.py
:language: python
:pyobject: BECMotorMap._update_plot
:dedent: 4
```

## Conclusion

The [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher)
is a key tool for developing interactive and responsive widgets within the BEC framework. By
leveraging this tool, you can create widgets that automatically respond to real-time data updates from the BEC server,
enhancing the interactivity and functionality of your user interface.

In next tutorials we will cover how to create a custom widget using the BECDispatcher and BECWidget base class.

```{note}
For more details on specific messages and endpoints, please refer to the [Message Endpoints Documentation](https://beamline-experiment-control.readthedocs.io/en/latest/api_reference/_autosummary/bec_lib.endpoints.MessageEndpoints.html#bec-lib-endpoints-messageendpoints).
```