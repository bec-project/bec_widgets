Add/modify the path in the following variable to make the plugin avaiable in Qt Designer:
```
$ export PYQTDESIGNERPATH=/<path to repo>/bec/bec_qtplugin:$PYQTDESIGNERPATH
```

All the available conda-forge `pyqt >=5.15` packages don't seem to support loading Qt Designer
python plugins at the time of writing. Use `pyqt =5.12` to solve the issue for now.
