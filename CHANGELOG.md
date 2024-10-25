# CHANGELOG


## v1.1.0 (2024-10-25)

### Features

* feat: add filter i/o utility class ([`0350833`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0350833f36e0a7cadce4173f9b1d1fbfdf985375))

### Refactoring

* refactor: do not flush selection upon receiving config update; allow widgetIO to receive kwargs to be able to use get_value to receive string instead of int for QComboBox ([`91959e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91959e82de8586934af3ebb5aaa0923930effc51))

* refactor: allow to set selection in DeviceInput; automatic update of selection on device config update; cleanup ([`5eb15b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5eb15b785f12e30eb8ccbc56d4ad9e759a4cf5eb))

* refactor: cleanup, added device_signal for signal inputs ([`6fb2055`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fb20552ff57978f4aeb79fd7f062f8d6b5581e7))

### Testing

* test(scan_control): tests added for grid_scan to ensure scan_args signal validity ([`acb7902`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/acb79020d4be546efc001ff47b6f5cdba2ee9375))


## v1.0.2 (2024-10-22)

### Bug Fixes

* fix(scan_control): scan args signal fixed to emit list instead of hardcoded structure ([`4f5448c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f5448cf51a204e077af162c7f0aed1f1a60e57a))


## v1.0.1 (2024-10-22)

### Bug Fixes

* fix(waveform): added support for live_data and data access ([`7469c89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7469c892c8076fc09e61f173df6920c551241cec))


## v1.0.0 (2024-10-18)

### Breaking

* feat!: ability to disable scatter from waveform & compatible crosshair with down sampling ([`2ab12ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2ab12ed60abb995abc381d9330fdcf399796d9e5))

### Bug Fixes

* fix(crosshair): downsample clear markers ([`f9a889f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f9a889fc6d380b9e587edcb465203122ea0bffc1))


## v0.119.0 (2024-10-17)

### Bug Fixes

* fix: fix syntax due to change of api for simulated devices ([`19f4e40`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/19f4e407e00ee242973ca4c3f90e4e41a4d3e315))

* fix: remove wrongly scoped test ([`a23841b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a23841b2553dc7162da943715d58275c7dc39ed9))

* fix: rename 'compact' property -> 'compact_view' ([`6982711`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6982711fea5fb8a73845ed7c0692e3ec53ef7871))

* fix: Alignment 1D update, make app window a main window (in .ui file) ([`0015f0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0015f0e2d62adc02d3ef334e1f6dbb2d0288fec6))

* fix: set (Minimum, Fixed) size policy on Stop button ([`523cc43`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/523cc435725b10b7d59a4477a1aaa24a1f3e37a2))

### Features

* feat: new PositionerGroup widget ([`af9655d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af9655de0c541092437accfbaa779628a2f48ccb))

* feat: add 'expand_popup' property to CompactPopupWidget

This property tells if expand should show a popup (by default), or
if the widget should expand in-place ([`e4121a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4121a01cb6b8d496e630cd43bc642b994b8f310))

* feat: PositionerBox with a popup view ([`2615787`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/261578796f1de8ca9cab9b91659bc1484f7aa89d))

* feat: emit 'device_selected' and 'scan_axis' from scan control widget ([`0b9b1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b9b1a3c89a98505079f7d4078915b7bbfaa1e23))

* feat: new 'device_selected' signals to ScanControl, ScanGroupBox, DeviceLineEdit ([`9801d27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9801d2769eb0ee95c94ec0c011e1dac1407142ae))

### Refactoring

* refactor: redesign of scan selection and scan control boxes ([`a69d287`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a69d2870e2b3539739781d741b27b8599c0f4abd))

* refactor: move add/remove bundle to scan group box ([`e3d0a7b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3d0a7bbf9918dc16eb7227a178c310256ce570d))


## v0.118.0 (2024-10-13)

### Documentation

* docs(sphinx-build): adjusted pyside verion ([`b236951`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b23695167ab969f754a058ffdccca2b40f00a008))

### Features

* feat(image): image widget can take data from monitor_1d endpoint ([`9ef1d1c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ef1d1c9ac2178d9fa2e655942208f8abbdf5c1b))


## v0.117.1 (2024-10-11)

### Bug Fixes

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

### Bug Fixes

* fix: make Alignment1D a MainWindow as it is an application ([`c5e9ed6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5e9ed6e422acb908e1ada32822f5d7cc256ade7))

* fix: adjust bec_qthemes dependency ([`b207e45`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b207e45a67818ee061272ce00a09fe7ea31cd1ba))

### Features

* feat: add bec-app script to launch applications ([`8bf4842`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8bf48427884338672a8e3de3deb20439b0bfdf99))


## v0.114.0 (2024-10-02)

### Bug Fixes

* fix: prevent exception when empty string updates are coming from widget ([`04cfb1e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/04cfb1edf19437d54f07b868bcf3cfc2a35fd3bc))

* fix: use new 'scan_axis' signal, to set_x and select x axis on waveform

Fixes #361, do not try to change x axis when not permitted ([`efa2763`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efa276358b0f5a45cce9fa84fa5f9aafaf4284f7))

### Features

* feat: new 'scan_axis' signal

Signal is emitted before "scan_started", to inform about scan positioner
and (start, stop) positions. In case of multiple bundles, the signal
is emitted multiple times. ([`f084e25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f084e2514bc9459cccaa951b79044bc25884e738))


## v0.113.0 (2024-10-02)

### Testing

* test: add tests for scan_status_callback ([`dc0c825`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dc0c825fd594c093a24543ff803d6c6564010e92))
