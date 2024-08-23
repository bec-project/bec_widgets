# CHANGELOG

## v0.96.3 (2024-08-23)

### Documentation

* docs(dispatcher): docs added ([`dd7c71b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd7c71bb1e0b7ef5398b1e1a05fc1147c772420a))

### Fix

* fix: minor fixes for type annotations ([`8c2e7c8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c2e7c82592ace50e4e1f47e392a0ddc988f57ae))

## v0.96.2 (2024-08-22)

### Fix

* fix(waveform): validation of custom curves removed ([`af28574`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af28574bd58457a05f1269f121db01ad627b5769))

* fix(waveform): skip validation for curves that are not BECCurve instances ([`617db36`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/617db36ed4932c8a0633724079b695bc67d5c77b))

## v0.96.1 (2024-08-22)

### Ci

* ci: fail pytest after 2 failed tests ([`f0203d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0203d9bf60c4975ba5ab93a057d9091762454d5))

### Fix

* fix(crosshair): update markers if necessary ([`4473805`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/44738057a36f5de2bbb55affdd309f92286d4a0f))

* fix(waveform_widget): fixed icon appearance ([`f98a9f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f98a9f9771b93226d47830aa52f45739624f51b4))

* fix: bubble-up signals ([`2fe72c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2fe72c9ccb71bcb196a1b78197b73acf9aa3f506))

* fix(crosshair): fixed crosshair for image and waveforms ([`37835cb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37835cbf76ca3ba1081f514ee7793244ac500e7f))

## v0.96.0 (2024-08-22)

### Documentation

* docs(scan_control): added designer options ([`9d7718c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d7718c3d9badf14150174410b9958a3134a1e23))

### Feature

* feat(scan_control): added the ability to configure the scan control widget from designer ([`9d8fb0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d8fb0b761efa92972399bcd9aea28e956074380))

## v0.95.1 (2024-08-22)

### Documentation

* docs: links section added ([`2bf5c70`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2bf5c7096e7d822713e1b50bde89f072e6356e17))

### Fix

* fix(docs): changed link to scan gui config in main docs ([`640464a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/640464a6543b2111bdb58d0174f2ce86c5836cbe))

### Refactor

* refactor: removed designer pngs ([`84abe46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84abe460502d838aac41bb8ff63d93c9fcec9214))

* refactor: moved to dynamically loaded material design icons ([`1d2afaa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1d2afaa09e64b7f714d72796e87e2cb49b2a75a7))

## v0.95.0 (2024-08-21)

### Documentation

* docs(device_browser): added user docs ([`2c31cc9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2c31cc90ae751f14a653cbbdd6c353d6359aaafe))

* docs(user): widget gallery with documentation added ([`7357f3d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7357f3d2a189f9f04954a027f39ce07c394d57ec))

* docs: added sphinx-inline-tabs as sphinx dependency ([`e9ecd26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e9ecd268c602ea9572df0e8d508e49ee62d0c170))

* docs(cards): changed index cards to custom css class instead of overwriting the default sd-card theme ([`91ba30e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91ba30e8d054a9c7f6c6d98b21113a5d0b1bbbbb))

### Feature

* feat(cli): added device_browser to cli ([`196504b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/196504b533367a899c19b88af4ccd5b39dc46aac))

* feat(widgets): added device_browser widget ([`73f5a2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/73f5a2f085b289ac18fa8a918b6ad7cfed595fb4))

### Fix

* fix(device_browser): fixed plugin assignment for designer ([`6500393`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/650039303aae9bbec62c676285938416fff146ce))

### Refactor

* refactor(docs): review response ([`4790afd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4790afde3d61fc9beb073c2775c339d4f80779e3))

### Test

* test: added test for device browser ([`e870e5b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e870e5ba083c61df581c9c0305adabe72967f997))

## v0.94.7 (2024-08-20)

### Fix

* fix: formatting of stdout, stderr captured text for logger ([`939f834`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/939f834a26ddbac0bdead0b60b1cdf52014f182f))

## v0.94.6 (2024-08-14)

### Fix

* fix(server): emit heartbeat with state ([`bc2abe9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc2abe945fb5adeec89ed5ac45e966db86ce6ffc))

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

### Refactor

* refactor: adjust dimensions ([`0273bf4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0273bf485694609325b5b556a3c69fb53c18446e))
