# CHANGELOG


## v1.24.0 (2025-02-26)

### Bug Fixes

- Make scan metadata use collapsible frame
  ([`1c0021f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1c0021f98b8e0419dba883b891a6035653c0ba0d))

- Replace add'l md table w/ tree view
  ([`42665b6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/42665b69c5cca60a9e5f2d7bd43dbfe5da5a7eb3))

### Code Style

- Isort
  ([`d32952a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d32952a0d590b03007271427bd85f00b88ef0851))

### Features

- Add expandable/collapsible frame
  ([`5206528`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5206528feccaf192f3d5872ac785470562b493f9))

- Add metadata widget to scan control
  ([`7309c1d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7309c1dede2ec93bf08f84f13596ce18dfdb1476))


## v1.23.1 (2025-02-24)

### Bug Fixes

- Update redis mock for changes in bec
  ([`6a43554`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a43554f3b57045325f57bdd5079d7f91af40bb6))


## v1.23.0 (2025-02-24)

### Features

- **bec_spin_box**: Double spin box with setting inside for defining decimals
  ([`f19d948`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f19d9485df403cb755315ac1a0ff4402d7a85f77))


## v1.22.0 (2025-02-19)

### Bug Fixes

- **modular_toolbar**: Add action to an already existing bundle
  ([`4c4f159`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4c4f1592c29974bb095c3c8325e93a1383efa289))

- **toolbar**: Qmenu Icons are visible
  ([`c2c0221`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c2c022154bddc15d81eb55aad912d8fe1e34c698))

- **toolbar**: Update_separators logic updated, there cannot be two separators next to each other
  ([`facb8c3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/facb8c30ffa3b12a97c7c68f8594b0354372ca17))

- **toolbar**: Widget actions are more compact
  ([`ef36a71`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ef36a7124d54319c2cd592433c95e4f7513e982e))

### Features

- **toolbar**: Switchabletoolbarbutton
  ([`333570b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/333570ba2fe67cb51fdbab17718003dfdb7f7b55))

### Refactoring

- **toolbar**: Added dark mode button for testing appearance for the toolbar example
  ([`6b08f7c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b08f7cfb2115609a6dc6f681631ecfae23fa899))

### Testing

- **toolbar**: Blocking tests fixed
  ([`6ae33a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ae33a23a62eafb7c820e1fde9d6d91ec1796e55))


## v1.21.4 (2025-02-19)

### Bug Fixes

- **colors**: Pyqtgraph styling updated on the app level
  ([`ae18279`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ae182796855719437bdf911c2e969e3f438d6982))

- **plot_base**: Mouse interactions default state fetch to toolbar
  ([`97c0ed5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/97c0ed53df21053fef9811c3dea3b79020137030))

### Refactoring

- **plot_base**: Change the PlotWidget to GraphicalLayoutWidget
  ([`ff8e282`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff8e282034f0970b69cf0447fc5f88b4f30bf470))


## v1.21.3 (2025-02-19)

### Bug Fixes

- **bec_signal_proxy**: Unblock signal timer cleanup added
  ([`0addef5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0addef5f172a7cc1412ac146a6eec2a2caa8ad9c))


## v1.21.2 (2025-02-18)

### Bug Fixes

- **client_utils**: Autoupdate has correct propagation of BECDockArea to plugin repos
  ([`056731c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/056731c9add7d92f7da7fa833343cf65e8f383a8))


## v1.21.1 (2025-02-17)

### Bug Fixes

- **bec_connector**: Workers stored in reference to not be cleaned up with garbage collector
  ([`383936f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/383936ffc2bd7d2e088d3367c76b14efa3d1732c))


## v1.21.0 (2025-02-17)

### Features

- Generated form for scan metadata
  ([`1708bd4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1708bd405f86b1353828b01fbf5f98383a19ec2a))


## v1.20.0 (2025-02-06)

### Features

- **widget**: Add LogPanel widget
  ([`b3217b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b3217b7ca5cabe8798f06787de4ae3f3ec1af3b6))

hopefully without segfaults - compared to first implementation: - explicitly set parent of all
  dialog components - try/except and log for redis new message callback - pass in ServiceStatusMixin
  and explicitly clean it up


## v1.19.2 (2025-02-06)

### Bug Fixes

- Cleanup timer in Minesweeper
  ([`fc6d7c0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc6d7c0824be841f1bff23c8dd66b203f5798333))

- Mock QTimer, improve timeout message
  ([`fb05186`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fb051865d5fe44150a9c3599f13e2473530970bc))


## v1.19.1 (2025-02-05)

### Bug Fixes

- **macos**: Suppress IMKClient warning on macos
  ([`5e3289f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5e3289f5bdd2af02423b9975749e53c011b8dcfa))


## v1.19.0 (2025-01-31)

### Bug Fixes

- Enable type checking for BECDispatcher in BECConnector
  ([`50a572d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50a572dacd5dfc29a9ecf1b567aac6822b632f60))

### Documentation

- Add docs for LogPanel
  ([`f219c6f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f219c6fb573cf42964f6a7c6f4a0b0b9946fb98d))

### Features

- **widget**: Add LogPanel widget
  ([`f048880`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0488802775401319a54a51d05a0ad534292af09))


## v1.18.1 (2025-01-30)

### Bug Fixes

- **signal_combo_box**: Added missing plugin modules for signal line_edit/combobox
  ([`db70442`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db70442cc21247d20e6f6ad78ad0e1d3aca24bf7))

### Documentation

- Add screenshots for device and signal input
  ([`f0c4efe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0c4efefa03bf36ae57bf1a17f6a1b2e4d32c6c4))


## v1.18.0 (2025-01-30)

### Bug Fixes

- **generate_cli**: Widgets can be tagged with RPC=False, then they are excluded from client.py for
  RPC
  ([`48fc63d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48fc63d83e26889843b09b1eb4792612b53200ec))

### Build System

- Pyqt6 support dropped
  ([`a20935e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a20935e8625a9490e6c451a3b4012476e19317e5))

### Continuous Integration

- Fix formatter 2024 versions
  ([`4f8e683`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f8e6835fe2312151dc2b40f0ab9eb50a9173f7c))

### Features

- **plot_base_next_gen**: New type of plot base inherited from QWidget
  ([`e7c9729`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e7c97290cd783d19128625567835d7ae9a414989))


## v1.17.2 (2025-01-28)

### Bug Fixes

- **widget_state_manager**: Skip QLabel saving; skip_setting property widget excluded from INI;
  stored=False property excluded from INI
  ([`b2b0450`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2b0450bcb07c974e5f8002e084b350599c32d39))


## v1.17.1 (2025-01-26)

### Bug Fixes

- **bec_signal_proxy**: Timeout for blocking implemented
  ([`6f2f2aa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f2f2aa06ae9b50f0451029caa1d8d83890a5b30))


## v1.17.0 (2025-01-23)

### Bug Fixes

- Focus policy and tab order for positioner_box_2d
  ([`6df5710`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6df57103bb57c97bedda570b07a31a3cc6e57d5d))

### Documentation

- Add documentation for 2D positioner box
  ([`9a8cc31`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9a8cc31f6c1fa5595f73c2a60372ef10d4c8eabb))

### Features

- **widget**: Add 2d positioner box widget
  ([`d2ffddb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2ffddb6d8d2473d8718f5aa650559902067ff12))

### Refactoring

- Move positioner_box and line into submodule
  ([`2419521`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2419521f5f05d8ff8ce975219629f77efb7fe6be))

PositionerBox and PositionerControlLine are now exported from from
  bec_widgets.widgets.control.device_control.positioner_box, removing one level of hierarchy

- Move positioner_box logic to base class
  ([`3770db5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3770db51be68a5f3fa65e0a67a4ed3efd1c7d6fe))


## v1.16.5 (2025-01-22)

### Bug Fixes

- **cli**: Server log level info and error
  ([`df961a9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df961a9b885fa996e0ef44a36c937690670637c8))

- **error_popups**: Errors in SafeProperty and in SafeSlot are always logged, even with error
  message popup enabled
  ([`219d43d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/219d43d325260569e17a8eb7d56f63267d6e9649))


## v1.16.4 (2025-01-21)

### Bug Fixes

- Make combo box plugin files conform to autogen name
  ([`141e1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/141e1a34c999756adc0f00f6a989251ba24cf42c))


## v1.16.3 (2025-01-20)

### Bug Fixes

- **error_popups**: Logger message in SafeSlot for errors; identification in error log from which
  property or signal errors comes from
  ([`02a4862`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02a4862afdbbb5d343f798a086395e1596d1239a))

### Testing

- **error_popups**: Safeslot tests adjusted; tests extended to cover SafeProperty
  ([`dfa2908`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dfa2908c3de39802d40a2dee3e77cd5ca2ccad3b))


## v1.16.2 (2025-01-20)

### Bug Fixes

- **widget_io**: Toggleswitchhandler added
  ([`889ea86`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/889ea8629fabdc8afe2211103f8b63dfa52cc262))


## v1.16.1 (2025-01-16)

### Bug Fixes

- **error_popups**: Safeproperty logger import fixed
  ([`b40d2c5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b40d2c5f0b55853323b1c71d90b3d91c4b41140f))


## v1.16.0 (2025-01-14)

### Bug Fixes

- **e2e**: Num of elements to wait for scan fixed to steps requested in the scan
  ([`0fd5dd5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fd5dd5a264beb93690365ad8befa34cfdd296d0))

- **toolbar**: Adjusted to future plot base
  ([`508abfa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/508abfa8a5a31829bdfd5853e967f5ac668d8d8d))

### Features

- **modular_toolbar**: Context menu and action bundles
  ([`001e6fc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/001e6fc807667187807656a55ab58e3b2f17c9ca))


## v1.15.1 (2025-01-13)

### Bug Fixes

- **error_popups**: Safeproperty wrapper extended to catch more errors and not crash Designer
  ([`3b04b98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3b04b985b66a7237703a87f6a53610171eb9ffa5))


## v1.15.0 (2025-01-10)

### Features

- **widget_state_manager**: Example app added
  ([`a00d368`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a00d368c25a19b04d6fbc8a07cff330d1a232e21))

- **widget_state_manager**: State manager for single widget
  ([`01b4608`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/01b4608331f375aeeeb692328b693f2d2802dc9c))


## v1.14.1 (2025-01-10)

### Bug Fixes

- Cast spinner widget angle to int when using for arc
  ([`fa9ecaf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa9ecaf43347f6a07f86075d7ea54463684344f1))


## v1.14.0 (2025-01-09)

### Documentation

- Add docs for games/minesweeper
  ([`e2c7dc9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e2c7dc98d2f1c627fcc1aac045fa32dc94057bb0))

### Features

- **widget**: Make Minesweeper into BEC widget
  ([`507d46f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/507d46f88bd06a3e77b1e60a6ce56c80f622cb6c))

- **widgets**: Added minesweeper widget
  ([`57dc1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57dc1a3afc60b6c27b42c258a6fd1ea1ddb24637))


## v1.13.0 (2025-01-09)

### Bug Fixes

- Add .windows property to keep track of top level windows, ensure all windows are shown/hidden
  ([`48c140f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48c140f937395f88ecf662e144b452a35b34ebb6))

- Bec-gui-server script: fix logic with __name__ == '__main__'
  ([`6f2eb6b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f2eb6b4cd920002449039da637945aae62eff88))

When started with "bec-gui-server" entry point, __name__ is "bec_widgets.cli.server". When started
  with "python -m bec_widgets.cli.server", __name__ is "__main__". So, better to not rely on
  __name__ at all.

- Determine default figure since the beginning
  ([`271a4a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/271a4a24e7de2101d63827e314bfdf3fa13d2f19))

- Do not display error popup if command is executed via RPC
  ([`52c5286`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52c5286d64e9d14ce10baadbcf66aac77497faf7))

- Prevent infinite recursion in show/hide methods
  ([`1b03ded`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b03ded906a730a3890e03c31137519ebbcdf46d))

- Prevent top-level dock areas to be destroyed with [X] button
  ([`09cb08a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/09cb08a233451c7d0c42aee6efdd8cad84bf8df7))

- Remove useless class member
  ([`42fd78d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/42fd78df40f78d4116f48d1791d33698fe2d61e5))

- Set minimum size hint on BECDockArea
  ([`2742a3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2742a3c6cf305c2fa1815c5dcae800999bf06d28))

- Simplify AutoUpdate code thanks to threadpool executor in BEC Connector
  ([`1b03825`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b0382524f3d7d871cc165ce6f87cdc5efbb2495))

- Tests: rename fixtures and add 'connected_client_gui_obj'
  ([`955cc64`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/955cc64257aaba49c13b7e781ff295eba456e0ee))

- Use generator exec feature of BEC Connector to remove the AutoUpdate thread+queue
  ([`c405421`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c405421db9a2c668c8e16fc1dcc74b2f9807ca89))

- Use specified timeout in _run_rpc
  ([`bdb2520`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bdb25206d9cbcb8a6a8b55d73d89bb29a4158fc8))

### Build System

- Fixed pytest bec dependency
  ([`bd54142`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bd5414288c189d82a2c3dce1a14e996db44d69d6))

### Continuous Integration

- Install pytest plugin from specified repo, not pypi
  ([`95f6a7c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/95f6a7ceb721581ebe8bc783e5aa8fd5622d0085))

### Features

- Add "new()" command to create new dock area windows from client
  ([`bde5618`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bde561869951baec967c603d15dbfb90c31a0f8f))

- Add '.delete()' method to BECDockArea, make main window undeletable
  ([`92b8020`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/92b802021f60ec88c81be55e5ed39d90a8b05261))

- Add test for BECGuiClient features .new, .delete, .show, .hide, .close
  ([`0ff0c06`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ff0c06bd1696920eb716768fc5a201b67e2ab51))

- **widget_io**: General change signal for supported widgets
  ([`54e64c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/54e64c9f10155c9cb6c77b6c18d45f65bac09f1e))

### Refactoring

- Becguiclientmixin -> BECGuiClient
  ([`809e654`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/809e65408717aabfabaf9c9f5a34f907ced106e1))

- Mixin class was only used with BECDockArea, now it is a class by itself which represents the
  client object connected to the GUI server ; ".main" is the dock area of the main window - Enhanced
  "wait_for_server" - ".selected_device" is stored in Redis, to allow server-side to know about the
  auto update configuration instead of keeping it on client

- Move RPC-related classes and modules to 'rpc' directory
  ([`5c83702`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c83702382f5b66a75aec9243d08774a30f88088))

This allows to break circular import, too

- **rpc,client_utils**: Minor cleanup and type hint improvements
  ([`1c8b06c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1c8b06cbe6a0e78bb60c8ef68f26b00130f04910))


## v1.12.0 (2024-12-12)

### Features

- **safe_property**: Added decorator to handle errors in Property decorator from qt to not crash
  designer
  ([`e380489`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e38048964f942f9f4edba225835ad0a937503dd4))


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

- Allow to set selection in DeviceInput; automatic update of selection on device config update;
  cleanup
  ([`5eb15b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5eb15b785f12e30eb8ccbc56d4ad9e759a4cf5eb))

- Cleanup, added device_signal for signal inputs
  ([`6fb2055`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fb20552ff57978f4aeb79fd7f062f8d6b5581e7))

- Do not flush selection upon receiving config update; allow widgetIO to receive kwargs to be able
  to use get_value to receive string instead of int for QComboBox
  ([`91959e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91959e82de8586934af3ebb5aaa0923930effc51))

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

- Alignment 1D update, make app window a main window (in .ui file)
  ([`0015f0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0015f0e2d62adc02d3ef334e1f6dbb2d0288fec6))

- Fix syntax due to change of api for simulated devices
  ([`19f4e40`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/19f4e407e00ee242973ca4c3f90e4e41a4d3e315))

- Remove wrongly scoped test
  ([`a23841b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a23841b2553dc7162da943715d58275c7dc39ed9))

- Rename 'compact' property -> 'compact_view'
  ([`6982711`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6982711fea5fb8a73845ed7c0692e3ec53ef7871))

- Set (Minimum, Fixed) size policy on Stop button
  ([`523cc43`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/523cc435725b10b7d59a4477a1aaa24a1f3e37a2))

### Features

- Add 'expand_popup' property to CompactPopupWidget
  ([`e4121a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4121a01cb6b8d496e630cd43bc642b994b8f310))

This property tells if expand should show a popup (by default), or if the widget should expand
  in-place

- Emit 'device_selected' and 'scan_axis' from scan control widget
  ([`0b9b1a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b9b1a3c89a98505079f7d4078915b7bbfaa1e23))

- New 'device_selected' signals to ScanControl, ScanGroupBox, DeviceLineEdit
  ([`9801d27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9801d2769eb0ee95c94ec0c011e1dac1407142ae))

- New PositionerGroup widget
  ([`af9655d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af9655de0c541092437accfbaa779628a2f48ccb))

- Positionerbox with a popup view
  ([`2615787`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/261578796f1de8ca9cab9b91659bc1484f7aa89d))

### Refactoring

- Move add/remove bundle to scan group box
  ([`e3d0a7b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3d0a7bbf9918dc16eb7227a178c310256ce570d))

- Redesign of scan selection and scan control boxes
  ([`a69d287`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a69d2870e2b3539739781d741b27b8599c0f4abd))


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


## v0.117.0 (2024-10-11)

### Features

- **utils**: Fps counter utility based on the viewBox updates, integrated to waveform and image
  widget
  ([`8c5ef26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c5ef268430d5243ac05fcbbdb6b76ad24ac5735))


## v0.116.0 (2024-10-11)

### Build System

- Fix PySide6 to 6.7.2
  ([`908dbc1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/908dbc1760da5b323722207163f00850b84fb90b))

### Features

- Adapt BECQueue and BECStatusBox widgets to use CompactPopupWidget
  ([`94ce92f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/94ce92f5b054d25ea3bb7976c1f75e14b78b9edc))

- Add 'CompactPopupWidget' container widget
  ([`49268e3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/49268e3829406d70b09e4d88989812f5578e46f4))

Makes it easy to write widgets which can have a compact representation with LED-like global state
  indicator, with the possibility to display a popup dialog with more complete UI

