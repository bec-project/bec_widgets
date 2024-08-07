# CHANGELOG

## v0.93.3 (2024-08-07)

### Fix

* fix(dock): properly shut down docks and temp areas ([`99ee545`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99ee545e41c6078654958b668b5b329f85553d16))

* fix(settings): shut down settings dialog ([`b50b3a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b50b3a27e68956e10e8169a0aa698c911d2d9642))

* fix(website): fixed teardown of website widgets ([`a3d4f5a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3d4f5ac4bc52acfed2791a1724fade6972ed320))

* fix(dock): properly shut down docks and dock areas ([`bc26497`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc264975b1363c9dfea516621d7878c320677d15))

* fix(figure): cleanup pyqtgraph ([`ad07bbf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad07bbf85e9c8d9838bdd686f69d41c235b7db19))

### Test

* test: removed quit from teardown ([`cf94599`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf94599c2544d6831c8afbe7b340082077557ed1))

* test: removed explicit call to close the widget ([`bf6294e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf6294ecbfd494565d2dc215e4d7e0c280ac7745))

* test: use factory instead of fixture to properly cleanup widgets on teardown ([`9856857`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9856857f4cc7fa229c10d00fbae4452464a207cb))

* test: ensure all toplevelwidgets are closed ([`f9e5897`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f9e58979009cf632feea529700ad191401dd7eb8))

## v0.93.2 (2024-08-07)

### Fix

* fix(scan_group_box): Scan Spinboxes limits increased to max allowed values; setting dialog for step size and decimal precision for ScanDoubleSpinBox on right click ([`a372925`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a372925fffa787c686198ae7cb3f9c15b459c109))

## v0.93.1 (2024-08-06)

### Documentation

* docs: added video tutorial section with BSEG YT video ([`302ae90`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/302ae90139f6a88e2401fe29fe312387486e27a9))

### Fix

* fix(dock): docks have more recognizable red icon for closing docks ([`af86860`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af86860bf35474805fb1a7bc3725cf8835ed4cc7))

## v0.93.0 (2024-08-05)

### Feature

* feat(themes): moved themes to bec_qthemes

This reverts commit fd6ae91993a23a7b8dbb2cf3c4b7c3eda6d2b0f6 ([`5aad401`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5aad401ef8774c7330784f72cd3b9d8c253e2b6a))

## v0.92.5 (2024-08-05)

### Fix

* fix(spinner): stop timer on close event ([`30fef92`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/30fef929cf6fb4b73f48151c92a0ee54c734031d))

* fix(status_box): fix cleanup of status box ([`1f30dd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f30dd73a9c1e3135087a5eef92c7329f54a604e))

### Refactor

* refactor(queue): refactored bec queue to inherit only from qwidget ([`7616ca0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7616ca0e145e233ccb48029a8c0b54b54b5b4194))

### Test

* test: register all widgets with qtbot and close them ([`73cd11e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/73cd11e47277e4437554b785a9551b28a572094f))

## v0.92.4 (2024-07-31)

### Fix

* fix: fix missmatch of signal/slot in image and motormap ([`dcc5fd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dcc5fd71ee9f51767a7b2b1ed6200e89d1ef754c))

## v0.92.3 (2024-07-28)

### Fix

* fix(docs): moved to pyside6 ([`71873dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/71873ddf359516ded8f74f4d2f73df4156aa1368))

## v0.92.2 (2024-07-28)

### Fix

* fix(widgets): fixed import for tictactoe example ([`995a795`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/995a795060bebe25c17108d80ae0fa30463f03b1))

## v0.92.1 (2024-07-28)

### Build

* build(ci): install ophyd_devices in editable mode for pipelines ([`06205e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06205e07903d93accf40abab153f440059f236ed))

### Fix

* fix: use SafeSlot instead of Slot ([`bc1e239`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc1e23944cc0e5a861e3d0b4dc5b4ac6292d5269))

* fix: linting ([`a3fe205`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3fe20500ae2ac03dcde07432f7e21ce5262ce46))

* fix: always add a QApplication for tests ([`61a4e32`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61a4e32deb337ed27f2f43358b88b7266413b58e))

* fix: add xvfb to draw offscreen ([`3d681f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3d681f77e144e74138fc5fa65630004d7c166878))

* fix: reset ErrorPopup singleton between tests ([`5a9ccfd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5a9ccfd1f6d2aacd5d86c1a34f74163b272d1ae4))

* fix: metaclass + QObject segfaults PyQt(cpp bindings) ([`fc57b7a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc57b7a1262031a2df9e6a99493db87e766b779a))

### Refactor

* refactor: renamed DeviceMonitor2DMessage ([`4be6fd6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be6fd6b83ea1048f16310f7d2bbe777b13b245e))

* refactor: rename device_monitor to device_monitor_2d ([`714e1e1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/714e1e139e0033d2725fefb636c419ca137a68c6))

## v0.92.0 (2024-07-24)

### Feature

* feat(dock): dock style sheets updated ([`8ca60d5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ca60d54b3cfa621172ce097fc1ba514c47ebac7))

* feat(general_gui): general gui added ([`5696c99`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5696c993dc1c0da40ff3e99f754c246cc017ea32))

### Fix

* fix(dock): custom label can be created closable ([`4457ef2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4457ef2147e21b856c9dcaf63c81ba98002dcaf1))

* fix(device_combobox): set minimum size to 125px ([`1206e15`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1206e153094cd8505badf69a1461572a76b4c5ad))

## v0.91.0 (2024-07-23)

### Feature

* feat(dock_area): plugin added ([`a16b87a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a16b87ac28d164230dd2e8020f50ff3a63cd407e))

* feat(dock_area): Added toolbar to dock area to add widgets without CLI interactions ([`cce1367`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cce1367a72fca7206d351894bd1831b7bbfa7ec6))

* feat(toolbar): expandable menu actions ([`28f26e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28f26e92a46063db1a194be552156a5d3b2c43e7))

### Fix

* fix(status_item): icons changed to material design ([`1b9c55a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b9c55a46a0dfd8678c8e95ff64dd6e8cfb9233e))

* fix(plugins): Qt Designer plugins icons adjusted ([`f4844d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f4844d2e067ce75dc64b89b230d7932b308ddfc2))

### Test

* test(dock_area): tests extended ([`06fab0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06fab0eab926cef5677d4988fd1fce09da342dd8))

## v0.90.0 (2024-07-23)
