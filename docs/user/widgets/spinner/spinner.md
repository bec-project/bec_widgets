(user.widgets.spinner)=

# Spinner Widget

````{tab} Overview

The [`SpinnerWidget`](/api_reference/_autosummary/bec_widgets.utility.spinner.spinner.SpinnerWidget) is a simple and versatile widget designed to indicate loading or movement within an application. It is commonly used to show that a device is in motion or that an operation is ongoing. The `SpinnerWidget` can be easily integrated into your GUI application either through direct code instantiation or by using `QtDesigner`.

## Key Features:
- **Loading Indicator**: Provides a visual indication of ongoing operations or device movement.
- **Smooth Animation**: Features a smooth, continuous spinning animation to catch the user's attention.
- **Easy Integration**: Can be added directly in code or through `QtDesigner`, making it adaptable to various use cases.
- **Customizable Appearance**: Automatically adapts to the application's theme, ensuring visual consistency.

````

````{tab} Examples

The `SpinnerWidget` can be embedded within a GUI application through direct code instantiation or by using `QtDesigner`. Below are examples demonstrating how to create and use the `SpinnerWidget`.

## Example 1 - Creating a Spinner Widget in Code

In this example, we demonstrate how to create a `SpinnerWidget` in code and start the spinner to indicate an ongoing operation.

```python
from qtpy.QtWidgets import QApplication, QMainWindow
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

app = QApplication([])

# Create a main window
window = QMainWindow()

# Create a SpinnerWidget instance
spinner = SpinnerWidget()

# Start the spinner
spinner.start()

# Set the spinner as the central widget
window.setCentralWidget(spinner)
window.show()

app.exec_()
```

## Example 2 - Stopping the Spinner

You can stop the spinner to indicate that an operation has completed.

```python
# Stop the spinner
spinner.stop()
```

## Example 3 - Integrating the Spinner Widget in QtDesigner

The `SpinnerWidget` can be added to your GUI layout using `QtDesigner`. Once added, you can assign the spinner to an attribute of your application, and then control the spinner using the `start` and `stop` methods, similar to the code examples above.

```python
# Example: Start the spinner in a QtDesigner-based application
self.spinner_widget.start()

# Example: Stop the spinner in a QtDesigner-based application
self.spinner_widget.stop()
```

````