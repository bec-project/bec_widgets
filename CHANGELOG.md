# CHANGELOG

## v0.85.1 (2024-07-17)

### Fix

* fix(waveform): readout_priority dict fixed, not overwritten to &#39;baseline&#39; key ([`b5b0aa4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b5b0aa4f82a998bb0162dc319591e854204a7354))

## v0.85.0 (2024-07-16)

### Feature

* feat(color_map_selector): added colormap selector with plugin ([`b98fd00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b98fd00adef97adf57f49b60ade99972b9f5a6bc))

## v0.84.0 (2024-07-15)

### Feature

* feat(waveform): async readback update implemented for async devices ([`0c6a9f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0c6a9f2310df31ddcd68050a17cfbf52c3e2e226))

* feat(waveform): data are taken directly from ScanItem which is defined from scan_status endpoint; scan update is triggered from scan_segment; plots can be added just specifying y_name -&gt; best effort for setting x reported device ([`b8717f1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8717f13276734dd655ab03cd6005985ad5af9fb))

### Fix

* fix(waveform): timestamp are not converted to human readable format ([`e495fd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e495fd30c4c16474689943c7263e3060cb09ffb4))

* fix(waveform): set_x method various bugs fixed ([`8516a1d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8516a1d639925a877f174fa13f427a71131cc918))

* fix(waveform): x axis switching logic fixed when axis are not compatible ([`e4e1a90`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4e1a905d19def22f970b364c18c953f00e10389))

* fix(waveform): dap leaked RID for all daps in current process; dap RID is now f&#34;{scan_id}-{gui_id}&#34; to distinguish for each plot instance ([`d23fd8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d23fd8bd074ede6e14eb8e85e025cbced4bd45ef))

* fix(waveform): only one type of x axis allowed; x mode validated ([`9d6ae87`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d6ae87d0f03ca227570fcca8af2d8190828d271))

* fix(waveform): data for axis are taken by separate method; validation consolidated ([`fc5a8bd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc5a8bdd8b260f5e9b59ec71a4610c57442e43fe))

* fix(bec_dispatcher): connect_slot can accept kwargs ([`0aa317a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0aa317aae58d3612d46f05b85f8b0db3d12bbe14))

### Refactor

* refactor(waveform): plot can be prompted without specifying kwargs ([`48911e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48911e934815923c94edb5ced6042058a11a97f5))

* refactor(jupyter_console_window): added more examples of waveforms ([`fc935d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc935d9fc81067c3a67389ff88ea97da2e0c903e))

### Test

* test(waveform): tests extended ([`006992e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/006992e43cc56d56261bc4fd3e9cae9abcab2153))

## v0.83.1 (2024-07-14)

### Fix

* fix(toolbar): default transparent background ([`eab7883`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eab78839792f175b7ac127ca603385c6baa5ff15))

* fix: use apply_theme ([`2d4249e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d4249e73a792fed1c2c7ab79bb8aec38c57466c))

* fix: spinner: update reference image for widget test, use apply_theme ([`63db135`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63db1352ee883d35670b3a692dbe51d6d01872ae))

* fix: replace pyqtdarktheme by qdarkstyle, add &#39;apply_theme&#39; function (in utils/colors.py) ([`8308115`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8308115f3646245d825fc47ab57297d3460bbcf5))

### Test

* test(toolbar): added reference pngs for spinner for Darwin ([`11a7204`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11a7204c98e0bf211a8721d296b45d24a3102b97))

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
