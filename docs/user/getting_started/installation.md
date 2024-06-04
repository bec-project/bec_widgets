(user.installation)=
# Installation


**Prerequisites**

Before installing BEC Widgets, please ensure the following requirements are met:

1. **Python Version:** BEC Widgets requires Python version 3.10 or higher. Verify your Python version to ensure compatibility.
2. **BEC Installation:** BEC Widgets works in conjunction with BEC. While BEC is a dependency and will be installed automatically, you can find more information about BEC and its installation process in the [BEC documentation](https://beamline-experiment-control.readthedocs.io/en/latest/).

**Standard Installation**

Install BEC Widgets using the pip package manager. Open your terminal and execute:

```bash
pip install bec_widgets PyQt6
```

This command installs BEC Widgets along with its dependencies, including the default PyQt6.

**Selecting a PyQt Version**

BEC Widgets supports both PyQt5 and PyQt6. To install a specific version, use:

For PyQt6:

```bash
pip install bec_widgets[pyqt6]
```

For PyQt5:

```bash
pip install bec_widgets[pyqt5]
```

**Troubleshooting**

If you encounter issues during installation, particularly with PyQt, try purging the pip cache:

```bash
pip cache purge
```

This can resolve conflicts or issues with package installations.
