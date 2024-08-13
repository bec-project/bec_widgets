# CHANGELOG

## v0.94.2 (2024-08-13)

### Fix

* fix(image): image is single image mode do not raise popup error when connected twice with the same monitor ([`98b79aa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/98b79aac7b47b73137f4d582f7f1d552b1d95366))

## v0.94.1 (2024-08-12)

### Fix

* fix: issue #292, wrong key was used to clean _slots internal dictionary ([`93d3977`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/93d397759c756397604ebff5e24f3a580be8620d))

## v0.94.0 (2024-08-08)

### Feature

* feat: add PositionerControlLine ([`c80a7cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c80a7cd1083baa9543a2cee2e3c3a51dfd209b19))

### Refactor

* refactor: adjust dimensions ([`0273bf4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0273bf485694609325b5b556a3c69fb53c18446e))

## v0.93.5 (2024-08-08)

### Fix

* fix(positioner_box): icons fixed ([`281633d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/281633deff15b6879dac3a4f0770fa6949aaecdc))

### Refactor

* refactor: add button for positioner selection ([`0d190c5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0d190c5c5996e59fec4bdd44d2003e10e200b009))

### Test

* test(dap): wait for fit ([`6269009`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6269009e5451f830cdee58a514c7858483488a8d))

* test(auto-update): wait for rendering ([`6d2442d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6d2442d23c683fe92af13df982ce681c07e99cde))

## v0.93.4 (2024-08-07)

### Fix

* fix: rename DeviceBox to PositionerBox, fix test for validation ([`37aa371`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37aa371e7c4c62d70abf37abc125db0c088790fe))

* fix: add validation for bec_lib.device.Positioner; closes #268 ([`eb54e9f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb54e9f788e97af23db8fe0c78f8facb8688bb99))

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
