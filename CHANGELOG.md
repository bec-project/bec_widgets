# CHANGELOG


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

* docs(device_box): updated screenshot ([`c8e614b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8e614b575b48be788a6389a7aa0cfa033d86ab8))

### Fixes

* fix: test e2e dap wait_for_fit ([`b2f7d3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2f7d3c5f3f4bf00cc628f788e2c278ebb5688ae))


## v0.112.0 (2024-09-17)

### Features

* feat: console: various improvements, auto-adapt rows to widget size, Qt Designer plugin ([`286ad71`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/286ad7196b0b8562d648fb304eab7d759b6a959b))


## v0.111.0 (2024-09-17)

### Documentation

* docs(position_indicator): updated position indicator documentation and added designer properties ([`60f7d54`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60f7d54e2b4c3129de6c95729b8b4aea1757174f))

### Features

* feat(position_indicator): improved design and added more customization options ([`d15b222`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d15b22250fbceb708d89872c0380693e04acb107))

### Fixes

* fix(position_indicator): fixed user access ([`dd932dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd932dd8f3910ab67ec8403124f4e176d048e542))

* fix(generate_cli): fixed type annotations ([`d3c1a1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d3c1a1b2edcba7afea9d369820fa7974ac29c333))

* fix(positioner_box): visual improvements to the positioner_box and positioner_control_line ([`7ea4a48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ea4a482e7cd9499a7268ac887b345cab01632aa))

* fix(palette viewer): fixed background for tool tip ([`9045323`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9045323049d2a39c36fc8845f3b2883d6933436b))


## v0.110.0 (2024-09-12)

### Features

* feat(palette_viewer): added widget to display the current palette and accent colors ([`a8576c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8576c164cad17746ec4fcd5c775fb78f70c055c))


## v0.109.1 (2024-09-09)

### Fixes

* fix: refactor textbox widget, remove inheritance, adhere to bec style; closes #324 ([`b0d786b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b0d786b991677c0846a0c6ba3f2252d48d94ccaa))


## v0.109.0 (2024-09-06)

### Features

* feat(accent colors): added helper function to get all accent colors ([`84a59f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84a59f70eed6d8a3c3aeeabc77a5f9ea4e864f61))

### Fixes

* fix(theme): fixed theme access for themecontainer ([`de303f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/de303f0227fc9d3a74a0410f1e7999ac5132273c))


## v0.108.0 (2024-09-06)

### Documentation

* docs(progressbar): added docs ([`7d07cea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d07cea946f9c884477b01bebfb60b332ff09e0a))

### Features

* feat(progressbar): added bec progressbar ([`f6d1d0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f6d1d0bbe3ba30a3b7291cd36a1f7f8e6bd5b895))
