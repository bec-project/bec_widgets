# CHANGELOG


## v1.11.0 (2024-12-11)

### Features

- **collapsible_panel_manager**: Panel manager to handle collapsing and expanding widgets from the
  main widget added
  ([`a434d3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a434d3ee574081356c32c096d2fd61f641e04542))

### Testing

- **collapsible_panel_manager**: Fixture changed to not use .show()
  ([`ff654b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff654b56ae98388a2b707c040d51220be6cbce13))


## v1.10.0 (2024-12-10)

### Features

- **layout_manager**: Grid layout manager widget
  ([`17a63e3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/17a63e3b639ecf6b41c379717d81339b04ef10f8))


## v1.9.1 (2024-12-10)

### Bug Fixes

- **designer**: General way to find python lib on linux
  ([`6563abf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6563abfddc9fc9baba6769022d6925545decdba9))


## v1.9.0 (2024-12-10)

### Features

- **side_menu**: Side menu with stack widget added
  ([`c7d7c6d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c7d7c6d9ed7c2dcc42b33fcd590f1f27499322c1))

### Testing

- **side_panel**: Tests added
  ([`9b95b5d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9b95b5d6164ff42673dbbc3031e5b1f45fbcde0a))


## v1.8.0 (2024-12-10)

### Features

- **modular_toolbar**: Material icons can be added/removed/hide/show/update dynamically
  ([`a55134c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a55134c3bfcbda6dc2d33a17cf5a83df8be3fa7f))

- **modular_toolbar**: Orientation setting
  ([`5fdb232`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5fdb2325ae970a7ecf4e2f4960710029891ab943))

- **round_frame**: Rounded frame for plot widgets and contrast adjustments
  ([`6a36ca5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a36ca512d88f2b4fe916ac991e4f17ae0baffab))

### Testing

- **modular_toolbar**: Tests added
  ([`9370351`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9370351abbd7a151065ea9300c500d5bea8ee4f6))


## v1.7.0 (2024-12-02)

### Bug Fixes

- **tests**: Add test for Console widget
  ([`da579b6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/da579b6d213bcdf28c40c1a9e4e2535fdde824fb))

### Features

- **console**: Add "prompt" signal to inform when shell is at prompt
  ([`3aeb0b6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3aeb0b66fbeb03d3d0ee60e108cc6b98fd9aa9b9))

- **console**: Add 'terminate' and 'send_ctrl_c' methods to Console
  ([`02086ae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02086aeae09233ec4e6ccc0e6a17f2b078d500b8))

.terminate() ends the started process, sending SIGTERM signal. If process is not dead after optional
  timeout, SIGKILL is sent. .send_ctrl_c() sends SIGINT to the child process, and waits for prompt
  until optional timeout is reached. Timeouts raise 'TimeoutError' exception.


## v1.6.0 (2024-11-27)

### Bug Fixes

- Add back accidentally removed variables
  ([`e998352`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e9983521ed2a1c04af048a55ece70a1943a84313))

- Differentiate click and drag for DeviceItem, adapt tests accordingly
  ([`cffcdf2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cffcdf292363249bcc7efa9d130431d0bc727fda))

This fixes the blocking "QDrag.exec_()" on Linux, indeed before the drag'n'drop operation was
  started with a simple click and it was waiting for drop forever. Now there are 2 different cases,
  click or drag'n'drop - the drag'n'drop test actually moves the mouse and releases the button.

- Do not quit automatically when last window is "closed"
  ([`96e255e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/96e255e4ef394eb79006a66d13e06775ae235667))

Qt confuses closed and hidden

- No need to call inspect.signature - it can fail on methods coming from C (like Qt methods)
  ([`6029246`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60292465e9e52d3248ae681c68c07298b9b3ce14))

- **rpc**: Gui hide/show also hide/show all floating docks
  ([`c27d058`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c27d058b01fe604eccec76454e39360122e48515))

- **server**: Use dock area by default
  ([`2fe7f5e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2fe7f5e1510a5ea72676045e6ea3485e6b11c220))

- **tests**: Make use of BECDockArea with client mixin to start server and use it in tests
  ([`da18c2c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/da18c2ceecf9aeaf0e0ea9b78f4c867b27b9c314))

Depending on the test, auto-updates are enabled or not.

### Features

- '._auto_updates_enabled' attribute can be used to activate auto updates installation in
  BECDockArea
  ([`31d8703`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/31d87036c9801e639a7ca6fc003c90e0c4edb19d))

- Add '--hide' argument to BEC GUI server
  ([`1f60fec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f60fec7201ed252d7e49bf16f2166ee7f6bed6a))

- Add main window container widget
  ([`f80ec33`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f80ec33ae5a261dbcab901ae30f4cc802316e554))

- Add rpc_id member to client objects
  ([`3ba0b1d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3ba0b1daf5b83da840e90fbbc063ed7b86ebe99b))

- Asynchronous .start() for GUI
  ([`2047e48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2047e484d5a4b2f5ea494a1e49035b35b1bbde35))

- Do not take focus when GUI is loaded
  ([`1f71d8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f71d8e5eded9952f9b34bfc427e2ff44cf5fc18))

- **client**: Add show()/hide() methods to "gui" object
  ([`e68e2b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e68e2b5978339475b97555c3e20795807932fbc9))

- **server**: Add main window, with proper gui_id derived from given id
  ([`daf6ea0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/daf6ea0159c9ffc7b53bb7ae6b9abc16a302972c))


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
