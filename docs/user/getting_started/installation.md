(user.installation)=
# Installation
**Prerequisites**

Before installing BEC Widgets, please ensure the following requirements are met:

1. **Python Version:** BEC Widgets requires Python version 3.10 or higher. Verify your Python version to ensure compatibility.
2. **BEC Installation:** BEC Widgets works in conjunction with BEC. While BEC is a dependency and will be installed automatically, you can find more information about BEC and its installation process in the [BEC documentation](https://beamline-experiment-control.readthedocs.io/en/latest/).

**Standard Installation**

To install BEC Widgets using the pip package manager, execute the following command in your terminal for getting the
default PySide6 version into your python environment for BEC:


```bash
pip install 'bec_widgets[pyside6]'
```

**Troubleshooting**

If you encounter issues during installation, particularly with Qt, try purging the pip cache:

```bash
pip cache purge
```

This can resolve conflicts or issues with package installations.

```{warning}
At the moment PyQt6 is no longer officially supported by BEC Widgets due to incompatibilities with BEC Designer. Please use PySide6 instead.
```
