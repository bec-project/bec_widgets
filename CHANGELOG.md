# CHANGELOG


## v1.4.0 (2024-11-11)

### Bug Fixes

- **crosshair**: Label of coordinates of TextItem displays numbers in general format
  ([`11e5937`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11e5937ae0f3c1413acd4e66878a692ebe4ef7d0))

- **crosshair**: Label of coordinates of TextItem is updated according to the current theme of qapp
  ([`4f31ea6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f31ea655cf6190e141e6a2720a2d6da517a2b5b))

- **crosshair**: Log is separately scaled for backend logic and for signal emit
  ([`b2eb71a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2eb71aae0b6a7c82158f2d150ae1e31411cfdeb))

### Features

- **crosshair**: Textitem to display crosshair coordinates
  ([`035136d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/035136d5171ec5f4311d15a9aa5bad2bdbc1f6cb))

### Testing

- **crosshair**: Tests extended
  ([`64df805`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/64df805a9ed92bb97e580ac3bc0a1bbd2b1cb81e))


## v1.3.3 (2024-11-07)

### Bug Fixes

- **scan_control**: Devicelineedit kwargs readings changed to get name of the positioner
  ([`5fabd4b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5fabd4bea95bafd2352102686357cc1db80813fd))

### Documentation

- Update outdated text in docs
  ([`4f0693c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f0693cae34b391d75884837e1ae6353a0501868))


## v1.3.2 (2024-11-05)

### Bug Fixes

- **plot_base**: Legend text color is changed when changing dark-light theme
  ([`2304c9f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2304c9f8497c1ab1492f3e6690bb79b0464c0df8))

### Build System

- Pyside6 version fixed 6.7.2
  ([`c6e48ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c6e48ec1fe5aaee6a7c7a6f930f1520cd439cdb2))


## v1.3.1 (2024-10-31)

### Bug Fixes

- **ophyd_kind_util**: Kind enums are imported from the bec widget util class
  ([`940ee65`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/940ee6552c1ee8d9b4e4a74c62351f2e133ab678))


## v1.3.0 (2024-10-30)

### Bug Fixes

- **colors**: Extend color map validation for matplotlib and colorcet maps (if available)
  ([`14dd8c5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/14dd8c5b2947c92f6643b888d71975e4e8d4ee88))

### Features

- **colormap_button**: Colormap button with menu to select colormap filtered by the colormap type
  ([`b039933`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b039933405e2fbe92bd81bd0748e79e8d443a741))


## v1.2.0 (2024-10-25)

### Features

- **colors**: Evenly spaced color generation + new golden ratio calculation
  ([`40c9fea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/40c9fea35f869ef52e05948dd1989bcd99f602e0))

### Refactoring

- Add bec_lib version to statusbox
  ([`5d4b86e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d4b86e1c6e1800051afce4f991153e370767fa6))


## v1.1.0 (2024-10-25)

### Features

- Add filter i/o utility class
  ([`0350833`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0350833f36e0a7cadce4173f9b1d1fbfdf985375))

### Refactoring

- Do not flush selection upon receiving config update; allow widgetIO to receive kwargs to be able
  to use get_value to receive string instead of int for QComboBox
  ([`91959e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91959e82de8586934af3ebb5aaa0923930effc51))

- Allow to set selection in DeviceInput; automatic update of selection on device config update;
  cleanup
  ([`5eb15b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5eb15b785f12e30eb8ccbc56d4ad9e759a4cf5eb))

- Cleanup, added device_signal for signal inputs
  ([`6fb2055`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fb20552ff57978f4aeb79fd7f062f8d6b5581e7))

### Testing

- **scan_control**: Tests added for grid_scan to ensure scan_args signal validity
  ([`acb7902`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/acb79020d4be546efc001ff47b6f5cdba2ee9375))


## v1.0.2 (2024-10-22)

### Bug Fixes

- **scan_control**: Scan args signal fixed to emit list instead of hardcoded structure
  ([`4f5448c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f5448cf51a204e077af162c7f0aed1f1a60e57a))


## v1.0.1 (2024-10-22)

### Bug Fixes

- **waveform**: Added support for live_data and data access
  ([`7469c89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7469c892c8076fc09e61f173df6920c551241cec))


## v1.0.0 (2024-10-18)

### Bug Fixes

- **crosshair**: Downsample clear markers
  ([`f9a889f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f9a889fc6d380b9e587edcb465203122ea0bffc1))

### Features

- Ability to disable scatter from waveform & compatible crosshair with down sampling
  ([`2ab12ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2ab12ed60abb995abc381d9330fdcf399796d9e5))


## v0.119.0 (2024-10-17)

### Bug Fixes

- Fix syntax due to change of api for simulated devices
  ([`19f4e40`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/19f4e407e00ee242973ca4c3f90e4e41a4d3e315))

- Remove wrongly scoped test
  ([`a23841b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a23841b2553dc7162da943715d58275c7dc39ed9))

- Rename 'compact' property -> 'compact_view'
  ([`6982711`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6982711fea5fb8a73845ed7c0692e3ec53ef7871))

- Alignment 1D update, make app window a main window (in .ui file)
  ([`0015f0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0015f0e2d62adc02d3ef334e1f6dbb2d0288fec6))

- Set (Minimum, Fixed) size policy on Stop button
  ([`523cc43`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/523cc435725b10b7d59a4477a1aaa24a1f3e37a2))

### Features

- New PositionerGroup widget
  ([`af9655d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af9655de0c541092437accfbaa779628a2f48ccb))

- Add 'expand_popup' property to CompactPopupWidget
  ([`e4121a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4121a01cb6b8d496e630cd43bc642b994b8f310))

This property tells if expand should show a popup (by default), or if the widget should expand
  in-place

- Positionerbox with a popup view
  ([`2615787`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/261578796f1de8ca9cab9b91659bc1484f7aa89d))

- Emit 'device_selected' and 'scan_axis' from scan control widget
  ([`0b9b1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b9b1a3c89a98505079f7d4078915b7bbfaa1e23))

- New 'device_selected' signals to ScanControl, ScanGroupBox, DeviceLineEdit
  ([`9801d27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9801d2769eb0ee95c94ec0c011e1dac1407142ae))

### Refactoring

- Redesign of scan selection and scan control boxes
  ([`a69d287`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a69d2870e2b3539739781d741b27b8599c0f4abd))

- Move add/remove bundle to scan group box
  ([`e3d0a7b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3d0a7bbf9918dc16eb7227a178c310256ce570d))


## v0.118.0 (2024-10-13)

### Documentation

- **sphinx-build**: Adjusted pyside verion
  ([`b236951`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b23695167ab969f754a058ffdccca2b40f00a008))

### Features

- **image**: Image widget can take data from monitor_1d endpoint
  ([`9ef1d1c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ef1d1c9ac2178d9fa2e655942208f8abbdf5c1b))


## v0.117.1 (2024-10-11)

### Bug Fixes

- **FPS**: Qtimer cleanup leaking
  ([`3a22392`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3a2239278075de7489ad10a58c31d7d89715e221))
