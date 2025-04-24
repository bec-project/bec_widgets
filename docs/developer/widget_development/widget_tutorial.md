(developer.widget_development.widget_tutorial)=

# Tutorial: Creating a New BEC-Connected Widget

In this tutorial, we'll create a BEC-connected widget that allows you to control a motor by setting its position. The
widget will demonstrate how to retrieve data from BEC, prompt an action in BEC (like moving a motor), and expose an RPC
interface for remote control. By the end of this tutorial, you'll have a functional widget that can interact with the
BEC system both through a graphical interface and via command-line control.

We'll break the tutorial into the following steps:

1. **Creating the Basic Widget Layout**: We’ll design a simple UI with a `QLabel`, `QDoubleSpinBox`, and
   a `QPushButton`.
2. **Connecting to BEC**: We’ll integrate our widget with the BEC system using
   the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
   base class
   and [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher).
3. **Implementing RPC for Remote Control**: We’ll set up an RPC interface to allow remote control of the widget via CLI.
4. **Running the Widget**: We’ll create a small script to run the widget in a `QApplication`.

## Step 1: Creating the Basic Widget Layout

First, let's start by creating the basic layout of our widget. We’ll add a `QLabel` to display the current coordinates
of the motor, a `QDoubleSpinBox` to input the desired coordinates, and a `QPushButton` to initiate the motor movement.

```python
from qtpy.QtWidgets import QWidget, QLabel, QDoubleSpinBox, QPushButton, QVBoxLayout


class MotorControlWidget(QWidget):
    def __init__(self, parent=None, motor_name: str = ""):
        super().__init__(parent)

        self.motor_name = motor_name

        # Initialize UI elements
        self.label_top = QLabel("Current Position:", self)
        self.label = QLabel(f"{self.motor_name} - N/A", self)
        self.spin_box = QDoubleSpinBox(self)
        self.spin_box.setRange(-10000, 10000)
        self.spin_box.setDecimals(3)
        self.spin_box.setSingleStep(0.1)

        self.move_button = QPushButton("Move Motor", self)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label_top)
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)
        layout.addWidget(self.move_button)
        self.setLayout(layout)

        # Connect button click to move motor
        self.move_button.clicked.connect(self.move_motor)

    def move_motor(self):
        # Placeholder method for motor movement
        print(f"Moving motor {self.motor_name} to {self.spin_box.value()}")
```

## Step 2: Connecting to BEC

Now that we have the basic layout, let's connect our widget to the BEC system using
the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class
and [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher).
We’ll modify the widget to inherit
from [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget),
pass the motor name to the widget, and use `get_bec_shortcuts` to access BEC services.

```python
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QDoubleSpinBox, QLabel, QPushButton, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class MotorControlWidget(BECWidget, QWidget):

    def __init__(self, parent=None, motor_name: str = "", **kwargs):
        super().__init__(parent=parent, **kwargs)

        self.motor_name = motor_name

        # Initialize BEC shortcuts
        self.get_bec_shortcuts()

        # Initialize UI elements
        self.label_top = QLabel(f"Current Position:", self)
        self.label = QLabel(f"{self.motor_name} - N/A", self)
        self.spin_box = QDoubleSpinBox(self)
        self.spin_box.setRange(-10000, 10000)
        self.spin_box.setDecimals(3)
        self.spin_box.setSingleStep(0.1)

        self.move_button = QPushButton("Move Motor", self)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label_top)
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)
        layout.addWidget(self.move_button)
        self.setLayout(layout)

        # Connect button click to move motor
        self.move_button.clicked.connect(self.move_motor)

        # Register BECDispatcher to listen for motor position updates
        self.bec_dispatcher.connect_slot(
            self.on_motor_update, MessageEndpoints.device_readback(self.motor_name)
        )

    @SafeSlot()
    def move_motor(self):
        target_position = self.spin_box.value()
        self.dev[self.motor_name].move(target_position)
        print(f"Commanding motor {self.motor_name} to move to {target_position}")

    @SafeSlot(dict, dict)
    def on_motor_update(self, msg_content, metadata):
        position = msg_content.get("signals", {}).get(self.motor_name, {}).get("value", "N/A")
        self.label.setText(f"{self.motor_name} : {round(position, 2)}")
```

