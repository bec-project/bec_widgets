# CHANGELOG

## v0.90.0 (2024-07-23)

### Feature

* feat(image_widget): plugin added ([`4371168`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/43711680ba253f81fb0ffe764bcaae701b02bb49))

* feat(image_widget): all toolbar actions added ([`501eb92`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/501eb923f12fa6aaa93f5428ca78e57694edfbc0))

* feat(image_widget): image_widget added ([`6a9317f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a9317facda896ee784c7fc1db0cd3d68cdfcf73))

### Fix

* fix(axis_setting): fix compatibility for issue with horizontal line for PyQt6 ([`1cf6e32`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1cf6e32303f82bc7c3f3391d0e96a88bc31f29fc))

* fix(image_widget): image_widget autorange fixed ([`7f49893`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7f49893d2ce3b9d02efa764f7f10442ed6ab8f3c))

* fix(image_widget): image widget adjusted ([`3d2ca48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3d2ca4855c36fe0af59a4b540caa3c8023a81773))

* fix(image): only single monitor image is allowed ([`fe7e542`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe7e542b19dc5b401523501acb74ac03edf62ad4))

* fix(image): raw data are saved in image item to always have precise processing ([`c15035b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c15035b6b769a96780a16da9e7f75af3b823654c))

### Refactor

* refactor(jupyter_console_example): added examples of standalone widgets ([`ba0d1ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ba0d1ea9031b4ae2e2e73bf269fbfad973b924a5))

### Test

* test(image_widget): tests added ([`70fb276`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/70fb276fdf31dffc105435d3dfe7c5caea0b10ce))

## v0.89.0 (2024-07-22)

### Feature

* feat(themes): moved themes to bec_qthemes ([`3798714`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3798714369adf4023f833b7749d2f46a0ec74eee))

### Unknown

* Revert &#34;feat(themes): moved themes to bec_qthemes&#34;

This reverts commit 3798714369adf4023f833b7749d2f46a0ec74eee ([`fd6ae91`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fd6ae91993a23a7b8dbb2cf3c4b7c3eda6d2b0f6))

## v0.88.1 (2024-07-22)

### Documentation

* docs: readthedocs icon path fixed ([`2bcaa42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2bcaa4256d6daaefacb3ead8c72458d7b1498e29))

### Fix

* fix(plot_base): set_xy autorange moved to plotbase from waveform ([`a3dff7d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3dff7decc16115c12dc6b4ef1572552368da309))

### Refactor

* refactor(toolbar): generalizations of the ToolBarAction ([`ad112d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad112d1f08157f6987edd48a0bacf9f669ef1997))

## v0.88.0 (2024-07-19)

### Feature

* feat(waveform_widget): designer plugin added ([`1f8ef52`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f8ef52b606283038052640849094f515a463403))

* feat(waveform_widget): switch between drag and rectangle mode ([`2be009c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2be009c6477ba26c5cfb4d827534c5d5eb428999))

* feat(waveform_widget): autorange button ([`8df6b00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8df6b003e5c6a942fa2e875d9790e492c087bf26))

* feat(waveform_widget): dap parameter window ([`1e551d6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1e551d6e9696f79ea2e0a179d13a4fc6c2a128b2))

* feat(waveform): export to matplotlib window of current scene ([`8d93405`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8d9340539967b06b1e15f21a2106a39d5c740f31))

* feat(figure): export dialog can be launched from CLI and from toolbar ([`6ff6111`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ff611109153b9412dce37c527b19e839d99bba7))

* feat(waveform_widget): added error handle utility ([`a8ff1d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8ff1d4cd09cae5eaeb4bd0ea90fdd102e32f3a3))

* feat(curve_dialog): add DAP functionality ([`e830565`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e8305652fde384da037242cf8f7e3606f22bcfb6))

* feat(curve_dialog): curves can be added ([`c926a75`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c926a75a7927d672c044ea8f68771209ae5accc6))

* feat(waveform_widget): BECWaveformWidget toolbar added import/export config ([`fa9b171`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa9b17191ddbb4043a658dae9aa0801e1dc22b84))

* feat(waveform_widget): BECWaveformWidget added with toolbar ([`755b394`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/755b394c1c4d7c443c442d89c630d08ce5415554))

### Fix

* fix(waveform_widget): plot API unified with BECFigure ([`2c8764a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2c8764a27de89b39b717032b58465e120ec57fbc))

* fix(colormap_selector): compatibility for PyQt6 when using designer fixed ([`50135b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50135b5fe90a88618291e9357f180cb19251dace))

* fix(waveform_widget): adapted for BECWidget base class ([`6eb313f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6eb313fa76e559d62ecd8fa8849142b83817e47c))

* fix(waveform_widget): temporary disabled save/load config ([`7089cf3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7089cf356a43d805241d5621952e544d690e65e0))

* fix(waveform_widget): use @SafeSlot decorator for automatic error message ([`8e588d7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8e588d79c86e950f6915e89c08fa9415c4bd8033))

* fix(waveform): colormaps of curves can be changed and normalised

feat(waveform): colormap can be changed from curve dialog

fix(curve_dialog): default dialog parameters fixed

curve Dialog colormap WIP ([`33495cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/33495cfe03b363f18db61d8af2983f49027b7a43))

* fix(waveform_widget): adapted for changes from improved scan logic from waveform widget ([`8ac35d7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ac35d7280b1ff007c10612228d163cc0c5d1a99))

### Refactor

* refactor(icons): icons moved to the assets directory ([`a8b6ef2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8b6ef20cccae87515b10f054d0ed5b10e152769))

* refactor(waveform_widget): removed PYSIDE6 check ([`47fcb9e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/47fcb9ebfe35ae600cced95a1edc68f6f6e37a04))

### Test

* test(waveform_widget): test added ([`8d764e2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8d764e2d46a1e017dadc3c4630648c1ca708afc2))

## v0.87.1 (2024-07-18)

### Fix

* fix(dock): added hasattr to cleanup method for widgets ([`d75c55b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d75c55b2b1ccf156fb789c7813f1c5bdf256f860))

* fix: add missing close() call, ensure jupyter console client.shutdown() is called in closeEvent ([`e52ee26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e52ee2604cb35096f1bd833ca9516d8a34197d35))

* fix: BECWidget checks if it is a widget, and implements closeEvent and cleanup ([`d64758f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d64758f268cad69e6a17bd52dc9913a6367d3cde))

* fix: add exit handlers for BECConnection objects ([`6202d22`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6202d224fe85c103a4c33bd8c255f18cfd027303))

### Refactor

* refactor: BECWidget is a mixin based on BECConnector, for each QWidget in BEC

Handles closeEvent() and RPC registering/unregistering ([`c7feb69`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c7feb6952d590b569f7b0cba3b019a9af0ce0c93))

## v0.87.0 (2024-07-17)

### Feature

* feat(qt_utils): added warning utility with simple API to setup warning message ([`787f749`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/787f74949bac27aaa51cbb43911919071481707c))

* feat(qt_utils): added error handle utility with popup messageBoxes ([`196ef7a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/196ef7afe11a1b5dcc536f8859dc3b6044ea628e))

### Unknown

* tests: add unit tests for error and warning message boxes ([`8f104cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8f104cf4024d3a4516e6aba5daa8fb78c85e2bfd))

## v0.86.0 (2024-07-17)
