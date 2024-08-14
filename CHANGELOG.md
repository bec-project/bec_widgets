# CHANGELOG

## v0.94.5 (2024-08-14)

### Build

* build: increased min version of bec to 2.21.4

Since we now rely on reusing the BECClient singleton, we need the fix introduced with 2.21.4 in BEC. ([`4f96d0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f96d0e4a14edc4b2839c1dddeda384737dc7a8a))

### Fix

* fix(rpc): use client singleton instead of dispatcher ([`ea9240d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ea9240d2f71931082f33fb6b68231469875c3d63))

* fix: removed qcoreapplication for polling events ([`4d02b42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4d02b42f11e9882b843317255a4975565c8a536f))

## v0.94.4 (2024-08-14)

### Documentation

* docs: review developer section; add introduction ([`2af5c94`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2af5c94913a3435c1839034df4f45f885b56d08b))

### Fix

* fix: do not shutdown client in &#34;close&#34;

Terminating client connections has to be done at the application level ([`198c1d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/198c1d1064cc2dae55de4b941929341faddacb28))

## v0.94.3 (2024-08-13)

### Fix

* fix(curve_dialog): async curves are shown in curve dialog after addition. ([`7aeb2b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7aeb2b5c26c7c2851e8d663d32521da8daec95ef))

* fix(waveform): async device entry is correctly passed, updated and with new scan the previous data are cleared ([`d56ea95`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d56ea95ef97bfdd0bc3eeddc4505d20b38e28559))

### Test

* test(waveform_widget): added tests for axis setting and curve dialog ([`f285b35`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f285b35b491660549e74349318119f7c2c44f619))

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
