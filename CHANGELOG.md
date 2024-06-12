# CHANGELOG



## v0.62.0 (2024-06-12)

### Feature

* feat: implement non-polling, interruptible waiting of gui instruction response with timeout ([`abc6caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/abc6caa2d0b6141dfbe1f3d025f78ae14deddcb3))

### Unknown

* doc: add documentation about creating custom GUI applications embedding BEC Widgets ([`17a0068`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/17a00687579f5efab1990cd83862ec0e78198633))


## v0.61.0 (2024-06-12)

### Feature

* feat(widgets/stop_button): General stop button added ([`61ba08d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61ba08d0b8df9f48f5c54c7c2b4e6d395206e7e6))

### Refactor

* refactor: improve labe of auto_update script ([`40b5688`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/40b568815893cd41af3531bb2e647ca1e2e315f4))


## v0.60.0 (2024-06-08)

### Ci

* ci: added git fetch for target branch ([`fc4f4f8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc4f4f81ad1be99cf5112f2188a46c5bed2679ee))

* ci: fixed pylint-check ([`6b1d582`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b1d5827d6599f06a3acd316060a8d25f0686d54))

* ci: cleanup ([`11173b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11173b9c0a7dc4b36e35962042e5b86407da49f1))

### Feature

* feat: added isort to bw-generate-cli ([`f0391f5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0391f59c9eb0a51b693fccfe2e399e869d35dda))

* feat: added entry point for bw-generate-cli ([`1c7f491`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1c7f4912ce5998e666276969bf4af8656d619a91))

* feat(cli): auto-discover rpc-enabled widgets ([`df1be10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df1be10057a5e85a3f35bef1c1b27366b6727276))

### Fix

* fix: removed BECConnector from rpc client interface ([`6428e38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6428e38ab94c15a2c904e75cc6404bb6d0394e04))

* fix: added bec_ipython_client as dependency; needed for jupyter widget ([`006a089`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/006a0894b85cba3b2773737ed6fe3e92c81cdee0))

* fix(BECFigure): removed duplicated user access for plot ([`954c576`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/954c576131f7deac669ddf9f51eeb1d41b6f92b7))

* fix(bec_connector): field validator should be a classmethod ([`867720a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/867720a897b6713bd0df9af71ffdd11a6a380f7d))

### Refactor

* refactor: minor cleanup ([`3adf6cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3adf6cfd586355c8b8ce7fdc9722f868e22287c5))

* refactor: disabled pylint for auto-gen client ([`b15816c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b15816ca9fd3e4ae87cca5fcfe029b4dfca570ca))

* refactor(isort): added bec_widgets as known first party package ([`9c5a471`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9c5a471234ed2928e4527b079436db2a807c5f6f))

* refactor(dock): parent_dock_area changed to orig_area (native for pyqtgraph) ([`2b40602`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b40602bdc593ece0447ec926c2100414bd5cf67))

### Test

* test: added missing pylint statement to header ([`f662985`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f6629852ebc2b4ee239fa560cc310a5ae2627cf7))


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
