# CHANGELOG

## v0.67.0 (2024-06-21)

### Documentation

* docs: add widget to documentation ([`6fa1c06`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fa1c06053131dabd084bb3cf13c853b5d3ce833))

### Feature

* feat: introduce BECStatusBox Widget ([`443b6c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/443b6c1d7b02c772fda02e2d1eefd5bd40249e0c))

### Refactor

* refactor: Change inheritance to QTreeWidget from QWidget ([`d2f2b20`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2f2b206bb0eab60b8a9b0d0ac60a6b7887fa6fb))

### Test

* test: add test suite for bec_status_box and status_item ([`5d4ca81`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d4ca816cdedec4c88aba9eb326f85392504ea1c))

### Unknown

* Update file requirements.txt ([`505a5ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/505a5ec8334ff4422913b3a7b79d39bcb42ad535))

## v0.66.1 (2024-06-20)

### Fix

* fix: fixed shutdown for pyside ([`2718bc6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2718bc624731301756df524d0d5beef6cb1c1430))

## v0.66.0 (2024-06-20)

### Feature

* feat(rpc): discover widgets automatically ([`ef25f56`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ef25f5638032f931ceb292540ada618508bb2aed))

## v0.65.2 (2024-06-20)

### Fix

* fix(pyqt): webengine must be imported before qcoreapplication ([`cbbd23a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cbbd23aa33095141e4c265719d176c4aa8c25996))

## v0.65.1 (2024-06-20)

### Fix

* fix: prevent segfault by closing the QCoreApplication, if any ([`fa344a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa344a5799b07a2d8ace63cc7010b69bc4ed6f1d))

## v0.65.0 (2024-06-20)

### Feature

* feat(device_input): DeviceLineEdit with QCompleter added ([`50e41ff`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50e41ff26160ec26d77feb6d519e4dad902a9b9b))

* feat(device_combobox): DeviceInputBase and DeviceComboBox added ([`430b282`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/430b282039806e3fbc6cf98e958861a065760620))

### Fix

* fix(device_input_base): bug with setting config and overwriting default device and filter ([`d79f7e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d79f7e9ccde03dc77819ca556c79736d30f7821a))

### Test

* test(device_input): tests added ([`1a0a98a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1a0a98a45367db414bed813bbd346b3e1ae8d550))

## v0.64.2 (2024-06-19)

### Fix

* fix(client_utils): added close rpc command to shutdown of gui from bec_ipython_client ([`e5a7d47`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5a7d47b21cbf066f740f1d11d7c9ea7c70f3080))

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

### Fix

* fix: removed BECConnector from rpc client interface ([`6428e38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6428e38ab94c15a2c904e75cc6404bb6d0394e04))
