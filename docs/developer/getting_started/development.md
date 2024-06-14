(developer.development)=
# Development

If you like to contribute to the development of BEC Widgets, you can follow the steps below to set up your development environment.
BEC Widgets works in conjunction with [BEC](https://bec.readthedocs.io/en/latest/). 
Therefore, we recommend that you install BEC first following the [developer instructions](https://bec.readthedocs.io/en/latest/developer/getting_started/install_developer_env.html) and include BEC Widgets. 

If you already have a BEC environment set up, you can install BEC Widgets in editable mode into your BEC Python environment.

**Prerequisites**
1. **Python Version:** BEC Widgets requires Python version 3.10 or higher. Verify your Python version to ensure compatibility.
2. **BEC Installation:** BEC Widgets works in conjunction with BEC. While BEC is a dependency and will be installed automatically, you can find more information about BEC and its installation process in the [BEC documentation](https://beamline-experiment-control.readthedocs.io/en/latest/).

**Clone the Repository**: 
```bash
git clone https://gitlab.psi.ch/bec/bec_widgets
cd bec_widgets
```
**Install in Editable Mode**:

Please install the package in editable mode into your BEC Python environemnt. 
```bash
pip install -e '.[dev,pyqt6]'
```
This installs the package together with [PyQT6](https://www.riverbankcomputing.com/static/Docs/PyQt6/introduction.html). 