## Step 3: Implementing RPC for Remote Control

Next, we’ll set up an RPC interface to allow remote control of the widget from the command line via
the `BECIPythonClient`. We’ll expose a method that allows changing the motor name through CLI commands.

```python
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QDoubleSpinBox, QLabel, QPushButton, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class MotorControlWidget(BECWidget, QWidget):
    USER_ACCESS = ["change_motor"]

    def __init__(self, parent=None, motor_name: str = "", **kwargs):
        super().__init__(parent=parent, **kwargs)

        self.motor_name = motor_name

        # Initialize BEC shortcuts
        self.get_bec_shortcuts()

        # Initialize UI elements
        self.label_top = QLabel(f"Current Position:", self)
        self.label = QLabel(f"{self.motor_name} - N/A", self)
        self.spin_box = QDoubleSpinBox(self)
        self.spin_box.setRange(-10000, 10000)
        self.spin_box.setDecimals(3)
        self.spin_box.setSingleStep(0.1)

        self.move_button = QPushButton("Move Motor", self)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label_top)
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)
        layout.addWidget(self.move_button)
        self.setLayout(layout)

        # Connect button click to move motor
        self.move_button.clicked.connect(self.move_motor)

        # Register BECDispatcher to listen for motor position updates
        self.bec_dispatcher.connect_slot(
            self.on_motor_update, MessageEndpoints.device_readback(self.motor_name)
        )

    @SafeSlot()
    def move_motor(self):
        target_position = self.spin_box.value()
        self.dev[self.motor_name].move(target_position)
        print(f"Commanding motor {self.motor_name} to move to {target_position}")

    @SafeSlot(dict, dict)
    def on_motor_update(self, msg_content, metadata):
        position = msg_content.get("signals", {}).get(self.motor_name, {}).get("value", "N/A")
        self.label.setText(f"{self.motor_name} : {round(position, 2)}")

    def change_motor(self, motor_name):
        """RPC method to change the motor being controlled."""
        # Disconnect from previous motor
        self.bec_dispatcher.disconnect_slot(
            self.on_motor_update, MessageEndpoints.device_readback(self.motor_name)
        )
        # Update motor name and reconnect to new motor
        self.motor_name = motor_name
        self.label.setText(f"{self.motor_name} - N/A")
        self.bec_dispatcher.connect_slot(
            self.on_motor_update, MessageEndpoints.device_readback(self.motor_name)
        )
```

```{warning}
After implementing an RPC method, you must run the `bw-generate-cli --target <your plugin repo name>` script to update the CLI commands for `BECIPythonClient`, e.g. `bw-generate-cli --target csaxs_bec`. This script generates the necessary command-line interface bindings, ensuring that your RPC method can be accessed and controlled remotely.
```

```{note}
In this tutorial, we used the @SafeSlot decorator from BEC Widgets to mark methods as slots for signals. This decorator ensures that the connected methods are treated as slots by the Qt framework, which can be connected to signals. It’s a best practice to use the @SafeSlot decorator to clearly indicate which methods are intended to handle signal events with correct argument signatures. @SafeSlot also provides error handling and logging capabilities, making it more robust and easier to debug.
```

## Step 4: Running the Widget

Finally, let’s create a script to run our widget within a `QApplication`. This script can be used to test the widget
independently. You can pass different motor names to control different motors using the same widget class.

```python
import sys
from qtpy.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MotorControlWidget(motor_name='samx')
    widget.show()
    sys.exit(app.exec_())
```

## Conclusion

In this tutorial, we've created a BEC-connected widget that allows you to control a motor. We started by designing the
UI, then connected it to the BEC system using
the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class
and [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher).
We also implemented an RPC interface, allowing remote control of the widget through the CLI. Finally, we tested our
widget by running it in a `QApplication`.

This widget demonstrates a simplified version of the [`PositionerBox`](user.widgets.positioner_box), showcasing the
power and flexibility of
the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class
and [`BECDispatcher`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher.html#bec_widgets.utils.bec_dispatcher.BECDispatcher),
making it easy to integrate with the BEC system and enabling robust, interactive control of devices directly from the
GUI or the command line.