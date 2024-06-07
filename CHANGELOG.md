# CHANGELOG



## v0.59.1 (2024-06-07)

### Fix

* fix(curve): set_color_map_z typo fixed in user access ([`e7838b0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e7838b0f2fc23b0a232ed7d68fbd7f3493a91b9e))


## v0.59.0 (2024-06-07)

### Build

* build: added webengine dependency ([`d56c549`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d56c5493cd28f379d04a79d90b01c73b0760da1b))

### Ci

* ci: merged additional tests to parallel matrix job ([`178fe4d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/178fe4d2da3a959f7cd90e7ea0f47314dc1ef4ed))

* ci: added webengine dependencies ([`2d79ef8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d79ef8fe5e52c61f4a78782770377cd6b41958b))

### Documentation

* docs: added website docs ([`cf6e5a4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf6e5a40fc8320e9898a446a5bf14b77e94ef013))

### Feature

* feat(widget): added simple website widget with rpc ([`64abd67`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/64abd67b9b416bff9c89880b248d6e8639aa1e70))


## v0.58.1 (2024-06-07)

### Fix

* fix(dock): new dock can be detached upon creation ([`02a2608`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02a26086c4540127a11c235cba30afc4fd712007))


## v0.58.0 (2024-06-07)

### Feature

* feat(utils.colors): general color validators ([`3094632`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/30946321348abc349fb4003dc39d0232dc19606c))

### Fix

* fix: bar colormap dynamic setting ([`67fd5e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67fd5e8581f60fe64027ac57f1f12cefa4d28343))

* fix: formatting isort ([`bf699ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf699ec1fbe2aacd31854e84fb0438c336840fcf))

* fix(curve): 2D scatter updated if color_map_z is changed ([`6985ff0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6985ff0fcef9791b53198206ec8cbccd1d65ef99))

* fix(curve): color_map_z setting works ([`33f7be4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/33f7be42c512402dab3fdd9781a8234e3ec5f4ba))

### Test

* test(color): validation tests added ([`c0ddece`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c0ddeceeeabacbf33019a8f24b18821926dc17ac))


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
