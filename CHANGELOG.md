# Changelog

<!--next-version-placeholder-->

## v0.6.2 (2023-08-17)

### Fix

* Correct coordinates for cursor table ([`ce54daf`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ce54daf754cb2410790216585467c0ffcc8e3587))

## v0.6.1 (2023-08-14)

### Fix

* Crosshair snaps to correct coordinates also with logx and logy ([`167a891`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/167a891c474b09ef7738e473c4a2e89dbbcbe881))

## v0.6.0 (2023-08-11)

### Feature

* New GUI for line_plot.py ([`b57b3bb`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b57b3bb1afc7c85acc7ed328ac8a219f392869f1))
* Cursor universal signals ([`20e9516`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/20e951659558b7fc023e357bfe07d812c5fd020a))

## v0.5.0 (2023-08-11)

### Feature

* Add generic connect function for slots ([`6a3df34`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6a3df34cdfbec2434153362ded630305e5dc5e28))
* Add possibility to provide service config ([`8c9a9c9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8c9a9c93535ee77c0622b483a3157af367ebce1f))

### Fix

* Dispatcher argparse and scan_plot tests ([`67f619e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/67f619ee897e0040c6310e67d69fbb2e0685293d))
* Gui event removing bugs ([`a9dd191`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a9dd191629295ca476e2f9a1b9944ff355216583))

## v0.4.0 (2023-08-11)

### Feature

* Cursor universal for 1D and 2D ([`f75554b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f75554bd7b072207847956a8720b9a62c20ba2c8))
* Added qt_utils package with general Crosshair function ([`5353fed`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5353fed7bfe1819819fa3348ec93d2d0ba540628))
* 2D plot updating ([`d32088b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d32088b643a4d0613c32fb464a0a55a3b6b684d6))
* Metadata available on_dap_update ([`18b5d46`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/18b5d46678619a972815532629ce96c121f5fcc9))
* Plotting from streamer ([`bb806c1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bb806c149dee88023ecb647b523cbd5189ea9001))
* Added Legend to plot ([`0feca4b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0feca4b1578820ec1f5f3ead3073e4d45c23798b))
* Cursor coordinate as a QTable ([`a999f76`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a999f7669a12910ad66e10a6d2e75197b2dce1c2))
* Changed from PlotItem to GraphicsLayoutWidget, added LabelItem ([`075cc79`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/075cc79d6fa011803cf4a06fbff8faa951c1b59f))
* Add display_ui_file.py ([`91d8ffa`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/91d8ffacffcbeebdf7623caf62e07244c4dcee16))
* Add disconnect_dap_slot ([`1325704`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1325704750ebab897e3dcae80c9d455bfbbf886f))
* Inherit from GraphicsView for consistency with 2D plot ([`d8c101c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d8c101cdd7f960a152a1f318911cac6eecf6bad4))
* Add BECScanPlot2D ([`67905e8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/67905e896c81383f57c268db544b3314104bda38))
* Emit the full bec message to slots ([`1bb3020`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1bb30207038f3a54c0e96dbbbcd1ea7f6c70eca2))

### Fix

* Q selection for gui_event signal ([`0bf452a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0bf452ad1b7d9ad941e2ef4b8d61ec4ed5266415))
* Fixed logic in data subscription ([`c2d469b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c2d469b4543fcf237b274399b83969cc2213b61b))
* Scan_plot to accept metadata from dap signal ([`7bec0b5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7bec0b5e6c1663670f8fcc2fc6aa6c8b6df28b61))
* Plotting latest 1d curves ([`378be81`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/378be81bf6dd5e9239f8f1fb908cafc97161c79d))
* Testing the data structure of plotting ([`4fb0a3b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4fb0a3b058957f5b37227ff7c8e9bdf5259a1cde))
* Fix examples when run directly as a script ([`cd11ee5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cd11ee51c1c725255e748a32b89a74487e84a631))
* Module paths ([`e7f644c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e7f644c5079a8665d7d872eb0b27ed7da6cbd078))

## v0.3.0 (2023-07-19)

### Feature

* Add auto-computed color_list from colormaps ([`3e1708b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3e1708bf48bc15a25c0d01242fff28d6db868e02))
* Add functionality for plotting multiple signals ([`10e2906`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/10e29064455f50bc3b66c55b4361575957db1489))
* Added lineplot widget ([`989a3f0`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/989a3f080839b98f1e1c2118600cddf449120124))
* Added ctrl_c from grum ([`8fee13a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8fee13a67bef3ed6ed6de9d47438f04687f548d8))

### Fix

* Add warning for non-existing signalz ([`48075e4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/48075e4fe3187f6ac8d0b61f94f8df73b8fd6daf))
* Documentation and bugfix for mouse_moved ([`a460f3c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a460f3c0bd7b9e106a758bc330f361868407b1e3))

### Documentation

* Add notes about qt designer install via conda-forge ([`d8038a8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d8038a8cd0efa3a16df403390164603e4e8afdd8))
* Added license ([`db2d33e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/db2d33e8912dc493cce9ee7f09d8336155110079))

## v0.2.1 (2023-07-13)

### Fix

* Fixed setup config (wrong name) ([`947db1e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/947db1e0f32b067e67f94a7c8321da5194b1547b))
* Fixed bec_lib dependency ([`86f4def`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/86f4deffd899111e8997010487ec54c6c62c43ab))

## v0.2.0 (2023-07-13)

### Feature

* Move ivan's qtwidgets to bec-widgets ([`34e5ed2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/34e5ed2cf7e6128a51c110db8870d9560f2b2831))

## v0.1.0 (2023-07-11)

### Feature

* Added config plotter ([`db274c6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/db274c644f643f830c35b6a92edd328bf7e24f59))
