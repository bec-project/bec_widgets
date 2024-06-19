# CHANGELOG

## v0.64.1 (2024-06-19)

### Fix

* fix(widgets): removed widget module import of sub widgets ([`216511b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/216511b951ff0e15b6d7c70133095f3ac45c23f4))

### Refactor

* refactor(utils): moved get_rpc_widgets to plugin_utils ([`6dabbf8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6dabbf874fbbdde89c34a7885bf95aa9c895a28b))

### Test

* test: moved rpc_classes test ([`b3575eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b3575eb06852b456cde915dfda281a3e778e3aeb))

## v0.64.0 (2024-06-19)

### Ci

* ci: add job optional dependency check ([`27426ce`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/27426ce7a52b4cbad7f3bef114d6efe6ad73bd7f))

### Documentation

* docs: fix links in developer section ([`9e16f2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9e16f2faf9c59a5d36ae878512c5a910cca31e69))

* docs: refactor developer section, add widget tutorial ([`2a36d93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a36d9364f242bf42e4cda4b50e6f46aa3833bbd))

### Feature

* feat: add option to change size of the fonts ([`ea805d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ea805d1362fc084d3b703b6f81b0180072f0825d))

### Fix

* fix(plot_base): font size is set with setScale which is scaling the whole legend window ([`5d66720`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d6672069ea1cbceb62104f66c127e4e3c23e4a4))

### Test

* test: add tests ([`140ad83`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/140ad83380808928edf7953e23c762ab72a0a1e9))

## v0.63.2 (2024-06-14)

### Fix

* fix: do not import &#34;server&#34; in client, prevents from having trouble with QApplication creation order

Like with QtWebEngine ([`6f96498`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f96498de66358b89f3a2035627eed2e02dde5a1))

### Unknown

* Reapply &#34;feat: implement non-polling, interruptible waiting of gui instruction response with timeout&#34;

This reverts commit fe04dd80e59a0e74f7fdea603e0642707ecc7c2a. ([`836b6e6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/836b6e64f694916d6b6f909dedf11a4a6d2c86a4))

## v0.63.1 (2024-06-13)

### Fix

* fix: just terminate the remote process in close() instead of communicating

The proper finalization sequence will be executed by the remote process
on SIGTERM ([`9263f8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9263f8ef5c17ae7a007a1a564baf787b39061756))

## v0.63.0 (2024-06-13)

### Documentation

* docs: add documentation ([`bc709c4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc709c4184c985d4e721f9ea7d1b3dad5e9153a7))

### Feature

* feat: add textbox widget ([`d9d4e3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d9d4e3c9bf73ab2a5629c2867b50fc91e69489ec))

### Refactor

* refactor: add pydantic config, add change_theme ([`6b8432f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b8432f5b20a71175a3537b5f6832b76e3b67d73))

### Test

* test: add test for text box ([`b49462a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b49462abeb186e56bac79d2ef0b0add1ef28a1a5))

### Unknown

* Revert &#34;feat: implement non-polling, interruptible waiting of gui instruction response with timeout&#34;

This reverts commit abc6caa2d0b6141dfbe1f3d025f78ae14deddcb3 ([`fe04dd8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe04dd80e59a0e74f7fdea603e0642707ecc7c2a))

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
