# CHANGELOG


## v1.6.0 (2024-11-27)

### Bug Fixes

- **tests**: Make use of BECDockArea with client mixin to start server and use it in tests
  ([`da18c2c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/da18c2ceecf9aeaf0e0ea9b78f4c867b27b9c314))

Depending on the test, auto-updates are enabled or not.

- Differentiate click and drag for DeviceItem, adapt tests accordingly
  ([`cffcdf2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cffcdf292363249bcc7efa9d130431d0bc727fda))

This fixes the blocking "QDrag.exec_()" on Linux, indeed before the drag'n'drop operation was
  started with a simple click and it was waiting for drop forever. Now there are 2 different cases,
  click or drag'n'drop - the drag'n'drop test actually moves the mouse and releases the button.

- **server**: Use dock area by default
  ([`2fe7f5e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2fe7f5e1510a5ea72676045e6ea3485e6b11c220))

- **rpc**: Gui hide/show also hide/show all floating docks
  ([`c27d058`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c27d058b01fe604eccec76454e39360122e48515))

- Do not quit automatically when last window is "closed"
  ([`96e255e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/96e255e4ef394eb79006a66d13e06775ae235667))

Qt confuses closed and hidden

- No need to call inspect.signature - it can fail on methods coming from C (like Qt methods)
  ([`6029246`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60292465e9e52d3248ae681c68c07298b9b3ce14))

- Add back accidentally removed variables
  ([`e998352`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e9983521ed2a1c04af048a55ece70a1943a84313))

### Features

- '._auto_updates_enabled' attribute can be used to activate auto updates installation in
  BECDockArea
  ([`31d8703`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/31d87036c9801e639a7ca6fc003c90e0c4edb19d))

- Add rpc_id member to client objects
  ([`3ba0b1d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3ba0b1daf5b83da840e90fbbc063ed7b86ebe99b))

- **client**: Add show()/hide() methods to "gui" object
  ([`e68e2b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e68e2b5978339475b97555c3e20795807932fbc9))

- **server**: Add main window, with proper gui_id derived from given id
  ([`daf6ea0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/daf6ea0159c9ffc7b53bb7ae6b9abc16a302972c))

- Add main window container widget
  ([`f80ec33`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f80ec33ae5a261dbcab901ae30f4cc802316e554))

- Asynchronous .start() for GUI
  ([`2047e48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2047e484d5a4b2f5ea494a1e49035b35b1bbde35))

- Do not take focus when GUI is loaded
  ([`1f71d8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f71d8e5eded9952f9b34bfc427e2ff44cf5fc18))

- Add '--hide' argument to BEC GUI server
  ([`1f60fec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f60fec7201ed252d7e49bf16f2166ee7f6bed6a))


## v1.5.3 (2024-11-21)

### Bug Fixes

- **alignment_1d**: Fix imports after widget module refactor
  ([`e71e3b2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e71e3b2956feb3f3051e538432133f6e85bbd5a8))

### Continuous Integration

- Fix ci syntax for package-dep-job
  ([`6e39bdb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6e39bdbf53b147c8ff163527b45691835ce9a2eb))


## v1.5.2 (2024-11-18)

### Bug Fixes

- Support for bec v3
  ([`746359b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/746359b2cc07a317473907adfcabbe5fe5d1b64c))


## v1.5.1 (2024-11-14)

### Bug Fixes

- **plugin_utils**: Plugin utils are able to detect classes for plugin creation based on class
  attribute rather than if it is top level widget
  ([`7a1b874`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7a1b8748a433f854671ac95f2eaf4604e6b8df20))

### Refactoring

- **widgets**: Widget module structure reorganised
  ([`aab0229`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aab0229a4067ad626de919e38a5c8a2e9e7b03c2))


## v1.5.0 (2024-11-12)

### Bug Fixes

- **crosshair**: Crosshair adapted for multi waveform widget
  ([`0cd85ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0cd85ed9fa5b67a6ecce89985cd4f54b7bbe3a4b))

### Documentation

- **multi_waveform**: Docs added
  ([`42d4f18`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/42d4f182f790a97687ca3b6d0e72866070a89767))

### Features

- **multi-waveform**: New widget added
  ([`f3a39a6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f3a39a69e29d490b3023a508ced18028c4205772))


## v1.4.1 (2024-11-12)

### Bug Fixes

- **positioner_box**: Adjusted default signals
  ([`8e5c0ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8e5c0ad8c8eff5a9308169bc663d2b7230f0ebb1))


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