- Ui changes to have top toolbar with compact popup widgets (fix issue #360)
  ([`499b6b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/499b6b9a12efd931b5728b519404c41a7e29e4d6))


## v0.115.0 (2024-10-08)

### Bug Fixes

- Adjust bec_qthemes dependency
  ([`b207e45`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b207e45a67818ee061272ce00a09fe7ea31cd1ba))

- Make Alignment1D a MainWindow as it is an application
  ([`c5e9ed6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5e9ed6e422acb908e1ada32822f5d7cc256ade7))

### Features

- Add bec-app script to launch applications
  ([`8bf4842`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8bf48427884338672a8e3de3deb20439b0bfdf99))


## v0.114.0 (2024-10-02)

### Bug Fixes

- Prevent exception when empty string updates are coming from widget
  ([`04cfb1e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/04cfb1edf19437d54f07b868bcf3cfc2a35fd3bc))

- Use new 'scan_axis' signal, to set_x and select x axis on waveform
  ([`efa2763`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efa276358b0f5a45cce9fa84fa5f9aafaf4284f7))

Fixes #361, do not try to change x axis when not permitted

### Features

- New 'scan_axis' signal
  ([`f084e25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f084e2514bc9459cccaa951b79044bc25884e738))

Signal is emitted before "scan_started", to inform about scan positioner and (start, stop)
  positions. In case of multiple bundles, the signal is emitted multiple times.


## v0.113.0 (2024-10-02)

### Bug Fixes

- Add is_log checks and functionality to plot_indicator_items
  ([`0f9953e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f9953e8fdcf3f9b5a09f994c69edb6b34756df9))

### Features

- Add first draft for alignment_1d GUI
  ([`63c24f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63c24f97a355edaa928b6e222909252b276bcada))

- Add move to position button to lmfit dialog
  ([`281cb27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/281cb27d8b5433e27a7ba0ca0a19e4b45b9c544f))

### Refactoring

- Add proxy to waveform to limit the dap_request frequency
  ([`5c74037`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c740371d86d9b1b341bc3c4d8bdf62027aa089b))

- Allow hiding of arg/kwarg boxes
  ([`efe90eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/efe90eb163e2123a5b4d0bb59f66025a569336ad))

- Linear_region_selector accepts log_x data
  ([`7cc0726`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7cc07263982a171744ff87adb10ea77585764b71))

- Update dap_model also if x and y axis are selected
  ([`28ee385`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28ee3856be2c47a63182b16454ece37a0ec04811))

- Use accent colors for bec_status_box icons; closes #338
  ([`e039304`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e039304fd3ee03dc4a3fa22a69c207139e0c0d28))

- Various minor improvements for the alignment gui
  ([`f554f3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f554f3c1672c4fe32968a5991dc98802556a6f3b))

### Testing

- Add tests for scan_status_callback
  ([`dc0c825`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dc0c825fd594c093a24543ff803d6c6564010e92))


## v0.112.1 (2024-09-19)

### Bug Fixes

- Test e2e dap wait_for_fit
  ([`b2f7d3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b2f7d3c5f3f4bf00cc628f788e2c278ebb5688ae))

### Documentation

- **dap_combo_box**: Updated screenshot
  ([`e3b5e33`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e3b5e338bfaec276979183fb6d79ab41a7ca21e1))

- **device_box**: Updated screenshot
  ([`c8e614b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8e614b575b48be788a6389a7aa0cfa033d86ab8))


## v0.112.0 (2024-09-17)

### Features

- Console: various improvements, auto-adapt rows to widget size, Qt Designer plugin
  ([`286ad71`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/286ad7196b0b8562d648fb304eab7d759b6a959b))


## v0.111.0 (2024-09-17)

### Bug Fixes

- **generate_cli**: Fixed type annotations
  ([`d3c1a1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d3c1a1b2edcba7afea9d369820fa7974ac29c333))

- **palette viewer**: Fixed background for tool tip
  ([`9045323`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9045323049d2a39c36fc8845f3b2883d6933436b))

- **position_indicator**: Fixed user access
  ([`dd932dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd932dd8f3910ab67ec8403124f4e176d048e542))

- **positioner_box**: Visual improvements to the positioner_box and positioner_control_line
  ([`7ea4a48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ea4a482e7cd9499a7268ac887b345cab01632aa))

### Documentation

- **position_indicator**: Updated position indicator documentation and added designer properties
  ([`60f7d54`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60f7d54e2b4c3129de6c95729b8b4aea1757174f))

### Features

- **position_indicator**: Improved design and added more customization options
  ([`d15b222`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d15b22250fbceb708d89872c0380693e04acb107))


## v0.110.0 (2024-09-12)

### Features

- **palette_viewer**: Added widget to display the current palette and accent colors
  ([`a8576c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8576c164cad17746ec4fcd5c775fb78f70c055c))


## v0.109.1 (2024-09-09)

### Bug Fixes

- Refactor textbox widget, remove inheritance, adhere to bec style; closes #324
  ([`b0d786b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b0d786b991677c0846a0c6ba3f2252d48d94ccaa))


## v0.109.0 (2024-09-06)

### Bug Fixes

- **theme**: Fixed theme access for themecontainer
  ([`de303f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/de303f0227fc9d3a74a0410f1e7999ac5132273c))

### Features

- **accent colors**: Added helper function to get all accent colors
  ([`84a59f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84a59f70eed6d8a3c3aeeabc77a5f9ea4e864f61))


## v0.108.0 (2024-09-06)

### Documentation

- **progressbar**: Added docs
  ([`7d07cea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d07cea946f9c884477b01bebfb60b332ff09e0a))

### Features

- **generate_cli**: Added support for property and qproperty setter
  ([`a52182d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a52182dca978833bfc3fad755c596d3a2ef45c42))

- **progressbar**: Added bec progressbar
  ([`f6d1d0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f6d1d0bbe3ba30a3b7291cd36a1f7f8e6bd5b895))


## v0.107.0 (2024-09-06)

### Documentation

- Extend waveform docs
  ([`e6976dc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6976dc15105209852090a00a97b7cda723142e9))

### Features

- Add roi select for dap, allow automatic clear curves on plot request
  ([`7bdca84`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7bdca8431496fe6562d2c28f5a6af869d1a2e654))

### Refactoring

- Change style to bec_accent_colors
  ([`bd126dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bd126dddbbec3e6c448cce263433d328d577c5c0))

### Testing

- Add tests, including extension to end-2-end test
  ([`b1aff6d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b1aff6d791ff847eb2f628e66ccaa4672fdeea08))


## v0.106.0 (2024-09-05)

### Features

- **plot_base**: Toggle to switch outer axes for plotting widgets
  ([`06d7741`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06d7741622aea8556208cd17cae521c37333f8b6))

### Refactoring

- Use DAPComboBox in curve_dialog selection
  ([`998a745`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/998a7451335b1b35c3e18691d3bab8d882e2d30b))

### Testing

- Fix tests
  ([`6b15abc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b15abcc73170cb49292741a619a08ee615e6250))


## v0.105.0 (2024-09-04)

### Features

- Add dap_combobox
  ([`cc691d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cc691d4039bde710e78f362d2f0e712f9e8f196f))

### Refactoring

- Cleanup and renaming of slot/signals
  ([`0fd5cee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fd5cee77611b6645326eaefa68455ea8de26597))

- **logger**: Changed prints to logger calls
  ([`3a5d7d0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3a5d7d07966ab9b38ba33bda0bed38c30f500c66))


## v0.104.0 (2024-09-04)

### Bug Fixes

- **scan_control**: Safeslot applied to run_scan to avoid faulty scan requests
  ([`9047916`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90479167fb5cae393c884e71a80fcfdb48a76427))

- **scan_control**: Scan parameters can be loaded from the last executed scan from redis
  ([`ec3bc8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec3bc8b5194c680b847d3306c41eef4638ccfcc7))

- **toggle**: State can be determined with the widget initialisation
  ([`2cd9c7f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2cd9c7f5854f158468e53b5b29ec31b1ff1e00e6))

### Documentation

- **scan_control**: Docs extended
  ([`730e25f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/730e25fd3a8be156603005982bfd2a2c2b16dff1))

### Features

- **scan_control**: Scan control remember the previously set parameters and shares kwarg settings
  across scans
  ([`d28f9b0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d28f9b04c45385179353cc247221ec821dcaa29b))

### Refactoring

- **scan_control**: Basic pydantic config added
  ([`fe8dc55`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe8dc55eb102c51c34bf9606690914da53b5ac02))

- **scan_control**: Scan control layout adjusted
  ([`85dcbda`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/85dcbdaa88fe77aeea7012bfc16f10c4f873f75e))

### Testing

- **conftest**: Only run cleanup checks if test passed
  ([`26920f8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/26920f8482bdb35ece46df37232af50ab9cab463))

- **scan_control**: Tests extended for getting kwargs between scan switching and getting parameters
  from redis
  ([`b07e677`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b07e67715c9284e9bf36056ba4ba8068f60cbaf3))


## v0.103.0 (2024-09-04)

### Bug Fixes

- **theme**: Fixed segfault for webengineview for auto updates
  ([`9866075`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9866075100577948755b563dc7b7dc4cdc60d040))

### Continuous Integration

- Prefill variables for manual pipeline start
  ([`158c19e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/158c19eda771562a325fd59405f9fd4cb9a17ed6))

### Features

- **vscode**: Open vscode on a free port
  ([`52da835`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52da835803f2453096a8b7df23bee5fdf93ae2bb))

- **website**: Added method to wait until the webpage is loaded
  ([`9be19d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9be19d4abebad08c5fc6bea936dd97475fe8f628))

### Testing

- **vscode**: Popen call does not have to be the only one
  ([`39f98ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/39f98ec223ba8b59e478ac788c08c59ffe886b4e))

- **webview**: Fixed tests after refactoring
  ([`d5eb30c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d5eb30cd7df4cb0dc3275dd362768afc211eaf2d))


## v0.102.0 (2024-09-04)

### Bug Fixes

- **queue_reset_button**: Queue reset has to be confirmed with msgBox
  ([`9dd43aa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9dd43aa1fd3991368002605df4389a7a7271011b))

### Documentation

- **buttons**: Buttons section of docs split to appearance and queue buttons
  ([`047aa26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/047aa26a60220c826cc1375cf81daf11d1f3ab5c))

- **tests**: Added tests tutorial for widget
  ([`18d8561`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/18d8561c965d149a7662085f7dbe2a39a8c4a475))

### Features

- **queue**: Becqueue controls extended with Resume, Stop, Abort, Reset buttons
  ([`0d7c10e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0d7c10e670e4937787e1afaa19ca8259ac752486))

### Refactoring

- **tests**: Positioner box test changed to use create_widget fixture
  ([`df5eff3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df5eff3147c79ff0278e6a5a09c8f73d5236aed3))


## v0.101.0 (2024-09-02)

### Features

- Add Dap dialog widget
  ([`9781b77`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9781b77de27b2810fbb1047a61b1832dd186db01))

### Refactoring

- Add docs, cleanup
  ([`61ecf49`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61ecf491e52bfbfa0d5a84764a9095310659043d))


## v0.100.0 (2024-09-01)

### Bug Fixes

- **pyqt slot**: Removed slot decorator to avoid problems with pyqt6
  ([`6c1f89a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6c1f89ad39b7240ab1d1c1123422b99ae195bf01))

### Documentation

- **becwidget**: Improvements to the bec widget base class docs; fixed type hint import for sphinx
  ([`99d5e8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99d5e8e71c7f89a53d7967126f4056dde005534c))

### Features

- **theme**: Added theme handler to bec widget base class; added tests
  ([`7fb938a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7fb938a8506685278ee5eeb6fe9a03f74b713cf8))


## v0.99.15 (2024-08-31)

### Bug Fixes

- **positioner_box**: Fixed positioner box dialog; added test; closes #332
  ([`0bf1cf9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0bf1cf9b8ab2f9171d5ff63d4e3672eb93e9a5fa))

- **theme**: Update pg axes on theme update
  ([`af23e74`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af23e74f71152f4abc319ab7b45e65deefde3519))


## v0.99.14 (2024-08-30)

### Bug Fixes

- **color_button**: Inheritance changed to QWidget
  ([`3c0e501`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c0e501c56227d4d98ff0ac2186ff5065bff8d7a))

- **color_button**: Signal and slot added for selecting color and for emitting color after change
  ([`99a98de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99a98de8a3b7a83d71e4b567e865ac6f5c62a754))


## v0.99.13 (2024-08-30)

### Bug Fixes

- **dark mode button**: Fixed dark mode button state for external updates, including auto
  ([`a3110d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3110d98147295dcb1f9353f9aaf5461cba9232a))

### Documentation

- Minor updates to the widget tutorial
  ([`ec9c8f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec9c8f29633364c45ebd998a5411d428c1ce488d))

- **widget tutorial**: Step by step guide added
  ([`b32ced8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b32ced85fff628a9e1303a781630cdae3865238e))


## v0.99.12 (2024-08-29)

### Bug Fixes

- **abort_button**: Abort button added; some minor fixes
  ([`a568633`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a568633c3206a8c26069d140f2d9a548bf4124b0))

- **reset_button**: Reset button added
  ([`6ed1efc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ed1efc6af193908f70aa37fb73157d2ca6a62f4))

- **toolbar**: Widget action added
  ([`2efd487`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2efd48736cbe04e84533f7933c552ea8274e2162))


## v0.99.11 (2024-08-29)

### Bug Fixes

- **resume_button**: Resume button added
  ([`8be8295`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8be8295b2b38f36da210ab36c5da6d0a00e330cc))

### Refactoring

- Add option to select scan and hide arg bundle buttons
  ([`7dadab1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7dadab1f14aa41876ad39e8cdc7f7732248cc643))

- **icons**: General app icon changed; jupyter app icon changed to material icon
  ([`5d73fe4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d73fe455a568ad40a9fadc5ce6e249d782ad20d))


## v0.99.10 (2024-08-29)

### Bug Fixes

- **stop_button**: Queue logic scan changed to halt instead of abort and reset
  ([`4a89028`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a890281f7eaef02d0ec9f4c5bf080be11fe0fe3))

### Refactoring

- Added hide option for device selection button
  ([`cdd1752`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cdd175207e922904b2efbb2d9ecf7c556c617f2e))

- **stop_button**: Stop button changed to QWidget and adapted for toolbar
  ([`097946f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/097946fd688b8faf770e7cc0e689ea668206bc7a))


## v0.99.9 (2024-08-28)

### Bug Fixes

- Fixed build process and excluded docs and tests from tarballs and wheels
  ([`719254c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/719254cf0a48e1fc4bd541edba239570778bcfea))


## v0.99.8 (2024-08-28)

### Bug Fixes

- **website**: Fixed designer integration for website widget
  ([`5f37e86`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5f37e862c95ac7173b6918ad39bcaef938dad698))

### Refactoring

- **website**: Changed inheritance of website widget to simple qwidget; closes #325
  ([`9925bbd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9925bbdb48b55eacbbce9fd6a1555a21b84221f9))


## v0.99.7 (2024-08-28)

### Bug Fixes

- **toolbar**: Material icons can accept color as kwarg
  ([`ffc871e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ffc871ebbd3b68abc3e151bb8f5849e6c50e775e))


## v0.99.6 (2024-08-28)

### Bug Fixes

- **toolbar**: Use of native qt separators
  ([`09c6c93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/09c6c93c397ce4a21c293f6c79106c74b2db65ca))

### Documentation

- Various bugs fixed
  ([`c31e9a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c31e9a3aff3ee8e984674dee0965ee7f1b6e2b8f))


## v0.99.5 (2024-08-28)

### Bug Fixes

- **dock_area**: Dark button added
  ([`e6f204b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6f204b6aa295747a68769f43af2e549149b401a))

### Documentation

- **index**: Index page is centered
  ([`02239de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02239de0a36fcd6cbf97990b0dec1ddf7ecf6ba6))


## v0.99.4 (2024-08-28)

### Bug Fixes

- **theme**: Apply theme to all pyqtgraph widgets on manual updates
  ([`c550186`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5501860e8e07a53f4bce144d44ed39eda6290ef))

### Documentation

- **buttons**: Added missing buttons docs
  ([`4e5520a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4e5520aee2115d2fc0cebb3865433478a5ec8253))

- **developer**: Tutorial for BECWidget base class
  ([`ac2cb51`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ac2cb5197deef4d51e26ee5beb070eba3ffc210d))

### Refactoring

- **buttons**: Changed grid and thumbnail fig in gallery
  ([`4591ba8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4591ba8f73e22aba7258cad93c073f1387cb74a0))

- **icons**: Moved widget icons to class attribute ICON_NAME
  ([`e890091`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e890091d862e42317c7a54fc414ba37c85f268b0))

- **icons**: Removed toolbar icons from assets
  ([`f335763`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f335763280adb1d83ba31f073ce206e4cb5d15ef))


## v0.99.3 (2024-08-27)

### Bug Fixes

- **cmaps**: Unified all defaults to magma cmap
  ([`1ca9499`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1ca9499edd334c19fe1e7aac71d3940a80a1ec95))

- **color maps**: Color maps should take the background color into account; fixed min colors to 10
  ([`060935f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/060935ffc5472a958c337bf60834c5291f104ece))

### Build System

- Updated min version of bec qthemes
  ([`d482434`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d48243483ef8228cc5eb85e40a6b8f5da3b45520))


## v0.99.2 (2024-08-27)

### Bug Fixes

- **widgets**: Fixed default theme for widgets
  ([`cf28730`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf28730515e3c2d5914e0205768734c578711e5c))

If not theme is set, the init of the BECWidget base class sets the default theme to "dark"

### Continuous Integration

- Additional tests are not allowed to fail
  ([`bb385f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bb385f07ca18904461a541b5cadde05398c84438))


## v0.99.1 (2024-08-27)

### Bug Fixes

- **crosshair**: Emit all crosshair events, not just line coordinates
  ([`2265458`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2265458dcc57970db18c62619f5877d542d72e81))


## v0.99.0 (2024-08-25)

### Bug Fixes

- **toggle**: Emit state change
  ([`c4f3308`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c4f3308dc0c3e4b2064760ccd7372d71b3e49f96))

### Documentation

- **darkmodebutton**: Added dark mode button docs
  ([`406c263`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/406c263746f0e809c1a4d98356c48f40428c23d7))

### Features

- **darkmodebutton**: Added button to toggle between dark and light mode
  ([`cc8c166`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cc8c166b5c1d37e0f64c83801b2347a54a6550b6))

### Refactoring

- **darkmodebutton**: Renamed set_dark_mode_enabled to toggle_dark_mode
  ([`c70724a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c70724a456900bcb06b040407a2c5d497e49ce77))

### Testing

- **dark_mode_button**: Added tests for dark mode button
  ([`df35aab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df35aabff30c5d00b1c441132bd370446653741e))


## v0.98.0 (2024-08-25)

### Bug Fixes

- Fix color palette if qtheme was not called
  ([`3f3b207`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3f3b207295ebd406ebaeecee465c774965161b8b))

- Transitioning to material icons
  ([`2a82032`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a82032644a84e38df04e2035a6aa63f4a046360))

- Use globally set theme instead of the internal bec widgets theme
  ([`77c5aa7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/77c5aa741cf1f5b969a42aa878aa2965176dbf41))

- **dock_area**: Transitioned to MaterialIconAction
  ([`88a2f66`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88a2f667588e9aeb34ae556fa327898824052bc3))

- **figure**: Removed theme from figure init
  ([`e42b84c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e42b84c63650297d67feffccc02a2c2ba111ca79))

- **toolbar**: Removed hardcoded color values
  ([`afdf4e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/afdf4e8782a22566932180224fa1c924d24c810f))

- **waveform**: Fixed icon appearance
  ([`36ad464`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/36ad4641594b67c9b789515c28f7db78a12757ee))

### Features

- **themes**: Added set_theme method
  ([`2b4449a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b4449afebdda0a97f95712a1353cf40ec55c283))

### Refactoring

- **waveform**: Use set theme for demo
  ([`44cfda1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/44cfda1c07306669c9a4e09706d95e6b91dee370))


## v0.97.0 (2024-08-23)

### Bug Fixes

- **toolbar icon**: Fixed material icon toolbar for theme changes
  ([`3ecbd60`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3ecbd60627994417c9175364e5909710dbcdceb2))

### Features

- **designer**: Added designer icon factory
  ([`82a55dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/82a55ddf3eafb589cb63408db1c0e7e5c9d629da))


## v0.96.3 (2024-08-23)

### Bug Fixes

- Minor fixes for type annotations
  ([`8c2e7c8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c2e7c82592ace50e4e1f47e392a0ddc988f57ae))

### Documentation

- **dispatcher**: Docs added
  ([`dd7c71b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd7c71bb1e0b7ef5398b1e1a05fc1147c772420a))


## v0.96.2 (2024-08-22)

### Bug Fixes

- **waveform**: Skip validation for curves that are not BECCurve instances
  ([`617db36`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/617db36ed4932c8a0633724079b695bc67d5c77b))

- **waveform**: Validation of custom curves removed
  ([`af28574`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af28574bd58457a05f1269f121db01ad627b5769))


## v0.96.1 (2024-08-22)

### Bug Fixes

- Bubble-up signals
  ([`2fe72c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2fe72c9ccb71bcb196a1b78197b73acf9aa3f506))

- **crosshair**: Fixed crosshair for image and waveforms
  ([`37835cb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37835cbf76ca3ba1081f514ee7793244ac500e7f))

- **crosshair**: Update markers if necessary
  ([`4473805`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/44738057a36f5de2bbb55affdd309f92286d4a0f))

- **waveform_widget**: Fixed icon appearance
  ([`f98a9f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f98a9f9771b93226d47830aa52f45739624f51b4))

### Continuous Integration

- Fail pytest after 2 failed tests
  ([`f0203d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0203d9bf60c4975ba5ab93a057d9091762454d5))


## v0.96.0 (2024-08-22)

### Documentation

- **scan_control**: Added designer options
  ([`9d7718c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d7718c3d9badf14150174410b9958a3134a1e23))

### Features

- **scan_control**: Added the ability to configure the scan control widget from designer
  ([`9d8fb0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d8fb0b761efa92972399bcd9aea28e956074380))


## v0.95.1 (2024-08-22)

### Bug Fixes

- **docs**: Changed link to scan gui config in main docs
  ([`640464a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/640464a6543b2111bdb58d0174f2ce86c5836cbe))

### Documentation

- Links section added
  ([`2bf5c70`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2bf5c7096e7d822713e1b50bde89f072e6356e17))

### Refactoring

- Moved to dynamically loaded material design icons
  ([`1d2afaa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1d2afaa09e64b7f714d72796e87e2cb49b2a75a7))

- Removed designer pngs
  ([`84abe46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84abe460502d838aac41bb8ff63d93c9fcec9214))


## v0.95.0 (2024-08-21)

### Bug Fixes

- **device_browser**: Fixed plugin assignment for designer
  ([`6500393`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/650039303aae9bbec62c676285938416fff146ce))

### Documentation

- Added sphinx-inline-tabs as sphinx dependency
  ([`e9ecd26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e9ecd268c602ea9572df0e8d508e49ee62d0c170))

- **cards**: Changed index cards to custom css class instead of overwriting the default sd-card
  theme
  ([`91ba30e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91ba30e8d054a9c7f6c6d98b21113a5d0b1bbbbb))

- **device_browser**: Added user docs
  ([`2c31cc9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2c31cc90ae751f14a653cbbdd6c353d6359aaafe))

- **user**: Widget gallery with documentation added
  ([`7357f3d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7357f3d2a189f9f04954a027f39ce07c394d57ec))

### Features

- **cli**: Added device_browser to cli
  ([`196504b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/196504b533367a899c19b88af4ccd5b39dc46aac))

- **widgets**: Added device_browser widget
  ([`73f5a2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/73f5a2f085b289ac18fa8a918b6ad7cfed595fb4))

### Refactoring

- **docs**: Review response
  ([`4790afd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4790afde3d61fc9beb073c2775c339d4f80779e3))

### Testing

- Added test for device browser
  ([`e870e5b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e870e5ba083c61df581c9c0305adabe72967f997))


## v0.94.7 (2024-08-20)

### Bug Fixes

- Formatting of stdout, stderr captured text for logger
  ([`939f834`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/939f834a26ddbac0bdead0b60b1cdf52014f182f))


## v0.94.6 (2024-08-14)

### Bug Fixes

- **server**: Emit heartbeat with state
  ([`bc2abe9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc2abe945fb5adeec89ed5ac45e966db86ce6ffc))


## v0.94.5 (2024-08-14)

### Bug Fixes

- Removed qcoreapplication for polling events
  ([`4d02b42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4d02b42f11e9882b843317255a4975565c8a536f))

- **rpc**: Use client singleton instead of dispatcher
  ([`ea9240d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ea9240d2f71931082f33fb6b68231469875c3d63))

### Build System

- Increased min version of bec to 2.21.4
  ([`4f96d0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f96d0e4a14edc4b2839c1dddeda384737dc7a8a))

Since we now rely on reusing the BECClient singleton, we need the fix introduced with 2.21.4 in BEC.


## v0.94.4 (2024-08-14)

### Bug Fixes

- Do not shutdown client in "close"
  ([`198c1d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/198c1d1064cc2dae55de4b941929341faddacb28))

Terminating client connections has to be done at the application level

### Documentation

- Review developer section; add introduction
  ([`2af5c94`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2af5c94913a3435c1839034df4f45f885b56d08b))


## v0.94.3 (2024-08-13)

### Bug Fixes

- **curve_dialog**: Async curves are shown in curve dialog after addition.
  ([`7aeb2b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7aeb2b5c26c7c2851e8d663d32521da8daec95ef))

- **waveform**: Async device entry is correctly passed, updated and with new scan the previous data
  are cleared
  ([`d56ea95`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d56ea95ef97bfdd0bc3eeddc4505d20b38e28559))

### Testing

- **waveform_widget**: Added tests for axis setting and curve dialog
  ([`f285b35`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f285b35b491660549e74349318119f7c2c44f619))


## v0.94.2 (2024-08-13)

### Bug Fixes

- **image**: Image is single image mode do not raise popup error when connected twice with the same
  monitor
  ([`98b79aa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/98b79aac7b47b73137f4d582f7f1d552b1d95366))


## v0.94.1 (2024-08-12)

### Bug Fixes

- Issue #292, wrong key was used to clean _slots internal dictionary
  ([`93d3977`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/93d397759c756397604ebff5e24f3a580be8620d))


## v0.94.0 (2024-08-08)

### Features

- Add PositionerControlLine
  ([`c80a7cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c80a7cd1083baa9543a2cee2e3c3a51dfd209b19))

### Refactoring

- Adjust dimensions
  ([`0273bf4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0273bf485694609325b5b556a3c69fb53c18446e))


## v0.93.5 (2024-08-08)

### Bug Fixes

- **positioner_box**: Icons fixed
  ([`281633d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/281633deff15b6879dac3a4f0770fa6949aaecdc))

### Refactoring

- Add button for positioner selection
  ([`0d190c5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0d190c5c5996e59fec4bdd44d2003e10e200b009))

### Testing

- **auto-update**: Wait for rendering
  ([`6d2442d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6d2442d23c683fe92af13df982ce681c07e99cde))

- **dap**: Wait for fit
  ([`6269009`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6269009e5451f830cdee58a514c7858483488a8d))


## v0.93.4 (2024-08-07)

### Bug Fixes

- Add validation for bec_lib.device.Positioner; closes #268
  ([`eb54e9f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb54e9f788e97af23db8fe0c78f8facb8688bb99))

- Rename DeviceBox to PositionerBox, fix test for validation
  ([`37aa371`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37aa371e7c4c62d70abf37abc125db0c088790fe))


## v0.93.3 (2024-08-07)

### Bug Fixes

- **dock**: Properly shut down docks and dock areas
  ([`bc26497`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc264975b1363c9dfea516621d7878c320677d15))

- **dock**: Properly shut down docks and temp areas
  ([`99ee545`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99ee545e41c6078654958b668b5b329f85553d16))

- **figure**: Cleanup pyqtgraph
  ([`ad07bbf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad07bbf85e9c8d9838bdd686f69d41c235b7db19))

- **settings**: Shut down settings dialog
  ([`b50b3a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b50b3a27e68956e10e8169a0aa698c911d2d9642))

- **website**: Fixed teardown of website widgets
  ([`a3d4f5a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3d4f5ac4bc52acfed2791a1724fade6972ed320))

### Testing

- Ensure all toplevelwidgets are closed
  ([`f9e5897`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f9e58979009cf632feea529700ad191401dd7eb8))

- Removed explicit call to close the widget
  ([`bf6294e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf6294ecbfd494565d2dc215e4d7e0c280ac7745))

- Removed quit from teardown
  ([`cf94599`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf94599c2544d6831c8afbe7b340082077557ed1))

- Use factory instead of fixture to properly cleanup widgets on teardown
  ([`9856857`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9856857f4cc7fa229c10d00fbae4452464a207cb))


## v0.93.2 (2024-08-07)

### Bug Fixes

- **scan_group_box**: Scan Spinboxes limits increased to max allowed values; setting dialog for step
  size and decimal precision for ScanDoubleSpinBox on right click
  ([`a372925`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a372925fffa787c686198ae7cb3f9c15b459c109))


## v0.93.1 (2024-08-06)

### Bug Fixes

- **dock**: Docks have more recognizable red icon for closing docks
  ([`af86860`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af86860bf35474805fb1a7bc3725cf8835ed4cc7))

### Documentation

- Added video tutorial section with BSEG YT video
  ([`302ae90`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/302ae90139f6a88e2401fe29fe312387486e27a9))


## v0.93.0 (2024-08-05)

### Features

- **themes**: Moved themes to bec_qthemes
  ([`5aad401`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5aad401ef8774c7330784f72cd3b9d8c253e2b6a))

This reverts commit fd6ae91993a23a7b8dbb2cf3c4b7c3eda6d2b0f6


## v0.92.5 (2024-08-05)

### Bug Fixes

- **spinner**: Stop timer on close event
  ([`30fef92`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/30fef929cf6fb4b73f48151c92a0ee54c734031d))

- **status_box**: Fix cleanup of status box
  ([`1f30dd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f30dd73a9c1e3135087a5eef92c7329f54a604e))

### Refactoring

- **queue**: Refactored bec queue to inherit only from qwidget
  ([`7616ca0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7616ca0e145e233ccb48029a8c0b54b54b5b4194))

### Testing

- Register all widgets with qtbot and close them
  ([`73cd11e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/73cd11e47277e4437554b785a9551b28a572094f))


## v0.92.4 (2024-07-31)

### Bug Fixes

- Fix missmatch of signal/slot in image and motormap
  ([`dcc5fd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dcc5fd71ee9f51767a7b2b1ed6200e89d1ef754c))


## v0.92.3 (2024-07-28)

### Bug Fixes

- **docs**: Moved to pyside6
  ([`71873dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/71873ddf359516ded8f74f4d2f73df4156aa1368))


## v0.92.2 (2024-07-28)

### Bug Fixes

- **widgets**: Fixed import for tictactoe example
  ([`995a795`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/995a795060bebe25c17108d80ae0fa30463f03b1))


## v0.92.1 (2024-07-28)

### Bug Fixes

- Add xvfb to draw offscreen
  ([`3d681f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3d681f77e144e74138fc5fa65630004d7c166878))

- Always add a QApplication for tests
  ([`61a4e32`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61a4e32deb337ed27f2f43358b88b7266413b58e))

- Linting
  ([`a3fe205`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3fe20500ae2ac03dcde07432f7e21ce5262ce46))

- Metaclass + QObject segfaults PyQt(cpp bindings)
  ([`fc57b7a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc57b7a1262031a2df9e6a99493db87e766b779a))

- Reset ErrorPopup singleton between tests
  ([`5a9ccfd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5a9ccfd1f6d2aacd5d86c1a34f74163b272d1ae4))

- Use SafeSlot instead of Slot
  ([`bc1e239`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc1e23944cc0e5a861e3d0b4dc5b4ac6292d5269))

### Build System

- **ci**: Install ophyd_devices in editable mode for pipelines
  ([`06205e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06205e07903d93accf40abab153f440059f236ed))

### Refactoring

- Rename device_monitor to device_monitor_2d
  ([`714e1e1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/714e1e139e0033d2725fefb636c419ca137a68c6))

- Renamed DeviceMonitor2DMessage
  ([`4be6fd6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be6fd6b83ea1048f16310f7d2bbe777b13b245e))


## v0.92.0 (2024-07-24)

### Bug Fixes

- **device_combobox**: Set minimum size to 125px
  ([`1206e15`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1206e153094cd8505badf69a1461572a76b4c5ad))

- **dock**: Custom label can be created closable
  ([`4457ef2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4457ef2147e21b856c9dcaf63c81ba98002dcaf1))

### Features

- **dock**: Dock style sheets updated
  ([`8ca60d5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ca60d54b3cfa621172ce097fc1ba514c47ebac7))

- **general_gui**: General gui added
  ([`5696c99`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5696c993dc1c0da40ff3e99f754c246cc017ea32))


## v0.91.0 (2024-07-23)

### Bug Fixes

- **plugins**: Qt Designer plugins icons adjusted
  ([`f4844d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f4844d2e067ce75dc64b89b230d7932b308ddfc2))

- **status_item**: Icons changed to material design
  ([`1b9c55a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b9c55a46a0dfd8678c8e95ff64dd6e8cfb9233e))

### Features

- **dock_area**: Added toolbar to dock area to add widgets without CLI interactions
  ([`cce1367`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cce1367a72fca7206d351894bd1831b7bbfa7ec6))

- **dock_area**: Plugin added
  ([`a16b87a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a16b87ac28d164230dd2e8020f50ff3a63cd407e))

- **toolbar**: Expandable menu actions
  ([`28f26e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28f26e92a46063db1a194be552156a5d3b2c43e7))

### Testing

- **dock_area**: Tests extended
  ([`06fab0e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/06fab0eab926cef5677d4988fd1fce09da342dd8))


## v0.90.0 (2024-07-23)

### Bug Fixes

- **axis_setting**: Fix compatibility for issue with horizontal line for PyQt6
  ([`1cf6e32`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1cf6e32303f82bc7c3f3391d0e96a88bc31f29fc))

- **image**: Only single monitor image is allowed
  ([`fe7e542`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe7e542b19dc5b401523501acb74ac03edf62ad4))

- **image**: Raw data are saved in image item to always have precise processing
  ([`c15035b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c15035b6b769a96780a16da9e7f75af3b823654c))

- **image_widget**: Image widget adjusted
  ([`3d2ca48`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3d2ca4855c36fe0af59a4b540caa3c8023a81773))

- **image_widget**: Image_widget autorange fixed
  ([`7f49893`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7f49893d2ce3b9d02efa764f7f10442ed6ab8f3c))

### Features

- **image_widget**: All toolbar actions added
  ([`501eb92`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/501eb923f12fa6aaa93f5428ca78e57694edfbc0))

- **image_widget**: Image_widget added
  ([`6a9317f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a9317facda896ee784c7fc1db0cd3d68cdfcf73))

- **image_widget**: Plugin added
  ([`4371168`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/43711680ba253f81fb0ffe764bcaae701b02bb49))

### Refactoring

- **jupyter_console_example**: Added examples of standalone widgets
  ([`ba0d1ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ba0d1ea9031b4ae2e2e73bf269fbfad973b924a5))

### Testing

- **image_widget**: Tests added
  ([`70fb276`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/70fb276fdf31dffc105435d3dfe7c5caea0b10ce))


## v0.89.0 (2024-07-22)

### Features

- **themes**: Moved themes to bec_qthemes
  ([`3798714`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3798714369adf4023f833b7749d2f46a0ec74eee))


## v0.88.1 (2024-07-22)

### Bug Fixes

- **plot_base**: Set_xy autorange moved to plotbase from waveform
  ([`a3dff7d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3dff7decc16115c12dc6b4ef1572552368da309))

### Documentation

- Readthedocs icon path fixed
  ([`2bcaa42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2bcaa4256d6daaefacb3ead8c72458d7b1498e29))

### Refactoring

- **toolbar**: Generalizations of the ToolBarAction
  ([`ad112d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad112d1f08157f6987edd48a0bacf9f669ef1997))


## v0.88.0 (2024-07-19)

### Bug Fixes

- **colormap_selector**: Compatibility for PyQt6 when using designer fixed
  ([`50135b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50135b5fe90a88618291e9357f180cb19251dace))

- **waveform**: Colormaps of curves can be changed and normalised
  ([`33495cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/33495cfe03b363f18db61d8af2983f49027b7a43))

feat(waveform): colormap can be changed from curve dialog

fix(curve_dialog): default dialog parameters fixed

curve Dialog colormap WIP

- **waveform_widget**: Adapted for BECWidget base class
  ([`6eb313f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6eb313fa76e559d62ecd8fa8849142b83817e47c))

- **waveform_widget**: Adapted for changes from improved scan logic from waveform widget
  ([`8ac35d7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ac35d7280b1ff007c10612228d163cc0c5d1a99))

- **waveform_widget**: Plot API unified with BECFigure
  ([`2c8764a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2c8764a27de89b39b717032b58465e120ec57fbc))

- **waveform_widget**: Temporary disabled save/load config
  ([`7089cf3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7089cf356a43d805241d5621952e544d690e65e0))

- **waveform_widget**: Use @SafeSlot decorator for automatic error message
  ([`8e588d7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8e588d79c86e950f6915e89c08fa9415c4bd8033))

### Features

- **curve_dialog**: Add DAP functionality
  ([`e830565`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e8305652fde384da037242cf8f7e3606f22bcfb6))

- **curve_dialog**: Curves can be added
  ([`c926a75`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c926a75a7927d672c044ea8f68771209ae5accc6))

- **figure**: Export dialog can be launched from CLI and from toolbar
  ([`6ff6111`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ff611109153b9412dce37c527b19e839d99bba7))

- **waveform**: Export to matplotlib window of current scene
  ([`8d93405`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8d9340539967b06b1e15f21a2106a39d5c740f31))

- **waveform_widget**: Added error handle utility
  ([`a8ff1d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8ff1d4cd09cae5eaeb4bd0ea90fdd102e32f3a3))

- **waveform_widget**: Autorange button
  ([`8df6b00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8df6b003e5c6a942fa2e875d9790e492c087bf26))

- **waveform_widget**: Becwaveformwidget added with toolbar
  ([`755b394`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/755b394c1c4d7c443c442d89c630d08ce5415554))

- **waveform_widget**: Becwaveformwidget toolbar added import/export config
  ([`fa9b171`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa9b17191ddbb4043a658dae9aa0801e1dc22b84))

- **waveform_widget**: Dap parameter window
  ([`1e551d6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1e551d6e9696f79ea2e0a179d13a4fc6c2a128b2))

- **waveform_widget**: Designer plugin added
  ([`1f8ef52`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f8ef52b606283038052640849094f515a463403))

- **waveform_widget**: Switch between drag and rectangle mode
  ([`2be009c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2be009c6477ba26c5cfb4d827534c5d5eb428999))

### Refactoring

- **icons**: Icons moved to the assets directory
  ([`a8b6ef2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a8b6ef20cccae87515b10f054d0ed5b10e152769))

- **waveform_widget**: Removed PYSIDE6 check
  ([`47fcb9e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/47fcb9ebfe35ae600cced95a1edc68f6f6e37a04))

### Testing

- **waveform_widget**: Test added
  ([`8d764e2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8d764e2d46a1e017dadc3c4630648c1ca708afc2))


## v0.87.1 (2024-07-18)

### Bug Fixes

- Add exit handlers for BECConnection objects
  ([`6202d22`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6202d224fe85c103a4c33bd8c255f18cfd027303))

- Add missing close() call, ensure jupyter console client.shutdown() is called in closeEvent
  ([`e52ee26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e52ee2604cb35096f1bd833ca9516d8a34197d35))

- Becwidget checks if it is a widget, and implements closeEvent and cleanup
  ([`d64758f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d64758f268cad69e6a17bd52dc9913a6367d3cde))

- **dock**: Added hasattr to cleanup method for widgets
  ([`d75c55b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d75c55b2b1ccf156fb789c7813f1c5bdf256f860))

### Refactoring

- Becwidget is a mixin based on BECConnector, for each QWidget in BEC
  ([`c7feb69`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c7feb6952d590b569f7b0cba3b019a9af0ce0c93))

Handles closeEvent() and RPC registering/unregistering


## v0.87.0 (2024-07-17)

### Features

- **qt_utils**: Added error handle utility with popup messageBoxes
  ([`196ef7a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/196ef7afe11a1b5dcc536f8859dc3b6044ea628e))

- **qt_utils**: Added warning utility with simple API to setup warning message
  ([`787f749`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/787f74949bac27aaa51cbb43911919071481707c))


## v0.86.0 (2024-07-17)

### Features

- **toolbar**: Added separator action
  ([`ba69e79`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ba69e7957cd20df1557ac0c3a9ca43a54493c34d))


## v0.85.1 (2024-07-17)

### Bug Fixes

- **waveform**: Readout_priority dict fixed, not overwritten to 'baseline' key
  ([`b5b0aa4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b5b0aa4f82a998bb0162dc319591e854204a7354))


## v0.85.0 (2024-07-16)

### Features

- **color_map_selector**: Added colormap selector with plugin
  ([`b98fd00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b98fd00adef97adf57f49b60ade99972b9f5a6bc))


## v0.84.0 (2024-07-15)

### Bug Fixes

- **bec_dispatcher**: Connect_slot can accept kwargs
  ([`0aa317a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0aa317aae58d3612d46f05b85f8b0db3d12bbe14))

- **waveform**: Dap leaked RID for all daps in current process; dap RID is now f"{scan_id}-{gui_id}"
  to distinguish for each plot instance
  ([`d23fd8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d23fd8bd074ede6e14eb8e85e025cbced4bd45ef))

- **waveform**: Data for axis are taken by separate method; validation consolidated
  ([`fc5a8bd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc5a8bdd8b260f5e9b59ec71a4610c57442e43fe))

- **waveform**: Only one type of x axis allowed; x mode validated
  ([`9d6ae87`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d6ae87d0f03ca227570fcca8af2d8190828d271))

- **waveform**: Set_x method various bugs fixed
  ([`8516a1d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8516a1d639925a877f174fa13f427a71131cc918))

- **waveform**: Timestamp are not converted to human readable format
  ([`e495fd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e495fd30c4c16474689943c7263e3060cb09ffb4))

- **waveform**: X axis switching logic fixed when axis are not compatible
  ([`e4e1a90`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4e1a905d19def22f970b364c18c953f00e10389))

### Features

- **waveform**: Async readback update implemented for async devices
  ([`0c6a9f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0c6a9f2310df31ddcd68050a17cfbf52c3e2e226))

- **waveform**: Data are taken directly from ScanItem which is defined from scan_status endpoint;
  scan update is triggered from scan_segment; plots can be added just specifying y_name -> best
  effort for setting x reported device
  ([`b8717f1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8717f13276734dd655ab03cd6005985ad5af9fb))

### Refactoring

- **jupyter_console_window**: Added more examples of waveforms
  ([`fc935d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc935d9fc81067c3a67389ff88ea97da2e0c903e))

- **waveform**: Plot can be prompted without specifying kwargs
  ([`48911e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48911e934815923c94edb5ced6042058a11a97f5))

### Testing

- **waveform**: Tests extended
  ([`006992e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/006992e43cc56d56261bc4fd3e9cae9abcab2153))


## v0.83.1 (2024-07-14)

### Bug Fixes

- Replace pyqtdarktheme by qdarkstyle, add 'apply_theme' function (in utils/colors.py)
  ([`8308115`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8308115f3646245d825fc47ab57297d3460bbcf5))

- Spinner: update reference image for widget test, use apply_theme
  ([`63db135`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63db1352ee883d35670b3a692dbe51d6d01872ae))

- Use apply_theme
  ([`2d4249e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d4249e73a792fed1c2c7ab79bb8aec38c57466c))

- **toolbar**: Default transparent background
  ([`eab7883`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eab78839792f175b7ac127ca603385c6baa5ff15))

### Testing

- **toolbar**: Added reference pngs for spinner for Darwin
  ([`11a7204`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11a7204c98e0bf211a8721d296b45d24a3102b97))


## v0.83.0 (2024-07-08)

### Bug Fixes

- **bec_widget**: Added cleanup method to bec widget base class
  ([`fd8766e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fd8766ed87770661da6591aeb4df5abdaf38afc7))

- **terminal**: Added default args to avoid designer crashes on startup
  ([`360d171`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/360d17135573e44b80ab517756da3c0b31daab0f))

- **website**: Fixed dummy input
  ([`903ce7d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/903ce7d46b5d37d40486d0fda92d3694d3faca62))

- **widget**: Fixed widget cleanup routine
  ([`2b29e34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b29e34b52d056349647bb2fcf649b749a60d292))

### Features

- Added reference utils to compare renderings of widgets
  ([`2988fd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2988fd387e6b8076fffec1d57e3ccab89ddb2aeb))

- **designer**: Added option to skip the widget validation for DesignerPluginGenerator
  ([`41bcb80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/41bcb801674ab6c4d6069bba34ffee09c9e665db))

- **widgets**: Added device box with spinner
  ([`1b017ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1b017edfad8e78fa079210486123976695b8915c))

### Testing

- **vscode**: Fixed vscode tests for new cleanup routine
  ([`eb26e2a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb26e2a11b229a52efe2e6d4fb28d760d3740136))

- **vscode**: Improved vscode test
  ([`5de8804`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5de8804da1e41eafad2472344904b3324438c13b))


## v0.82.2 (2024-07-08)

### Bug Fixes

- **rpc_server**: Pass cli config to server
  ([`90178e2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90178e2f61fa9dac7d82c0d0db40a9767bb133e6))


## v0.82.1 (2024-07-07)

### Bug Fixes

- **motor_map**: Bug where motors without limits were selected
  ([`c78cd89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c78cd898f203f950d7cb589eb5609feaa88062cf))

### Refactoring

- **setting_dialog**: Moved to qt_utils
  ([`3826bb3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3826bb3d9e870e85709b5b20ef09a4d22641280c))

- **toolbar**: Toolbar moved from widgets to qt_utils
  ([`7ffc06f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ffc06f3c7ddd86a1681408a75221b9bbadb236b))

### Testing

- **setting_dialog**: Tests added
  ([`74a249b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/74a249bd065d01006cb532bfff2a9bfedb34b592))


## v0.82.0 (2024-07-07)

### Features

- **toggle**: Added angular component-like toggle
  ([`b9bff38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b9bff38b64b86f06b3bc047922ef9df0c7d32e71))

### Refactoring

- **color_button**: Colorbutton moved to top level of widgets
  ([`fa1e86f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa1e86ff07b25d2c47c73117b00765b8e2f25da4))

- **device_input**: Devicecombobox and DeviceLineEdit moved to top layer of widgets
  ([`f048629`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f04862933f049030554086adef3ec9e1aebd3eda))

- **motor_map_widget**: Removed restriction of only PySide6 for widget
  ([`db1cdf4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db1cdf42806fef6d7c6d2db83528f32df3f9751d))

- **stop_button**: Moved to top layer, plugin added
  ([`f5b8375`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f5b8375fd36e3bb681de571da86a6c0bdb3cb6f0))


## v0.81.2 (2024-07-07)

### Bug Fixes

- **waveform**: Scan_history error check for IndexError
  ([`dd1875e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dd1875ea5cc18bcef9aad743347a8accf144c08d))


## v0.81.1 (2024-07-07)

### Bug Fixes

- **motor_control**: Temporary remove of motor control widgets
  ([`99114f1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99114f14f62202e1fd8bf145616fa8c69937ada4))


## v0.81.0 (2024-07-06)

### Features

- **color_button**: Can get colors in RGBA or HEX
  ([`9594be2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9594be260680d11c8550ff74ffb8d679e5a5b8f6))


## v0.80.1 (2024-07-06)

### Bug Fixes

- **entry_validator**: Check for entry == ""
  ([`61de7e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61de7e9e221c766b9fb3ec23246da6a11c96a986))


## v0.80.0 (2024-07-06)

### Features

- **plugins**: Added bec widgets base class
  ([`1aa83e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1aa83e0ef1ffe45b01677b0b4590535cb0ca1cff))

- **plugins**: Added support for pyqt6 ui files
  ([`d6d0777`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d6d07771135335cb78dc648508ce573b8970261a))

- **plugins**: Moved plugin dict to dataclass and container
  ([`03819a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/03819a3d902b4a51f3e882d52aedd971b2a8e127))

- **qt5**: Dropped support for qt5; pyside2 and pyqt5
  ([`fadbf77`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fadbf77866903beff6580802bc203d53367fc7e7))


## v0.79.3 (2024-07-05)

### Bug Fixes

- Add designer plugin classes
  ([`1586ce2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1586ce2d6cba2bb086b2ef596e724bb9e40ab4f2))

- Changed inheritance to adress qt designer bug in rendering
  ([`e403870`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e403870874bd5e45840a034d6f1b3dd576d9c846))

### Refactoring

- Simplify logic in bec_status_box
  ([`576353c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/576353cfe8c6fd64db561f0b6e2bc951300643d3))


## v0.79.2 (2024-07-04)

### Bug Fixes

- Overwrite closeEvent and call super class
  ([`bc0ef78`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc0ef7893ef100b71b62101c459655509b534a56))


## v0.79.1 (2024-07-03)

### Bug Fixes

- Use libdir env var to preload Python library, also for Linux platform
  ([`d7718d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d7718d4dcb9728c050b6421388af4d484f3741f2))


## v0.79.0 (2024-07-03)

### Bug Fixes

- **motor_map**: Fixed bug with residual trace after changing motors
  ([`aaa0d10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aaa0d1003d2e94b45bafe4f700852c2c05288aea))

- **toolbar**: Change default color to black to match BECFigure theme
  ([`b8774e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8774e0b0bc43dcd00f94f42539a778e507ca27d))

- **widget_io**: Widget handler adjusted for spinboxes and comboboxes
  ([`3dc0532`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3dc0532df05b6ec0a2522107fa0b1e210ce7d91b))

### Features

- **motor_map**: Method to reset history trace
  ([`5960918`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5960918137dd41cdeb94e50f8abc4f169cf45c11))

- **motor_map_widget**: Standalone MotorMap Widget with toolbar + plugin
  ([`6e75642`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6e756420907d7093557e945bc92bc4cfc0138d07))

### Refactoring

- **toolbar**: Cleanup and adjusted colors
  ([`96863ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/96863adf53c15112645d20eb6200733617801c6d))


## v0.78.1 (2024-07-02)

### Bug Fixes

- **ui_loader**: Ui loader is compatible with bec plugins
  ([`b787759`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b787759f44486dc7af2c03811efb156041e4b6cb))


## v0.78.0 (2024-07-02)

### Features

- **color_button**: Patched ColorButton from pyqtgraph to be able to be opened in another QDialog
  ([`c36bb80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c36bb80d6a4939802a4a1c8e5452c7b94bac185e))


## v0.77.0 (2024-07-02)

### Bug Fixes

- **bec_figure**: Full reconstruction with config from other bec figure
  ([`b6e1e20`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b6e1e20b7c8549bb092e981062329e601411dda6))

- **bec_figure**: Waveforms can be initialised from the config; widgets are deleteLater after
  removal
  ([`78673ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/78673ea11a47aad878128197ae6213925228ed59))

- **figure**: Api cleanup
  ([`008a33a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/008a33a9b192473cc58e90cd6d98c5bcb5f7b8c0))

- **figure**: If/else logic corrected in subplot_factory
  ([`3e78723`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3e787234c7274b0698423d7bf9a4c54ec46bad5f))

- **figure**: Subplot methods consolidated; added subplot factory
  ([`4a97105`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a97105e4bd2ce77d72dfe5f8307dd9ee65b21b0))

- **image**: Image add_custom_image fixed, closes #225
  ([`f0556e4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0556e44113ffee66cf735aa2dd758c62cb634f4))

- **image**: Image can be fully reconstructed from config
  ([`797f73c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/797f73c39aa73e07d6311f3de4baea53f6c380e0))

- **image**: Processing of already displayed data; closes #106
  ([`1173510`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1173510105d2d70d7e498c2ac1e122cea3a16597))

- **image_item**: Vrange added int for pydantic model check
  ([`b8f796f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8f796fd3fcc15641e8fc6a3ca75c344ce90fc45))

- **motor_map**: Api changes updates current visualisation; motor_map can be initialised from config
  ([`2e2d422`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2e2d422910685a2527a3d961a468c787f771ca44))

- **waveform**: Scatter 2D brush error
  ([`215d59c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/215d59c8bfe7fda9aff8cec8353bef9e1ce2eca1))

### Features

- **bec_connector**: Export config to yaml
  ([`a391f30`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a391f3018c50fee6a4a06884491b957df80c3cd3))

- **utils**: Colors added convertor for rgba to hex
  ([`572f2fb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/572f2fb8110d5cb0e80f3ca45ce57ef405572456))


## v0.76.1 (2024-06-29)

### Bug Fixes

- **plugins**: Fixes and tests for auto-gen plugins
  ([`c42511d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c42511dd44cc13577e108a6cef3166376e594f54))


## v0.76.0 (2024-06-28)

### Bug Fixes

- Fixed qwidget inheritance for ring progress bar
  ([`0610d2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0610d2f9f027f8659e7149f2dfbb316ff30e337d))

### Features

- **designer**: Added support for creating designer plugins automatically
  ([`c1dd0ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c1dd0ee1906dba1f2e2ae9ce40a84d55c26a1cce))


## v0.75.0 (2024-06-26)

### Features

- **widgets**: Added simple bec queue widget
  ([`3faee98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3faee98ec80041a27e4c1f1156178de6f9dcdc63))

### Refactoring

- **dispatcher**: Cleanup
  ([`ca02132`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca02132c8d18535b37e9192e00459d2aca6ba5cf))


## v0.74.1 (2024-06-26)

### Bug Fixes

- **motor_map**: Motor map can be removed from BECFigure with .remove()
  ([`6b25abf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b25abff70280271e2eeb70450553c05d4b7c99c))

- **rings**: Rings properties updated right after setting
  ([`c8b7367`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c8b7367815b095f8e4aa8b819481efb701f2e542))

### Build System

- Added missing pytest-bec-e2e dependency; closes #219
  ([`56fdae4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56fdae42757bdb9fa301c1e425a77e98b6eaf92b))

- Fixed dependency ranges; closes #135
  ([`e6a06c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6a06c9f43e0ad6bbfcfa550a2f580d2a27aff66))

### Chores

- Sorted dependencies alphabetically
  ([`21c807f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/21c807f35831fdd1ef2e488ab90edae4719f0cb7))

### Documentation

- Fixed doc string
  ([`f979a63`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f979a63d3d1a008f80e500510909750878ff4303))

### Testing

- **bec_figure**: Tests for removing widgets with rpc e2e
  ([`a268caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a268caaa30711fcc7ece542d24578d74cbf65c77))


## v0.74.0 (2024-06-25)

### Documentation

- **becfigure**: Docs added
  ([`a51b15d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a51b15da3f5e83e0c897a0342bdb05b9c677a179))

### Features

- **waveform1d**: Dap LMFit model can be added to plot
  ([`1866ba6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1866ba66c8e3526661beb13fff3e13af6a0ae562))

### Testing

- **waveform1d**: Dap e2e test added
  ([`7271b42`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7271b422f98ef9264970d708811c414b69a644db))


## v0.73.2 (2024-06-25)

### Bug Fixes

- **rpc**: Remove of calling "close" and waiting for gui_is_alive
  ([`f75fc19`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f75fc19c5b10022763252917ca473f404a25165a))

- **rpc**: Trigger shutdown of server when gui is terminated
  ([`acc1318`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/acc13183e28030e3ca9af21bb081e1eed081622b))

- **vscode**: Only run terminate if the process is still alive
  ([`7120f3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7120f3e93b054b788f15e2d5bcd688e3c140c1ce))


## v0.73.1 (2024-06-25)

### Bug Fixes

- **ringprogressbar**: Removed hard-coded endpoint strings
  ([`1de3cbf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1de3cbf65a1832150917a7549a1bf3efdee6371a))


## v0.73.0 (2024-06-25)

### Features

- Add new default scaling of image_item
  ([`df812ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df812eaad5989f2930dde41d87491868505af946))

### Testing

- Add test for imageitem
  ([`88ecd05`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88ecd05b95974938ef1efff40e81854baf004cb4))


## v0.72.2 (2024-06-25)

### Bug Fixes

- **designer**: Fixed designer for pyenv and venv; closes #237
  ([`e631fc1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e631fc15d8707b73d58cb64316e115a7e43961ea))


## v0.72.1 (2024-06-24)

### Bug Fixes

- Renamed spiral progress bar to ring progress bar; closes #235
  ([`e5c0087`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5c0087c9aed831edbe1c172746325a772a3bafa))

### Testing

- Bugfix to prohibit leackage of mock
  ([`4348ed1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4348ed1bb2182da6bdecaf372d6db85279e60af8))


## v0.72.0 (2024-06-24)

### Features

- **connector**: Added threadpool wrapper
  ([`4ca1efe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4ca1efeeb8955604069f7b98374c7f82e1a8da67))


## v0.71.1 (2024-06-23)

### Bug Fixes

- Don't print exception if the auto-update module cannot be found in plugins
  ([`860517a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/860517a3211075d1f6e2af7fa6a567b9e0cd77f3))


## v0.71.0 (2024-06-23)

### Bug Fixes

- **cleanup**: Cleanup added to device_input widgets and scan_control
  ([`8badb6a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8badb6adc1d003dbf0b2b1a800c34821f3fc9aa3))

- **scan_control**: Adapted widget to scan BEC gui config
  ([`8b822e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8b822e0fa8e28f080b9a4bf81948a7280a4c07bf))

- **scan_control**: Added default min limit for args bundle if specified
  ([`ec4574e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec4574ed5c2c85ea6fbbe2b98f162a8e1220653b))

- **scan_control**: Argbox delete later added to prevent overlapping gui if scan changed
  ([`7ce3a83`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ce3a83c58cb69c2bf7cb7f4eaba7e6a2ca6c546))

- **scan_control**: Only scans with defined gui_config are allowed
  ([`6dff187`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6dff1879c4178df0f8ebfd35101acdebb028d572))

- **scan_control**: Scan_control.py combatible with the newest BEC versions, test disabled
  ([`67d398c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67d398caf74e08ab25a70cc5d85a5f0c2de8212d))

- **scan_group_box**: Added row counter based on widgets
  ([`37682e7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37682e7b8a6ede38308880d285e41a948d6fe831))

- **WidgetIO**: Find handlers within base classes
  ([`ca85638`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca856384f380dabf28d43f1cd48511af784c035b))

### Features

- **scan_group_box**: Scan box for args and kwargs separated from ScanControlGUI code
  ([`d8cf441`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8cf44134c30063e586771f9068947fef7a306d1))

### Refactoring

- **device_line_edit**: Renamed default_device to default
  ([`4e2c9df`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4e2c9df6a4979d935285fd7eba17fd7fd455a35c))

### Testing

- **scan_control**: Tests added
  ([`56e74a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/56e74a0e7da72d18e89bc30d1896dbf9ef97cd6b))


## v0.70.0 (2024-06-21)

### Bug Fixes

- **bec-desiger+plugins**: Imports fixed, PYSIDE6 check to not enable run plugins with pyqt6
  ([`50b3422`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50b3422528d46d74317e8c903b6286e868ab7fe0))

### Documentation

- Fix typo in link
  ([`fdf11d8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fdf11d8147750e379af9b17792761a267b49ae53))

### Features

- Added entry point for bec-designer
  ([`36391db`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/36391db60735d57b371211791ddf8d3d00cebcf1))

- **bec-designer**: Automatic plugin discovery
  ([`4639eee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4639eee0b975ebd7a946e0e290449f5b88c372eb))

- **device_combobox**: Plugin added to bec-designer
  ([`e483b28`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e483b282db20a81182b87938ea172654092419b5))

- **device_line_edit**: Plugin added to bec-designer
  ([`b4b27ae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b4b27aea3d8c08fa3d5d5514c69dbde32721d1dc))

- **utils/bec-designer**: Added startup script to launched QtDesigner compatible with conda
  environments
  ([`5362334`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5362334ff3b07fc83653323a084a4b6946bade96))


## v0.69.0 (2024-06-21)

### Bug Fixes

- **generate_cli**: Fixed rpc generate for classes without user access; closes #226
  ([`925c893`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/925c893f3ff4337fc8b4d237c8ffc19a597b0996))

### Features

- **widgets**: Added vscode widget
  ([`48ae950`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48ae950d57b454307ce409e2511f7b7adf3cfc6b))


## v0.68.0 (2024-06-21)

### Bug Fixes

- Do not create 'BECClient' logger when instantiating BECDispatcher
  ([`f7d0b07`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f7d0b0768ace42a33e2556bb33611d4f02e5a6d9))

- Ignore GUI server output (any output will go to log file)
  ([`ce37416`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ce374163cab87a92847409051739777bc505a77b))

If a logger is given to log `_start_log_process`, the server stdout and stderr streams will be
  redirected as log entries with levels DEBUG or ERROR in their parent process

### Features

- Add logger for BEC GUI server
  ([`630616e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/630616ec729f60aa0b4d17a9e0379f9c6198eb96))

- Bec-gui-server: redirect stdout and stderr (if any) as proper debug and error log entries
  ([`d1266a1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d1266a1ce148ff89557a039e3a182a87a3948f49))

- Properly handle SIGINT (ctrl-c) in BEC GUI server -> calls qapplication.quit()
  ([`3644f34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3644f344da2df674bc0d5740c376a86b9d0dfe95))


## v0.67.0 (2024-06-21)

### Documentation

- Add widget to documentation
  ([`6fa1c06`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fa1c06053131dabd084bb3cf13c853b5d3ce833))

### Features

- Introduce BECStatusBox Widget
  ([`443b6c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/443b6c1d7b02c772fda02e2d1eefd5bd40249e0c))

### Refactoring

- Change inheritance to QTreeWidget from QWidget
  ([`d2f2b20`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2f2b206bb0eab60b8a9b0d0ac60a6b7887fa6fb))

### Testing

- Add test suite for bec_status_box and status_item
  ([`5d4ca81`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d4ca816cdedec4c88aba9eb326f85392504ea1c))


## v0.66.1 (2024-06-20)

### Bug Fixes

- Fixed shutdown for pyside
  ([`2718bc6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2718bc624731301756df524d0d5beef6cb1c1430))


## v0.66.0 (2024-06-20)

### Features

- **rpc**: Discover widgets automatically
  ([`ef25f56`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ef25f5638032f931ceb292540ada618508bb2aed))


## v0.65.2 (2024-06-20)

### Bug Fixes

- **pyqt**: Webengine must be imported before qcoreapplication
  ([`cbbd23a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cbbd23aa33095141e4c265719d176c4aa8c25996))


## v0.65.1 (2024-06-20)

### Bug Fixes

- Prevent segfault by closing the QCoreApplication, if any
  ([`fa344a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa344a5799b07a2d8ace63cc7010b69bc4ed6f1d))


## v0.65.0 (2024-06-20)

### Bug Fixes

- **device_input_base**: Bug with setting config and overwriting default device and filter
  ([`d79f7e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d79f7e9ccde03dc77819ca556c79736d30f7821a))

### Features

- **device_combobox**: Deviceinputbase and DeviceComboBox added
  ([`430b282`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/430b282039806e3fbc6cf98e958861a065760620))

- **device_input**: Devicelineedit with QCompleter added
  ([`50e41ff`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/50e41ff26160ec26d77feb6d519e4dad902a9b9b))

### Testing

- **device_input**: Tests added
  ([`1a0a98a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1a0a98a45367db414bed813bbd346b3e1ae8d550))


## v0.64.2 (2024-06-19)

### Bug Fixes

- **client_utils**: Added close rpc command to shutdown of gui from bec_ipython_client
  ([`e5a7d47`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5a7d47b21cbf066f740f1d11d7c9ea7c70f3080))


## v0.64.1 (2024-06-19)

### Bug Fixes

- **widgets**: Removed widget module import of sub widgets
  ([`216511b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/216511b951ff0e15b6d7c70133095f3ac45c23f4))

### Refactoring

- **utils**: Moved get_rpc_widgets to plugin_utils
  ([`6dabbf8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6dabbf874fbbdde89c34a7885bf95aa9c895a28b))

### Testing

- Moved rpc_classes test
  ([`b3575eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b3575eb06852b456cde915dfda281a3e778e3aeb))


## v0.64.0 (2024-06-19)

### Bug Fixes

- **plot_base**: Font size is set with setScale which is scaling the whole legend window
  ([`5d66720`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d6672069ea1cbceb62104f66c127e4e3c23e4a4))

### Continuous Integration

- Add job optional dependency check
  ([`27426ce`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/27426ce7a52b4cbad7f3bef114d6efe6ad73bd7f))

### Documentation

- Fix links in developer section
  ([`9e16f2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9e16f2faf9c59a5d36ae878512c5a910cca31e69))

- Refactor developer section, add widget tutorial
  ([`2a36d93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a36d9364f242bf42e4cda4b50e6f46aa3833bbd))

### Features

- Add option to change size of the fonts
  ([`ea805d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ea805d1362fc084d3b703b6f81b0180072f0825d))

### Testing

- Add tests
  ([`140ad83`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/140ad83380808928edf7953e23c762ab72a0a1e9))


## v0.63.2 (2024-06-14)

### Bug Fixes

- Do not import "server" in client, prevents from having trouble with QApplication creation order
  ([`6f96498`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f96498de66358b89f3a2035627eed2e02dde5a1))

Like with QtWebEngine


## v0.63.1 (2024-06-13)

### Bug Fixes

- Just terminate the remote process in close() instead of communicating
  ([`9263f8e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9263f8ef5c17ae7a007a1a564baf787b39061756))

The proper finalization sequence will be executed by the remote process on SIGTERM


## v0.63.0 (2024-06-13)

### Documentation

- Add documentation
  ([`bc709c4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bc709c4184c985d4e721f9ea7d1b3dad5e9153a7))

### Features

- Add textbox widget
  ([`d9d4e3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d9d4e3c9bf73ab2a5629c2867b50fc91e69489ec))

### Refactoring

- Add pydantic config, add change_theme
  ([`6b8432f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b8432f5b20a71175a3537b5f6832b76e3b67d73))

### Testing

- Add test for text box
  ([`b49462a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b49462abeb186e56bac79d2ef0b0add1ef28a1a5))


## v0.62.0 (2024-06-12)

### Features

- Implement non-polling, interruptible waiting of gui instruction response with timeout
  ([`abc6caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/abc6caa2d0b6141dfbe1f3d025f78ae14deddcb3))


## v0.61.0 (2024-06-12)

### Features

- **widgets/stop_button**: General stop button added
  ([`61ba08d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/61ba08d0b8df9f48f5c54c7c2b4e6d395206e7e6))

### Refactoring

- Improve labe of auto_update script
  ([`40b5688`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/40b568815893cd41af3531bb2e647ca1e2e315f4))


## v0.60.0 (2024-06-08)

### Bug Fixes

- Added bec_ipython_client as dependency; needed for jupyter widget
  ([`006a089`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/006a0894b85cba3b2773737ed6fe3e92c81cdee0))

- Removed BECConnector from rpc client interface
  ([`6428e38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6428e38ab94c15a2c904e75cc6404bb6d0394e04))

- **bec_connector**: Field validator should be a classmethod
  ([`867720a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/867720a897b6713bd0df9af71ffdd11a6a380f7d))

- **BECFigure**: Removed duplicated user access for plot
  ([`954c576`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/954c576131f7deac669ddf9f51eeb1d41b6f92b7))

### Continuous Integration

- Added git fetch for target branch
  ([`fc4f4f8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc4f4f81ad1be99cf5112f2188a46c5bed2679ee))

- Cleanup
  ([`11173b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11173b9c0a7dc4b36e35962042e5b86407da49f1))

- Fixed pylint-check
  ([`6b1d582`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b1d5827d6599f06a3acd316060a8d25f0686d54))

### Features

- Added entry point for bw-generate-cli
  ([`1c7f491`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1c7f4912ce5998e666276969bf4af8656d619a91))

- Added isort to bw-generate-cli
  ([`f0391f5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0391f59c9eb0a51b693fccfe2e399e869d35dda))

- **cli**: Auto-discover rpc-enabled widgets
  ([`df1be10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df1be10057a5e85a3f35bef1c1b27366b6727276))

### Refactoring

- Disabled pylint for auto-gen client
  ([`b15816c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b15816ca9fd3e4ae87cca5fcfe029b4dfca570ca))

- Minor cleanup
  ([`3adf6cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3adf6cfd586355c8b8ce7fdc9722f868e22287c5))

- **dock**: Parent_dock_area changed to orig_area (native for pyqtgraph)
  ([`2b40602`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b40602bdc593ece0447ec926c2100414bd5cf67))

- **isort**: Added bec_widgets as known first party package
  ([`9c5a471`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9c5a471234ed2928e4527b079436db2a807c5f6f))

### Testing

- Added missing pylint statement to header
  ([`f662985`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f6629852ebc2b4ee239fa560cc310a5ae2627cf7))


## v0.59.1 (2024-06-07)

### Bug Fixes

- **curve**: Set_color_map_z typo fixed in user access
  ([`e7838b0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e7838b0f2fc23b0a232ed7d68fbd7f3493a91b9e))


## v0.59.0 (2024-06-07)

### Build System

- Added webengine dependency
  ([`d56c549`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d56c5493cd28f379d04a79d90b01c73b0760da1b))

### Continuous Integration

- Added webengine dependencies
  ([`2d79ef8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d79ef8fe5e52c61f4a78782770377cd6b41958b))

- Merged additional tests to parallel matrix job
  ([`178fe4d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/178fe4d2da3a959f7cd90e7ea0f47314dc1ef4ed))

### Documentation

- Added website docs
  ([`cf6e5a4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf6e5a40fc8320e9898a446a5bf14b77e94ef013))

### Features

- **widget**: Added simple website widget with rpc
  ([`64abd67`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/64abd67b9b416bff9c89880b248d6e8639aa1e70))


## v0.58.1 (2024-06-07)

### Bug Fixes

- **dock**: New dock can be detached upon creation
  ([`02a2608`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02a26086c4540127a11c235cba30afc4fd712007))


## v0.58.0 (2024-06-07)

### Bug Fixes

- Bar colormap dynamic setting
  ([`67fd5e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67fd5e8581f60fe64027ac57f1f12cefa4d28343))

- Formatting isort
  ([`bf699ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf699ec1fbe2aacd31854e84fb0438c336840fcf))

- **curve**: 2d scatter updated if color_map_z is changed
  ([`6985ff0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6985ff0fcef9791b53198206ec8cbccd1d65ef99))

- **curve**: Color_map_z setting works
  ([`33f7be4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/33f7be42c512402dab3fdd9781a8234e3ec5f4ba))

### Features

- **utils.colors**: General color validators
  ([`3094632`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/30946321348abc349fb4003dc39d0232dc19606c))

### Testing

- **color**: Validation tests added
  ([`c0ddece`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c0ddeceeeabacbf33019a8f24b18821926dc17ac))


## v0.57.7 (2024-06-07)

### Bug Fixes

- Add model_config to pydantic models to allow runtime checks after creation
  ([`ca5e8d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca5e8d2fbbffbf221cc5472710fef81a33ee29d6))

### Documentation

- Added schema of BECDockArea and BECFigure
  ([`828067f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/828067f486a905eb4678538df58e2bdd6c770de1))


## v0.57.6 (2024-06-06)

### Bug Fixes

- **bar**: Docstrings extended
  ([`edb1775`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/edb1775967c3ff0723d0edad2b764f1ffc832b7c))


## v0.57.5 (2024-06-06)

### Bug Fixes

- **plot_base**: .plot removed from plot_base.py, because there is no use case for it
  ([`82e2c89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/82e2c898d2e26f786b2d481f85c647472675e75b))

- **waveform**: Added .plot method with the same signature as BECFigure.plot
  ([`8479caf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8479caf53a7325788ca264e5bd9aee01f1d4c5a0))

### Documentation

- **figure**: Docs adjusted to be compatible with new signature
  ([`c037b87`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c037b87675af91b26e8c7c60e76622d4ed4cf5d5))

### Refactoring

- **figure**: Logic for .add_image and .image consolidated; logic for .add_plot and .plot
  consolidated
  ([`52bc322`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52bc322b2b8d3ef92ff3480e61bddaf32464f976))


## v0.57.4 (2024-06-06)

### Bug Fixes

- **docks**: Docks widget_list adn dockarea panels return values fixed
  ([`ffae5ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ffae5ee54e6b43da660131092452adff195ba4fb))

- **docks**: Set_title do update dock internal _name now
  ([`15cbc21`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/15cbc21e5bb3cf85f5822d44a2b3665b5aa2f346))


## v0.57.3 (2024-06-06)

### Bug Fixes

- **ring**: Automatic updates are disabled uf user specify updates manually with .set_update;
  'scan_progres' do not reset number of rings
  ([`e883dba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e883dbad814dbcc0a19c341041c6d836e58a5918))

- **ring**: Enable_auto_updates(true) do not reset properties of already setup bars
  ([`a2abad3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a2abad344f4c0039516eb60a825afb6822c5b19a))

- **ring**: Set_min_max accepts floats
  ([`d44b1cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d44b1cf8b107cf02deedd9154b77d01c7f9ed05d))

- **ring**: Set_update changed to Literals, no need to specify endpoint manually
  ([`c5b6499`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5b6499e41eb1495bf260436ca3e1b036182c360))

### Documentation

- Added auto update; closes #206
  ([`32da803`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32da803df9f7259842c43e85ba9a0ce29a266d06))

- Cleanup
  ([`07d60cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/07d60cf7355d2edadb3c5ef8b86607d74b360455))

- Fixed syntax of add_widget
  ([`a951ebf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a951ebf1be6c086d094aa8abef5e0dfd1b3b8558))

- **bar**: Docs updated
  ([`4be0d14`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be0d14b7445c2322c2aef86257db168a841265c))


## v0.57.2 (2024-06-06)

### Bug Fixes

- Accept scalars or numpy arrays of 1 element
  ([`2a88e17`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a88e17b23436c55d25b7d3449e4af3a7689661c))

- Rpc_server_dock fixture now spawns the server process
  ([`cd9fc46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cd9fc46ff8a947242c8c28adcd73d7de60b11c44))

- **test/e2e**: Autoupdate e2e rewritten
  ([`e1af5ca`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e1af5ca60f0616835f9f41d84412f29dc298c644))

- **test/e2e**: Dockarea and dock e2e tests changed to check asserts against config_dict
  ([`5c6ba65`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c6ba65469863ea1e6fc5abdc742650e20eba9b9))

- **test/e2e**: Spiral_progress_bar e2e tests rewritten to use config_dict
  ([`7fb31fc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7fb31fc4d762ff4ca839971b3092a084186f81b8))

### Refactoring

- Move _get_output and _start_plot_process at the module level
  ([`69f4371`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/69f4371007c66aee6b7521a6803054025adf8c92))


## v0.57.1 (2024-06-06)

### Bug Fixes

- Tests references to add_widget_bec refactored
  ([`f51b25f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f51b25f0af4ab8b0a75ee48a40bfbb079c16e9d1))

- **dock**: Add_widget and add_widget_bec consolidated
  ([`8ae323f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ae323f5c3c0d9d0f202d31d5e8374a272a26be2))

### Documentation

- Docs refactored from add_widget_bec to add_widget
  ([`c3f4845`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c3f4845b4f95005ff737fed5542600b0b9a9cc2b))


## v0.57.0 (2024-06-05)

### Documentation

- Extend user documentation for BEC Widgets
  ([`4160f3d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4160f3d6d7ec1122785b5e3fdfc4afe67a95e9a1))

### Features

- **widgets/console**: Becjupyterconsole added
  ([`8c03034`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c03034acf6b3ed1e346ebf1b785d41068513cc5))


## v0.56.3 (2024-06-05)

### Bug Fixes

- Fixed support for auto updates
  ([`131f49d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/131f49da8ea65af4d44b50e81c1acfc29cd92093))

### Continuous Integration

- Increased verbosity for e2e tests
  ([`4af1abe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4af1abe4e15b62d2f7e70bf987a1a7d8694ef4d5))


## v0.56.2 (2024-06-05)

### Bug Fixes

- **bar**: Ring saves current value in config
  ([`9648e3e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9648e3ea96a4109be6be694d855151ed6d3ad661))

- **dock**: Dock saves configs of all children widgets
  ([`4be756a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4be756a8676421c3a3451458995232407295df84))

- **dock_area**: Save/restore state is saved in config
  ([`46face0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/46face0ee59122f04cb383da685a6658beeeb389))

- **figure**: Added correct types of configs to subplot widgets
  ([`6f3b1ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f3b1ea985c18929b9bab54239eeb600f03b274a))

### Documentation

- Restructured docs layout
  ([`3c9181d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c9181d93d68faa4efb3b91c486ca9ca935975a0))


## v0.56.1 (2024-06-04)

### Bug Fixes

- **spiral_progress_bar**: Endpoint is always stored as a string in the RingConnection Config
  ([`d253991`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2539918b296559e1d684344e179775a2423daa9))

- **spiral_progress_bar/rings**: Config min/max values added check for floats
  ([`9d615c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d615c915c8f7cc2ea8f1dc17993b98fe462c682))


## v0.56.0 (2024-05-29)

### Bug Fixes

- Compatibility adjustment to .ui loading and tests for PySide6
  ([`07b99d9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/07b99d91a57a645cddd76294f48d78773e4c9ea5))

- **examples**: Outdated examples removed (mca_plot.py, stream_plot.py, motor_example.py)
  ([`ddc9510`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ddc9510c2ba8dadf291809eeb5b135a105259492))

### Build System

- Added pyside6 as dependency
  ([`db301b1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db301b1be27bba76c8bb21fbff93cb4902b592a5))

### Continuous Integration

- Added tests for pyside6, pyqt6 and pyqt5, default test and e2e is python 3.11 and pyqt6
  ([`855be35`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/855be3551a1372bcbebba6f8930903f99202bbca))

### Documentation

- **examples**: Example apps section deleted
  ([`ad208a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad208a5ef8495c45a8b83a4850ba9a1041b42717))

### Features

- **utils/ui_loader**: Universal ui loader for pyside/pyqt
  ([`0fea8d6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fea8d606574fa99dda3b117da5d5209c251f694))


## v0.55.0 (2024-05-24)

### Features

- **widgets/progressbar**: Spiralprogressbar added with rpc interface
  ([`76bd0d3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/76bd0d339ac9ae9e8a3baa0d0d4e951ec1d09670))


## v0.54.0 (2024-05-24)

### Build System

- Added pyqt6 as sphinx build dependency
  ([`a47a8ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a47a8ec413934cf7fce8d5b7a5913371d4b3b4a5))

### Features

- **figure**: Changes to support direct plot functionality
  ([`fc4d0f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc4d0f3bb2a7c2fca9c326d86eb68b305bcd548b))

### Refactoring

- **clean-up**: 1st generation widgets are removed
  ([`edc25fb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/edc25fbf9d5a0321e5f0a80b492b6337df807849))

- **reconstruction**: Repository structure is changed to separate assets needed for each widget
  ([`3455c60`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3455c602361d3b5cc3ff9190f9d2870474becf8a))


## v0.53.3 (2024-05-16)

### Bug Fixes

- Removed apparently unnecessary sleep while waiting for an rpc response
  ([`7d64cac`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d64cac6610b39d3553ff650354f78ead8ee6b55))


## v0.53.2 (2024-05-15)

### Bug Fixes

- Adapt to bec_lib changes (no more submodules in `__init__.py`)
  ([`5d09a13`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d09a13d8820a8bdb900733c97593b723a2fce1d))

- Check device class without importing to speed up initial import time
  ([`9f8fbdd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9f8fbdd5fc13cf2be10eacb41e10cf742864cd92))

- Speed up initial import times using lazy import (from bec_lib)
  ([`d1e6cd3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d1e6cd388c6c9f345f52d6096d8a75a1fa7e6934))

### Continuous Integration

- Added echo to highlight the current branch
  ([`0490e80`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0490e80c48563e4fb486bce903b3ce1f08863e83))


## v0.53.1 (2024-05-09)

### Bug Fixes

- Docs config
  ([`0f6a5e5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f6a5e5fa9530969c98a9266c9ca7b89a378ff70))

### Continuous Integration

- Fixed rtd pages url
  ([`8ff3610`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ff36105d1e637c429915b4bfc2852d54a3c6f19))


## v0.53.0 (2024-05-09)

### Bug Fixes

- Fixed semver job and upgraded to v9
  ([`32e1a9d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32e1a9d8472eb1c25d30697d407a8ffecd04e75d))

### Continuous Integration

- Use formatter config of toml file
  ([`5cc816d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5cc816d0af73e20c648e044a027c589704ab1625))

### Documentation

- Update install instructions
  ([`57ee735`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57ee735e5c2436d45a285507cdc939daa20e8e8f))

### Features

- Moved to pyproject.toml; closes #162
  ([`c86ce30`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c86ce302a964d71ee631f0817609ab5aa0e3ab0f))

### Refactoring

- Applied formatter
  ([`4117fd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4117fd7b5b2090ff4fb7ad9e0d92cc87cd13ed5f))


## v0.52.1 (2024-05-08)

### Bug Fixes

- **docstrings**: Docstrings formating fixed for sphinx to properly format readdocs
  ([`7f2f7cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7f2f7cd07a14876617cd83cedde8c281fdc52c3a))


## v0.52.0 (2024-05-07)

### Bug Fixes

- **widgets/dock**: Becdockarea close overwrites the default pyqtgraph Container close + minor
  improvements
  ([`ceae979`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ceae979f375ecc33c5c97148f197655c1ca57b6c))

### Continuous Integration

- Fixed support for child pipelines
  ([`e65c7f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e65c7f3be895ada407bd358edf67d569d2cab08e))

### Features

- **utils/layout_manager**: Added GridLayoutManager to extend functionalities of native QGridLayout
  ([`fcd6ef0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fcd6ef0975dc872f69c9d6fb2b8a1ad04a423aae))

- **widget/dock**: Becdock and BECDock area for dockable windows
  ([`d8ff8af`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8ff8afcd474660a6069bbdab05f10a65f221727))

### Refactoring

- **widget/plots**: Widgetconfig changed to SubplotConfig
  ([`03fa1f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/03fa1f26d0fa6b58ed05556fb2438d1e62f6c107))


## v0.51.0 (2024-05-07)

### Build System

- **cli**: Changed repo name to bec_widgets
  ([`799ea55`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/799ea554de9a7f3720d100be4886a63f02c6a390))

- **setup**: Fakeredis added to dev env
  ([`df32350`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df323504fea024a97304d96c2e39e61450714069))

- **setup**: Pyqt6 version is set to 6.7
  ([`0ab8aa3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ab8aa3a2fe51b5c38b25fca44c1c422bb42478d))

### Continuous Integration

- Added rule for parent-child pipelines
  ([`e085125`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e0851250eecb85503db929d37f75d2ba366308a6))

### Features

- **utils**: Added plugin helper to find and load
  ([`5ece269`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ece269adb0e9b0c2a468f1dfbaa6212e86d3561))


## v0.50.2 (2024-04-30)

### Bug Fixes

- 'disconnect_slot' has to be symmetric with 'connect_slot' regarding QtThreadSafeCallback
  ([`0dfcaa4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0dfcaa4b708948af0a40ec7cf34d03ff1e96ffac))


## v0.50.1 (2024-04-29)

### Bug Fixes

- **cli**: Becfigure takes the port to connect to redis from the current BECClient, supporting
  plugins
  ([`57cb136`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57cb136a098e87a452414bf44e627edb562f6799))


## v0.50.0 (2024-04-29)

### Bug Fixes

- **plots**: Cleanup policy reviewed for children items
  ([`8f20a0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8f20a0b3b1b5dd117b36b45645717190b9ee9cbf))

- **rpc/client_utils**: Getoutput more transparent + error handling
  ([`6b6a6b2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b6a6b2249f24d3d02bd5fcd7ef1c63ed794c304))

- **rpc_register**: Thread lock for listign all connections
  ([`2ca3267`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2ca32675ec3f00137e2140259db51f6e5aa7bb71))

- **widgets/figure**: Access pattern changed for getting widgets by coordinates for rpc
  ([`13c018a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/13c018a79704a7497c140df57179d294e43ecffa))

### Features

- **plots**: Universal cleanup and remove also for children items
  ([`381d713`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/381d713837bb9217c58ba1d8b89691aa35c9f5ec))

- **rpc/rpc_register**: Singleton rpc register for all rpc connections for session
  ([`a898e7e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a898e7e4f14e9ae854703dddbd1eb8c50cb640ff))

### Testing

- **cli/rpc_register**: E2e RPCRegister
  ([`4f261be`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f261be4c7cfe54501443d031f9266f4f838f6e2))

- **cli/rpc_register**: Rpc_register tests added
  ([`40eb75f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/40eb75f85a4d99d498b086a37e799276a9d2ac3f))


## v0.49.1 (2024-04-26)

### Bug Fixes

- **widgets/editor**: Qscintilla editor removed
  ([`ab85374`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ab8537483da6c87cb9a0b0f01706208c964f292d))

### Build System

- **pyqt6**: Fixing PyQt6-Qt6 package to 6.6.3
  ([`a222298`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a22229849cbb57c15e4c1bae02d7e52e672f8c4c))


## v0.49.0 (2024-04-24)

### Bug Fixes

- **rpc/client_utils**: Close clean up policy for BECFigure
  ([`9602085`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9602085f82cbc983f89b5bfe48bf35f08438fa87))

### Features

- **rpc/client_utils**: Timeout for rpc response
  ([`6500a00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6500a00682a2a7ca535a138bd9496ed8470856a8))


## v0.48.0 (2024-04-24)

### Features

- **cli**: Added auto updates plugin support
  ([`6238693`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6238693ffb44b47a56b969bc4129f2af7a2c04fe))


## v0.47.0 (2024-04-23)

### Features

- **utils/thread_checker**: Util class to check the thread leakage for closeEvent in qt
  ([`71cb80d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/71cb80d544c5f4ef499379a431ce0c17907c7ce8))

### Refactoring

- **utils/container_utils**: Part of the logic regarding locating widgets moved from BECFigure to
  utility class
  ([`77ff796`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/77ff7962cc91bce15d1c91b67b75b66fbea612c3))


## v0.46.7 (2024-04-21)

### Bug Fixes

- **plot/image**: Monitors are now validated with current bec session
  ([`67a99a1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67a99a1a19c261f9a1f09635f274cd9fbfe53639))


## v0.46.6 (2024-04-19)

### Bug Fixes

- **cli**: Fixed support for devices as cli input
  ([`1111610`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1111610f3206c5c46db6b4bd1e8827f1a4cd9e3f))

### Continuous Integration

- Changed ophyd default branch to main
  ([`81484e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/81484e8160a4a09907313ed747c27ab3b6cbfdc4))


## v0.46.5 (2024-04-19)

### Bug Fixes

- **plots/waveform**: Colormap is correctly passed from BECFigure
  ([`026c079`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/026c0792bee25723013fffe57ccff10d9b652913))

- **widgets/figure**: Individual cleanup disabled, making stuck rpc
  ([`ff52100`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff52100e234debdfb5ccc0869352cfafde52ac93))

### Refactoring

- **examples/jupyter_console_window**: Jupyter console debugging window moved to examples
  ([`b632ed1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b632ed10956c7feeaa03e04fe5b755965e64da9f))

- **rpc/client_utils**: Update script for grid_scan adds z axis device
  ([`2955b5e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2955b5ec024dbdeb5a792ba5c7b5519c003959c0))

### Testing

- **rpc/bec_figure**: Test_rpc_plotting_shortcuts_init_configs extended by testing scatter z
  gradient for BECWaveform through RPC
  ([`a156803`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a1568033899bbcdbd457e697d6c8d478df26ba54))


## v0.46.4 (2024-04-16)

### Bug Fixes

- Renaming of bec_client to bec_ipython_client
  ([`4da625e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4da625e4398bdd937c2b788592f15f7530148292))

- **plots/image**: User can get data as np.ndarray from BECImageItem
  ([`c2c583f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c2c583fce6f28981990c504dd065705124e40e44))

- **plots/motor_map**: User can get data as dict from BECMotorMap
  ([`c12f2ce`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c12f2cee80b13137a2b70e2d121a079e20d124e2))

- **rpc/server**: Server can accept client or dispatcher
  ([`ecdf0f1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ecdf0f122b628ee378b80793d498cedafe50fbf8))

### Continuous Integration

- "master" renamed to "main" in semver and pages section
  ([`05e268d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/05e268d4663c58720caf5bf9d3ff310132e9cc32))

- Added workflow .gitlab-ci.yml
  ([`42a9a0c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/42a9a0ca158bbadd6ebe01b88a62cdca47d6f4e8))

- Changed default BEC branch to main
  ([`bd3b1ba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bd3b1ba0439cd88eb0533d14e645837e84d2e5ed))

- Ci_merge_request_target_branch_name changed to main
  ([`b6feb9a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b6feb9adb3f4abbf780af8d82d6e3526fb473d32))

- Fixed multi-project pipeline
  ([`22fb5a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/22fb5a5656618c388d20e9c31f34127f733ca12d))

- Merge AdditionalTests with test stage
  ([`2e3f46e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2e3f46ea363f8fbd0adc74d32b38ade2a5dcf7c1))

- Pull images via gitlab dependency proxy
  ([`df5234a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df5234aa52066888f03701d14ac2a67855467a20))

- Set branch name for semver
  ([`4bcae0f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4bcae0f92110ac7f6588af35c2669064b9faccf6))

- **tests**: Unit tests ci path corrected
  ([`66c0649`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/66c0649d7ee1ad5219615efba91cc39c93481ce1))

### Refactoring

- **isort**: Isort applied
  ([`5600624`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5600624c57fc78edbfea45a1c2929909d1044277))

- **plots/image**: All rpc widgets can access `config_dict` as property
  ([`be9847e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/be9847e9d222b12ca4398cae590b4c3456b9e709))

- **plots/image**: Images are accessed as property .images -> returns list[BECImage]
  ([`2f7317b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2f7317b3288027baeca55e27d5b6cdda485c285a))

### Testing

- Unit tests moved to separate folder; scope of autouse bec_dispatcher fixture reduced only for unit
  tests; ci adjusted
  ([`2446c40`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2446c401d9ec3fff770ec9ba40b604210a5ea0c0))

- **e2e/rpc**: Rpc e2e tests extended
  ([`1bc18a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1bc18a201c27277365815f8c654c747d344c50f7))

- **end-2-end**: Rpc end-2-end tests
  ([`4d0df36`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4d0df364d3a6f5738889279c441be09f076a0576))


## v0.46.3 (2024-04-11)

### Bug Fixes

- Producer->connector
  ([`9def373`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9def3734afb361ac2d5cc933661766cdc440e09d))

- **cli/client_utils**: Print_log is buffered; add output processing thread
  ([`285bf01`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/285bf0164b6deb91678f03ab2a190680b6d83a02))

- **plots/motor_map**: Removed single callback flag for connecting device_readback motors
  ([`49327a8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/49327a8dbde270c67bc0ce7c757fd4a3eae118b4))

- **test_fake_redis**: Testmessage fixed to pydantic BaseModel
  ([`0b86a00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b86a0009d9366b710294a3ab55cb9f4894472c0))

### Refactoring

- **bec_dispatcher**: New BEC dispatcher - rebased
  ([`90907e0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90907e0a9cf9525705a56cccf0628319dbfd506f))

### Testing

- **utils/bec_dispatcher**: Tests fixed
  ([`301bb91`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/301bb916da9716f5d2d515279b5765d3b3722112))


## v0.46.2 (2024-04-10)

### Bug Fixes

- **widget/plots**: Added "get_config" to all children of `BECConnector` to USER_ACCESS
  ([`ee617b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ee617b73a2fcad8194394182fcecb0dd4f583a8e))

### Refactoring

- **utils/bec_dispatcher**: New singleton definition
  ([`92cea90`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/92cea90971169cca9850bc661ec9574be4a8dee7))


## v0.46.1 (2024-04-10)

### Bug Fixes

- **rpc/client**: Correct name for RPC class BECWaveform (instead of BECWaveform1D)
  ([`cf29035`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf29035e283e55efa547cbac88e8b622190dfc4d))


## v0.46.0 (2024-04-09)

### Features

- **plot/waveform1d**: Becwaveform1d can show z data of scatter coded to different detector like
  BECMonitor2DScatter; BECWaveform1D name changed to BECWaveform
  ([`3d399ba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3d399ba1f5d85bc67964febcf8921355f9f1c285))

### Refactoring

- **widget/monitor_scatter_2D**: Deleted
  ([`fe101f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fe101f93287a2d47aace7d0f6fe242e1662d9e7f))

### Testing

- Fixed default value for scan id
  ([`6dc1000`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6dc1000de5da0105c581b97802feddc89e9c8db2))

- **plot/figure**: Test extended to check shortcuts for creating subplots
  ([`754d81e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/754d81edf372aa0988ec1e00a7d8a985419cd5cf))


## v0.45.0 (2024-03-26)

### Documentation

- Added api reference; closes #123
  ([`88014d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88014d24c1c272a6deea7436a6fa058bdb06fb57))

### Features

- **plots/bec_figure**: Motor Map integrated to BECFigure
  ([`b8519e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8519e8770f8ffc46a1255c18119fc7978ff1d39))

- **plots/bec_motor_map**: Becmotormap build on BECPlotBase
  ([`0f69c34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0f69c346cd24b7afcd23f444525a170e062b0368))

### Testing

- Mock_client unified for all tests
  ([`ea4d743`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ea4d743a250b1889f8b9241903dfec851e02f0c5))

- **plot/motor_map**: Tests extended
  ([`6e0e69b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6e0e69b9f7eed7911a7f46aea3957079473c1559))


## v0.44.5 (2024-03-25)

### Bug Fixes

- Circular imports
  ([`c5826f8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5826f8887ed44d15d05c8ed0e337080b3146c5a))

### Refactoring

- Isort import formatting
  ([`62f0b15`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/62f0b1519385189f1b47022754cc65588a744cf9))

- Renamed scanID to scan_id
  ([`d846266`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d84626633231863b25cc3c57a827f6d6fd78e284))


## v0.44.4 (2024-03-22)

### Bug Fixes

- **cli/server**: Removed BECFigure.start(), the QApplication event loop is started by server.py
  ([`f3a96de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f3a96dedd7ba49f9a1b713f6a5565f2b3dbb141e))

- **cli/server**: Thread heartbeat replaced with QTimer
  ([`e6b0657`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6b065767c8605aaef6ed6032ba893d3900b552c))


## v0.44.3 (2024-03-21)

### Bug Fixes

- **cli**: Added gui heartbeat
  ([`882cf55`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/882cf55fc5266a2cfb610702e834badff3ad0428))

- **cli**: Don't call user script if gui is not alive
  ([`a92aead`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a92aead7698fa98d6f7f582d030845d0b940ea2d))


## v0.44.2 (2024-03-20)

### Bug Fixes

- **utils/bec_dispatcher**: Bec_dispatcher adjusted to the new BECClient; dropped support to inject
  bec_config.yaml, instead BECClient can be passed as arg
  ([`86416d5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/86416d50cb850b42d312fe17fc46f0b4743dc940))

- **utils/bec_dispatcher**: Try/except to start client, to avoid crash when redis is not running
  ([`9ccd4ea`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ccd4ea235be4c4332045b7a7f09d6cc6291f7ff))

### Continuous Integration

- Now testing against master branches of bec_lib and ophyd_devices
  ([`1d5442a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1d5442ac083a494b76b5e3241c49c763af64e04e))


## v0.44.1 (2024-03-19)

### Bug Fixes

- **examples/motor_compilation**: Motor_control_compilations.py do not have any hardcoded config
  anymore
  ([`14f901f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/14f901f1bea2ba7b79903c4743e37384e11533d3))


## v0.44.0 (2024-03-18)

### Bug Fixes

- **cli**: Fixed cleanup procedure
  ([`2d39c5e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d39c5e4d18bbb66a5f3340fce7f8944dd4ba19f))

- **cli**: Removed hard-coded signal
  ([`203ae09`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/203ae0960688608fb609a742a23e5994bfe9805c))

### Features

- **cli**: Added update script to BECFigure
  ([`9049e0d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9049e0d27fe9a3860e21ffc3b350eb69e567b71c))


## v0.43.2 (2024-03-18)

### Bug Fixes

- **cli/server**: Added QApplications to enter separate QT event loop ensuring that QT objects are
  not deleted
  ([`d0f9bf1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d0f9bf17339296a60301e5e6ffe602db369c6c7c))


## v0.43.1 (2024-03-15)

### Bug Fixes

- **plots/image**: Same access pattern for image and image_item for setting up parameters, autorange
  of z scale disabled by default
  ([`b8d4e69`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8d4e697ac2a5929a1374ce1778046efc3f8187a))

- **widget/various**: Corrected USER_ACCESS methods for children widgets to include inherited
  methods to RPC
  ([`4664661`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4664661cfb4e8bd4a6adb71f2050b25d0b4f3d36))

- **widgets/figure**: Added widgets can be accessed as a list (fig.axes) or as a dictionary
  (fig.widgets)
  ([`fcf918c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fcf918c48862d069b9fe69cbba7dbecbe7429790))

### Refactoring

- **cli**: Commented debug CLI messages
  ([`32747ba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32747baa276f23ff842815f8ee2840020c18408d))

- **widget/figure**: Changed add_plot and add_image to specify what should be content of the widget,
  instead of widget id
  ([`d99fd76`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d99fd76c0bb86c7311b3acb2be26e430479d76c9))


## v0.43.0 (2024-03-14)

### Bug Fixes

- **cli**: Find_widget_by_id for BECImageShow changed to be compatible with RPC logic
  ([`4ef6ae9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4ef6ae90f2afd5e2442465c11ce5165517cd4218))

- **cli**: Fix cli connector.send to set_and_publish for gui_instruction_response
  ([`4076698`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/407669853097b40e6fba7d43da001f083140ad74))

- **plots/image**: Access pattern for ImageItems in BECImageShow
  ([`3362fab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3362fabed7ccd611b35f524c1970aeefbf3a9faf))

- **plots/waveform1d**: Curves_data access disabled
  ([`598479b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/598479bb555a6cd077d5a137052d91314e5af6b7))

### Features

- **plots/image**: Basic image visualisation, getting data are based on stream_connector
  (deprecated)
  ([`9ad0055`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ad0055336dba50886504a616db6f9f63b23beb3))

- **plots/image**: Change stream processor to QThread with connector.get_last; cleanup method for
  BECFigure to kill all threads if App is closed during acquisition
  ([`7ffedd9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ffedd9cebb382fc22f24a6b0b46823db6378d89))

- **plots/image**: Image processor can run in threaded or non-threaded version
  ([`4865b10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4865b10ced6b321974e7b4b4db12786fe21fd916))

### Refactoring

- **plots/image**: Image logic moved to BECImageItem, image updated from bec_dispatcher with
  register_stream fetching data from dispatcher
  ([`a21bfec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a21bfec3d9611d6f82a84e23d0d85f1616a2583f))

- **plots/plot_base**: Becplotbase inherits from pg.GraphicalLayout instead of pg.PlotItem, this
  will allow us to add multiple plots into each coordinate of BECFigure.
  ([`70c4e9b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/70c4e9bc5ebba2445480a56d2bf6721840cfd170))


## v0.42.1 (2024-03-10)

### Bug Fixes

- **various**: Repo cleanup, removed - [plot_app, one_plot, scan_plot, scan2d_plot,
  crosshair_example, qtplugins], tests adjusted
  ([`f3b3c2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f3b3c2f526d66687b3cc596a5877921953dd0803))


## v0.42.0 (2024-03-07)

### Features

- **utils/bec_dispatcher**: Becdispatcher can register redis stream
  ([`4c0a7bb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4c0a7bbec7abafc7d04a8aaf10dabd7e668fa908))


## v0.41.4 (2024-03-07)

### Bug Fixes

- **utils/bec_dispatcher**: Becdispatcher can accept new EndpointInfo dataclass.
  ([`c319dac`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c319dacb24e64930af258a81484feeadcb1bc341))

### Continuous Integration

- Drop python/3.9
  ([`8147685`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/814768525fda523718a7d54ff3c22085004191af))


## v0.41.3 (2024-03-01)

### Bug Fixes

- **cli/generate_cli**: Added automatic black formatting; added black as a dependency
  ([`d89f596`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d89f596a5d0f0674b1ef3268a9cfee5e32b64ba5))

- **cli/generate_cli**: Typing.get_overloads are only used if the python version is higher than 3.11
  ([`f386563`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f386563aa162eaca9202af16574860bf3eb5a092))

### Testing

- **cli/generate_cli**: Import from future
  ([`110506c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/110506c9a977e6c1b3692d6b0056e0069fd94097))

- **cli/generate_cli**: Test added
  ([`7e0058a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7e0058a6117941f56c0de359703e673fe3572095))


## v0.41.2 (2024-02-28)

### Bug Fixes

- **utils/bec_dispatcher**: Msg is unp[acked from dict before accessing .content
  ([`bb1f066`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bb1f066c3c5e5076a8906e309030cfb47a6cad12))


## v0.41.1 (2024-02-26)

### Bug Fixes

- **bec_dispatcher**: Adapt code to redis connector refactoring
  ([`8127fc2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8127fc2960bebd3e862dbe55ac9401af4a6dccb6))

- **bec_dispatcher**: Handle redis connection errors more gracefully
  ([`a2ed2eb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a2ed2ebe00c623eb183b03f8182ffd672fbf9e1e))


## v0.41.0 (2024-02-26)

### Bug Fixes

- After removing plot from BECFigure, the coordinates are correctly resigned
  ([`d678a85`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d678a85957c13c1fda2b52692c0d3b9b7ff40834))

- Removed DI references, fixed set when adding plot by fig
  ([`7c15d75`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7c15d750117aec9e75111853074630a44dca87ae))

- **cli**: Fixed property access, rebased
  ([`f71dc5c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f71dc5c5abdd6b8b585cb9b502b11ef513d7813e))

- **cli**: Fixed rpc construction of nested widgets
  ([`da640e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/da640e888d575b536fdd5d7adbf1df3eda802219))

- **cli/client_utils**: "__rpc__" pop from msg_results
  ([`ebb36f6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ebb36f62ddc1c5013435f9e7727648b977b6b732))

- **cli/rpc**: Rpc client can return any type of object + config dict of the widgets
  ([`fd711b4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fd711b475f268fbdb59739da0a428f0355b25bac))

- **cli/rpc**: Server access children widget.find_widget_by_id(gui_id)
  ([`57132a4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57132a472165c55bf99e1994d09f5fe3586c24da))

- **plots/waveform1d**: Pandas import clean up, export curves with none skipped
  ([`35cd4fd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/35cd4fd6f176ba670fad5d9fec44b305094280d6))

- **rpc**: Added annotations to pass py3.9 tests
  ([`c6bdf0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c6bdf0b6a5b12c054863b101a3944efc366686cb))

- **rpc**: Connection to on_rpc_update done through bec_dispatcher
  ([`1c2fb8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1c2fb8b972d4cb28cead11989461aea010c4571d))

- **rpc_server**: Fixed gui_id lookup
  ([`4630d78`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4630d78fc28109da7daf53e49dd3cdb9b8084941))

- **tests**: Becdispatcher fixture putted back
  ([`644f103`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/644f1031f6ff27064111565b0882cb8b2544aa2f))

- **widget/figure**: Add cleanup method to disconnect all slots before removing Waveform1D from
  layout
  ([`a28b9c8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a28b9c8981d1058e4dc4146463f16c53413e8db9))

- **widgets/plots**: Added placeholder for cleanup method to BECPlotBase
  ([`24c7737`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/24c77376b232c3846a1d6be360ec46acc077b48d))

### Features

- Added @user_access from bec_lib.utils
  ([`b827e9e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b827e9eaa77f8b64433bb7a54e40ab5ccd86f4b6))

- Becconnector -> mixin class for all BEC Widget to hook them to BEC client
  ([`91447a2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91447a2d6234de1e8f2bac792e822bfda556abba))

- Becfigure and BECPlotBase created
  ([`9ef331c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9ef331c272b88f725de9b8497fdf906056c0738b))

- Curve can be modified after adding to the plot
  ([`684592a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/684592ae37e9dd5328a96018c78ca242e10395b2))

- Figure.py create widget factory
  ([`c781b1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c781b1b4e4121c4ec6fc8871a4cdf6f494913138))

- Plot can be removed from BECFigure
  ([`60d150a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60d150a41193aa7659285cf3612965f1a3c57244))

- Rpc decorator to add methods to USER_ACCESS
  ([`b676877`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b6768772424a3ad5ee7e271de19131f8065eef09))

- Start method for BECFigure, jupyter console .ui added to git
  ([`1d26b23`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1d26b2322147d9ea5a6a245e1648c00986f80881))

- Waveform1d.py curves can be removed by identifier by order(int) or by curve_id(str)
  ([`f0ed243`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0ed243c9197b7d1aab0d99a15e9ba175708ec90))

- Waveform1d.py curves can be stylised; access scan history by index or scanID
  ([`cba3863`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cba3863e5a9ac1187ea643be67db6cfc36b44ee2))

- Waveform1d.py draft
  ([`565e475`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/565e475ace72ccc103d71ea98af1dcaf04f37861))

- **cli**: Added cli interface, rebased
  ([`a61bf36`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a61bf36df5d54ad44f78479c2474c4e38e68ed26))

- **utils/entry_validator**: Possibility to validate add_scan_curve with current BEC session
  ([`1db77b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1db77b969bcf9b38716ae3d38bf4695b2b8c1f37))

- **widgets/figure**: Clear_all method for BECFigure
  ([`0363fd5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0363fd5194320a7ea868ef883f8022ea464d0298))

- **widgets/figure.py**: Dark/light theme changer
  ([`08534a4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/08534a4739ec8e85d82a00ab639411dd0198e9d8))

- **widgets/waveform1d**: Data can be exported from rendered curve
  ([`5fc8047`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5fc8047c8ff971cdc2807d02743eae56d288f4d7))

- **widgets/Waveform1D**: Waveform1d can be fully constructed by config
  ([`9a5c86e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9a5c86ea35178b9cab270fc35e668dd22f3ec8da))

### Refactoring

- Becconnector changed config structure
  ([`4a1792c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a1792c20977271b74eed6fba1cd67807c178fbf))

- Becfigure, BECPlotBase changed back to pyqtgraph classes inheritance
  ([`7768e59`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7768e594b529e16c1b69332470747279cd42cc85))

- **plot/Waveform1D,plot/BECCurve**: Beccurve inherits from BECConnector and can refer to parent_id
  (Waveform1D) and has its own gui_id
  ([`99dce07`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/99dce077c4ecd5dead2575b247691020a9112cfd))

- **rpc/client**: Changed path to client.py to relative one
  ([`402adc4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/402adc44e86f0e456b6ae673231431a53884408d))

- **widgets/BECCurve**: Set kwargs for curve style while adding curve
  ([`5964778`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5964778a649cdc6dee70922bf118565cc2341290))

### Testing

- **plots/waveform1d**: Tests added
  ([`f06e652`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f06e652b82d3cdcb03da462172d08a123d180c78))

- **test_bec_figure**: Tests for BECFigure added
  ([`f668eb8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f668eb8b9b2df1cf46e50f3720baa08a53a7b19d))

- **test_plot_base**: Becplotbase tests added
  ([`826a5e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/826a5e9874c3d87649dc384fc5498aba648a6637))

- **tests/client_mocks**: Added general mock_client with container for fake devices for testing
  ([`4051902`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4051902f09566a3eee5b2c812cbaaae38f113905))

- **tests/test_bec_connector**: Test_bec_connector.py added
  ([`8135f68`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8135f6823013f18d3ee072074e3e3f1c0af58b93))


## v0.40.1 (2024-02-23)

### Bug Fixes

- **utils/bec_dispatcher**: _do_disconnect_slot will shutdown consumer of slots/signals which were
  already disconnected
  ([`feca7a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/feca7a3dcde6d0befa415db64fc8f9bbf0c06e52))


## v0.40.0 (2024-02-16)

### Features

- **utils.colors**: Golden_angle_color utility can return colors as a list of QColor, RGB or HEC
  ([`5125909`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/51259097fa23ff861eac3f7c63624ea591bf1bd3))


## v0.39.0 (2024-02-12)

### Build System

- Added all .ui and .yaml files to pypi install; removed gauss_bpm from default config from
  monitor.py
  ([`968da6f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/968da6f55837b4e2bc52f87d5c0900933828a07d))

### Features

- Active motors from motor_map.py can be changed by slot without changing the whole config
  ([`17f1458`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/17f14581d7c4662a2f5814ea477dfae8ef6de555))

- Added full app with all motor movement related widgets into motor_control_compilations.py
  ([`fa4ca93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa4ca935bb39fdba4c6500ce9569d47400190e65))

- Comboboxes of motor selection are changed to orange if the motors are not connected yet
  ([`0b9927f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b9927fcf5f46410d05187b2e5a83f97a6ca9246))

- Control panels compilations
  ([`8361736`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/83617366796ce2926650e38a1a9cec296befd3c6))

- Motor_control.py MotorControl widgets - Absolute + Relative movement, MotorSelection, ErrorMessage
  popups
  ([`6fe08e6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6fe08e6b8206bcaaa292b7ff0e6b0d32b883f24f))

- Motor_control.py MotorCoordinateTable added basic version to store coordinates and show them in
  motor_map.py
  ([`031cb09`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/031cb094e7f8a7be4a295bea99b7ca8e095db8d7))

- Motorcoordinatetable mode_switch added for "Individual" and "Start/Stop" modes
  ([`2f96e10`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2f96e10b9deb76eedd8f6b6e201ba3b0e526a6f0))

### Refactoring

- Base class for motor_control.py widgets
  ([`8139e27`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8139e271de115819e05b7dd03ec6603d50f5482c))

- Motor_control.py clean up
  ([`b52e22d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b52e22d81f4b0e7d049cb5f834553797b07feae6))

- Motor_control_compilations.py moved to example part of repository
  ([`8afc5f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8afc5f0c0c87a61ff7a986e8aff5900f3a3f1973))

- Pylint ignore for tests
  ([`4b0542a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4b0542a513535117dd18b879f3121b4b6bf0c21e))

### Testing

- Motor_control_compilations.py and motor_control.py tests added
  ([`bf04a4e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf04a4e04ab1e3b0e2b2c0895ce052403276533c))


## v0.38.2 (2024-02-07)

### Bug Fixes

- Adapt code to BEC 1.0
  ([`b36131e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b36131eed5c3a3ea58c0fa4d083e63a3717cdf22))

### Testing

- Fixed import in test_validator_errors.py
  ([`5ebfd2a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ebfd2a3c259a64f287e18c41a07df736eca016d))


## v0.38.1 (2024-01-26)

### Bug Fixes

- Monitor.py replots last scan after changing config with new signals; config_dialog.py checks if
  the new config is valid with BEC
  ([`ab275b8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ab275b8e5f226d6c5d22a844c4c0fae0fdc66108))

### Documentation

- 2d waveform scatter plot changed to 2D scatter plot
  ([`812ffaf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/812ffaf8eafc3f8c3a6973717149e4befba2c395))

- Documentation for example apps and widgets updated
  ([`f7a4967`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f7a496723c3fd113867a712928e06636e3212e1a))

### Refactoring

- Black v24 formatting
  ([`d211b47`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d211b47f4c51f86de129b3fd488690389f8f77f0))


## v0.38.0 (2024-01-23)

### Bug Fixes

- Monitor_scatter_2d.py changed to new BECDispatcher definition
  ([`747e97e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/747e97e0c924cdedb85e9fe7d47512002b791b10))

### Features

- Becmonitor2dscatter for plotting x/y/z signal as a mesh of scatter plot
  ([`75090b8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/75090b857526fa642218986806d0daeb1dec0914))

### Refactoring

- Monitor_scatter_2d.py _init_database replaced with defaultdict
  ([`3c14327`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c143274c5a0fb9e280d7117115a1456665e057f))

### Testing

- Fix test_bec_monitor_scatter2D.py database init test change to check defaultdict
  ([`8d0083c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8d0083c4aafd72dcddd9190d5323406d10171e17))

- Test_bec_monitor_scatter2d.py added
  ([`c6fe9d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c6fe9d20268204b14bc86c2c4782a380c39c3c5f))


## v0.37.1 (2024-01-23)

### Bug Fixes

- **tests**: Ensure BEC service is shutdown after bec dispatcher test
  ([`4664568`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/46645686725a2acb7196dbd1a504c98dbf2e4b5d))

- **tests**: Ensure threads started during plot tests are properly stopped
  ([`3fb6644`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3fb6644543b4065236216b70a583641956a09a60))

### Refactoring

- **tests**: Ensure BEC dispatcher singleton object is renewed at each test
  ([`d909673`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d9096730719997ad02141af25ae9bb9ec3a0e4ee))


## v0.37.0 (2024-01-17)

### Features

- Independent motor_map widget
  ([`1a429b3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1a429b3024e76446ed530bee71ed797c20843fba))

### Refactoring

- Motor_map.py clean up
  ([`249170e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/249170ea302255922e62d8d93418b8ee3e27a27a))

- Pylint improvement
  ([`8bebc4f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8bebc4f692056aad69e4bac28c175730565e0f3f))

### Testing

- Test_motor_map.py added
  ([`1cd273c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1cd273c37542b6581b22fb0ea02c1882c53771e5))


## v0.36.2 (2024-01-17)

### Bug Fixes

- Bec_dispatcher.py can connect multiple topics to one callback slot
  ([`e51be04`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e51be04b95f1a9549a4a3b00d76944aa58b0526a))

- Bec_dispatcher.py can partially disconnect topics from slot
  ([`7607d7a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7607d7a3b64b3861f4833c9b8f5afc360f31b38d))


## v0.36.1 (2024-01-15)

### Bug Fixes

- Motor_example.py fix to the new .read() structure from bec_lib
  ([`f9c5c82`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f9c5c82381907a19582bf9132740fe27b48d48cc))

### Refactoring

- Motor_example.py get coordinates by .readback.get() method
  ([`bf819bc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf819bcf4845c3e7e9f3c3e288a2fb21d20617e1))

- Using motor.readback.read() to access motor coordinates
  ([`6f26e5c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6f26e5cc3dd0300a5275734d0209a51ef71c4d4f))


## v0.36.0 (2024-01-12)

### Features

- Bec_dispatcher can link multiple endpoints topics for one qt slot
  ([`58721be`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/58721bea1a2b4b06220ef0e3b2dcec8c1656213d))


## v0.35.0 (2024-01-12)

### Bug Fixes

- Monitor.py change import of ConfigDialog from relative to absolute in order to make BECPlotter be
  able to open it
  ([`6061b31`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6061b3150e990141eafb8d5b17c7e931c7bf8631))

- Monitor.py clear command from BECPlotter CLI clear now flush database and clear the plots
  ([`ebd4fcc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ebd4fccda2321aa0dc108a5436fb4cc717911d4b))

- Monitor.py crosshair enabled by default
  ([`97dcc5a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/97dcc5ac768cc4f0122382591238fd5a9d035270))

- Monitor.py fixed not updating config changes after receiving refresh from BECPlotter
  ([`00ef3ae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/00ef3ae9256a368f4842c1dc38a407131181ec1d))

- Monitor.py fixed scan mode
  ([`a706da2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a706da2490f4cce80e9515633e8437b3667b0db0))

- Monitor_config_validator.py changed to check .describe() instead of signals
  ([`5ab82bc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ab82bc13340adb992c921a7211e8e2265861f7a))

- Monitor_config_validator.py valid color is Literal['black','white']
  ([`86c5f25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/86c5f25205dbaa45b7b2efd255f3a3cb2d3eb0b1))

- Motor_config_validation changed to new monitor config structure
  ([`d67bdd2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d67bdd26167dca6c65627192dbd098af08355d06))

### Continuous Integration

- Fix cobertura for gitlab/16
  ([`9c7a189`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9c7a189bebed9e583304d5f43a93642c10f6958f))

### Features

- Monitor.py access data directly from scan storage
  ([`26c07c3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/26c07c3205debaf88a346410a8ebab0a3ab7a5d9))

- Monitor.py can access custom data send through redis
  ([`6e4775a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6e4775a1248153f6027be754054f3f43c18514d1))

### Refactoring

- Config_dialog.py refactored to accept new config formatting
  ([`3982c5d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3982c5d498bf1f8e868091316be66e8ce45022d9))

- Modular_app.py configs changed to new format
  ([`404ca49`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/404ca49821514be7d3a6c9e6a009b60222b7e812))

- Monitor.py clean up
  ([`1128ca5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1128ca5252813228fdc5cf23bd9f133d457e8d24))

- Monitor.py config hierarchy refactor for source (can be 'scan_segment','history', 'redis')
  ([`c995e0d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c995e0d2350f6a3ab55a4b29cef48f253b648356))

- Monitor.py data for scan segment are only accessed through queue.scan_storage
  ([`c3f2ad4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c3f2ad45c3a3b54597ab64de4e5105f49ef50a79))

- Monitor.py on_scan_segment old logic separated from on_scan_segment function
  ([`463a60a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/463a60a99c3e77771027b9bd838fe34199235ac9))

- Review response for MR !31
  ([`eb529d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb529d24d2bb1b542fbe12a8bb9cef00fb84814c))

### Testing

- Test_bec_monitor.py fixed
  ([`457567e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/457567ef74fbecfde1b6cea09536eae1ed7b121f))

- Test_validator_errors.py fixed
  ([`90d8069`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90d8069cc3dd35fc5ac867a81688216f45e40ec4))


## v0.34.1 (2023-12-12)

### Bug Fixes

- Formatter and tests fixed
  ([`186c42d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/186c42d6676a495bc2f66d8b7ed37dbf7d0be747))

### Build System

- Fix python requirement
  ([`3ec9caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3ec9caae098a001b4c3d52ca6dd1ccf567a6fb4b))

### Continuous Integration

- Added rtd update job
  ([`11281fe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11281fef533c71b6774400506aed921c9818db1f))

### Documentation

- Gitlab templates for issues and merge requests from main bec repo
  ([`831eddc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/831eddc13600cc06b67de92d39509af37bb05002))

- Readdocs updated
  ([`af995a7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af995a74f34d59eeaff5d9100117f103ec79765d))

- Readme.md updated
  ([`cba8131`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cba81313671acfee0a40410753c1974008316d07))

### Refactoring

- Replace deprecated imports from typing
  ([`9e852d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9e852d1afccdce1a8cea7287c928f233604e4c62))

https://peps.python.org/pep-0585/#implementation

- Repo reorganisation
  ([`f3a47a5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f3a47a5b080b705620f75035e5c9f052672261d8))

- Repo reorganization
  ([`3abd955`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3abd955465551c1cddc5832e2aa44fbc8870d3bd))


## v0.34.0 (2023-12-08)

### Bug Fixes

- Monitor_config_validator.py - Signal validation changed from field_validator to model_validator to
  check first name and then entry
  ([`0868047`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/086804780d19956331d8385381d2f7f9c181e77c))

- Monitor_config_validator.py fix entry validation executed only if name validator is successful
  ([`af71e35`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af71e35e73733472228c4be0061faefaf655b769))

### Features

- Monitor.py error message popup
  ([`a3b24f9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3b24f92420420c8968ef4793342c3857c826e57))

### Refactoring

- Monitor.py pylint improvement
  ([`731fba5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/731fba55ec2e0ad3141f429c8e9107a9caab1b1e))

### Testing

- Validation errors tests
  ([`2a33415`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a334156a8e9c5d10176dfe2aae03cf71b837a71))


## v0.33.0 (2023-12-07)

### Bug Fixes

- Added hooks to react to incoming config messages and instructions
  ([`1084bc0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1084bc0a803ff73cfa2ab53819bc9809588fa622))

- Fixed default config options
  ([`03bdf98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/03bdf980bcfc37e217cde1beb258d11cee97e0eb))

### Features

- Added axis_width and axis_color as optional plot settings
  ([`504944f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/504944f696a7b2881adec06d29c271fec7e2c981))


## v0.32.2 (2023-12-06)

### Bug Fixes

- Changed exec_ to exec for all apps
  ([`080c258`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/080c258d1542aaace093bca74225297b30453f77))

- Yaml_dialog.py changed to use native solution of OS -> should prevent crashing on py3.11
  ([`5adde23`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5adde23a457bbd3ae1488b77d4b927b5bded0473))

### Testing

- Additional tests for error handling for yaml_dialog.py
  ([`f5d1127`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f5d1127d21a53abc2f38f64e0fb10102268baa49))

- Removed captured code for Permission tests
  ([`aad754f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aad754f4720a4d32f0f5b7d0895ff30f2f4a64f4))


## v0.32.1 (2023-12-06)

### Bug Fixes

- Widget_io print_widget_hierarchy fix comboboxes
  ([`d1f9979`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d1f9979ab1372c2f650c8aff12ccb17d668b52eb))

- Widgetio combobox fixed for qt6 distributions
  ([`4f70097`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f700976ddd78a6f06e358950786b731ef9051ce))

### Refactoring

- Improve pylint for WidgetIO
  ([`bcc47f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bcc47f3740e2e6e70e75e15861a685b7caee5539))


## v0.32.0 (2023-11-30)

### Bug Fixes

- Added missing dependency jedi
  ([`d978740`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d978740f9879580d01e092ad1fead46786d3ed5c))

- Editor.py compact signature on tooltip
  ([`f96cacc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f96caccfcb43c904887ebfc0b34fd779ffff8bf1))

- Editor.py removed automatic background behind edited text
  ([`d865e2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d865e2f1af6eb3d5fb31f9c53088b629a232343f))

- Editor.py switch to disable docstring
  ([`3cc05cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3cc05cde147cd520b98f0896beb64781ea47d816))

- Terminal output as QThread
  ([`a0d172e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a0d172e3dc35bdc2d7e1b43185e31bb9a3629631))

- Toolbar.py automatic initialisation works
  ([`8ad3059`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ad305959257a58b297896218baae06d09520ee1))

### Build System

- Added option to add PyQt6/PyQt5/PySide2/PySide6 as qt distribution with PyQt6 as default
  ([`b14d95a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b14d95ad2b608d4c52eb8791f380b2d2c9f11fad))

- Added qtconsole to dependency
  ([`e5010c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5010c77728c37ce8c42d53511a1ae354f06c240))

- Disabled support to PySide2/PySide6, due to no QScintilla support; added pyqtdarktheme
  ([`c174326`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c1743267625c7b368e871e0e2ce0761444d1075e))

### Continuous Integration

- Added libdbus
  ([`65cbd6e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/65cbd6ef287e2adc3f7c1d5642bf9df49d45a262))

- Added libegl1-mesa to the apt-get install command in tests
  ([`bb64088`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bb640882826a65a6edb534df6e121c0731296782))

- Added pylint to ci
  ([`745aa6e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/745aa6e812ae99410a0b37538c0ef58e2fdfe8da))

### Features

- Basic text editor + running terminal output
  ([`9487844`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/94878448c8f39a69e9e65df2789da029a9acfc0e))

- Editor.py added splitter between editor and terminal
  ([`c70ddb3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c70ddb3cb19fecf7ce14b551d7d265e2e0cff357))

- Editor.py basic signature calltip
  ([`045b1ba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/045b1baa60a93d2266800821940d7aa29bd8bbe1))

- Editor.py jedi autocomplete hooked
  ([`fb555b2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fb555b278a5139f180592280408742d34dc5fa84))

- Jupyter rich console added as alternative to default QTextEdit terminal output
  ([`016b26f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/016b26f5cf05e90da144487a9359ac2a54c8e549))

- Toolbar.py proof-of-concept
  ([`286e62d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/286e62df92927d2efe0b4ab07995f7b5e36a0435))

### Refactoring

- Change from QMainWindow to QWidget
  ([`10dfe9f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/10dfe9fb650bea4939740d87bcb18f0e49e4d491))

- Changed dependency to CAPS
  ([`7d15397`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d15397ce3f251df77ad0717266da9feb378a6e1))

- Editor.py migration to qtpy
  ([`b07bb3d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b07bb3dde20e44ba493c9242c31c10f330b4d907))

- Editor.py open/save file refactored to not use native window
  ([`d967faf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d967fafe3c77249ad24cc01c8cd3288184bf33d5))

- Editor.py signature tooltip process moved to AutoCompleter; simpler logic for signature tooltip
  ([`d7a2c68`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d7a2c6830f47d09b7a4f7f37a5476d08c2a72dfc))

- Improve pylint score
  ([`a4d9713`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a4d9713785d5ba8d60f541260de4be6f5d224480))

- Migration to qtpy
  ([`b6f6bc5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b6f6bc5b2083ede0f7345996823872a1d603fce1))

- Toolbar.py migration to native qt QToolBar
  ([`ee3b616`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ee3b616ec12939e5035db85b8b19b8eb429c0f7b))

### Testing

- Test_editor.py tests added
  ([`b21c1db`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b21c1db2a9251c78568ba7fe2e968e5973c8acf6))


## v0.31.0 (2023-11-13)

### Documentation

- Pydantic validation module docs
  ([`92a5325`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/92a5325aad02fe308caaf9088a3c4386ca055124))

### Features

- Pydantic validation module for monitor.py
  ([`7fec0c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7fec0c7e4411c221413d69aeeb4d68ade10d502b))

### Refactoring

- Becmonitor cleanup for validation in on_scan_segment; dropped support for multiple entries for
  single device
  ([`cd9cd9e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cd9cd9ef9da7f189eabf90deeff21cc0dcc9ebd7))

- Clean up
  ([`6b114c2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b114c24611cf7f93aac5bcbe5d914ed76860e3b))

- Configs for BECMonitor are validated by pydantic outside the main widget
  ([`37278e3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37278e363c701801b774e1533417bca0ea51019f))

- Fix bec_lib imports
  ([`5ec2b08`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ec2b08e343142b9a449fe25ddb275f4ff8ffaa4))

- Fix bec_lib imports in tests
  ([`cae4f8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cae4f8b9342b15562fff93c5d80b37cb38f8af41))

- Monitor.py update_config renamed to on_config_update; gui_id added
  ([`59bc404`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/59bc40427cd3bd903bd90268560573ea5e4e0f29))

- Monitor_config_validator.py device_manager renamed to devices
  ([`53494c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/53494c73271d544edbce222d48161bbb287eefd5))

- Monitor_config_validator.py name validation logic
  ([`84ef7e5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84ef7e59c9864c9c55dab8e4a1584283c3e7798c))

### Testing

- Tests fixed; test_bec_monitor.py extended for FakeDevice class
  ([`05c8226`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/05c822617a9e75ba99113eaa8b9325af4db1fbef))


## v0.30.0 (2023-11-10)

### Bug Fixes

- Added imports to __init__.py in widget for ScanControl class
  ([`b85cc89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b85cc898d521df1c99a65e579b8fe853bb04cc32))

- Scan_control.py all kwargs are rendered
  ([`4b7592c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4b7592c2795a26591b3e30870c73aa406316588d))

- Scan_control.py args_size_max fixed
  ([`da9025e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/da9025e032c2bc9b34cf359a20745e3156d2f731))

- Scan_control.py default spinBox limits increases
  ([`5c67026`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5c67026637472d9c77185a59e1bf9a24cfe01307))

- Scan_control.py kwargs and args are added to the correct layouts
  ([`b311069`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b311069722226b95a7902f42815d2c1e219e9584))

- Scan_control.py scan can be executed from GUI
  ([`2e42ba1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2e42ba174f7abe1590b9afb099dc2d068eb848ae))

- Scan_control.py supports minimum and maximum number of args
  ([`ee2f36f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ee2f36fb402d626c300a018afacbd57eff14a665))

- Scan_control.py wipe table and reinitialise devices when scan is changed
  ([`5ac3526`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ac3526384b9ee0eb94568bac035b348eaa52abd))

- Widget_io.py added handler for QCheckBox
  ([`18a7025`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/18a702572f6bed41081d368e39c8fc69122c6203))

### Features

- Scan_control.py a general widget which can generate GUI for scan input
  ([`088fa51`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/088fa516a8876d112a98cd60aa2a5701dff6b97c))

- Scan_control.py added option to limit scan selection from list of strings as init parameter
  ([`0fe06ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0fe06ade5b44d13a9188aef474364b36baa480ef))

- Widgetio support for QLabel
  ([`aa4c7c3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aa4c7c3385f52e4bbc805ee2aced181929943a89))

### Refactoring

- Changed buttons name to be consistent with other projects
  ([`43777f5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/43777f58f6d16c53e0fb42c543b71f647ba6d038))

- Changed widget_IO.py to widget_io.py for consistency; widget_io.py example excluded from coverage
  ([`975aadb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/975aadbf073eae6eb5617bd6c639daded0b185ce))

- Clean up
  ([`1f01034`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1f0103480d2c8dd4b073eb0321a2f87b61e22da6))

- Scan_control.py clean up
  ([`27f6a89`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/27f6a89a290b49eec1517b939d12a2fce1ec40c8))

- Scan_control.py extraction of args separated
  ([`63f23cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63f23cf78ef58cace2bc44b3c3897be6ac4ecfb3))

- Scan_control.py generate_input_field refactored into smaller functions
  ([`26c6e1f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/26c6e1f4b8f14f91c5d78f8c527bb7e673160bae))

- Scan_control.py kwargs and args layouts changed to QGridLayouts
  ([`f5ff15f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f5ff15fb9a2508e35ddb8b7ad21f684b10e806f5))

- Scan_control.py kwargs are in grid layout, args in table widget
  ([`8bc88ca`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8bc88ca195695c4428f7f219d42bf0ed547f62a0))

- Scan_control.py refactor to use WidgetIO
  ([`3be9c97`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3be9c974b50eb1dbee4a2a21e218364832e90ab7))

- Widget_hierarchy.py changed into general purpose modul to extract values from widgets using
  handlers
  ([`9308f60`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9308f60b889a403bfc6973f4bc359620dadb2c6a))

- Widget_hierarchy.py renamed to widgets_io.py
  ([`3c28cf0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c28cf0e0180a338eb326f3170852f479d1389c2))

### Testing

- Test_widget_io.py fixed
  ([`679d3e1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/679d3e198085daa4bef451a06f9bd6f6854559cf))

- Tests for scan_control
  ([`832a438`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/832a438b24bbb6be6f0d5e6e14a51a0d4e8c65b4))


## v0.29.0 (2023-10-31)

### Bug Fixes

- Config_dialog.py can load the current configuration of the plot
  ([`f94a29b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f94a29bf4be0a883abc200821746c3d81a0c00d4))

- Config_dialog.py config from default mode can be exported to dict
  ([`55b5ca7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/55b5ca7381dc33119baac0f48c76fc9d9e8215ae))

- Config_dialog.py export to .yaml fixed
  ([`7e99920`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7e99920fc565acd59cb3a4286ac5ee40597d8af4))

- Config_dialog.py prevents to add one scan twice
  ([`12469c8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/12469c8c1e45f83cc0c65708bd412103a8ec1838))

- Config_dialog.py scan_type structure implemented
  ([`e41d81c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e41d81cbd9371f8633c1e7de82c8f9b64fcb721b))

- Config_dialog.py tabs for scans and plots are closable now
  ([`ec88564`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ec88564e6577cd6579c30f36193c4a0e5fcbc483))

- Device_monitor.py BECDeviceMonitor can be promoted in the QtDesigner and then setup in the modular
  app
  ([`afab283`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/afab283988a1acc008bc53ae5a56a8f67504da81))

- Device_monitor.py crosshairs can be attached again
  ([`644a97a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/644a97aee848c973125375d5f28d3edf2ffc20cf))

- Modular_app.py configs are linked to the actual version of the state of the device monitor
  ([`d78940d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d78940da3f114062aa397b87c169f26cbc131a5f))

- Test_bec_monitor.py config loaded fresh in the test function to avoid parameter leak
  ([`3866d7c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3866d7ce4de3391fe57ef872808f7620562eeeb0))

- Test_bec_monitor.py QApplication instance removed
  ([`77e1d09`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/77e1d0925db2dc6669159fbe3fb08daf330cb5c8))

- Test_bec_monitor.py setup_monitor help function changed to pytest.fixture
  ([`989cd51`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/989cd51162147805db1229b50b330af29f275204))

- Test_config_dialog.py - QApplication removed
  ([`1cdd760`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1cdd760e4062de1f19837737766ce05edc9ac2da))

- Test_config_dialog.py - test_add_new_plot_and_modify qtbot action .click() changed -> function
  called directly
  ([`1333e6c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1333e6cbca18943b0a61206dc1ba63720b031b40))

- Test_config_dialog.py disabled
  ([`4e710dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4e710dda5e88b2e82ec87db350e8b1fe6aa09181))

- Test_config_dialog.py QApplication instance added
  ([`60e864b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/60e864b2590d121e1b0ad645d39d1a028abe8d7b))

- Wrong __init__.py in modular_app
  ([`d52aa15`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d52aa15aac42f09487c828836e377c78596037bd))

- Yaml_dialog.py added return None if no file path is specified
  ([`ff1d918`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff1d918d43f0f2e5fe8d78c6de9051c50e0e12c1))

- Yaml_dialog.py added support for .yml files
  ([`10539f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/10539f0ba59be716102b2c0577ea62f5c4a3136a))

### Documentation

- Added sphinx base structure
  ([`9d36b96`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d36b9686e31b2c4b4206ad47b385c8f2769c641))

- Config_dialog.py comments added to example cases
  ([`4a6e73f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a6e73f4f791d2152ff29680a4e28529a8df0b47))

- Device_monitor.py update docstrings
  ([`a785bca`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a785bca8806613f9e1e4b67380e72867b581fe6e))

### Features

- Config_dialog.py interactive editor of plot settings
  ([`c9e5dd5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c9e5dd542c9eb7c9069d1c0f1256a634a166eb40))

- Modular_app.py, device_monitor.py, config_dialog.py linked together, plot configuration can be
  done through GUI
  ([`bf2a09e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf2a09e6307da63ecf02a1286095a19e5f1dcab4))

- Qt_utils custom class for class where one can delete the row with backspace or delete
  ([`a6616f5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a6616f5986d59ad8d065105234f5b704731cce71))

- Widget_hierarchy.py tool to inspect hierarchy of the widget
  ([`cda8dae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cda8daeb35b36692316173a19fb29f1cc0dbdb7c))

- Yaml_dialog.py interactive QFileDialog window to load/save .yaml files to/from dict
  ([`2b29b6c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2b29b6cfe2ea94a974da4a332c47473176ddddff))

### Refactoring

- Becdevicemonitor changed to BECMonitor
  ([`cb6fb9d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cb6fb9d78b9c7dba2289adb64ed081098fe1ebdc))

- Config_dialog.py add_new_plot_tab and add_new_scan_tab changed names
  ([`fd49f1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fd49f1b484c190cf1dc5f7d0e74ce78371d0f3f3))

- Config_dialog.py clean up
  ([`93db0c2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/93db0c21efe9d7170a82af2cb0621caa3cd6cb09))

- Config_dialog.py hook_plot_tab_signals refactored
  ([`fbb7a91`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fbb7a918cc4b31f8e3d810970c3979cc718616fa))

- Config_dialog.py load dict without scan mode
  ([`7d5429a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d5429a162df6e5096200250ee232761de618a6b))

- Config_dialog.py simpler add_new_scan and add_new_plot
  ([`8ffb7d8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ffb7d8961476239a1cf6eedd2e5f3937662b636))

- Dialogconfig implemented directly to the BECDeviceMonitor
  ([`f1d7abe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f1d7abeb25392e62524fc08fd335b4fa73688b30))

- Qt_utils/hierarchy function refactored to use widget handler allowing to add more widget support
  in the future
  ([`de23c28`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/de23c28e40ddf034c6be58ba13b3dba3203b60b4))

- Test configs are saved as yaml and shared for similar tests
  ([`5ad19b4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ad19b4d7b76c1424ae105c711c4e08a2225d2a9))

- Test_bec_monitor.py and test_config_dialog.py cleaned up
  ([`3a4cbb1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3a4cbb1bb684539e7457f04ee36349181d149231))

- Test_bec_monitor.py widget name changed
  ([`a3a72b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a3a72b9b935e7d703be382e47c68db46bd4468c3))

- Test_config_dialog.py and test_bec_monitor.py clean up
  ([`1fd0185`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1fd018512fb0fd5901c0cefab1e9e1353b508755))

- Yaml_dialog.py save/load logic changed
  ([`42fe859`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/42fe859fca80cc6f08a02d3cda2c4cb2ccec9329))

### Testing

- Becdevicemonitor tests
  ([`e4336cc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4336cca30d7f9bef400fe1eed0d6b20c8ae9bfa))

- Test_config_dialog.py added
  ([`6a5e0ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a5e0adfb29b4caf5e6b5c15869390370c623af5))

- Test_hierarchy.py added
  ([`f396f98`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f396f98e7327ffd8bdadd3ab03cb3da9a95ab967))

- Test_yaml_dialog.py tests for loading/saving dialog for .yaml export
  ([`850f023`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/850f02338e4dc7fe587bad0faa85a69faa0a9abb))


## v0.28.1 (2023-10-19)

### Bug Fixes

- Stream_plot.py on_dap_update data dict opened correctly
  ([`28908dd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/28908dd07c1eef8a9d3213a581393e665b310d1b))

### Refactoring

- Bec_dispatcher.py changed to Ivan's version
  ([`6d6b1e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6d6b1e9155096f60f8d6c5f02fe8491cd69fa653))

- Duplicate scripts of BasicPlot removed, BasicPlot renamed to StreamPlot
  ([`144e56c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/144e56cdd91fccb29acfebb6f61d08a6c5a7f412))

- Placeholders for stream plot
  ([`f022153`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f022153fa26a7c8b2682505f1a21a0d0295044c1))

- Stream_plot.py changed client initialization
  ([`17ea7ab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/17ea7ab703b1b22b4d0c3c5fb30bd28a57b2c807))

- Stream_plot.py color static methods removed
  ([`ad2b798`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad2b798f116a191f6bc15fdd5111ab61ee1aeb7a))

### Testing

- Add bec_dispatcher tests
  ([`7152c5b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7152c5b229cb7fb5bfd8d4e7697f668a867c602c))

- Test_basic_plot.py deactivated due to non-existing method on_scan_segment
  ([`8f83115`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8f83115efc2ef53ef1f0ff3ece5a5987b08920ae))

- Test_stream_plot.py basic tests for stream_plot.py, test_basic_plot.py removed
  ([`2925a5f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2925a5f20ef3b0dc6d66f2d9781775f53c01dbfc))


## v0.28.0 (2023-10-13)

### Bug Fixes

- Scan_mode for BECDeviceMonitor fixed init_ui
  ([`59bba14`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/59bba1429c1f8aeeb562b539583e71303506bd58))

### Features

- Becdevicemonitor modular class which can be used to replace placeholder in .ui file.
  ([`f3f55a7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f3f55a7ee0ad58aab74526a24f27436fd2bef61d))

- Placeholders initialised
  ([`75af040`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/75af0404b3aa5f454528255e8971af07c4e8b39b))


## v0.27.2 (2023-10-12)

### Bug Fixes

- Scan_plot tests
  ([`f7cbdbc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f7cbdbc5ca318d60a9501df3fa03c7dea15b5b21))

Add scanID key to scan_segment in tests

### Refactoring

- Emit content and metadata from messages in connect_slot
  ([`78b666f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/78b666ffdb89ddf160a2e9ad91c8577e64884f6a))

- Remove all custom topic connection methods
  ([`f01078f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f01078fc2165f236ae07539fd1d5d05f25712235))

- Replace connect with connect_slot
  ([`7335aa9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7335aa9597a519371c3f02f21ea89edb06333eaf))

- Switch to generic connect_slot method in plots
  ([`616de26`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/616de26150f473342fbac4f2db80e9acca035a1b))


## v0.27.1 (2023-10-10)

### Bug Fixes

- Extreme.py advanced error handling with possibility to reload different config
  ([`d623cf9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d623cf95391adfc89837cd54ca1b2a1b6e491a3c))

- Extreme.py advanced error handling with possibility to reload different config
  ([`51c3a9e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/51c3a9e9ee3d75c8324300afac366dcdb9adb876))

- Extreme.py client and device manager initialisation
  ([`cf15163`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf15163bd91291e9851662c147b2e799ae022b9e))

- Extreme.py client and device manager initialisation
  ([`ae79faa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ae79faa7ed8e9d8f680e1be1afefe43706305d9a))

- Extreme.py default config file changed to the config_example.yaml
  ([`d356cf7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d356cf734b81fd7ed2c9b48ee85a1722af179d83))

- Extreme.py default config file changed to the config_example.yaml
  ([`5814113`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5814113f73fb1c4552bb715b27d3330decd9c878))

- Extreme.py error in configuration are displayed as messagebox
  ([`89a52a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/89a52a0948ee300e57bb7198eac339ee771bff06))

- Extreme.py error in configuration are displayed as messagebox
  ([`9750039`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9750039097c9e4b9a45603dcefe76e5b2e8920fd))

- Extreme.py improved error handling for scan types mode
  ([`ece1859`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ece1859a63b83b1d56b33cc610efea6876dd9e1f))

- Extreme.py improved error handling for scan types mode
  ([`fbd299c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fbd299c7e7cf548886e2b1787d8e188c708ee8cd))

- Extreme.py init_plot_background error handling
  ([`dafb6fa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dafb6fae7a526d5b311ded1d0424ac4dbb3c8b74))

- Extreme.py init_plot_background error handling
  ([`c525eba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c525eba88576e0094063019d00fba6a43c52b42e))

- Extreme.py init_ui changed > to >= for setting number of columns
  ([`a0a89fe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a0a89fe704db6c11a99a26a080051af1c677ba7a))

- Extreme.py init_ui changed > to >= for setting number of columns
  ([`6c773c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6c773c7c94e5eee700b74a792657978be86dbbf4))

- Extreme.py retry action fixed in ErrorHandler
  ([`b76df1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b76df1b583a5922229f97876f9e65e0cad64c88e))

- Extreme.py retry action fixed in ErrorHandler
  ([`5162270`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5162270d28ca8eab4eac9d9665e2fb4c5e8a33a3))

- Extreme.py ui is initialised for the first scan of config in scan mode
  ([`82bebe6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/82bebe6b41004befcb1b54db141e20ff844f76e5))

- Extreme.py ui is initialised for the first scan of config in scan mode
  ([`fc60984`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc6098414e328e14ec9ab6006538f46e36f17723))

- Extreme.py validation function to check config key component structure
  ([`5a7ac86`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5a7ac860a8cf5cef53ae699b2869e649c1721f9d))

- Extreme.py validation function to check config key component structure
  ([`824ce82`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/824ce821cd5f060f2c550b970afb1f3479a006ef))

- Formatter fixed
  ([`153c5f4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/153c5f4f9d168f433380bd2deddd2b17a45916a3))

### Refactoring

- Added __init__.py to all example folders
  ([`4772c24`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4772c244c2c98230115c387a04f0d5d6943aa7b3))

- Added __init__.py to all example folders
  ([`f74a6a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f74a6a0b8bbac0bc665cb51d8ababaf195162126))

- Extreme.py error messages for config file moved to ErrorHandler class
  ([`8050bdf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8050bdf82d8a76257c834105e13b72fdb6193792))

- Extreme.py error messages for config file moved to ErrorHandler class
  ([`d2c12a9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d2c12a9f1cd31489666bf9264e90e73bcf6435da))

- Extreme.py ErrorHandler fixed, new configs are correctly loaded
  ([`aed65b4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aed65b411a68d64c8206c61db0a95c0e36ac1e90))

- Extreme.py ErrorHandler fixed, new configs are correctly loaded
  ([`5637c93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5637c938cfb75b75d98304f4c041f82c21d603cd))

- Fixed formatting for mca plot
  ([`977ce3a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/977ce3ae93c65560820aedfc2083cc243b9b5ae1))

- Test_extreme.py corrected typos
  ([`9e7224e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9e7224e0ae283ca1bc668f27bbf1d43f0104e97f))

- Test_extreme.py corrected typos
  ([`eb1f1d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/eb1f1d481e21fd9c174d893a4fe2d65347719f3c))

### Testing

- Added initial tests for extreme.py
  ([`80190cc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/80190ccba782325e0b9b4f3c67d3aff2e5004663))

- Added initial tests for extreme.py
  ([`779f34f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/779f34f5006aabd7d701699b6f8490bcbe875182))

- Added test_on_image_update for eiger_plot.py
  ([`ad1d69f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ad1d69fa662dbdb29ead4731ae205f5adc493c6a))

- Added test_on_image_update for eiger_plot.py
  ([`70684d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/70684d119f1e8ee7d0d69df0e3587ab8aac15ad3))

- Added test_start_zmq_consumer for eiger_plot.py
  ([`7485aa9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7485aa999f0c5b255f9279bb8d73fa9d10246560))

- Added test_start_zmq_consumer for eiger_plot.py
  ([`0a0d51d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0a0d51d278679fc5eca234293b70c91759cbdbbe))

- Added test_zmq_consumer for eiger_plot.py
  ([`abd3ebe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/abd3ebec1fdddb54247a45544e4f5eb9046716e4))

- Added test_zmq_consumer for eiger_plot.py
  ([`c827a25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c827a25dab5f31f330128bdc4e944f568537d51b))

- Test_eiger_plot.py added qtbot.waitExposed(widget)
  ([`8b3a0ba`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8b3a0baaa60b9f98550e6ddcd2b8ed7435f76dc0))

- Test_eiger_plot.py added qtbot.waitExposed(widget)
  ([`6322c47`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6322c4720f67ef38d35ee1a9c5811348e8cd672e))

- Test_eiger_plot.py optimised imports
  ([`5e9deae`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5e9deae7651053de6d939f79eb6220fb139cc8ac))

- Test_eiger_plot.py optimised imports
  ([`08d9569`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/08d956940e744987176556c728560ecf5dce1ffb))

- Test_extreme.py error handling tested
  ([`fc31960`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc31960c618323332ef38474b79b379f16432f87))

- Test_extreme.py error handling tested
  ([`90f22c2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/90f22c2288ef3e9f9430a4c0dc80030c0a514ba1))

- Test_extreme.py ErrorHandler tested separately
  ([`835bda0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/835bda0a539cef18bf626a8b3307a050bd1f9232))

- Test_extreme.py ErrorHandler tested separately
  ([`ac2a41d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ac2a41d2d859de16ce322fad0356b97203330d96))

- Test_extreme.py init_ui more edge cases
  ([`7b3a873`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7b3a87380056fef260d92a5487e4a6eb29338647))

- Test_extreme.py init_ui more edge cases
  ([`36942b3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/36942b316a8162e905c6679f014dcb5238c7f84a))

- Test_extreme.py MessageBox buttons Cancel and Retry tested
  ([`2faeb63`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2faeb639be4ae44d982a78539468419114c8b9ef))

- Test_extreme.py MessageBox buttons Cancel and Retry tested
  ([`6c3dfdd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6c3dfddd2823b22b5bfd64f833934a8ebd731d24))

- Test_extreme.py on_scan_segment tested with all entries correctly defined
  ([`126451a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/126451a7a98bde9433eb2d907988d69b6fe25a67))

- Test_extreme.py on_scan_segment tested with all entries correctly defined
  ([`0ec65a0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ec65a0b4109b50a9bbc2d7a9501610031492596))

- Test_extreme.py test_init_config fixed for scan_config
  ([`69aaea2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/69aaea24f93fd4ede22a37649fbd84a5012a0594))

- Test_extreme.py test_init_config fixed for scan_config
  ([`0338462`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0338462a85c55683bfc09f6531af5a6137449517))

- Test_extreme.py test_init_config new config tested
  ([`f8d30c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f8d30c9b0e563e19b32efff417d20ee802edc600))

- Test_extreme.py test_init_config new config tested
  ([`daf4ee1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/daf4ee190e659bc9a7146631d01560d8f3b7e81f))


## v0.27.0 (2023-09-25)

### Bug Fixes

- Epics removed from requirements
  ([`44cc881`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/44cc881ac9e69c68f1f5296fea62a14daa55d4e3))

- Extreme.py formatting fixed
  ([`63f52fc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63f52fc8419cd53856a32af6be3f548f8e077cd1))

- Line_plot.py ROI interactions fixed
  ([`e4f23f5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e4f23f51012b54cde5cd41bb9ab356a277ef4b2f))

- Motor_example.py - new more robust logic for getting coordinates for table go buttons
  ([`08f508f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/08f508f4c3c3e1f3c2d4c6dda0d8e6693e9331b5))

- Motor_example.py duplicate table fixed
  ([`401fec8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/401fec85395886ea2816b6993bf8084b6e652967))

- Motor_example.py export .csv logic fixed
  ([`85841cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/85841cdf1fc44472cfcc7e3e6529a41018140896))

- Motor_example.py load .csv logic fixed
  ([`b78152b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b78152b14999ba5c07d7cd2ef2e3309df1ba5ca6))

- Motor_example.py manual changing coordinates in start/stop works again
  ([`b13509e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b13509e9eb88b55a59b141b0cec06f3c8a983151))

- Motor_example.py new independent mapping relying on the table
  ([`673ed32`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/673ed325d1f56505035899549ea555497823a31f))

- Motor_example.py precision in duplicate table fixed
  ([`05f48de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/05f48de3f1f6793de3f6a8bc2c5e3ad3261dfcf0))

- Motor_example.py replot points logic simplified
  ([`a15860a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a15860abac984328382868b0a953960c44792c41))

- Motor_example.py user is blocked to duplicate last entry in start/end mode if end coordinate was
  not defined
  ([`418480f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/418480f1fcdc72c05887e8b73c24f76e1e8475b2))

- Online changes e21543
  ([`b41d63e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b41d63ea4d6e15c80a7baab7a70c607079152d0a))

### Features

- Motor_example.py in start/end mode new button allowing user to go to end position
  ([`65b045e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/65b045e1a26a0f799311e9dca25e2a9dfd7f7147))

### Performance Improvements

- Motor_example.py replot logic optimizes
  ([`a4fb6bd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a4fb6bd1d2c819740077cdc7291daf28a9e4abdd))

### Refactoring

- Motor_example.py - function to connect buttons in the table
  ([`6124eab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6124eab971d04ba0f214d9cdcff688d7aceed661))

- Motor_example.py removed old table related functions
  ([`ed3f656`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ed3f656d5e018463761e336981d3b6fdfa8283d2))


## v0.26.7 (2023-09-19)

### Bug Fixes

- Eiger_plot_hist.py removed
  ([`abe35bf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/abe35bf96757a38395733bddbd8702a29fd26f42))


## v0.26.6 (2023-09-19)

### Bug Fixes

- Extreme.py fixed logic of loading new config.yaml during app operation
  ([`4287ac8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4287ac888591abf27a4e4ce8c23f94d54bc6c2a9))

- Extreme.py saved to .yaml works correctly for different scans configurations
  ([`cb144c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cb144c7c2cba50fc49ba53b0a9e3293b549665be))

### Documentation

- Extreme.py updated documentation
  ([`7ff72b4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7ff72b4086e5e340d591d130f011f83fc8370315))

### Refactoring

- Extreme.py changed initialisation of config
  ([`a694023`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a6940235be0dbe6ee0ee8f74a07c75df08c8d061))

- Extreme.py plot init moved to config_init
  ([`5f3d55b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5f3d55b760ed69a57afbfa8bb1d7eb8db0f4c078))


## v0.26.5 (2023-09-13)

### Bug Fixes

- Motor_example.py help extended
  ([`a5c6ffa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a5c6ffaa024a0dd6901976c81ea9146e5be016ec))

### Refactoring

- Extreme config example
  ([`34c785b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/34c785b92c95c682541980f0b729c195c545f339))


## v0.26.4 (2023-09-12)

### Bug Fixes

- Logic fixed
  ([`7cb56e9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7cb56e9e7f2cbeee5a141c4a52a3489c26963839))


## v0.26.3 (2023-09-12)


## v0.26.2 (2023-09-12)

### Bug Fixes

- Import with start/stop mode works again
  ([`cacc076`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cacc076959cdd55218b74de2974d890e583c3d94))

- Import works for both modes
  ([`b867f25`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b867f25c780ba97393ca65fe76c1cb492f365ded))


## v0.26.1 (2023-09-12)


## v0.26.0 (2023-09-12)

### Bug Fixes

- Removed scipy from eiger_plot.py
  ([`0e634ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0e634ee2ac58b8be43b7f4e64fbc08ef08675aa1))

### Features

- Plot different signals and plot configurations based on different scans
  ([`57e6990`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57e69907d55f7693e97d48026f3bb426adfb4870))

### Refactoring

- Config_example.yaml
  ([`7235038`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/723503851bbbb542177dc7a773388920e655d745))


## v0.25.1 (2023-09-12)

### Bug Fixes

- Mode lock in config to disable changing the mode for users
  ([`10ccf0c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/10ccf0cc977cae30c0c185a920e15b9cf2def58f))

- Specific config for csaxs
  ([`8ff983f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8ff983f16e78d881582d4aaaa0261e10d9d62bf2))


## v0.25.0 (2023-09-12)

### Bug Fixes

- Extra columns works again
  ([`2123361`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2123361ada9767333792d34de56d6f1447f67cda))

- Resize table is user controlled
  ([`63e3896`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63e389672560e505159de2014846d1506b05633f))

### Features

- Combobox to switch between entries mode
  ([`f2fde2c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f2fde2cf5c4b219520eb0257c1c8e02ce66cde87))

### Refactoring

- Align_table_center as a static method
  ([`702e758`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/702e758812848c73052aca83512613085afb997c))

- Changed order of columns
  ([`14a0c92`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/14a0c92fb9a42716549ddacc3401d41249c0c295))


## v0.24.2 (2023-09-12)

### Bug Fixes

- Changes e20643
  ([`2657440`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/265744076cc53bd054b45c12de3bb24b23e1845c))


## v0.24.1 (2023-09-08)


## v0.24.0 (2023-09-08)

### Bug Fixes

- Typo fixed in mca_plot.py
  ([`3b12f1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3b12f1bc1d65772fc3613f62013809445dcead7a))

### Features

- Histogramlut for mca_plot
  ([`ae04072`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ae040727fc60160de8b50ac1af51fba676106e52))


## v0.23.0 (2023-09-08)

### Features

- Added key bindings and help dialog
  ([`ade893d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ade893d33d07f1190994de19b84d4021586bcbcb))


## v0.22.0 (2023-09-08)


## v0.21.2 (2023-09-08)

### Bug Fixes

- Moved mask as a last step of image processing
  ([`87d5467`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/87d546764318679cd80e56d17d590f0e31e51504))

### Features

- Added FFT
  ([`b984f0f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b984f0f36e2178690eaaec091d4a7b9443f2378f))


## v0.21.1 (2023-09-08)

### Bug Fixes

- Update_signal typo fixed
  ([`43f03b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/43f03b543083da9b743828139a92f87732187dd9))


## v0.21.0 (2023-09-08)


## v0.20.0 (2023-09-08)

### Bug Fixes

- Added missing .ui file to git
  ([`ae8fc94`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ae8fc9497954ca49c16d76eaeea7ecc7659c1269))

- Path to mask fixed
  ([`ef42921`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ef42921c9a585bce8a97fc8bb251e27a9455a771))

### Features

- Added functionality to load mask
  ([`33d1193`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/33d1193c9623b157cc74883184677a727b8e33ce))

- Added rotate and transpose logic
  ([`acd7a3b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/acd7a3bc92746c7e56dc8699c4378d2ab778267f))


## v0.19.2 (2023-09-08)


## v0.19.1 (2023-09-08)

### Bug Fixes

- Rotation logic fixed
  ([`6733371`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6733371c2ccb4e233d9aa9421e21d627978925d7))


## v0.19.0 (2023-09-08)

### Bug Fixes

- Rotation always counter-clockwise
  ([`00385ab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/00385abbf98add7945af170b292774d377473a70))


## v0.18.1 (2023-09-08)

### Bug Fixes

- Online changes
  ([`29c983f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/29c983fb268bb2dbcfe552453501ff42442f075f))

### Features

- Eiger_plot.py in example folder with new GUI
  ([`5cbedec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5cbedec5d9f6a6ae763e2cb336ecb40c4d3e1ed1))

- Rotation of the image to the left/right by 90, 180, 270 degree
  ([`327f6b3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/327f6b3df300d1f88b475973a86175379688aa9b))

- Simulation stream with Gaussian peak in 1st quadrant
  ([`4fa8d46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4fa8d46631ff822d5465564434d173dd766a6b1a))


## v0.18.0 (2023-09-08)


## v0.17.1 (2023-09-08)

### Bug Fixes

- Start_device_consumer changed from EP device_status to scan_status
  ([`46a3981`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/46a3981e7dfd5ded7b7f325301d2a25c47abd16f))


## v0.17.0 (2023-09-07)

### Features

- Console arguments added for Redis port, device, and sub_device tag
  ([`fb52b2a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fb52b2a8e59fca556764e0dc32bd4edc167e31d3))

- Device_consumer is getting scanID and initialise stream_consumer
  ([`9271b91`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9271b91113a3bbd46f0bffdaef7b50b629e4f44f))

- Eigerplot added
  ([`70d74c7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/70d74c774d2b318d99c049f0f03743e77812df98))

- Plot flips every second row
  ([`c368871`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c36887191914d23e85a1b480dac324be0eefb963))

- Simulation and simple 2D plot for mca card stream
  ([`bfef713`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bfef71382e6a1180d750d2c800650942c5da7a21))

### Refactoring

- Functionalities separated to different methods
  ([`b7136e7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b7136e769ff2749d133aa3b95f5e0dad60ad300d))

- Project cleaned up
  ([`7d996ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7d996ec8e7307b5909b83c43c306196624011056))


## v0.16.4 (2023-09-06)

### Bug Fixes

- Self.limit_map_data fixed to be initialised only with integers from limits
  ([`b62509a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b62509a28e970358c3ffd4f7d55c2a6bbef35970))


## v0.16.3 (2023-09-06)

### Bug Fixes

- Limit spinBoxes morphed to doubleSpinBoxes
  ([`a1264fe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a1264fe4e2e0c864c68786d6db16550f489b00fa))

### Documentation

- Pyqtgraph controls in help
  ([`2397af1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2397af140f2f9ee23ed5e62ef9bdf4d0aba249a1))

### Refactoring

- Code cleaned up
  ([`63744b0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63744b0fbfbef33e09206e436e51da4ca494d149))


## v0.16.2 (2023-09-06)

### Bug Fixes

- X and y motor can be linked again
  ([`f45512e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f45512e0ae9c189a1d26456333c5b348cd681ce7))

### Refactoring

- Code cleaned up
  ([`197ebad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/197ebad7657cbfc5fe018bc28a7a7c489d2fd2da))


## v0.16.1 (2023-09-06)

### Bug Fixes

- Default values fixed from .yaml
  ([`8a6e2da`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8a6e2daaf95cb5417951cbe3cca0cb3e909b08b4))


## v0.16.0 (2023-09-06)

### Bug Fixes

- Content always aligned to centre
  ([`74884a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/74884a37076cd047e2dc75e07246f73e5f93167e))

- Help extended
  ([`9fba033`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9fba0334a0389f66344b84dd434d4d9a39b1565e))

- Table loads number of columns correctly
  ([`bf12963`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf129632471da2e6dc5d637a5b02c321d8d3dcac))

### Features

- Added help button
  ([`2087d19`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2087d19d3c2349e160327880210a5cf129852f09))

- Additional columns can be added through .yaml
  ([`fa76acb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fa76acbd6dda1695add1c1159c4a96c33741a4c7))

- Additional extra rows takes values from previous row
  ([`1235294`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1235294b034dae50ff9a2ea93bc1a318383cbbf5))

- Table can be exported to csv
  ([`772f18f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/772f18fa09bef54c849d2fdd58e02e8dada84a4e))

- Table can be loaded from .csv
  ([`15d995f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/15d995f66b892f55526bd8b0954b6886d8f861ea))

### Refactoring

- Change order of columns
  ([`3132b4f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3132b4fb4d544c3533d7de226ecd1768bd5e7876))


## v0.15.0 (2023-09-06)

### Bug Fixes

- Added float validator to the table
  ([`be1bd81`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/be1bd81d60373a0d9e776dc3f0d879d1bf905f7a))

- Coordinates markers are updated on the map, if X, Y in table manually is changed
  ([`0aa667b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0aa667b70d48356bdda59b879baa3862c5e2e756))

- Partial fix to table checkBox
  ([`75f5c8f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/75f5c8fcd6e80288e1f3bc1b9c0c0b3edd1335bc))

- Table bug, when deleted multiple rows
  ([`9d83a45`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9d83a455e899e3018364123707064882076c4eb0))

- Table bug, when user deleted row and wanted to go to the previous position
  ([`63e6d61`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/63e6d61c2e6f9cbc069c9d55c7006d18b6b34b4d))

- Table checkbox fixed
  ([`7e6244c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7e6244c5d3698e6fea944b9501064470b6c884c7))

### Features

- Step for x and y can be linked or separated
  ([`16ab746`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/16ab746f54007ee0647b6602b7d74a4a59401705))

- User can choose if to save coordinates when moving to absolute coordinates
  ([`6324199`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/632419929921fbe4e970149ce8d4e617566f71fc))

### Refactoring

- Change_step_size generalised to one function
  ([`aede198`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aede1988ece9d40e2319b5342d761d53f4850882))

- Code cleaned up
  ([`1241fc7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1241fc7516ff61129f366bb8e032a674e1de89ab))

- Doublevalidationdelegate moved to qt_utils
  ([`ca099ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ca099eced33dc72a00a123d837b509d8b8df3218))

- Init_ui separated into multiple sections for each ui functionality
  ([`b9920f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b9920f3b6c6cd9ad1f8ac1ac41cd293e43c53c1e))

- Sync_step_sizes generalised to one function
  ([`9beaa8f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9beaa8f8cf28c0466c062d5f3e6ddede84af617d))


## v0.14.2 (2023-09-05)

### Bug Fixes

- Bec_config initialisation by command line argument
  ([`b7a1b8b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b7a1b8bca1b89df859c9ed0ed17862bb6d533de7))


## v0.14.1 (2023-09-05)


## v0.14.0 (2023-09-05)

### Bug Fixes

- Checkbox visibility toggle is working.
  ([`a178c43`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a178c434b1d9efc1795b6f5115e2a8b9685ccdf2))

- Gui default tab changed to coordinates table
  ([`3c74fa5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c74fa59b7b83976b13afc821c1333868e62a686))

- Highlight disapear with new motor
  ([`3fb8651`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3fb8651dd5777861488928b414d5bdacb517d0e9))

- Motor position points can be switched on/off if points were deleted
  ([`5b30dfd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5b30dfd43fcbe4b9941e26cab76005ffeb21d95f))

- New points do not make invisible points visible again
  ([`fb10551`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fb105513e52bcd9c62dfead16e91b45ecd817612))

- Saved coordinates can be removed from table and from the map again
  ([`c32e95a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c32e95a57d3faec46652b413581d830698855367))

### Features

- Enable gui button, in the case that motor movement is not finished
  ([`84155d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/84155d22640e229820fa5104975d2675f63cef31))

- Saved coordinates are shown on the map
  ([`0ca665a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ca665a1e91d9c5dee9af0218c2e211de8304b26))


## v0.13.0 (2023-09-05)

### Bug Fixes

- Precision updated correctly
  ([`172ccc6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/172ccc69056380abcddf572f668a4ddbd5d34eec))

- Spinbox limits in ui file
  ([`8de08cf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8de08cf9ccb092b3cfa5cf751f69fbf5edd2b217))

### Features

- Crosshair highlight at motor position
  ([`9228e5a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9228e5aea3d5e4192733539643654fd635c63559))

- Go, set, save current coordinates and keyboard shortcuts
  ([`5d6a328`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d6a328728a017eb4f1d191c96d2659800d41941))

- Increase step size double with key bindings
  ([`e9ef1e3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e9ef1e315bc7222c38c1f2f3f410f5cdff994f08))


## v0.12.0 (2023-09-04)

### Bug Fixes

- Error message if motor do not have limits attribute
  ([`bf93b02`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bf93b02cdc82086b32e2bd16f4b506c1bb76c65d))

### Documentation

- Added documentation to all classes and methods
  ([`4afaa1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4afaa1b0ce1f29e4193e6999ecc13b1f0f662213))

### Features

- Config from .yaml file
  ([`1a67758`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1a677584708e1c91491fe84db169103bdda488e5))

- Removal of motor configurations from user
  ([`34212d4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/34212d4d45c88a7bba75f289a25e5488ff95fc73))


## v0.11.0 (2023-09-04)

### Bug Fixes

- Colorbutton change now symbols as well
  ([`6d2e1c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6d2e1c9d08595a45f502287c6490905e8df3db10))

- User selected colors are preserved with the new scan
  ([`8e7885f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8e7885f36dd2812e3285c4d2d101212055644c7b))

### Features

- Colorbutton next to each curve in the table to be able to set up colors
  ([`2c6719c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2c6719cf390e6638cadbc814eb0c085bb45c3c6c))


## v0.10.0 (2023-09-01)

### Bug Fixes

- Add max number of columns according to the number of plots
  ([`fbd71c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fbd71c131386508a9ec7bb5963afefc13f8b1618))

- Bec_dispatcher.py can take multiple workers as a list
  ([`7bcf88d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7bcf88d5eb139aa3cf491185b9fb3f45aa5e39a2))

- Check if num_columns is not higher that actual number of plots
  ([`aac6e17`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/aac6e172f6e4583e751bee00db6f381aaff8ac69))

- Columns span generalised for any number of columns
  ([`2d851b6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d851b6b4eb0002e32908c2effbfb79122f18c24))

- Config.yaml can be passed as a console argument to extreme.py
  ([`b8aa373`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b8aa37321d6ac0ebd9f2237c8d2ed6594b614b57))

- More specific error messages
  ([`583e643`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/583e643dacac3d7aaa744751baef2da69f6f892e))

### Documentation

- Fixed documentation
  ([`2f7c1b9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2f7c1b92a9624741f6dea44fc8f3c19a8a506fd9))

- Updated documentation and TODOs
  ([`0ebe35a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ebe35ac7a144db84c323f9ecb85dfdf6de66c21))

### Features

- Error messages if name or entry is wrong
  ([`415c4ee`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/415c4ee3f232c02ee5a00a82352c7fbb0d324449))

- Load and export configuration into .yaml from GUI
  ([`e527353`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e5273539741a1261e69b1bf76af78c7c1ab0d901))

- Multi window interface created for extreme BL
  ([`69c38d6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/69c38d67e4e9b8a30767f6f67defce6c5c2e5b16))

- Number of columns can be dynamically changed
  ([`65bfccc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/65bfccce8fce158150652fead769721de805d99e))

### Refactoring

- Changed the .yaml structure and the logic of the whole app how to access
  ([`96a88d2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/96a88d23154d7f5578ee742c91feb658a74d7ede))

- Moved colormap related static methods to qt_utils colors.py
  ([`1a06dd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1a06dd75346fb9e85e2c0392ce8f48021c84a6fd))


## v0.9.0 (2023-08-29)

### Features

- Better color coding of curves
  ([`0eff18f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0eff18f5a074ea806d43d52ae72bf87f0187a26d))

- Migrate to .yaml config file instead of argparse
  ([`a9f1688`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a9f16884b0b274e36fdb531b56a26343692a78f5))

### Refactoring

- X_value and y_values arguments separately
  ([`abd88f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/abd88f71098e0cc9fbab5506c12de3c71029d9ba))


## v0.8.1 (2023-08-29)

### Bug Fixes

- Added missing local .ui file
  ([`f0589b7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f0589b79ec7f50ee9d040b911d1874b4232659d5))


## v0.8.0 (2023-08-29)

### Bug Fixes

- Crosshair snaps correctly to x dataset
  ([`2ed5d72`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2ed5d7208c42f8a1175a49236d706ebf503875e4))

- User can disable dap_worker and just choose signals to plot
  ([`cab5354`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cab53543e644921df69c57c70ad2b3a03bbafcc1))

### Features

- Crosshair snapped to x, y data automatically, clicked coordinates glows
  ([`49ba6fe`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/49ba6feb3a8494336c5772a06e9569d611fc240a))

- Crosshair snaps to data, but it is activated with button due to debug
  ([`223f102`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/223f102aa9f0e625fecef37c827c55f9062330d7))

- Dap fit plotted as curve, data as scatter
  ([`118f6af`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/118f6af2b97188398a3dd0e2121f73328c53465b))

- Fit table hardcode to "gaussian_fit_worker_3"
  ([`3af57ab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3af57abc4888dfcd0224bf50708488dc8192be84))

- Oneplot can receive one motor and one monitor signal
  ([`ff545bf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff545bf5c9e707f2dd9b43f9d059aa8605f3916b))

- Oneplot initialized as an example app for plotting motor vs monitor signals + dispatcher loop over
  msg
  ([`98c0c64`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/98c0c64e8577f7e40eb0324dfe97d0ae4670c3a2))

- User can specify tuple of (x,y) devices which wants to plot
  ([`3344f1b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3344f1b92a7e4f4ecd2e63c66aa01d3a4c325070))

### Refactoring

- Plot update via proxy
  ([`fc4b542`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc4b54239eaf3eb9608fb5f916ce61df5830f7c6))


## v0.7.0 (2023-08-28)

### Bug Fixes

- Init_motor_map receive motor position from motor_thread
  ([`95ead71`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/95ead7117e59e0979aec51b85b49537ab728cad4))

- Line_plot.py default changed back to "gauss_bpm"
  ([`64708bc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/64708bc1b2e6a4256da9123d0215fc87e0afa455))

- Motor movement absolute fixed - movement by thread
  ([`11aa15f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/11aa15fefda7433e885cc8586f93c97af83b0c48))

- Motor selection is disabled while motor is moving
  ([`c7e35d7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c7e35d7da69853343aa7eee53c8ad988eb490d93))

### Features

- Ability to choose how many points should be dimmed before reaching the threshold + total number of
  point which should be stored.
  ([`9eae697`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9eae697df8a2f3961454db9ed397353f110c0e67))

- Controls are disabled while motor is moving and enabled when motor movement is finished
  ([`ed84293`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ed842931971fbf87ed2f3e366eb822531ef5aacc))

- Delete coordinate table row by DELETE or BACKSPACE key
  ([`5dd0af6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5dd0af6894a5d97457d60ef18b098e40856e4875))

- Going to absolute coordinates saves coordinate in the table for later use with tag
  ([`8be98c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8be98c9bb6af941a69c593c62d5c52339d2262bc))

- Keyboard shortcut to go to coordinates
  ([`3c0e595`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3c0e5955d40a67935b8fb064d5c52fd3f29bd1a1))

- Labels of current motors are shown in motors limits
  ([`413e435`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/413e4356cfde6e2432682332e470eb69427ad397))

- Map of motor position
  ([`e6952a6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6952a6d13c84487fd6ab08056f1f5b46d594b8a))

- Motor coordinates are now scatter instead of image
  ([`3f6d5c6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3f6d5c66411459703c402f7449e8b1abae9a2b08))

- Motor limits can be changed by spinBoxes
  ([`2d1665c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2d1665c76b8174d9fffa3442afa98fe1ea6ac207))

- Motor move to absolute (X,Y) coordinates
  ([`cbe27e4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cbe27e46cfb6282c71844641e1ed6059e8fa96bf))

- Motor selection
  ([`cab32be`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cab32be0092185870b5a12398103475342c8b1fd))

- Motor_example.py created, motor samx and samy can be moved by buttons
  ([`947ba9f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/947ba9f8b730e96082cb51ff6894734a0e119ca1))

- New GUI
  ([`0226188`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0226188079f1dac4eece6b1a6fa330620f1504bc))

- Setting map according to motor limits
  ([`512e698`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/512e698e26d9eef05b4f430475ccc268b68ad632))

- Speed and frequency can be updated from GUI
  ([`f391a2f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f391a2fd004f1dc8187cfe12d60f856427ae01ec))

- Speed and frequency is retrieved from devices
  ([`ce98164`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ce9816480b82373895b602d1a1bca7d1d9725f01))

- Stop movement function, one callback function for 2 motors, move_finished is emitted in move_motor
  function not in callback
  ([`187c748`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/187c748e87264448d5026d9fa2f15b5fc9a55949))

- Switch for keyboard shortcuts for motor movement
  ([`cac4562`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cac45626fc9a315f9012b110760a92e27e5ed226))

- Table with coordinates getting initial coordinates of motor
  ([`92388c3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/92388c3cab7e024978aaa2906afbd698015dec66))

- Total number of points, scatter size and number of point to dim after last position can be changed
  from GUI
  ([`e0b52fc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e0b52fcedca46d913d1677b45f9815eccd92e8f7))

### Refactoring

- Folder organization changed
  ([`a2f7aa5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a2f7aa58f9639b76b4243d4d5f5bf0efd7b98054))

- Getting motor limits and coordinates moved to MotorControl(QThread)
  ([`349c06b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/349c06bcac6c61c96681a00dd846741898dedf30))

- Introduced MotorActions enum to replace hardcoded strings + project cleanup
  ([`7575c91`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7575c91c9949a4c6b0c92efa24757509b476c086))

- Migrate to use just np.array for tracking position, only latest N points are being dimmed.
  ([`3e408b3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3e408b304ba6b755fc472ea0d39d457b93b55be9))

- Motor movement as a QThread
  ([`af2fcff`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/af2fcffd5f4efa49e3cd728e4d481665584af941))


## v0.6.3 (2023-08-17)

### Bug Fixes

- Crosshair handles dynamic changes of number of curves in 1D plot
  ([`242737b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/242737b516af7c524a6c8a98db566815f0f4ab65))

### Documentation

- Crosshair class documentation
  ([`8a60cad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8a60cad9187df2b2bc93dc78dd01ceb42df9c9af))

### Testing

- Crosshair mouse_moved signals for 1D and 2D
  ([`2fa1755`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2fa175517058c2fe8f41f3596b4855782e5c0a86))


## v0.6.2 (2023-08-17)

### Bug Fixes

- Correct coordinates for cursor table
  ([`ce54daf`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ce54daf754cb2410790216585467c0ffcc8e3587))


## v0.6.1 (2023-08-14)

### Bug Fixes

- Crosshair snaps to correct coordinates also with logx and logy
  ([`167a891`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/167a891c474b09ef7738e473c4a2e89dbbcbe881))


## v0.6.0 (2023-08-11)

### Features

- New GUI for line_plot.py
  ([`b57b3bb`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b57b3bb1afc7c85acc7ed328ac8a219f392869f1))

### Refactoring

- Rename line_plot to basic_plot
  ([`23c206d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/23c206d550c0971a6090863ae0064d9988d41a7b))

- Renamed line_plot.ui to basic_plot.ui
  ([`3768015`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/37680152fb9945ec49410a75e9f80399c3d0bc32))


## v0.5.0 (2023-08-11)

### Bug Fixes

- Dispatcher argparse and scan_plot tests
  ([`67f619e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67f619ee897e0040c6310e67d69fbb2e0685293d))

- Gui event removing bugs
  ([`a9dd191`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a9dd191629295ca476e2f9a1b9944ff355216583))

### Features

- Add generic connect function for slots
  ([`6a3df34`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6a3df34cdfbec2434153362ded630305e5dc5e28))

- Add possibility to provide service config
  ([`8c9a9c9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8c9a9c93535ee77c0622b483a3157af367ebce1f))

### Refactoring

- Register scan_segment callback directly
  ([`dfce55b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dfce55b6751f27a2805ce683cb08859312650379))

* this allows to skip client.start() setup


## v0.4.0 (2023-08-11)

### Bug Fixes

- Fix examples when run directly as a script
  ([`cd11ee5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cd11ee51c1c725255e748a32b89a74487e84a631))

- Fixed logic in data subscription
  ([`c2d469b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c2d469b4543fcf237b274399b83969cc2213b61b))

- Module paths
  ([`e7f644c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e7f644c5079a8665d7d872eb0b27ed7da6cbd078))

- Plotting latest 1d curves
  ([`378be81`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/378be81bf6dd5e9239f8f1fb908cafc97161c79d))

- Q selection for gui_event signal
  ([`0bf452a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0bf452ad1b7d9ad941e2ef4b8d61ec4ed5266415))

- Scan_plot to accept metadata from dap signal
  ([`7bec0b5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7bec0b5e6c1663670f8fcc2fc6aa6c8b6df28b61))

* as a consequence of 18b5d46678619a972815532629ce96c121f5fcc9

- Testing the data structure of plotting
  ([`4fb0a3b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4fb0a3b058957f5b37227ff7c8e9bdf5259a1cde))

### Features

- 2d plot updating
  ([`d32088b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d32088b643a4d0613c32fb464a0a55a3b6b684d6))

- Add BECScanPlot2D
  ([`67905e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67905e896c81383f57c268db544b3314104bda38))

- Add disconnect_dap_slot
  ([`1325704`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1325704750ebab897e3dcae80c9d455bfbbf886f))

- Add display_ui_file.py
  ([`91d8ffa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/91d8ffacffcbeebdf7623caf62e07244c4dcee16))

- Added Legend to plot
  ([`0feca4b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0feca4b1578820ec1f5f3ead3073e4d45c23798b))

- Added qt_utils package with general Crosshair function
  ([`5353fed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5353fed7bfe1819819fa3348ec93d2d0ba540628))

- Changed from PlotItem to GraphicsLayoutWidget, added LabelItem
  ([`075cc79`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/075cc79d6fa011803cf4a06fbff8faa951c1b59f))

- Cursor coordinate as a QTable
  ([`a999f76`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a999f7669a12910ad66e10a6d2e75197b2dce1c2))

- Cursor universal for 1D and 2D
  ([`f75554b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f75554bd7b072207847956a8720b9a62c20ba2c8))

- Cursor universal signals
  ([`20e9516`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/20e951659558b7fc023e357bfe07d812c5fd020a))

- Emit the full bec message to slots
  ([`1bb3020`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1bb30207038f3a54c0e96dbbbcd1ea7f6c70eca2))

* some widgets will require metadata for their operation

- Inherit from GraphicsView for consistency with 2D plot
  ([`d8c101c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8c101cdd7f960a152a1f318911cac6eecf6bad4))

- Metadata available on_dap_update
  ([`18b5d46`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/18b5d46678619a972815532629ce96c121f5fcc9))

- Plotting from streamer
  ([`bb806c1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bb806c149dee88023ecb647b523cbd5189ea9001))

### Refactoring

- Changed from bec client to dispatcher
  ([`14e92e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/14e92e8d6839616191aa0a0cdae4ed04eaaa7520))

- Made client a module import
  ([`dc5fd99`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/dc5fd9959f6697a83694a9b923cea5996e2e87b1))

- Move plugins into a separate folder
  ([`b16406a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b16406a7fc1a6c169e3db466a0cdc2be50d74f5b))

- Use BECClient for cb on scan_segment
  ([`ff534ad`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ff534ad67ffea1e7ebf94366a7c8f7b336cb8776))

- Widgets setup their own connections
  ([`87163fd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/87163fde32cdc4fad3404cb6ac2bc3767db6f953))


## v0.3.0 (2023-07-19)

### Bug Fixes

- Add warning for non-existing signalz
  ([`48075e4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/48075e4fe3187f6ac8d0b61f94f8df73b8fd6daf))

- Documentation and bugfix for mouse_moved
  ([`a460f3c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a460f3c0bd7b9e106a758bc330f361868407b1e3))

### Build System

- Fixed setup.cfg metadata
  ([`65b94ec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/65b94ecd45b540f03346caf40dc67253b4b8f4c5))

### Continuous Integration

- Added security tests
  ([`81b6355`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/81b6355932a936be9156dfd9d7c92f868226d3ed))

- Fixed python-semantic-release version to 7.*
  ([`cc69cf9`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cc69cf9b61fa23e447c48d70d0b9d72436a484fd))

- Fixed stage name
  ([`004faec`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/004faecc69a2638fc6bad4cfe6ff5be3a1e6f8d7))

### Documentation

- Add notes about qt designer install via conda-forge
  ([`d8038a8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8038a8cd0efa3a16df403390164603e4e8afdd8))

- Added license
  ([`db2d33e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db2d33e8912dc493cce9ee7f09d8336155110079))

### Features

- Add auto-computed color_list from colormaps
  ([`3e1708b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3e1708bf48bc15a25c0d01242fff28d6db868e02))

- Add functionality for plotting multiple signals
  ([`10e2906`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/10e29064455f50bc3b66c55b4361575957db1489))

- Added ctrl_c from grum
  ([`8fee13a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8fee13a67bef3ed6ed6de9d47438f04687f548d8))

- Added lineplot widget
  ([`989a3f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/989a3f080839b98f1e1c2118600cddf449120124))

### Refactoring

- Added pylintrc file; cleanup
  ([`5e5c0ed`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5e5c0ed980d7e6ea9c12b151f51bf79e1f580d52))

### Testing

- Add test for line_plot
  ([`d37fbf5`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d37fbf5c4f0f413e5b295566027293be3b10b6af))

- Fixed client mock
  ([`9883caa`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9883caa1b3c114e5d0e50014b8f1546bdd59b350))

- Removed deprecated waitforwindowshown method of qtbot
  ([`b790dd2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b790dd2d081e824f9094afc32546d4b70a018119))


## v0.2.1 (2023-07-13)

### Bug Fixes

- Fixed bec_lib dependency
  ([`86f4def`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/86f4deffd899111e8997010487ec54c6c62c43ab))

- Fixed setup config (wrong name)
  ([`947db1e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/947db1e0f32b067e67f94a7c8321da5194b1547b))

### Build System

- Added black as dev dependency
  ([`b5f7b4f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b5f7b4feee63eda57af977c15993dfba48c210f6))

### Refactoring

- Added example usage within main statement
  ([`4ee18ac`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4ee18ac3af2b414b6bf2757a02a8e86e94593db1))

### Testing

- Added tests for scan plot
  ([`f10de38`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f10de383a84ad94b7ba4e089ab7bd103d4693a20))


## v0.2.0 (2023-07-13)

### Features

- Move ivan's qtwidgets to bec-widgets
  ([`34e5ed2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/34e5ed2cf7e6128a51c110db8870d9560f2b2831))

### Refactoring

- Added .git_hook
  ([`550c368`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/550c36860efaad0a77b65d209d36b4eab0e5a650))


## v0.1.0 (2023-07-11)

### Build System

- Setting up repo
  ([`88f5aca`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88f5aca2ddc8ad6d1681c674c5d845e076c4de8e))

### Continuous Integration

- Added ci file
  ([`fc6382b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fc6382b8c7bf407650a176669606e6dd2916bf41))

- Testing ci
  ([`b089903`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/b089903ad9bca7bd6bd9700910da45554f433e04))

- Testing ci
  ([`52f26d1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/52f26d12ff11e8a773cb886daea82b16c181f135))

- Testing ci
  ([`e924337`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e924337ccabfa7530aebf219c432dd373cd1fd9b))

- Testing ci
  ([`14c59f7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/14c59f76fb465ec50aa8ef1f01c8560faa22ee8a))

- Testing ci
  ([`8be84a7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8be84a7eced5fc0176139accb03c0c4618318632))

- Testing ci
  ([`185fbe6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/185fbe6061265dbc53106af50fbe16446d04d2a2))

- Testing ci
  ([`78fd26a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/78fd26ad8dfaaa67107c8ab41ac1d75c6bea0c30))

- Testing ci
  ([`0b7a659`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0b7a659d88c13b73bfdbd71059abe45bcbca5898))

- Testing ci
  ([`4250d47`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4250d47ff885f2863d41a31b8e7dea090164db6c))

### Features

- Added config plotter
  ([`db274c6`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/db274c644f643f830c35b6a92edd328bf7e24f59))
