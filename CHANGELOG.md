# CHANGELOG

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

### Documentation

* docs(scan_control): docs extended ([`730e25f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/730e25fd3a8be156603005982bfd2a2c2b16dff1))

### Feature

* feat(scan_control): scan control remember the previously set parameters and shares kwarg settings across scans ([`d28f9b0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d28f9b04c45385179353cc247221ec821dcaa29b))

### Fix

* fix(scan_control): SafeSlot applied to run_scan to avoid faulty scan requests ([`9047916`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90479167fb5cae393c884e71a80fcfdb48a76427))

* fix(scan_control): scan parameters can be loaded from the last executed scan from redis ([`ec3bc8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec3bc8b5194c680b847d3306c41eef4638ccfcc7))

* fix(toggle): state can be determined with the widget initialisation ([`2cd9c7f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2cd9c7f5854f158468e53b5b29ec31b1ff1e00e6))

### Refactor

* refactor(scan_control): scan control layout adjusted ([`85dcbda`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/85dcbdaa88fe77aeea7012bfc16f10c4f873f75e))

* refactor(scan_control): basic pydantic config added ([`fe8dc55`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe8dc55eb102c51c34bf9606690914da53b5ac02))

### Test

* test(scan_control): tests extended for getting kwargs between scan switching and getting parameters from redis ([`b07e677`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b07e67715c9284e9bf36056ba4ba8068f60cbaf3))

* test(conftest): only run cleanup checks if test passed ([`26920f8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/26920f8482bdb35ece46df37232af50ab9cab463))

## v0.103.0 (2024-09-04)

### Feature

* feat(vscode): open vscode on a free port ([`52da835`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52da835803f2453096a8b7df23bee5fdf93ae2bb))

* feat(website): added method to wait until the webpage is loaded ([`9be19d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9be19d4abebad08c5fc6bea936dd97475fe8f628))

### Test

* test(webview): fixed tests after refactoring ([`d5eb30c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d5eb30cd7df4cb0dc3275dd362768afc211eaf2d))
