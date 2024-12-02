(user.widgets.user_script_widget)=
# User Script Widget

````{tab} Overview

The [`UserScriptWidget`] is designed to allow users to run their user-defined scripts directly from a BEC GUI. This widget lists all available user scripts and allows users to execute them with a single click. The widget also provides an interface to open a VSCode editor to modify the files hosting the user scripts. This widget is particularly useful to provide a user-friendly interface to run custom scripts to users without using the command line. We note that the scripts are executed in a BEC client that does not share the full namespace with the BEC IPython kernel.

## Key Features:
- **User Script Execution**: Run user-defined scripts directly from the BEC GUI.
- **VSCode Integration**: Open the VSCode editor to modify the files hosting the user scripts.


````{tab} Examples

The `UserScriptWidget` widget can be integrated within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `BECDesigner`. Below are examples demonstrating how to create and use the `BECStatusBox` widget.

## Example 1 - Adding BEC Status Box to BECDockArea

In this example, we demonstrate how to add a `BECStatusBox` widget to a `BECDockArea`, allowing users to monitor the status of BEC processes directly from the GUI.

```python
# Add a new dock with a BECStatusBox widget
user_script = gui.add_dock().add_widget("UserScriptWidget")
```

```{hint}
The widget will automatically display the list of available user scripts. Users can click on the script name to execute it.
```
````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.UserScriptWidget.rst
```
````