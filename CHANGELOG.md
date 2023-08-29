# Changelog

<!--next-version-placeholder-->

## v0.8.0 (2023-08-29)

### Feature

* User can specify tuple of (x,y) devices which wants to plot ([`3344f1b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3344f1b92a7e4f4ecd2e63c66aa01d3a4c325070))
* Fit table hardcode to "gaussian_fit_worker_3" ([`3af57ab`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3af57abc4888dfcd0224bf50708488dc8192be84))
* Crosshair snapped to x, y data automatically, clicked coordinates glows ([`49ba6fe`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/49ba6feb3a8494336c5772a06e9569d611fc240a))
* Crosshair snaps to data, but it is activated with button due to debug ([`223f102`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/223f102aa9f0e625fecef37c827c55f9062330d7))
* Dap fit plotted as curve, data as scatter ([`118f6af`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/118f6af2b97188398a3dd0e2121f73328c53465b))
* Oneplot can receive one motor and one monitor signal ([`ff545bf`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ff545bf5c9e707f2dd9b43f9d059aa8605f3916b))
* Oneplot initialized as an example app for plotting motor vs monitor signals + dispatcher loop over msg ([`98c0c64`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/98c0c64e8577f7e40eb0324dfe97d0ae4670c3a2))

### Fix

* User can disable dap_worker and just choose signals to plot ([`cab5354`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cab53543e644921df69c57c70ad2b3a03bbafcc1))
* Crosshair snaps correctly to x dataset ([`2ed5d72`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2ed5d7208c42f8a1175a49236d706ebf503875e4))

## v0.7.0 (2023-08-28)

### Feature

* Labels of current motors are shown in motors limits ([`413e435`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/413e4356cfde6e2432682332e470eb69427ad397))
* Total number of points, scatter size and number of point to dim after last position can be changed from GUI ([`e0b52fc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e0b52fcedca46d913d1677b45f9815eccd92e8f7))
* Speed and frequency can be updated from GUI ([`f391a2f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f391a2fd004f1dc8187cfe12d60f856427ae01ec))
* Speed and frequency is retrieved from devices ([`ce98164`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ce9816480b82373895b602d1a1bca7d1d9725f01))
* Delete coordinate table row by DELETE or BACKSPACE key ([`5dd0af6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5dd0af6894a5d97457d60ef18b098e40856e4875))
* Motor selection ([`cab32be`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cab32be0092185870b5a12398103475342c8b1fd))
* New GUI ([`0226188`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0226188079f1dac4eece6b1a6fa330620f1504bc))
* Keyboard shortcut to go to coordinates ([`3c0e595`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3c0e5955d40a67935b8fb064d5c52fd3f29bd1a1))
* Ability to choose how many points should be dimmed before reaching the threshold + total number of point which should be stored. ([`9eae697`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9eae697df8a2f3961454db9ed397353f110c0e67))
* Stop movement function, one callback function for 2 motors, move_finished is emitted in move_motor function not in callback ([`187c748`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/187c748e87264448d5026d9fa2f15b5fc9a55949))
* Controls are disabled while motor is moving and enabled when motor movement is finished ([`ed84293`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ed842931971fbf87ed2f3e366eb822531ef5aacc))
* Motor coordinates are now scatter instead of image ([`3f6d5c6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3f6d5c66411459703c402f7449e8b1abae9a2b08))
* Going to absolute coordinates saves coordinate in the table for later use with tag ([`8be98c9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8be98c9bb6af941a69c593c62d5c52339d2262bc))
* Table with coordinates getting initial coordinates of motor ([`92388c3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/92388c3cab7e024978aaa2906afbd698015dec66))
* Motor move to absolute (X,Y) coordinates ([`cbe27e4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cbe27e46cfb6282c71844641e1ed6059e8fa96bf))
* Motor limits can be changed by spinBoxes ([`2d1665c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2d1665c76b8174d9fffa3442afa98fe1ea6ac207))
* Switch for keyboard shortcuts for motor movement ([`cac4562`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cac45626fc9a315f9012b110760a92e27e5ed226))
* Setting map according to motor limits ([`512e698`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/512e698e26d9eef05b4f430475ccc268b68ad632))
* Map of motor position ([`e6952a6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e6952a6d13c84487fd6ab08056f1f5b46d594b8a))
* Motor_example.py created, motor samx and samy can be moved by buttons ([`947ba9f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/947ba9f8b730e96082cb51ff6894734a0e119ca1))

### Fix

* Line_plot.py default changed back to "gauss_bpm" ([`64708bc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/64708bc1b2e6a4256da9123d0215fc87e0afa455))
* Motor selection is disabled while motor is moving ([`c7e35d7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c7e35d7da69853343aa7eee53c8ad988eb490d93))
* Init_motor_map receive motor position from motor_thread ([`95ead71`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/95ead7117e59e0979aec51b85b49537ab728cad4))
* Motor movement absolute fixed - movement by thread ([`11aa15f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/11aa15fefda7433e885cc8586f93c97af83b0c48))

## v0.6.3 (2023-08-17)

### Fix

* Crosshair handles dynamic changes of number of curves in 1D plot ([`242737b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/242737b516af7c524a6c8a98db566815f0f4ab65))

### Documentation

* Crosshair class documentation ([`8a60cad`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8a60cad9187df2b2bc93dc78dd01ceb42df9c9af))

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
