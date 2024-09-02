(user.widgets.buttons_queue)=

# Queue Control Buttons

`````{tab} Overview
This section consolidates various buttons designed to manage the BEC scan queue, providing essential controls for operations like stopping, resuming, aborting, and resetting the scan queue.

## Stop Button

The `Stop Button` is a specialized control that provides an immediate interface to halt ongoing operations in the BEC Client. It is essential for scenarios where operations need to be terminated quickly, such as in the case of an error or when an operation needs to be interrupted by the user.

**Key Features:**
- **Immediate Termination**: Instantly halts the execution of the current script or process.
- **Queue Management**: Stops the current scan or the entire scan queue.

## Resume Button

The `Resume Button` allows users to continue the paused scan queue. It’s useful in scenarios where the scan queue has been halted and needs to be resumed.

**Key Features:**
- **Queue Continuation**: Resumes the scan queue after a pause.
- **Toolbar and Button Options**: Can be configured as a toolbar button or a standard push button.

## Abort Button

The `Abort Button` provides an interface to abort a specific scan or the entire queue. This is useful for scenarios where an operation needs to be terminated but in a controlled manner.

**Key Features:**
- **Scan Abortion**: Aborts the current scan or a specific scan in the queue.
- **Toolbar and Button Options**: Can be configured as a toolbar button or a standard push button.

## Reset Queue Button

The `Reset Button` is used to reset the scan queue. It prompts the user for confirmation before resetting, ensuring that the action is intentional.

**Key Features:**
- **Queue Reset**: Resets the entire scan queue.
- **Confirmation Dialog**: Prompts the user to confirm the reset action to prevent accidental resets.
- **Toolbar and Button Options**: Can be configured as a toolbar button or a standard push button.
`````

````{tab} Examples

Integrating these buttons into a BEC GUI layout is straightforward. The following examples demonstrate how to embed these buttons within a custom GUI layout using `QtWidgets`.

### Example 1 - Embedding a Stop Button in a Custom GUI Layout

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import StopButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the StopButton to the layout
        self.stop_button = StopButton()
        self.layout().addWidget(self.stop_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

### Example 2 - Embedding a Resume Button in a Custom GUI Layout

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import ResumeButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))  # Initialize the layout for the widget

        # Create and add the ResumeButton to the layout
        self.resume_button = ResumeButton()
        self.layout().addWidget(self.resume_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

### Example 3 - Adding an Abort Button

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import AbortButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the AbortButton to the layout
        self.abort_button = AbortButton()
        self.layout().addWidget(self.abort_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```

### Example 4 - Adding a Reset Queue Button

```python
from qtpy.QtWidgets import QWidget, QVBoxLayout
from bec_widgets.widgets.buttons import ResetButton

class MyGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout(self))

        # Create and add the ResetButton to the layout
        self.reset_button = ResetButton()
        self.layout().addWidget(self.reset_button)

# Example of how this custom GUI might be used:
my_gui = MyGui()
my_gui.show()
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.StopButton.rst
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ResumeButton.rst
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.AbortButton.rst
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.ResetButton.rst
```
````
