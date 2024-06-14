(developer.widgets.how_to_develop_a_widget)=
# How to Develop a Widget
This section provides a step-by-step guide on how to develop a new widget for BEC Widgets. We will develop a simple widget that allows you to press a button and specify a user-defined action. The general widget will be based on a [QPushButton](https://doc.qt.io/qt-6/qpushbutton.html) which we will extend to be capable of communicating with BEC through the interface provided by BEC Widgets.

## Button to start a scan
Developing a new widget in BEC Widgets is straightforward. Let's create a widget that allows a user to press a button and execute a `line_scan` in BEC. The proper location to create a new widget is either in the `bec_widgets/widgets` directory, or the beamline plugin widget direction, i.e. `csaxs_bec/bec_widgets`, depending on where your development takes place. 

### Step 1: Create a new widget class

We first create a simple class that inherits from the `QPushButton` class.
The following code snippet demonstrates how to create a new widget:

``` python
from qtpy.QtWidgets import QPushButton

class StartScanButton(QPushButton):
    def __init__(self, parent=None):
        QPushButton.__init__(self, parent=parent)
        # Connect the button to the on_click method
        self.clicked.connect(self.on_click)

    def on_click(self):
        pass
```
So far we have created the button, but we have not yet put any logic to the `on_click` event of the button.
Adding the functionality to be able to execute a scans will be tackled in the next step.

````{note} 
To make the button work as a standalone application, you can simply add the following lines at the end.
``` python
if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = StartScanButton()
    widget.show()
    sys.exit(app.exec_())
```
````


### Step 2: Connect with BEC, implement *on_click* functionality
To be able to start a scan, we need to communicate with BEC. This can be facilitated easily by inheriting additionally from [`BECConnector`](../../api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector). 
With the *BECConnector*, we will also have to pass the *client* ([BECClient](https://bec.readthedocs.io/en/latest/api_reference/_autosummary/bec_lib.client.BECClient.html)) and the *gui_id* (str) to init function of both, our *StartScanButton* widget and the `super().__init__(client=client, gui_id=gui_id)` call.
In the init of *BECConnector*, the client will be initialised and stored in `self.client`, which gives us access to the available scan objects via `self.client.scans`.

``` python
from qtpy.QtWidgets import QPushButton
from bec_widgets.utils import BECConnector

class StartScanButton(BECConnector, QPushButton):
    def __init__(self, parent=None, client:=None, gui_id=None):
        super().__init__(client=client, gui_id=gui_id)
        QPushButton.__init__(self, parent=parent)

        # Set a default scan command, args and kwargs
        self.scan_name = "line_scan"
        self.scan_args = (dev.samx, -5, 5)
        self.scan_kwargs = {"steps": 50, "exp_time": 0.1, "relative": True}
        # Set the text of the button to display the current scan name
        self.set_button_text()
        # Connect the button to the on_click method
        self.clicked.connect(self.on_click)

    def set_button_text(self):
        """Set the text of the button"""
        self.setText(f"Start {self.scan_name}")

    def run_command(self):
        """Run the scan command."""
        # Get the scan command from the scans library
        scan_command = getattr(self.client.scans, self.scan_name)
        # Run the scan command
        scan_report = scan_command(*self.scan_args, **self.scan_kwargs)
        # Wait for the scan to finish
        scan_report.wait()

    def on_click(self):
        """Start a line scan"""
        self.run_command()
```

```{note}
For the args and kwargs of the scan command, we are using the same syntax as in the client: `dev.samx` is not a string but the same object as in the client.
```
In the *run_command* method, we retrieve the scan object from the client by its name, and execute the method with all *args* and *kwargs* that we have set.
The current implementation of *run_command* is a blocking call due to `scan_report.wait()`,  which is not ideal for a GUI application since it freezes the GUI. We will adress this in the next step.

### Step 3: Improving the widget interactivity
To not freeze the GUI, we need to run the scan command in a separate thread. We can either use [QThreads](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html) or the Python [threading module](https://docs.python.org/3/library/threading.html#thread-objects). In this example, we will use the Python threading module. In addition, we add a method `update_style` to change the style of the button to indicate to the user that the scan is running. We also extend the cleanup procedure of `BECConnector` to ensure that the thread is stopped when the widget is closed. This is good practice to avoid having threads running in the background when the widget is closed. 

``` python

def update_style(self, mode: Literal["ready", "running"]):
    """Update the style of the button based on the mode.

    Args:
        mode (Literal["ready", "running"): The mode of the button.
    """
    if mode == "ready":
        self.setStyleSheet(
            "background-color: #4CAF50; color: white; font-size: 16px; padding: 10px 24px;"
        )
    elif mode == "running":
        self.setStyleSheet(
            "background-color: #808080; color: white; font-size: 16px; padding: 10px 24px;"
        )

def run_command(self):
    """Run the scan command."""
    # Switch the style of the button
    self.update_style("running")
    # Disable the buttom while the scan is running
    self.setEnabled(False)
    # Get the scan command from the scans library
    scan_command = getattr(self.scans, self.scan_name)
    # Run the scan command
    scan_report = scan_command(*self.scan_args, **self.scan_kwargs)
    # Wait for the scan to finish
    scan_report.wait()
    # Reactivate the button
    self.setEnabled(True)
    # Switch the style of the button back to ready
    self.update_style("ready")

def on_click(self):
    """Start a line scan"""
    thread = threading.Thread(target=self.run_command)
    thread.start()

def cleanup(self):
    """Cleanup the widget"""
    # stop thread
    # stop the thread or if this is implemented via QThread, ensure stopping of QThread.
    # Ideally, the BECConnector should take care of this automatically.
    # Important to call super().cleanup() to ensure that the cleanup of the BECConnector is also called
    super().cleanup()
```
We now added started the scan in a separate thread, which allows the GUI to remain responsive. We also added a method to change the style of the button to indicate to the user that the scan is running. The cleanup method ensures that the thread is stopped when the widget is closed. In a last step, we know like to make the scan command configurable.

### Step 4: Make the scan command configurable
In order to make the scan comman configurable, we implement a method `set_scan_command` which allows the user to set the scan command, arguments and keyword arguments.
This method should also become available through the RPC interface of BEC Widgets, so we add the class attribute `USER_ACCESS` which is a list of strings with functions that should become available for the CLI. 

``` python
    def set_scan_command(
        self, scan_name: str, args: tuple, kwargs: dict
    ): 
        """Set the scan command to run.

        Args:
            scan_name (str): The name of the scan command.
            args (tuple): The arguments for the scan command.
            kwargs (dict): The keyword arguments for the scan command.
        """
        # check if scan_command starts with scans.
        if not getattr(self.client.scans, scan_name):
            raise ValueError(
                f"The scan type must be implemented in the scan library of BEC, received {scan_name}"
            )
        self.scan_name = scan_name
        self.scan_args = args
        self.scan_kwargs = kwargs
        self.set_button_text()
```

### Step 5: Generate client interface for RPC 
We have now prepared the widget which is fully functional as a standalone widget. But we also want to make it available to the BEC command-line-interface (CLI), for which we prepared the **USER_ACCESS** class attribute.
The communication between the BEC IPythonClient and the widget is done vie the RPC interface of BEC Widgets. 
For this, we need to run the `bec_widgets.cli.generate_cli` script to generate the CLI interface.

``` bash
python bec_widgets.cli.generate_cli --core
# alternatively use the entry point from BEC Widgets
bw-generate-cli
```

This will generate a new client with all relevant methods in [`bec_widgets.cli.client.py`](../../api_reference/_autosummary/bec_widgets.bec_widgets.cli.client.rst). 
The last step is to make the RPCWidgetHandler class aware of the widget, which means to add the name of the widget to the widgets list in the [`RPCWidgetHandler`](../../api_reference/_autosummary/bec_widgets.bec_widgets.cli.rpc_widget_handler.RPCWidgetHandler.rst) class. 

````{dropdown} View code: RPCWidgetHandler class
:icon: code-square
:animate: fade-in-slide-down

```{literalinclude} ../../../bec_widgets/cli/rpc_widget_handler.py
:language: python
:pyobject: RPCWidgetHandler
```
````

With this, we have a fully functional widget that allows the user to start a scan with a button. The scan command, arguments and keyword arguments can be set by the user. 
The full code is shown once again below:

````{dropdown} View code: Full code of the StartScanButton widget
:icon: code-square
:animate: fade-in-slide-down

``` 
import threading
from typing import Literal

from qtpy.QtWidgets import QPushButton

from bec_widgets.utils import BECConnector


class StartScanButton(BECConnector, QPushButton):
    """A button to start a line scan.

    Args:
        parent: The parent widget.
        client (BECClient): The BEC client.
        gui_id (str): The unique ID of the widget.
    """

    USER_ACCESS = ["set_scan_command"]

    def __init__(self, parent=None, client=None, gui_id=None):
        super().__init__(client=client, gui_id=gui_id)
        QPushButton.__init__(self, parent=parent)

        # Set the scan command to None
        self.scan_command = None
        # Set default scan command
        self.scan_name = "line_scan"
        self.scan_args = (dev.samx, -5, 5)
        self.scan_kwargs = {"steps": 50, "exp_time": 0.1, "relative": True}
        # Set the text of the button
        self.set_button_text()
        # Set the style of the button
        self.update_style("ready")
        # Connect the button to the on_click method
        self.clicked.connect(self.on_click)

    def update_style(self, mode: Literal["ready", "running"]):
        """Update the style of the button based on the mode.

        Args:
            mode (Literal["ready", "running"): The mode of the button.
        """
        if mode == "ready":
            self.setStyleSheet(
                "background-color: #4CAF50; color: white; font-size: 16px; padding: 10px 24px;"
            )
        elif mode == "running":
            self.setStyleSheet(
                "background-color: #808080; color: white; font-size: 16px; padding: 10px 24px;"
            )

    def set_button_text(self):
        """Set the text of the button."""
        self.setText(f"Start {self.scan_name}")

    def set_scan_command(self, scan_name: str, args: tuple, kwargs: dict):
        """Set the scan command to run.

        Args:
            scan_name (str): The name of the scan command.
            args (tuple): The arguments for the scan command.
            kwargs (dict): The keyword arguments for the scan command.
        """
        # check if scan_command starts with scans.
        if not getattr(self.client.scans, scan_name):
            raise ValueError(
                f"The scan type must be implemented in the scan library of BEC, received {scan_name}"
            )
        self.scan_name = scan_name
        self.scan_args = args
        self.scan_kwargs = kwargs
        self.set_button_text()

    def run_command(self):
        """Run the scan command."""
        # Switch the style of the button
        self.update_style("running")
        # Disable the buttom while the scan is running
        self.setEnabled(False)
        # Get the scan command from the scans library
        scan_command = getattr(self.scans, self.scan_name)
        # Run the scan command
        scan_report = scan_command(*self.scan_args, **self.scan_kwargs)
        # Wait for the scan to finish
        scan_report.wait()
        # Reactivate the button
        self.setEnabled(True)
        # Switch the style of the button back to ready
        self.update_style("ready")

    def on_click(self):
        """Start a line scan"""
        thread = threading.Thread(target=self.run_command)
        thread.start()

    def cleanup(self):
        """Cleanup the widget"""
        # stop thread
        # stop the thread or if this is implemented via QThread, ensure stopping of QThread.
        # Ideally, the BECConnector should take care of this automatically.
        # Important to call super().cleanup() to ensure that the cleanup of the BECConnector is also called
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = StartScanButton()
    widget.show()
    sys.exit(app.exec_())


```
````

### Step 6: Write a test for the widget
We highly recommend writing tests for the widget to ensure that they work as expected. This allows to run the tests automatically in a CI/CD pipeline and to ensure that the widget works as expected not only now but als in the future.
The following code snippet shows an example to test the set_scan_command from the `StartScanButton` widget.
``` python 
import pytest

from bec_widgets.widgets.start_scan_button import StartScanButton

from .client_mocks import mocked_client


@pytest.fixture
def test_scan_button(qtbot, mocked_client):
    widget = StartScanButton(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_set_scan_command(test_scan_button):
    """Test the set_scan_command function."""
    test_scan_button.set_scan_command(
        scan_name="grid_scan",
        args=(dev.samx, -5, 5, 10, dev.samy, -5, 5, 20),
        kwargs={"exp_time": 0.1, "relative": True},
    )
    # Check first if all parameter have been properly set
    assert test_scan_button.scan_name == "grid_scan"
    assert test_scan_button.scan_args == (dev.samx, -5, 5, 10, dev.samy, -5, 5, 20)
    assert test_scan_button.scan_kwargs == {"exp_time": 0.1, "relative": True}
    # Next, we check if the displayed text of the button has been updated
    # We use the .text() method from the QPushButton class to retrieve the text displayed
    assert test_scan_button.text() == "Start grid_scan"
```