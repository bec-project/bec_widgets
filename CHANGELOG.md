# CHANGELOG



## v0.57.0 (2024-06-05)

### Documentation

* docs: extend user documentation for BEC Widgets ([`4160f3d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4160f3d6d7ec1122785b5e3fdfc4afe67a95e9a1))

### Feature

* feat(widgets/console): BECJupyterConsole added ([`8c03034`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c03034acf6b3ed1e346ebf1b785d41068513cc5))


## v0.56.3 (2024-06-05)

### Ci

* ci: increased verbosity for e2e tests ([`4af1abe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4af1abe4e15b62d2f7e70bf987a1a7d8694ef4d5))

### Fix

* fix: fixed support for auto updates ([`131f49d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/131f49da8ea65af4d44b50e81c1acfc29cd92093))


## v0.56.2 (2024-06-05)

### Documentation

* docs: restructured docs layout ([`3c9181d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c9181d93d68faa4efb3b91c486ca9ca935975a0))

### Fix

* fix(bar): ring saves current value in config ([`9648e3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9648e3ea96a4109be6be694d855151ed6d3ad661))

* fix(dock): dock saves configs of all children widgets ([`4be756a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be756a8676421c3a3451458995232407295df84))

* fix(dock_area): save/restore state is saved in config ([`46face0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/46face0ee59122f04cb383da685a6658beeeb389))

* fix(figure): added correct types of configs to subplot widgets ([`6f3b1ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f3b1ea985c18929b9bab54239eeb600f03b274a))


## v0.56.1 (2024-06-04)

### Fix

* fix(spiral_progress_bar/rings): config min/max values added check for floats ([`9d615c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d615c915c8f7cc2ea8f1dc17993b98fe462c682))

* fix(spiral_progress_bar): Endpoint is always stored as a string in the RingConnection Config ([`d253991`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2539918b296559e1d684344e179775a2423daa9))


## v0.56.0 (2024-05-29)

### Build

* build: added pyside6 as dependency ([`db301b1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db301b1be27bba76c8bb21fbff93cb4902b592a5))

### Ci

* ci: added tests for pyside6, pyqt6 and pyqt5, default test and e2e is python 3.11 and pyqt6 ([`855be35`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/855be3551a1372bcbebba6f8930903f99202bbca))

### Documentation

* docs(examples): example apps section deleted ([`ad208a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad208a5ef8495c45a8b83a4850ba9a1041b42717))

### Feature

* feat(utils/ui_loader): universal ui loader for pyside/pyqt ([`0fea8d6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fea8d606574fa99dda3b117da5d5209c251f694))

### Fix

* fix(examples): outdated examples removed (mca_plot.py, stream_plot.py, motor_example.py) ([`ddc9510`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ddc9510c2ba8dadf291809eeb5b135a105259492))

* fix: compatibility adjustment to .ui loading and tests for PySide6 ([`07b99d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/07b99d91a57a645cddd76294f48d78773e4c9ea5))


## v0.55.0 (2024-05-24)

### Feature

* feat(widgets/progressbar): SpiralProgressBar added with rpc interface ([`76bd0d3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/76bd0d339ac9ae9e8a3baa0d0d4e951ec1d09670))


## v0.54.0 (2024-05-24)

### Build

* build: added pyqt6 as sphinx build dependency ([`a47a8ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a47a8ec413934cf7fce8d5b7a5913371d4b3b4a5))

### Feature

* feat(figure): changes to support direct plot functionality ([`fc4d0f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc4d0f3bb2a7c2fca9c326d86eb68b305bcd548b))

### Refactor

* refactor(reconstruction): repository structure is changed to separate assets needed for each widget ([`3455c60`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3455c602361d3b5cc3ff9190f9d2870474becf8a))

* refactor(clean-up): 1st generation widgets are removed ([`edc25fb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/edc25fbf9d5a0321e5f0a80b492b6337df807849))


## v0.53.3 (2024-05-16)

### Fix

* fix: removed apparently unnecessary sleep while waiting for an rpc response ([`7d64cac`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d64cac6610b39d3553ff650354f78ead8ee6b55))


## v0.53.2 (2024-05-15)

### Ci

* ci: added echo to highlight the current branch ([`0490e80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0490e80c48563e4fb486bce903b3ce1f08863e83))

### Fix

* fix: check device class without importing to speed up initial import time ([`9f8fbdd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9f8fbdd5fc13cf2be10eacb41e10cf742864cd92))

* fix: speed up initial import times using lazy import (from bec_lib) ([`d1e6cd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d1e6cd388c6c9f345f52d6096d8a75a1fa7e6934))

* fix: adapt to bec_lib changes (no more submodules in `__init__.py`) ([`5d09a13`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d09a13d8820a8bdb900733c97593b723a2fce1d))


## v0.53.1 (2024-05-09)

### Ci

* ci: fixed rtd pages url ([`8ff3610`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ff36105d1e637c429915b4bfc2852d54a3c6f19))

### Fix

* fix: docs config ([`0f6a5e5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f6a5e5fa9530969c98a9266c9ca7b89a378ff70))


## v0.53.0 (2024-05-09)

### Ci

* ci: use formatter config of toml file ([`5cc816d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5cc816d0af73e20c648e044a027c589704ab1625))

### Documentation

* docs: update install instructions ([`57ee735`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57ee735e5c2436d45a285507cdc939daa20e8e8f))

### Feature

* feat: moved to pyproject.toml; closes #162 ([`c86ce30`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c86ce302a964d71ee631f0817609ab5aa0e3ab0f))

### Fix

* fix: fixed semver job and upgraded to v9 ([`32e1a9d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32e1a9d8472eb1c25d30697d407a8ffecd04e75d))

### Refactor

* refactor: applied formatter ([`4117fd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4117fd7b5b2090ff4fb7ad9e0d92cc87cd13ed5f))


## v0.52.1 (2024-05-08)

### Fix

* fix(docstrings): docstrings formating fixed for sphinx to properly format readdocs ([`7f2f7cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7f2f7cd07a14876617cd83cedde8c281fdc52c3a))


## v0.52.0 (2024-05-07)

### Feature

* feat(utils/layout_manager): added GridLayoutManager to extend functionalities of native QGridLayout ([`fcd6ef0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fcd6ef0975dc872f69c9d6fb2b8a1ad04a423aae))

* feat(widget/dock): BECDock and BECDock area for dockable windows ([`d8ff8af`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8ff8afcd474660a6069bbdab05f10a65f221727))

### Fix

* fix(widgets/dock): BECDockArea close overwrites the default pyqtgraph Container close + minor improvements ([`ceae979`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ceae979f375ecc33c5c97148f197655c1ca57b6c))
