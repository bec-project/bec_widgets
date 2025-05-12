# BEC Widgets


[![CI](https://github.com/bec-project/bec_widgets/actions/workflows/ci.yml/badge.svg)](https://github.com/bec-project/bec_widgets/actions/workflows/ci.yml)
[![badge](https://img.shields.io/pypi/v/bec-widgets)](https://pypi.org/project/bec-widgets/)
[![License](https://img.shields.io/github/license/bec-project/bec_widgets)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org)
[![PySide6](https://img.shields.io/badge/PySide6-blue?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Conventional Commits](https://img.shields.io/badge/conventional%20commits-1.0.0-yellow?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)
[![codecov](https://codecov.io/gh/bec-project/bec_widgets/graph/badge.svg?token=0Z9IQRJKMY)](https://codecov.io/gh/bec-project/bec_widgets)


**⚠️ Important Notice:**

🚨 **PyQt6 is no longer supported** due to incompatibilities with Qt Designer. Please use **PySide6** instead. 🚨

BEC Widgets is a GUI framework designed for interaction with [BEC (Beamline Experiment Control)](https://gitlab.psi.ch/bec/bec).

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install BEC Widgets:

```bash
pip install bec_widgets[pyside6]
```

For development purposes, you can clone the repository and install the package locally in editable mode:

```bash
git clone https://gitlab.psi.ch/bec/bec-widgets
cd bec_widgets
pip install -e .[dev,pyside6]
```

BEC Widgets now **only supports PySide6**. Users must manually install PySide6 as no default Qt distribution is
specified.

## Documentation

Documentation of BEC Widgets can be found [here](https://bec-widgets.readthedocs.io/en/latest/). The documentation of the BEC can be found [here](https://bec.readthedocs.io/en/latest/).

## Contributing

All commits should use the Angular commit scheme:

> #### <a name="commit-header"></a>Angular Commit Message Header
>
> ```
> <type>(<scope>): <short summary>
>   │       │             │
>   │       │             └─⫸ Summary in present tense. Not capitalized. No period at the end.
>   │       │
>   │       └─⫸ Commit Scope: animations|bazel|benchpress|common|compiler|compiler-cli|core|
>   │                          elements|forms|http|language-service|localize|platform-browser|
>   │                          platform-browser-dynamic|platform-server|router|service-worker|
>   │                          upgrade|zone.js|packaging|changelog|docs-infra|migrations|ngcc|ve|
>   │                          devtools
>   │
>   └─⫸ Commit Type: build|ci|docs|feat|fix|perf|refactor|test
> ```
>
> The `<type>` and `<summary>` fields are mandatory, the `(<scope>)` field is optional.

> ##### Type
>
> Must be one of the following:
>
> * **build**: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
> * **ci**: Changes to our CI configuration files and scripts (examples: CircleCi, SauceLabs)
> * **docs**: Documentation only changes
> * **feat**: A new feature
> * **fix**: A bug fix
> * **perf**: A code change that improves performance
> * **refactor**: A code change that neither fixes a bug nor adds a feature
> * **test**: Adding missing tests or correcting existing tests

## License

[BSD-3-Clause](https://choosealicense.com/licenses/bsd-3-clause/)

