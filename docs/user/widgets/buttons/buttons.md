(user.widgets.buttons)=

# Service Buttons

````{tab} Overview

This section consolidates various custom buttons used within the BEC GUIs, providing essential controls for managing operations and processes. These buttons are designed for easy integration into different layouts within the BEC environment, allowing users to embed functional controls into their applications seamlessly.

## Stop Button

The `Stop Button` is a specialized control that provides an immediate interface to halt ongoing operations in the BEC Client. It is essential for scenarios where operations need to be terminated quickly, such as in the case of an error or when an operation needs to be interrupted by the user.

**Key Features:**
- **Immediate Termination**: Instantly halts the execution of the current script or process.
- **Queue Management**: Clears any pending operations in the scan queue, ensuring the system is reset and ready for new tasks.

````

````{tab} Examples

Integrating the `StopButton` into a BEC GUI layout is straightforward. The following example demonstrates how to embed a `StopButton` within a custom GUI layout using `QtWidgets`.

## Example 1 - Embedding a Stop Button in a Custom GUI Layout

This example shows how to create a simple GUI layout with a `StopButton` integrated, allowing the user to halt processes directly from the interface.

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

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.StopButton.rst
```
````