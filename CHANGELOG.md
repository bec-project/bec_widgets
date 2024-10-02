# CHANGELOG

## v0.113.0 (2024-10-02)

### Feature

* feat: add first draft for alignment_1d GUI ([`63c24f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63c24f97a355edaa928b6e222909252b276bcada))

* feat: add move to position button to lmfit dialog ([`281cb27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/281cb27d8b5433e27a7ba0ca0a19e4b45b9c544f))

### Fix

* fix: add is_log checks and functionality to plot_indicator_items ([`0f9953e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f9953e8fdcf3f9b5a09f994c69edb6b34756df9))

### Refactor

* refactor: various minor improvements for the alignment gui ([`f554f3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f554f3c1672c4fe32968a5991dc98802556a6f3b))

* refactor: allow hiding of arg/kwarg boxes ([`efe90eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efe90eb163e2123a5b4d0bb59f66025a569336ad))

* refactor: add proxy to waveform to limit the dap_request frequency ([`5c74037`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c740371d86d9b1b341bc3c4d8bdf62027aa089b))

* refactor: update dap_model also if x and y axis are selected ([`28ee385`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28ee3856be2c47a63182b16454ece37a0ec04811))

* refactor: linear_region_selector accepts log_x data ([`7cc0726`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7cc07263982a171744ff87adb10ea77585764b71))

* refactor: use accent colors for bec_status_box icons; closes #338 ([`e039304`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e039304fd3ee03dc4a3fa22a69c207139e0c0d28))

### Test

* test: add tests for scan_status_callback ([`dc0c825`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dc0c825fd594c093a24543ff803d6c6564010e92))

### Unknown

* feat : Add bec_signal_proxy to handle signals with option to unblock them manually. ([`1dcfeb6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1dcfeb6cfce3c69f0c5401731d4d3f9a1981b22e))

## v0.112.1 (2024-09-19)

### Documentation

* docs(dap_combo_box): updated screenshot ([`e3b5e33`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3b5e338bfaec276979183fb6d79ab41a7ca21e1))

* docs(device_box): updated screenshot ([`c8e614b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8e614b575b48be788a6389a7aa0cfa033d86ab8))

### Fix

* fix: test e2e dap wait_for_fit ([`b2f7d3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2f7d3c5f3f4bf00cc628f788e2c278ebb5688ae))

## v0.112.0 (2024-09-17)

### Feature

* feat: console: various improvements, auto-adapt rows to widget size, Qt Designer plugin ([`286ad71`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/286ad7196b0b8562d648fb304eab7d759b6a959b))

## v0.111.0 (2024-09-17)

### Documentation

* docs(position_indicator): updated position indicator documentation and added designer properties ([`60f7d54`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60f7d54e2b4c3129de6c95729b8b4aea1757174f))

### Feature

* feat(position_indicator): improved design and added more customization options ([`d15b222`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d15b22250fbceb708d89872c0380693e04acb107))

### Fix

* fix(position_indicator): fixed user access ([`dd932dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd932dd8f3910ab67ec8403124f4e176d048e542))

* fix(generate_cli): fixed type annotations ([`d3c1a1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d3c1a1b2edcba7afea9d369820fa7974ac29c333))

* fix(positioner_box): visual improvements to the positioner_box and positioner_control_line ([`7ea4a48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ea4a482e7cd9499a7268ac887b345cab01632aa))

* fix(palette viewer): fixed background for tool tip ([`9045323`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9045323049d2a39c36fc8845f3b2883d6933436b))

## v0.110.0 (2024-09-12)

### Feature

* feat(palette_viewer): added widget to display the current palette and accent colors ([`a8576c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8576c164cad17746ec4fcd5c775fb78f70c055c))

## v0.109.1 (2024-09-09)

### Fix

* fix: refactor textbox widget, remove inheritance, adhere to bec style; closes #324 ([`b0d786b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b0d786b991677c0846a0c6ba3f2252d48d94ccaa))

## v0.109.0 (2024-09-06)

### Feature

* feat(accent colors): added helper function to get all accent colors ([`84a59f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84a59f70eed6d8a3c3aeeabc77a5f9ea4e864f61))

### Fix

* fix(theme): fixed theme access for themecontainer ([`de303f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/de303f0227fc9d3a74a0410f1e7999ac5132273c))

## v0.108.0 (2024-09-06)

### Documentation

* docs(progressbar): added docs ([`7d07cea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d07cea946f9c884477b01bebfb60b332ff09e0a))

### Feature

* feat(progressbar): added bec progressbar ([`f6d1d0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f6d1d0bbe3ba30a3b7291cd36a1f7f8e6bd5b895))

* feat(generate_cli): added support for property and qproperty setter ([`a52182d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a52182dca978833bfc3fad755c596d3a2ef45c42))

## v0.107.0 (2024-09-06)

### Documentation

* docs: extend waveform docs ([`e6976dc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6976dc15105209852090a00a97b7cda723142e9))

### Feature

* feat: add roi select for dap, allow automatic clear curves on plot request ([`7bdca84`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7bdca8431496fe6562d2c28f5a6af869d1a2e654))

### Refactor

* refactor: change style to bec_accent_colors ([`bd126dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bd126dddbbec3e6c448cce263433d328d577c5c0))

### Test

* test: add tests, including extension to end-2-end test ([`b1aff6d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b1aff6d791ff847eb2f628e66ccaa4672fdeea08))

## v0.106.0 (2024-09-05)

### Feature

* feat(plot_base): toggle to switch outer axes for plotting widgets ([`06d7741`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06d7741622aea8556208cd17cae521c37333f8b6))

### Refactor

* refactor: use DAPComboBox in curve_dialog selection ([`998a745`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/998a7451335b1b35c3e18691d3bab8d882e2d30b))

### Test

* test: fix tests ([`6b15abc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b15abcc73170cb49292741a619a08ee615e6250))

## v0.105.0 (2024-09-04)

### Feature

* feat: add dap_combobox ([`cc691d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cc691d4039bde710e78f362d2f0e712f9e8f196f))

### Refactor

* refactor: cleanup and renaming of slot/signals ([`0fd5cee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fd5cee77611b6645326eaefa68455ea8de26597))

* refactor(logger): changed prints to logger calls ([`3a5d7d0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3a5d7d07966ab9b38ba33bda0bed38c30f500c66))

## v0.104.0 (2024-09-04)

### Fix

* fix(scan_control): SafeSlot applied to run_scan to avoid faulty scan requests ([`9047916`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90479167fb5cae393c884e71a80fcfdb48a76427))
