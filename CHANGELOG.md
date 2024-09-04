# CHANGELOG

## v0.103.0 (2024-09-04)

### Ci

* ci: prefill variables for manual pipeline start ([`158c19e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/158c19eda771562a325fd59405f9fd4cb9a17ed6))

### Feature

* feat(vscode): open vscode on a free port ([`52da835`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52da835803f2453096a8b7df23bee5fdf93ae2bb))

* feat(website): added method to wait until the webpage is loaded ([`9be19d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9be19d4abebad08c5fc6bea936dd97475fe8f628))

### Fix

* fix(theme): fixed segfault for webengineview for auto updates ([`9866075`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9866075100577948755b563dc7b7dc4cdc60d040))

### Test

* test(webview): fixed tests after refactoring ([`d5eb30c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d5eb30cd7df4cb0dc3275dd362768afc211eaf2d))

* test(vscode): popen call does not have to be the only one ([`39f98ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/39f98ec223ba8b59e478ac788c08c59ffe886b4e))

## v0.102.0 (2024-09-04)

### Documentation

* docs(buttons): buttons section of docs split to appearance and queue buttons ([`047aa26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/047aa26a60220c826cc1375cf81daf11d1f3ab5c))

* docs(tests): added tests tutorial for widget ([`18d8561`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/18d8561c965d149a7662085f7dbe2a39a8c4a475))

### Feature

* feat(queue): BECQueue controls extended with Resume, Stop, Abort, Reset buttons ([`0d7c10e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0d7c10e670e4937787e1afaa19ca8259ac752486))

### Fix

* fix(queue_reset_button): queue reset has to be confirmed with msgBox ([`9dd43aa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9dd43aa1fd3991368002605df4389a7a7271011b))

### Refactor

* refactor(tests): positioner box test changed to use create_widget fixture ([`df5eff3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df5eff3147c79ff0278e6a5a09c8f73d5236aed3))

## v0.101.0 (2024-09-02)

### Feature

* feat: add Dap dialog widget ([`9781b77`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9781b77de27b2810fbb1047a61b1832dd186db01))

### Refactor

* refactor: add docs, cleanup ([`61ecf49`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61ecf491e52bfbfa0d5a84764a9095310659043d))

## v0.100.0 (2024-09-01)

### Documentation

* docs(becwidget): improvements to the bec widget base class docs; fixed type hint import for sphinx ([`99d5e8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99d5e8e71c7f89a53d7967126f4056dde005534c))

### Feature

* feat(theme): added theme handler to bec widget base class; added tests ([`7fb938a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7fb938a8506685278ee5eeb6fe9a03f74b713cf8))

### Fix

* fix(pyqt slot): removed slot decorator to avoid problems with pyqt6 ([`6c1f89a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6c1f89ad39b7240ab1d1c1123422b99ae195bf01))

## v0.99.15 (2024-08-31)

### Fix

* fix(theme): update pg axes on theme update ([`af23e74`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af23e74f71152f4abc319ab7b45e65deefde3519))

* fix(positioner_box): fixed positioner box dialog; added test; closes #332 ([`0bf1cf9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0bf1cf9b8ab2f9171d5ff63d4e3672eb93e9a5fa))

## v0.99.14 (2024-08-30)

### Fix

* fix(color_button): signal and slot added for selecting color and for emitting color after change ([`99a98de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99a98de8a3b7a83d71e4b567e865ac6f5c62a754))

* fix(color_button): inheritance changed to QWidget ([`3c0e501`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c0e501c56227d4d98ff0ac2186ff5065bff8d7a))

## v0.99.13 (2024-08-30)

### Documentation

* docs: minor updates to the widget tutorial ([`ec9c8f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec9c8f29633364c45ebd998a5411d428c1ce488d))

* docs(widget tutorial): step by step guide added ([`b32ced8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b32ced85fff628a9e1303a781630cdae3865238e))

### Fix

* fix(dark mode button): fixed dark mode button state for external updates, including auto ([`a3110d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3110d98147295dcb1f9353f9aaf5461cba9232a))

## v0.99.12 (2024-08-29)

### Fix

* fix(toolbar): widget action added ([`2efd487`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2efd48736cbe04e84533f7933c552ea8274e2162))

* fix(reset_button): reset button added ([`6ed1efc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ed1efc6af193908f70aa37fb73157d2ca6a62f4))

* fix(abort_button): abort button added; some minor fixes ([`a568633`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a568633c3206a8c26069d140f2d9a548bf4124b0))

## v0.99.11 (2024-08-29)

### Fix

* fix(resume_button): resume button added ([`8be8295`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8be8295b2b38f36da210ab36c5da6d0a00e330cc))

### Refactor

* refactor(icons): general app icon changed; jupyter app icon changed to material icon ([`5d73fe4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d73fe455a568ad40a9fadc5ce6e249d782ad20d))

* refactor: add option to select scan and hide arg bundle buttons ([`7dadab1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7dadab1f14aa41876ad39e8cdc7f7732248cc643))

## v0.99.10 (2024-08-29)

### Fix

* fix(stop_button): queue logic scan changed to halt instead of abort and reset ([`4a89028`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a890281f7eaef02d0ec9f4c5bf080be11fe0fe3))

### Refactor

* refactor(stop_button): stop button changed to QWidget and adapted for toolbar ([`097946f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/097946fd688b8faf770e7cc0e689ea668206bc7a))

* refactor: added hide option for device selection button ([`cdd1752`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cdd175207e922904b2efbb2d9ecf7c556c617f2e))

## v0.99.9 (2024-08-28)

### Fix

* fix: fixed build process and excluded docs and tests from tarballs and wheels ([`719254c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/719254cf0a48e1fc4bd541edba239570778bcfea))

## v0.99.8 (2024-08-28)

### Fix

* fix(website): fixed designer integration for website widget ([`5f37e86`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5f37e862c95ac7173b6918ad39bcaef938dad698))

### Refactor

* refactor(website): changed inheritance of website widget to simple qwidget; closes #325 ([`9925bbd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9925bbdb48b55eacbbce9fd6a1555a21b84221f9))

## v0.99.7 (2024-08-28)

### Fix

* fix(toolbar): material icons can accept color as kwarg ([`ffc871e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ffc871ebbd3b68abc3e151bb8f5849e6c50e775e))

## v0.99.6 (2024-08-28)

### Fix

* fix(toolbar): use of native qt separators ([`09c6c93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/09c6c93c397ce4a21c293f6c79106c74b2db65ca))
