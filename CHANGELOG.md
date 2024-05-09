# CHANGELOG



## v0.53.0 (2024-05-09)

### Ci

* ci: use formatter config of toml file ([`5cc816d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5cc816d0af73e20c648e044a027c589704ab1625))

### Documentation

* docs: update install instructions ([`57ee735`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57ee735e5c2436d45a285507cdc939daa20e8e8f))

### Feature

* feat: moved to pyproject.toml; closes #162 ([`c86ce30`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c86ce302a964d71ee631f0817609ab5aa0e3ab0f))

### Fix

* fix: fixed semver job and upgraded to v9 ([`32e1a9d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/32e1a9d8472eb1c25d30697d407a8ffecd04e75d))

### Refactor

* refactor: applied formatter ([`4117fd7`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4117fd7b5b2090ff4fb7ad9e0d92cc87cd13ed5f))


## v0.52.1 (2024-05-08)

### Fix

* fix(docstrings): docstrings formating fixed for sphinx to properly format readdocs ([`7f2f7cd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7f2f7cd07a14876617cd83cedde8c281fdc52c3a))


## v0.52.0 (2024-05-07)

### Ci

* ci: fixed support for child pipelines ([`e65c7f3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e65c7f3be895ada407bd358edf67d569d2cab08e))

### Feature

* feat(utils/layout_manager): added GridLayoutManager to extend functionalities of native QGridLayout ([`fcd6ef0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/fcd6ef0975dc872f69c9d6fb2b8a1ad04a423aae))

* feat(widget/dock): BECDock and BECDock area for dockable windows ([`d8ff8af`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d8ff8afcd474660a6069bbdab05f10a65f221727))

### Fix

* fix(widgets/dock): BECDockArea close overwrites the default pyqtgraph Container close + minor improvements ([`ceae979`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ceae979f375ecc33c5c97148f197655c1ca57b6c))

### Refactor

* refactor(widget/plots): WidgetConfig changed to SubplotConfig ([`03fa1f2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/03fa1f26d0fa6b58ed05556fb2438d1e62f6c107))


## v0.51.0 (2024-05-07)

### Build

* build(cli): changed repo name to bec_widgets ([`799ea55`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/799ea554de9a7f3720d100be4886a63f02c6a390))

* build(setup): fakeredis added to dev env ([`df32350`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df323504fea024a97304d96c2e39e61450714069))

* build(setup): PyQt6 version is set to 6.7 ([`0ab8aa3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0ab8aa3a2fe51b5c38b25fca44c1c422bb42478d))

### Ci

* ci: added rule for parent-child pipelines ([`e085125`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e0851250eecb85503db929d37f75d2ba366308a6))

### Feature

* feat(utils): added plugin helper to find and load ([`5ece269`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ece269adb0e9b0c2a468f1dfbaa6212e86d3561))


## v0.50.2 (2024-04-30)

### Fix

* fix: &#39;disconnect_slot&#39; has to be symmetric with &#39;connect_slot&#39; regarding QtThreadSafeCallback ([`0dfcaa4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/0dfcaa4b708948af0a40ec7cf34d03ff1e96ffac))


## v0.50.1 (2024-04-29)

### Fix

* fix(cli): BECFigure takes the port to connect to redis from the current BECClient, supporting plugins ([`57cb136`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/57cb136a098e87a452414bf44e627edb562f6799))


## v0.50.0 (2024-04-29)

### Feature

* feat(plots): universal cleanup and remove also for children items ([`381d713`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/381d713837bb9217c58ba1d8b89691aa35c9f5ec))

* feat(rpc/rpc_register): singleton rpc register for all rpc connections for session ([`a898e7e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a898e7e4f14e9ae854703dddbd1eb8c50cb640ff))

### Fix

* fix(widgets/figure): access pattern changed for getting widgets by coordinates for rpc ([`13c018a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/13c018a79704a7497c140df57179d294e43ecffa))

* fix(plots): cleanup policy reviewed for children items ([`8f20a0b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8f20a0b3b1b5dd117b36b45645717190b9ee9cbf))

* fix(rpc/client_utils): getoutput more transparent + error handling ([`6b6a6b2`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6b6a6b2249f24d3d02bd5fcd7ef1c63ed794c304))

* fix(rpc_register): thread lock for listign all connections ([`2ca3267`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2ca32675ec3f00137e2140259db51f6e5aa7bb71))

### Test

* test(cli/rpc_register): e2e RPCRegister ([`4f261be`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4f261be4c7cfe54501443d031f9266f4f838f6e2))

* test(cli/rpc_register): rpc_register tests added ([`40eb75f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/40eb75f85a4d99d498b086a37e799276a9d2ac3f))


## v0.49.1 (2024-04-26)

### Build

* build(pyqt6): fixing PyQt6-Qt6 package to 6.6.3 ([`a222298`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a22229849cbb57c15e4c1bae02d7e52e672f8c4c))

### Fix

* fix(widgets/editor): qscintilla editor removed ([`ab85374`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ab8537483da6c87cb9a0b0f01706208c964f292d))


## v0.49.0 (2024-04-24)

### Feature

* feat(rpc/client_utils): timeout for rpc response ([`6500a00`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6500a00682a2a7ca535a138bd9496ed8470856a8))

### Fix

* fix(rpc/client_utils): close clean up policy for BECFigure ([`9602085`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9602085f82cbc983f89b5bfe48bf35f08438fa87))


## v0.48.0 (2024-04-24)

### Feature

* feat(cli): added auto updates plugin support ([`6238693`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6238693ffb44b47a56b969bc4129f2af7a2c04fe))


## v0.47.0 (2024-04-23)

### Feature

* feat(utils/thread_checker): util class to check the thread leakage for closeEvent in qt ([`71cb80d`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/71cb80d544c5f4ef499379a431ce0c17907c7ce8))

### Refactor

* refactor(utils/container_utils): part of the logic regarding locating widgets moved from BECFigure to utility class ([`77ff796`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/77ff7962cc91bce15d1c91b67b75b66fbea612c3))


## v0.46.7 (2024-04-21)

### Fix

* fix(plot/image): monitors are now validated with current bec session ([`67a99a1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/67a99a1a19c261f9a1f09635f274cd9fbfe53639))


## v0.46.6 (2024-04-19)

### Ci

* ci: changed ophyd default branch to main ([`81484e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/81484e8160a4a09907313ed747c27ab3b6cbfdc4))

### Fix

* fix(cli): fixed support for devices as cli input ([`1111610`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1111610f3206c5c46db6b4bd1e8827f1a4cd9e3f))


## v0.46.5 (2024-04-19)

### Test

* test(rpc/bec_figure): test_rpc_plotting_shortcuts_init_configs extended by testing scatter z gradient for BECWaveform through RPC ([`a156803`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a1568033899bbcdbd457e697d6c8d478df26ba54))
