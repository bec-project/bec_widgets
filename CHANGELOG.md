# CHANGELOG

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

* fix(bec_figure): waveforms can be initialised from the config; widgets are deleteLater after removal ([`78673ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/78673ea11a47aad878128197ae6213925228ed59))

### Unknown

* Resolve &#34;add VT100 console executing BEC as a widget&#34; ([`c6a14c0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c6a14c0768a90695567a83a7895247ed0c64f3ce))

## v0.76.1 (2024-06-29)

### Fix

* fix(plugins): fixes and tests for auto-gen plugins ([`c42511d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c42511dd44cc13577e108a6cef3166376e594f54))

## v0.76.0 (2024-06-28)

### Feature

* feat(designer): added support for creating designer plugins automatically ([`c1dd0ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c1dd0ee1906dba1f2e2ae9ce40a84d55c26a1cce))

### Fix

* fix: fixed qwidget inheritance for ring progress bar ([`0610d2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0610d2f9f027f8659e7149f2dfbb316ff30e337d))

### Unknown

* fix:parent set as first kwarg TextBox and WebsiteWidget ([`a45c407`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a45c4075684b93bfdcee03e5a416b84f61d3bc6f))

## v0.75.0 (2024-06-26)

### Feature

* feat(widgets): added simple bec queue widget ([`3faee98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3faee98ec80041a27e4c1f1156178de6f9dcdc63))

### Refactor

* refactor(dispatcher): cleanup ([`ca02132`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca02132c8d18535b37e9192e00459d2aca6ba5cf))

## v0.74.1 (2024-06-26)

### Build

* build: added missing pytest-bec-e2e dependency; closes #219 ([`56fdae4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56fdae42757bdb9fa301c1e425a77e98b6eaf92b))

* build: fixed dependency ranges; closes #135 ([`e6a06c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6a06c9f43e0ad6bbfcfa550a2f580d2a27aff66))

### Chore

* chore: sorted dependencies alphabetically ([`21c807f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/21c807f35831fdd1ef2e488ab90edae4719f0cb7))

### Documentation

* docs: fixed doc string ([`f979a63`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f979a63d3d1a008f80e500510909750878ff4303))

### Fix

* fix(rings): rings properties updated right after setting ([`c8b7367`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8b7367815b095f8e4aa8b819481efb701f2e542))

* fix(motor_map): motor map can be removed from BECFigure with .remove() ([`6b25abf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b25abff70280271e2eeb70450553c05d4b7c99c))

### Test

* test(bec_figure): tests for removing widgets with rpc e2e ([`a268caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a268caaa30711fcc7ece542d24578d74cbf65c77))

## v0.74.0 (2024-06-25)

### Documentation

* docs(becfigure): docs added ([`a51b15d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a51b15da3f5e83e0c897a0342bdb05b9c677a179))

### Feature

* feat(waveform1d): dap LMFit model can be added to plot ([`1866ba6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1866ba66c8e3526661beb13fff3e13af6a0ae562))

### Test

* test(waveform1d): dap e2e test added ([`7271b42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7271b422f98ef9264970d708811c414b69a644db))

## v0.73.2 (2024-06-25)

### Fix

* fix(vscode): only run terminate if the process is still alive ([`7120f3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7120f3e93b054b788f15e2d5bcd688e3c140c1ce))
