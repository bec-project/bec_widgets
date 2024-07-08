# CHANGELOG

## v0.83.0 (2024-07-08)

### Feature

* feat: added reference utils to compare renderings of widgets ([`2988fd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2988fd387e6b8076fffec1d57e3ccab89ddb2aeb))

* feat(widgets): added device box with spinner ([`1b017ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b017edfad8e78fa079210486123976695b8915c))

* feat(designer): added option to skip the widget validation for DesignerPluginGenerator ([`41bcb80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/41bcb801674ab6c4d6069bba34ffee09c9e665db))

### Fix

* fix(terminal): added default args to avoid designer crashes on startup ([`360d171`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/360d17135573e44b80ab517756da3c0b31daab0f))

* fix(widget): fixed widget cleanup routine ([`2b29e34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b29e34b52d056349647bb2fcf649b749a60d292))

* fix(bec_widget): added cleanup method to bec widget base class ([`fd8766e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fd8766ed87770661da6591aeb4df5abdaf38afc7))

* fix(website): fixed dummy input ([`903ce7d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/903ce7d46b5d37d40486d0fda92d3694d3faca62))

### Test

* test(vscode): fixed vscode tests for new cleanup routine ([`eb26e2a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb26e2a11b229a52efe2e6d4fb28d760d3740136))

* test(vscode): improved vscode test ([`5de8804`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5de8804da1e41eafad2472344904b3324438c13b))

## v0.82.2 (2024-07-08)

### Fix

* fix(rpc_server): pass cli config to server ([`90178e2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90178e2f61fa9dac7d82c0d0db40a9767bb133e6))

## v0.82.1 (2024-07-07)

### Fix

* fix(motor_map): bug where motors without limits were selected ([`c78cd89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c78cd898f203f950d7cb589eb5609feaa88062cf))

### Refactor

* refactor(setting_dialog): moved to qt_utils ([`3826bb3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3826bb3d9e870e85709b5b20ef09a4d22641280c))

* refactor(toolbar): toolbar moved from widgets to qt_utils ([`7ffc06f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ffc06f3c7ddd86a1681408a75221b9bbadb236b))

### Test

* test(setting_dialog): tests added ([`74a249b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/74a249bd065d01006cb532bfff2a9bfedb34b592))

### Unknown

* tests(motor_map_widget): tests added ([`734f4c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/734f4c77507a1edafd477d81b5f7401d8e759be2))

* feat(settings_dialog):apply button ([`2020953`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2020953b933b6fcad61ecc770588d39518c26fdd))

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
