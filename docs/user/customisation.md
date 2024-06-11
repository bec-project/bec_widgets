(user.customisation)=
# Customisation

## Leveraging BEC Widgets in custom GUI applications

BEC Widgets can be used to compose a complete Qt graphical application, along with
other QWidgets. The only requirement is to connect to BEC servers in order to get
data, or to interact with BEC components. This role is devoted to the BECDispatcher,
a singleton object which has to be instantiated **after the QApplication is created**.

A typical BEC Widgets custom application "main" entry point should follow the template
below: 

```
import argparse
import sys

from bec_widgets.utils.bec_dispatcher import BECDispatcher
from qtpy.QtWidgets import QApplication

# optional command line arguments processing
parser = argparse.ArgumentParser(description="...")
parser.add_argument( ...)
...
args = parser.parse_args()

# creation of the Qt application
app = QApplication([])

# creation of BEC Dispatcher
# /!\ important: after the QApplication has been instantiated
bec_dispatcher = BECDispatcher()
client = bec_dispatcher.client
client.start()

# (optional) processing of command line args,
# creation of a main window depending on the command line arguments (or not)
if args.xxx == "...":
    window = ...
 
# display of the main window and start of Qt event loop
window.show()
sys.exit(app.exec())
```

The main "window" object presents the layout of widgets to the user and allows
users to interact. BEC Widgets must be placed in the window:

```
from qtpy.QWidgets import QMainWindow
from bec_widgets.widgets import BECFigure

window = QMainWindow()
bec_figure = BECFigure(gui_id="my_gui_app_id")
window.setCentralWidget(bec_figure)

# prepare to plot samx motor vs bpm4i value
bec_figure.plot(x_name="samx", y_name="bpm4i")
```

In the example just above, the resulting application will show a plot of samx
positions on the horizontal axis, and beam intensity on the vertical axis
(when the next scan will be started).

It is important to ensure proper cleanup of the resources is done when application
quits:

```
def final_cleanup():
    bec_figure.clear_all()
    bec_figure.client.shutdown()

window.aboutToQuit.connect(final_cleanup)
```

Final example:

```
import sys
from qtpy.QtWidgets import QMainWindow, QApplication
from bec_widgets.widgets import BECFigure
from bec_widgets.utils.bec_dispatcher import BECDispatcher

# creation of the Qt application
app = QApplication([])

# creation of BEC Dispatcher
bec_dispatcher = BECDispatcher()
client = bec_dispatcher.client
client.start()

# creation of main window
window = QMainWindow()

# inserting BEC Widgets
bec_figure = BECFigure(parent=window, gui_id="my_gui_app_id")
window.setCentralWidget(bec_figure)

bec_figure.plot(x_name="samx", y_name="bpm4i")

# ensuring proper cleanup
def final_cleanup():
    bec_figure.clear_all()
    bec_figure.client.shutdown()

app.aboutToQuit.connect(final_cleanup)

# execution
window.show()
sys.exit(app.exec())
```

## Writing applications using Qt Designer

BEC Widgets are designed to be used with QtDesigner to quickly design GUI.

## Example of promoting widgets in Qt Designer

_Work in progress_

## Implementation of plugins into Qt Designer

_Work in progress_
