# CHANGELOG

## v0.82.0 (2024-07-07)

### Feature

* feat(toggle): added angular component-like toggle ([`b9bff38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b9bff38b64b86f06b3bc047922ef9df0c7d32e71))

### Refactor

* refactor(device_input): DeviceComboBox and DeviceLineEdit moved to top layer of widgets ([`f048629`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f04862933f049030554086adef3ec9e1aebd3eda))

* refactor(stop_button): moved to top layer, plugin added ([`f5b8375`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f5b8375fd36e3bb681de571da86a6c0bdb3cb6f0))

* refactor(motor_map_widget): removed restriction of only PySide6 for widget ([`db1cdf4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db1cdf42806fef6d7c6d2db83528f32df3f9751d))

* refactor(color_button): ColorButton moved to top level of widgets ([`fa1e86f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa1e86ff07b25d2c47c73117b00765b8e2f25da4))

## v0.81.2 (2024-07-07)

### Fix

* fix(waveform): scan_history error check for IndexError ([`dd1875e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd1875ea5cc18bcef9aad743347a8accf144c08d))

## v0.81.1 (2024-07-07)

### Fix

* fix(motor_control): temporary remove of motor control widgets ([`99114f1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99114f14f62202e1fd8bf145616fa8c69937ada4))

## v0.81.0 (2024-07-06)

### Feature

* feat(color_button): can get colors in RGBA or HEX ([`9594be2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9594be260680d11c8550ff74ffb8d679e5a5b8f6))

## v0.80.1 (2024-07-06)

### Fix

* fix(entry_validator): check for entry == &#34;&#34; ([`61de7e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61de7e9e221c766b9fb3ec23246da6a11c96a986))

## v0.80.0 (2024-07-06)

### Feature

* feat(qt5): dropped support for qt5; pyside2 and pyqt5 ([`fadbf77`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fadbf77866903beff6580802bc203d53367fc7e7))

* feat(plugins): moved plugin dict to dataclass and container ([`03819a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/03819a3d902b4a51f3e882d52aedd971b2a8e127))

* feat(plugins): added support for pyqt6 ui files ([`d6d0777`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d6d07771135335cb78dc648508ce573b8970261a))

* feat(plugins): added bec widgets base class ([`1aa83e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1aa83e0ef1ffe45b01677b0b4590535cb0ca1cff))

## v0.79.3 (2024-07-05)

### Fix

* fix: changed inheritance to adress qt designer bug in rendering ([`e403870`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e403870874bd5e45840a034d6f1b3dd576d9c846))

* fix: add designer plugin classes ([`1586ce2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1586ce2d6cba2bb086b2ef596e724bb9e40ab4f2))

### Refactor

* refactor: simplify logic in bec_status_box ([`576353c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/576353cfe8c6fd64db561f0b6e2bc951300643d3))

## v0.79.2 (2024-07-04)

### Fix

* fix: overwrite closeEvent and call super class ([`bc0ef78`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc0ef7893ef100b71b62101c459655509b534a56))

## v0.79.1 (2024-07-03)

### Fix

* fix: use libdir env var to preload Python library, also for Linux platform ([`d7718d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d7718d4dcb9728c050b6421388af4d484f3741f2))

## v0.79.0 (2024-07-03)

### Feature

* feat(motor_map_widget): standalone MotorMap Widget with toolbar + plugin ([`6e75642`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6e756420907d7093557e945bc92bc4cfc0138d07))

* feat(motor_map): method to reset history trace ([`5960918`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5960918137dd41cdeb94e50f8abc4f169cf45c11))

### Fix

* fix(toolbar): change default color to black to match BECFigure theme ([`b8774e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8774e0b0bc43dcd00f94f42539a778e507ca27d))

* fix(motor_map): fixed bug with residual trace after changing motors ([`aaa0d10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aaa0d1003d2e94b45bafe4f700852c2c05288aea))

* fix(widget_io): widget handler adjusted for spinboxes and comboboxes ([`3dc0532`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3dc0532df05b6ec0a2522107fa0b1e210ce7d91b))

### Refactor

* refactor(toolbar): cleanup and adjusted colors ([`96863ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/96863adf53c15112645d20eb6200733617801c6d))

## v0.78.1 (2024-07-02)

### Fix

* fix(ui_loader): ui loader is compatible with bec plugins ([`b787759`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b787759f44486dc7af2c03811efb156041e4b6cb))

## v0.78.0 (2024-07-02)

### Feature

* feat(color_button): patched ColorButton from pyqtgraph to be able to be opened in another QDialog ([`c36bb80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c36bb80d6a4939802a4a1c8e5452c7b94bac185e))

## v0.77.0 (2024-07-02)

### Feature

* feat(bec_connector): export config to yaml ([`a391f30`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a391f3018c50fee6a4a06884491b957df80c3cd3))

* feat(utils): colors added convertor for rgba to hex ([`572f2fb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/572f2fb8110d5cb0e80f3ca45ce57ef405572456))

### Fix

* fix(waveform): scatter 2D brush error ([`215d59c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/215d59c8bfe7fda9aff8cec8353bef9e1ce2eca1))

* fix(figure): API cleanup ([`008a33a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/008a33a9b192473cc58e90cd6d98c5bcb5f7b8c0))

* fix(figure): if/else logic corrected in subplot_factory ([`3e78723`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3e787234c7274b0698423d7bf9a4c54ec46bad5f))

* fix(image): processing of already displayed data; closes #106 ([`1173510`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1173510105d2d70d7e498c2ac1e122cea3a16597))

* fix(bec_figure): full reconstruction with config from other bec figure ([`b6e1e20`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b6e1e20b7c8549bb092e981062329e601411dda6))

* fix(motor_map): API changes updates current visualisation; motor_map can be initialised from config ([`2e2d422`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2e2d422910685a2527a3d961a468c787f771ca44))

* fix(image): image add_custom_image fixed, closes #225 ([`f0556e4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0556e44113ffee66cf735aa2dd758c62cb634f4))

* fix(figure): subplot methods consolidated; added subplot factory ([`4a97105`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a97105e4bd2ce77d72dfe5f8307dd9ee65b21b0))

* fix(image): image can be fully reconstructed from config ([`797f73c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/797f73c39aa73e07d6311f3de4baea53f6c380e0))

* fix(image_item): vrange added int for pydantic model check ([`b8f796f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8f796fd3fcc15641e8fc6a3ca75c344ce90fc45))
