(developer.widget_development)=

# Widget Development
This section provides an introduction to the building blocks of BEC Widgets: widgets. Widgets are the basic components of the graphical user interface (GUI) and are used to create larger applications. We will cover key topics such as how to develop new widgets or how to customise existing widgets. For details on the already available widgets and their usage, please refer to user section about [widgets](#user.widgets). 

To facilitate the development of new widgets, integrated into the BEC framework, we provide two main base classes: `BECWidget` and its parent class `BECDispatcher`. The `BECDispatcher` class is responsible for managing the communication between widgets and the BEC framework. The `BECWidget` class is the base class for all widgets and provides the basic functionality for creating and managing widgets. Leveraging these classes, you can rapidly develop new widgets that are responsive and interactive. 

A very simple "Hello World" example of a widget can be seen below:

````{dropdown} View code: Hello World Widget
:icon: code-square
:animate: fade-in-slide-down

```python
from qtpy.QtWidgets import QLabel, QWidget

from bec_widgets.utils.bec_widget import BECWidget


class HelloWorldWidget(BECWidget, QWidget):
    def __init__(
        self, parent: QWidget | None = None, client=None, gui_id: str | None = None
    ) -> None:
        # Initialize the BECWidget and QWidget
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)

        # Create a label with the text "Hello World"
        self.label = QLabel(self)
        self.label.setText("Hello World")


# Run the widget as a standalone application
if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = HelloWorldWidget()
    w.show()
    sys.exit(app.exec_())
```
````

The following sections will provide more details on how to develop new widgets and how to leverage the `BECDispatcher` and `BECWidget` classes to create interactive and responsive widgets.

```{toctree}
---
maxdepth: 2
hidden: false
---

bec_dispatcher
widget_base_class
widget_tutorial
tutorial_tests
```