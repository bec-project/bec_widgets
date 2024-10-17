# CHANGELOG


## v0.119.0 (2024-10-17)

### Features

* feat: new PositionerGroup widget ([`af9655d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af9655de0c541092437accfbaa779628a2f48ccb))

* feat: add 'expand_popup' property to CompactPopupWidget

This property tells if expand should show a popup (by default), or
if the widget should expand in-place ([`e4121a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4121a01cb6b8d496e630cd43bc642b994b8f310))

* feat: PositionerBox with a popup view ([`2615787`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/261578796f1de8ca9cab9b91659bc1484f7aa89d))

* feat: emit 'device_selected' and 'scan_axis' from scan control widget ([`0b9b1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b9b1a3c89a98505079f7d4078915b7bbfaa1e23))

* feat: new 'device_selected' signals to ScanControl, ScanGroupBox, DeviceLineEdit ([`9801d27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9801d2769eb0ee95c94ec0c011e1dac1407142ae))

### Fixes

* fix: fix syntax due to change of api for simulated devices ([`19f4e40`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/19f4e407e00ee242973ca4c3f90e4e41a4d3e315))

* fix: remove wrongly scoped test ([`a23841b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a23841b2553dc7162da943715d58275c7dc39ed9))

* fix: rename 'compact' property -> 'compact_view' ([`6982711`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6982711fea5fb8a73845ed7c0692e3ec53ef7871))

* fix: Alignment 1D update, make app window a main window (in .ui file) ([`0015f0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0015f0e2d62adc02d3ef334e1f6dbb2d0288fec6))

* fix: set (Minimum, Fixed) size policy on Stop button ([`523cc43`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/523cc435725b10b7d59a4477a1aaa24a1f3e37a2))

### Refactoring

* refactor: redesign of scan selection and scan control boxes ([`a69d287`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a69d2870e2b3539739781d741b27b8599c0f4abd))

* refactor: move add/remove bundle to scan group box ([`e3d0a7b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3d0a7bbf9918dc16eb7227a178c310256ce570d))


## v0.118.0 (2024-10-13)

### Documentation

* docs(sphinx-build): adjusted pyside verion ([`b236951`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b23695167ab969f754a058ffdccca2b40f00a008))

### Features

* feat(image): image widget can take data from monitor_1d endpoint ([`9ef1d1c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ef1d1c9ac2178d9fa2e655942208f8abbdf5c1b))


## v0.117.1 (2024-10-11)

### Fixes

* fix(FPS): qtimer cleanup leaking ([`3a22392`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3a2239278075de7489ad10a58c31d7d89715e221))

### Unknown

* feature(vscode): added support for vscode instructions ([`f5f1f6c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f5f1f6c304b890dc162e8653005233bce4ea82e4))

* feature(vscode): support for controlling vscode from widgets ([`9238679`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/923867947f62db026ac0378c30ef62c883596058))


## v0.117.0 (2024-10-11)

### Features

* feat(utils): FPS counter utility based on the viewBox updates, integrated to waveform and image widget ([`8c5ef26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c5ef268430d5243ac05fcbbdb6b76ad24ac5735))

### Unknown

* tests(plot_base): tests extended ([`8dc892d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8dc892df0a47ccbdd812555b7c5775a455a23ede))


## v0.116.0 (2024-10-11)

### Build System

* build: fix PySide6 to 6.7.2 ([`908dbc1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/908dbc1760da5b323722207163f00850b84fb90b))

### Features

* feat: UI changes to have top toolbar with compact popup widgets (fix issue #360) ([`499b6b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/499b6b9a12efd931b5728b519404c41a7e29e4d6))

* feat: adapt BECQueue and BECStatusBox widgets to use CompactPopupWidget ([`94ce92f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/94ce92f5b054d25ea3bb7976c1f75e14b78b9edc))

* feat: add 'CompactPopupWidget' container widget

Makes it easy to write widgets which can have a compact
representation with LED-like global state indicator,
with the possibility to display a popup dialog with more
complete UI ([`49268e3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/49268e3829406d70b09e4d88989812f5578e46f4))


## v0.115.0 (2024-10-08)

### Features

* feat: add bec-app script to launch applications ([`8bf4842`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8bf48427884338672a8e3de3deb20439b0bfdf99))

### Fixes

* fix: make Alignment1D a MainWindow as it is an application ([`c5e9ed6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5e9ed6e422acb908e1ada32822f5d7cc256ade7))

* fix: adjust bec_qthemes dependency ([`b207e45`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b207e45a67818ee061272ce00a09fe7ea31cd1ba))


## v0.114.0 (2024-10-02)

### Features

* feat: new 'scan_axis' signal

Signal is emitted before "scan_started", to inform about scan positioner
and (start, stop) positions. In case of multiple bundles, the signal
is emitted multiple times. ([`f084e25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f084e2514bc9459cccaa951b79044bc25884e738))

### Fixes

* fix: prevent exception when empty string updates are coming from widget ([`04cfb1e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/04cfb1edf19437d54f07b868bcf3cfc2a35fd3bc))

* fix: use new 'scan_axis' signal, to set_x and select x axis on waveform

Fixes #361, do not try to change x axis when not permitted ([`efa2763`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efa276358b0f5a45cce9fa84fa5f9aafaf4284f7))


## v0.113.0 (2024-10-02)

### Features

* feat: add first draft for alignment_1d GUI ([`63c24f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63c24f97a355edaa928b6e222909252b276bcada))

* feat: add move to position button to lmfit dialog ([`281cb27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/281cb27d8b5433e27a7ba0ca0a19e4b45b9c544f))

### Fixes

* fix: add is_log checks and functionality to plot_indicator_items ([`0f9953e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f9953e8fdcf3f9b5a09f994c69edb6b34756df9))

### Refactoring

* refactor: various minor improvements for the alignment gui ([`f554f3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f554f3c1672c4fe32968a5991dc98802556a6f3b))

* refactor: allow hiding of arg/kwarg boxes ([`efe90eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efe90eb163e2123a5b4d0bb59f66025a569336ad))

* refactor: add proxy to waveform to limit the dap_request frequency ([`5c74037`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c740371d86d9b1b341bc3c4d8bdf62027aa089b))

* refactor: update dap_model also if x and y axis are selected ([`28ee385`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28ee3856be2c47a63182b16454ece37a0ec04811))

* refactor: linear_region_selector accepts log_x data ([`7cc0726`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7cc07263982a171744ff87adb10ea77585764b71))

* refactor: use accent colors for bec_status_box icons; closes #338 ([`e039304`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e039304fd3ee03dc4a3fa22a69c207139e0c0d28))

### Testing

* test: add tests for scan_status_callback ([`dc0c825`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dc0c825fd594c093a24543ff803d6c6564010e92))

### Unknown

* feat : Add bec_signal_proxy to handle signals with option to unblock them manually. ([`1dcfeb6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1dcfeb6cfce3c69f0c5401731d4d3f9a1981b22e))


## v0.112.1 (2024-09-19)

### Documentation

* docs(dap_combo_box): updated screenshot ([`e3b5e33`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3b5e338bfaec276979183fb6d79ab41a7ca21e1))

### Fixes

* fix: test e2e dap wait_for_fit ([`b2f7d3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2f7d3c5f3f4bf00cc628f788e2c278ebb5688ae))
