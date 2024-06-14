(user.installation)=
# Installation
**Prerequisites**

Before installing BEC Widgets, please ensure the following requirements are met:

1. **Python Version:** BEC Widgets requires Python version 3.10 or higher. Verify your Python version to ensure compatibility.
2. **BEC Installation:** BEC Widgets works in conjunction with BEC. While BEC is a dependency and will be installed automatically, you can find more information about BEC and its installation process in the [BEC documentation](https://beamline-experiment-control.readthedocs.io/en/latest/).

**Standard Installation**

To install BEC Widgets using the pip package manager, execute the following command in your terminal for getting the default PyQT6 version into your python environment for BEC:


```bash
pip install bec_widgets[pyqt6]
```

In case you want to use PyQt5, you can install it by using the following command:

```bash
pip install bec_widgets[pyqt5]
```

**Troubleshooting**

If you encounter issues during installation, particularly with PyQt, try purging the pip cache:

```bash
pip cache purge
```

This can resolve conflicts or issues with package installations.
