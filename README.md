# BEC Widgets

BEC Widgets is a GUI framework designed for interaction with [BEC (Beamline Experiment Control)](https://gitlab.psi.ch/bec/bec).
## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install BEC Widgets:

```bash
pip install bec_widgets
```

For development purposes, you can clone the repository and install the package locally in editable mode:

```bash
git clone https://gitlab.psi.ch/bec/bec-widgets
cd bec_widgets
pip install -e .[dev]
```

BEC Widgets currently supports both PyQt5 and PyQt6. By default, PyQt6 is installed.

To select a specific Python Qt distribution, install the package with an additional tag:

```bash
pip install bec_widgets[pyqt6]
```
or 

```bash
pip install bec_widgets[pyqt5]
```
## Documentation

Documentation of BEC Widgets can be found [here](https://bec-widgets.readthedocs.io/en/latest/). The documentation of the BEC can be found [here](https://beamline-experiment-control.readthedocs.io/en/latest/).

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