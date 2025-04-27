(user.plugin_widgets)=
# Plugin repository widgets

## Adding widgets to the plugin repository

Widgets can be created by users and added to a beamline plugin repository, then they can be used in
all the same ways as built-in widgets. To make this work, the widget author should follow a few
simple guidelines.

Widgets should be added in `plugin_repo.bec_widgets.widgets`. They may be added in submodules. If
so, please make sure that these are properly defined python submodules with `__init__.py` files, so
that the widgets are discoverable.

### Preparing a widget to be a plugin

- make sure that the widget class inherits from both `BECWidget` as well as `QWidget` or  a subclass
  of it, such as `QComboBox` or `QLineEdit`.
- make sure it initialises each of these superclasses in its `__init__()` method, and passes the
  `parent` keyword argumment on to `QWidget.__init__()`.
- add `PLUGIN = True` as a class variable to the widget class
- add `USER_ACCESS = [...]`, including any methods and properties which should be accessible in the
  client to the list, as strings.

(Search the `bec_widgets` code for one of the above names for examples of these magic variables)

### Example / template

```Python
class TestWidget(BECWidget, QWidget):
    USER_ACCESS = ["set_text"]
    PLUGIN = True

    def __init__(self, parent=None, **kwargs):
        super().__init__(**kwargs)
        QWidget.__init__(self, parent=parent)
        self.setLayout(QHBoxLayout())
        self._text_widget = QLabel("Test widget text")
        self.layout().addWidget(self._text_widget)

    def set_text(self, value: str):
      self._text_widget.setText(value)
```

### Generating the plugin files and RPC client template

To allow the BEC client to communicate with the GUI server and to know which widgets are available,
as well as to allow the BEC Designer to find the available widgets, a code generation tool should be
run to prepare a client file which lists all the available widget classes and functions. Make sure
you are in the BEC python environment where your plugin repository is also installed, and run:

```bash
$ bw-generate-cli --target plugin_repo
```

replacing `plugin_repo` with the name of your repository. This will overwrite the file for
`plugin_repo.bec_widgets.client`. This file should not be edited by hand, and should always be
regenerated when changes are made to widgets in the plugin repository. BEC will need to be restarted
for changes made here to take effect.