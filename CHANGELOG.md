# CHANGELOG

## v0.70.0 (2024-06-21)

### Documentation

* docs: fix typo in link ([`fdf11d8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fdf11d8147750e379af9b17792761a267b49ae53))

### Feature

* feat(bec-designer): automatic plugin discovery ([`4639eee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4639eee0b975ebd7a946e0e290449f5b88c372eb))

* feat(device_line_edit): plugin added to bec-designer ([`b4b27ae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b4b27aea3d8c08fa3d5d5514c69dbde32721d1dc))

* feat(device_combobox): plugin added to bec-designer ([`e483b28`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e483b282db20a81182b87938ea172654092419b5))

* feat: added entry point for bec-designer ([`36391db`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/36391db60735d57b371211791ddf8d3d00cebcf1))

* feat(utils/bec-designer): added startup script to launched QtDesigner compatible with conda environments ([`5362334`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5362334ff3b07fc83653323a084a4b6946bade96))

### Fix

* fix(bec-desiger+plugins): imports fixed, PYSIDE6 check to not enable run plugins with pyqt6 ([`50b3422`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50b3422528d46d74317e8c903b6286e868ab7fe0))

## v0.69.0 (2024-06-21)

### Feature

* feat(widgets): added vscode widget ([`48ae950`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48ae950d57b454307ce409e2511f7b7adf3cfc6b))

### Fix

* fix(generate_cli): fixed rpc generate for classes without user access; closes #226 ([`925c893`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/925c893f3ff4337fc8b4d237c8ffc19a597b0996))

## v0.68.0 (2024-06-21)

### Feature

* feat: properly handle SIGINT (ctrl-c) in BEC GUI server -&gt; calls qapplication.quit() ([`3644f34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3644f344da2df674bc0d5740c376a86b9d0dfe95))

* feat: bec-gui-server: redirect stdout and stderr (if any) as proper debug and error log entries ([`d1266a1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d1266a1ce148ff89557a039e3a182a87a3948f49))

* feat: add logger for BEC GUI server ([`630616e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/630616ec729f60aa0b4d17a9e0379f9c6198eb96))

### Fix

* fix: ignore GUI server output (any output will go to log file)

If a logger is given to log `_start_log_process`, the server stdout and
stderr streams will be redirected as log entries with levels DEBUG or ERROR
in their parent process ([`ce37416`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ce374163cab87a92847409051739777bc505a77b))

* fix: do not create &#39;BECClient&#39; logger when instantiating BECDispatcher ([`f7d0b07`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f7d0b0768ace42a33e2556bb33611d4f02e5a6d9))

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
