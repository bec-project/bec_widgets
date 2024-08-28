(developer.widget_development.widget_base_class)=

# BECWidget Base Class

When developing new widgets, it is crucial to ensure seamless integration with the BEC system. This is achieved by using
the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class, which provides essential functionalities and shortcuts to interact with various BEC services. In this
tutorial, we will explore the importance of this base class, the role of
the [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
mixin, and how these components work together to facilitate the development of powerful and responsive widgets.

## Understanding the `BECWidget` Base Class

The [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class is designed to serve as the foundation for all BEC-connected widgets. It ensures that your widget is properly
integrated with the BEC system by providing:

1. **Connection to BEC Services**: 
   [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget) includes the [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
   mixin, which handles all the necessary connections to BEC services such as the BEC server, device manager, scan
   control, and more.

2. **Qt Integration**:
   The [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
   base class also ensures that your widget is correctly integrated with Qt by requiring that it inherits from
   both [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
   and [`QWidget`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html). This combination allows your widget
   to leverage the full power of Qt for creating rich user interfaces while staying connected to the BEC ecosystem.

3. **Configuration Management**: The base class provides a `ConnectionConfig` model (based on Pydantic) that helps
   manage and validate the configuration of your widget. This configuration can be easily serialized to and from Python
   dictionaries, JSON, or YAML formats, allowing for persistent storage and retrieval of widget states.

4. **RPC Registration**: Widgets derived
   from [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
   are automatically registered with
   the [`RPCRegister`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.cli.rpc_register.RPCRegister.html#bec_widgets.cli.rpc_register.RPCRegister),
   enabling them to handle remote procedure calls (RPCs) efficiently. This allows the widget to be controlled remotely
   from the `BECIPythonClient` via CLI, providing powerful control and automation capabilities. For example, you can
   remotely adjust widget settings, start/stop operations, or query the widget’s status directly from the command line.

Here’s a basic example of a widget inheriting
from [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget):

```python
from bec_widgets.utils.bec_widget import BECWidget
from qtpy.QtWidgets import QWidget, QVBoxLayout


class MyWidget(BECWidget, QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QWidget.__init__(self, parent=parent)
        self.get_bec_shortcuts()  # Initialize BEC shortcuts
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Add more UI components here
        self.setLayout(layout)
```

### The Role of `BECConnector`

At the heart
of [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
is
the [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
mixin, which plays a crucial role in managing the connection between your widget and the BEC system.
The [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
provides several key functionalities:

1. **Client Initialization**: It initializes a `BECClient` instance if one isn't provided, ensuring your widget is
   connected to the BEC server. This client is central to all interactions with the BEC system.

2. **Task Management**:
   The [`submit_task`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector.submit_task)
   method allows for running tasks in separate threads, preventing long-running operations from blocking the main UI
   thread.

3. **Configuration Handling
   **: [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
   uses the `ConnectionConfig` model to manage the widget’s configuration, ensuring all parameters are validated and
   properly set up.

4. **RPC Registration**: Widgets are registered with
   the [`RPCRegister`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.cli.rpc_register.RPCRegister.html#bec-widgets-cli-rpc-register-rpcregister),
   allowing them to handle remote procedure calls effectively.

5. **Error Handling**: It includes utilities for handling errors gracefully within the Qt environment, ensuring that
   issues are reported to the user without crashing the application.

### Utilizing `get_bec_shortcuts`

One of the most powerful features of
the [`BECConnector`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_connector.BECConnector.html#bec_widgets.utils.bec_connector.BECConnector)
is the `get_bec_shortcuts` method. This method provides your widget with direct access to essential components of the
BEC system through convenient shortcuts:

1. **Device Manager (`self.dev`)**:
    - Access all devices registered with the BEC system. You can interact with devices, retrieve their status, and send
      commands directly through this shortcut.
   ```python
   # Moves 'motor1' to position 10
   self.dev["motor1"].move(10)  
   ```

2. **Scan Control (`self.scans`)**:
    - Control scans, initiate new ones, monitor progress, and manage their execution.
   ```python
   # Starts Line Scan from -10 to 10 in samx and -5 to 5 in samy
   self.scans.line_scan(self.dev.samx,-10,10,self.dev.samy,-5,5, steps=100, exp_time=0.001,relative=False)
   ```

3. **Queue Management (`self.queue`)**:
    - Manage the BEC scan queue, such as adding scans, checking status, or removing scans.
   ```python
   # Request abortion of the current scan queue
   self.queue.request_scan_abortion() 
   ```

4. **Scan Storage (`self.scan_storage`)**:
    - Access stored scan data for retrieval and analysis.
   ```python
   # Retrieve scan item for a specific scan ID
   self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)  
   ```

5. **Full BECClient Access (`self.client`)**:
    - Direct access to the BECClient instance, allowing for additional functionalities not covered by the shortcuts.
   ```python
   # Shutdown the BECClient
   self.client.shutdown()  
   ```

### Example: [`PositionerBox`](user.widgets.positioner_box) Widget

Let’s look at an example of a widget that leverages
the [`BECWidget`](https://bec.readthedocs.io/projects/bec-widgets/en/latest/api_reference/_autosummary/bec_widgets.utils.bec_widget.BECWidget.html#bec_widgets.utils.bec_widget.BECWidget)
base class and `get_bec_shortcuts`:

````{dropdown} View code: PositionerBox Widget
:icon: code-square
:animate: fade-in-slide-down
```{literalinclude} ../../../bec_widgets/widgets/positioner_box/positioner_box.py
:language: python
:pyobject: PositionerBox
```
````

In this widget:

- **Device Interaction**: The widget uses `self.dev` to interact with a positioner device, reading its state and
  updating the UI accordingly.

- **Scan and Queue Control**: Although not shown in this example, the widget could easily use `self.scans`
  and `self.queue` to manage scans related to the positioner or queue up new operations.

### Conclusion

The `BECWidget` base class and the `BECConnector` mixin are foundational components for creating widgets that seamlessly
integrate with the BEC system. By inheriting from `BECWidget`, you gain access to powerful connection management, task
handling, and configuration capabilities, as well as shortcuts that make interacting with BEC services straightforward
and efficient.

By leveraging these tools, you can focus on building the core functionality of your widget, confident that the
complexities of BEC integration are handled robustly and efficiently. In the next tutorial we will demonstrate
step-by-step how to create a custom widget using the `BECWidget` base class and explore advanced features for creating
responsive and interactive user interfaces.