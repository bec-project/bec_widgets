(user.widgets.buttons)=

# Buttons Widgets

This section consolidates various custom buttons used within the BEC GUIs, facilitating the integration of these
controls into different layouts.

## Stop Button

**Purpose:**

The `Stop Button` provides a user interface control to immediately halt the execution of the current operation in the
BEC Client. It is designed for easy integration into any BEC GUI layout.

**Key Features:**

- **Immediate Termination:** Halts the execution of the current script or process.
- **Queue Management:** Clears any pending operations in the scan queue, ensuring the system is ready for new tasks.

**Code example:**

Integrating the `StopButton` into a BEC GUI layout is straightforward. The following example demonstrates how to embed
a `StopButton` within a GUI layout:

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import StopButton


class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the StopButton to the layout
        self.stop_button = StopButton()
        self.layout().addWidget(self.stop_button)
```