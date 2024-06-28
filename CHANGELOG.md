# CHANGELOG

## v0.76.0 (2024-06-28)

### Feature

* feat(designer): added support for creating designer plugins automatically ([`c1dd0ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c1dd0ee1906dba1f2e2ae9ce40a84d55c26a1cce))

### Fix

* fix: fixed qwidget inheritance for ring progress bar ([`0610d2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0610d2f9f027f8659e7149f2dfbb316ff30e337d))

### Unknown

* fix:parent set as first kwarg TextBox and WebsiteWidget ([`a45c407`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a45c4075684b93bfdcee03e5a416b84f61d3bc6f))

## v0.75.0 (2024-06-26)

### Feature

* feat(widgets): added simple bec queue widget ([`3faee98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3faee98ec80041a27e4c1f1156178de6f9dcdc63))

### Refactor

* refactor(dispatcher): cleanup ([`ca02132`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca02132c8d18535b37e9192e00459d2aca6ba5cf))

## v0.74.1 (2024-06-26)

### Build

* build: added missing pytest-bec-e2e dependency; closes #219 ([`56fdae4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56fdae42757bdb9fa301c1e425a77e98b6eaf92b))

* build: fixed dependency ranges; closes #135 ([`e6a06c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6a06c9f43e0ad6bbfcfa550a2f580d2a27aff66))

### Chore

* chore: sorted dependencies alphabetically ([`21c807f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/21c807f35831fdd1ef2e488ab90edae4719f0cb7))

### Documentation

* docs: fixed doc string ([`f979a63`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f979a63d3d1a008f80e500510909750878ff4303))

### Fix

* fix(rings): rings properties updated right after setting ([`c8b7367`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8b7367815b095f8e4aa8b819481efb701f2e542))

* fix(motor_map): motor map can be removed from BECFigure with .remove() ([`6b25abf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b25abff70280271e2eeb70450553c05d4b7c99c))

### Test

* test(bec_figure): tests for removing widgets with rpc e2e ([`a268caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a268caaa30711fcc7ece542d24578d74cbf65c77))

## v0.74.0 (2024-06-25)

### Documentation

* docs(becfigure): docs added ([`a51b15d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a51b15da3f5e83e0c897a0342bdb05b9c677a179))

### Feature

* feat(waveform1d): dap LMFit model can be added to plot ([`1866ba6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1866ba66c8e3526661beb13fff3e13af6a0ae562))

### Test

* test(waveform1d): dap e2e test added ([`7271b42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7271b422f98ef9264970d708811c414b69a644db))

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

### Test

* test(scan_control): tests added ([`56e74a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56e74a0e7da72d18e89bc30d1896dbf9ef97cd6b))

### Unknown

* test(scan_control):e2e tests added ([`83001a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/83001a0d8267e1320549b07032857dcf46ecd293))

* doc(scan_control): docs added ([`1b7921a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b7921a7f2e3bcc846219a2a7aa0de0fd27bb8fe))

* fix(device_line_edit):SizePolicy fixed for 100 horizontal ([`21d20e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/21d20e0fc78e9a3853abe802733388cce119ce20))

* tests WIP ([`c09644b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c09644b29ddb291c91dc58bcd6ebf02ff45cab36))
