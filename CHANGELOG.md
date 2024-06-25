# CHANGELOG

## v0.73.2 (2024-06-25)

### Fix

* fix(vscode): only run terminate if the process is still alive ([`7120f3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7120f3e93b054b788f15e2d5bcd688e3c140c1ce))

* fix(rpc): trigger shutdown of server when gui is terminated ([`acc1318`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/acc13183e28030e3ca9af21bb081e1eed081622b))

* fix(rpc): remove of calling &#34;close&#34; and waiting for gui_is_alive ([`f75fc19`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f75fc19c5b10022763252917ca473f404a25165a))

## v0.73.1 (2024-06-25)

### Fix

* fix(ringprogressbar): removed hard-coded endpoint strings ([`1de3cbf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1de3cbf65a1832150917a7549a1bf3efdee6371a))

## v0.73.0 (2024-06-25)

### Feature

* feat: add new default scaling of image_item ([`df812ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df812eaad5989f2930dde41d87491868505af946))

### Test

* test: add test for imageitem ([`88ecd05`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88ecd05b95974938ef1efff40e81854baf004cb4))

## v0.72.2 (2024-06-25)

### Fix

* fix(designer): fixed designer for pyenv and venv; closes #237 ([`e631fc1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e631fc15d8707b73d58cb64316e115a7e43961ea))

## v0.72.1 (2024-06-24)

### Fix

* fix: renamed spiral progress bar to ring progress bar; closes #235 ([`e5c0087`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5c0087c9aed831edbe1c172746325a772a3bafa))

### Test

* test: bugfix to prohibit leackage of mock ([`4348ed1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4348ed1bb2182da6bdecaf372d6db85279e60af8))

## v0.72.0 (2024-06-24)

### Feature

* feat(connector): added threadpool wrapper ([`4ca1efe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4ca1efeeb8955604069f7b98374c7f82e1a8da67))

### Unknown

* tests(status_box_test): temporary disabled tests for status_box due to high rate of failures ([`aa7ce2e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aa7ce2ea27bb9564d4f5104bbff30725b8656453))

## v0.71.1 (2024-06-23)

### Fix

* fix: don&#39;t print exception if the auto-update module cannot be found in plugins ([`860517a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/860517a3211075d1f6e2af7fa6a567b9e0cd77f3))

## v0.71.0 (2024-06-23)

### Feature

* feat(scan_group_box): scan box for args and kwargs separated from ScanControlGUI code ([`d8cf441`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8cf44134c30063e586771f9068947fef7a306d1))

### Fix

* fix(cleanup): cleanup added to device_input widgets and scan_control ([`8badb6a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8badb6adc1d003dbf0b2b1a800c34821f3fc9aa3))

* fix(scan_group_box): added row counter based on widgets ([`37682e7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37682e7b8a6ede38308880d285e41a948d6fe831))

* fix(scan_control): added default min limit for args bundle if specified ([`ec4574e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec4574ed5c2c85ea6fbbe2b98f162a8e1220653b))

* fix(scan_control): argbox delete later added to prevent overlapping gui if scan changed ([`7ce3a83`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ce3a83c58cb69c2bf7cb7f4eaba7e6a2ca6c546))

* fix(scan_control): only scans with defined gui_config are allowed ([`6dff187`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6dff1879c4178df0f8ebfd35101acdebb028d572))

* fix(WidgetIO): find handlers within base classes ([`ca85638`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca856384f380dabf28d43f1cd48511af784c035b))

* fix(scan_control): adapted widget to scan BEC gui config ([`8b822e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8b822e0fa8e28f080b9a4bf81948a7280a4c07bf))

* fix(scan_control): scan_control.py combatible with the newest BEC versions, test disabled ([`67d398c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67d398caf74e08ab25a70cc5d85a5f0c2de8212d))

### Refactor

* refactor(device_line_edit): renamed default_device to default ([`4e2c9df`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4e2c9df6a4979d935285fd7eba17fd7fd455a35c))

### Test

* test(scan_control): tests added ([`56e74a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56e74a0e7da72d18e89bc30d1896dbf9ef97cd6b))

### Unknown

* test(scan_control):e2e tests added ([`83001a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/83001a0d8267e1320549b07032857dcf46ecd293))

* doc(scan_control): docs added ([`1b7921a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b7921a7f2e3bcc846219a2a7aa0de0fd27bb8fe))

* fix(device_line_edit):SizePolicy fixed for 100 horizontal ([`21d20e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/21d20e0fc78e9a3853abe802733388cce119ce20))

* tests WIP ([`c09644b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c09644b29ddb291c91dc58bcd6ebf02ff45cab36))

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

### Fix

* fix: ignore GUI server output (any output will go to log file)

If a logger is given to log `_start_log_process`, the server stdout and
stderr streams will be redirected as log entries with levels DEBUG or ERROR
in their parent process ([`ce37416`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ce374163cab87a92847409051739777bc505a77b))

* fix: do not create &#39;BECClient&#39; logger when instantiating BECDispatcher ([`f7d0b07`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f7d0b0768ace42a33e2556bb33611d4f02e5a6d9))
