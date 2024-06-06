# CHANGELOG



## v0.57.3 (2024-06-06)

### Documentation

* docs(bar): docs updated ([`4be0d14`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be0d14b7445c2322c2aef86257db168a841265c))

* docs: fixed syntax of add_widget ([`a951ebf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a951ebf1be6c086d094aa8abef5e0dfd1b3b8558))

* docs: added auto update; closes #206 ([`32da803`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32da803df9f7259842c43e85ba9a0ce29a266d06))

* docs: cleanup ([`07d60cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/07d60cf7355d2edadb3c5ef8b86607d74b360455))

### Fix

* fix(ring): automatic updates are disabled uf user specify updates manually with .set_update; &#39;scan_progres&#39; do not reset number of rings ([`e883dba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e883dbad814dbcc0a19c341041c6d836e58a5918))

* fix(ring): enable_auto_updates(True) do not reset properties of already setup bars ([`a2abad3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a2abad344f4c0039516eb60a825afb6822c5b19a))

* fix(ring): set_min_max accepts floats ([`d44b1cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d44b1cf8b107cf02deedd9154b77d01c7f9ed05d))

* fix(ring): set_update changed to Literals, no need to specify endpoint manually ([`c5b6499`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5b6499e41eb1495bf260436ca3e1b036182c360))


## v0.57.2 (2024-06-06)

### Fix

* fix(test/e2e): autoupdate e2e rewritten ([`e1af5ca`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e1af5ca60f0616835f9f41d84412f29dc298c644))

* fix(test/e2e): spiral_progress_bar e2e tests rewritten to use config_dict ([`7fb31fc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7fb31fc4d762ff4ca839971b3092a084186f81b8))

* fix(test/e2e): dockarea and dock e2e tests changed to check asserts against config_dict ([`5c6ba65`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c6ba65469863ea1e6fc5abdc742650e20eba9b9))

* fix: rpc_server_dock fixture now spawns the server process ([`cd9fc46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cd9fc46ff8a947242c8c28adcd73d7de60b11c44))

* fix: accept scalars or numpy arrays of 1 element ([`2a88e17`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a88e17b23436c55d25b7d3449e4af3a7689661c))

### Refactor

* refactor: move _get_output and _start_plot_process at the module level ([`69f4371`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/69f4371007c66aee6b7521a6803054025adf8c92))


## v0.57.1 (2024-06-06)

### Documentation

* docs: docs refactored from add_widget_bec to add_widget ([`c3f4845`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c3f4845b4f95005ff737fed5542600b0b9a9cc2b))

### Fix

* fix: tests references to add_widget_bec refactored ([`f51b25f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f51b25f0af4ab8b0a75ee48a40bfbb079c16e9d1))

* fix(dock): add_widget and add_widget_bec consolidated ([`8ae323f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ae323f5c3c0d9d0f202d31d5e8374a272a26be2))


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
