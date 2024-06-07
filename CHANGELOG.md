# CHANGELOG



## v0.57.7 (2024-06-07)

### Documentation

* docs: added schema of BECDockArea and BECFigure ([`828067f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/828067f486a905eb4678538df58e2bdd6c770de1))

### Fix

* fix: add model_config to pydantic models to allow runtime checks after creation ([`ca5e8d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca5e8d2fbbffbf221cc5472710fef81a33ee29d6))


## v0.57.6 (2024-06-06)

### Fix

* fix(bar): docstrings extended ([`edb1775`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/edb1775967c3ff0723d0edad2b764f1ffc832b7c))


## v0.57.5 (2024-06-06)

### Documentation

* docs(figure): docs adjusted to be compatible with new signature ([`c037b87`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c037b87675af91b26e8c7c60e76622d4ed4cf5d5))

### Fix

* fix(waveform): added .plot method with the same signature as BECFigure.plot ([`8479caf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8479caf53a7325788ca264e5bd9aee01f1d4c5a0))

* fix(plot_base): .plot removed from plot_base.py, because there is no use case for it ([`82e2c89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/82e2c898d2e26f786b2d481f85c647472675e75b))

### Refactor

* refactor(figure): logic for .add_image and .image consolidated; logic for .add_plot and .plot consolidated ([`52bc322`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52bc322b2b8d3ef92ff3480e61bddaf32464f976))


## v0.57.4 (2024-06-06)

### Fix

* fix(docks): set_title do update dock internal _name now ([`15cbc21`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/15cbc21e5bb3cf85f5822d44a2b3665b5aa2f346))

* fix(docks): docks widget_list adn dockarea panels return values fixed ([`ffae5ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ffae5ee54e6b43da660131092452adff195ba4fb))


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

### Documentation

* docs(examples): example apps section deleted ([`ad208a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad208a5ef8495c45a8b83a4850ba9a1041b42717))

### Fix

* fix(examples): outdated examples removed (mca_plot.py, stream_plot.py, motor_example.py) ([`ddc9510`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ddc9510c2ba8dadf291809eeb5b135a105259492))
