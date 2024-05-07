# Changelog

<!--next-version-placeholder-->

## v0.51.0 (2024-05-07)

### Feature

* **utils:** Added plugin helper to find and load ([`5ece269`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5ece269adb0e9b0c2a468f1dfbaa6212e86d3561))

## v0.50.2 (2024-04-30)

### Fix

* 'disconnect_slot' has to be symmetric with 'connect_slot' regarding QtThreadSafeCallback ([`0dfcaa4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0dfcaa4b708948af0a40ec7cf34d03ff1e96ffac))

## v0.50.1 (2024-04-29)

### Fix

* **cli:** BECFigure takes the port to connect to redis from the current BECClient, supporting plugins ([`57cb136`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/57cb136a098e87a452414bf44e627edb562f6799))

## v0.50.0 (2024-04-29)

### Feature

* **plots:** Universal cleanup and remove also for children items ([`381d713`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/381d713837bb9217c58ba1d8b89691aa35c9f5ec))
* **rpc/rpc_register:** Singleton rpc register for all rpc connections for session ([`a898e7e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a898e7e4f14e9ae854703dddbd1eb8c50cb640ff))

### Fix

* **widgets/figure:** Access pattern changed for getting widgets by coordinates for rpc ([`13c018a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/13c018a79704a7497c140df57179d294e43ecffa))
* **plots:** Cleanup policy reviewed for children items ([`8f20a0b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8f20a0b3b1b5dd117b36b45645717190b9ee9cbf))
* **rpc/client_utils:** Getoutput more transparent + error handling ([`6b6a6b2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6b6a6b2249f24d3d02bd5fcd7ef1c63ed794c304))
* **rpc_register:** Thread lock for listign all connections ([`2ca3267`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2ca32675ec3f00137e2140259db51f6e5aa7bb71))

## v0.49.1 (2024-04-26)

### Fix

* **widgets/editor:** Qscintilla editor removed ([`ab85374`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ab8537483da6c87cb9a0b0f01706208c964f292d))

## v0.49.0 (2024-04-24)

### Feature

* **rpc/client_utils:** Timeout for rpc response ([`6500a00`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6500a00682a2a7ca535a138bd9496ed8470856a8))

### Fix

* **rpc/client_utils:** Close clean up policy for BECFigure ([`9602085`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9602085f82cbc983f89b5bfe48bf35f08438fa87))

## v0.48.0 (2024-04-24)

### Feature

* **cli:** Added auto updates plugin support ([`6238693`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6238693ffb44b47a56b969bc4129f2af7a2c04fe))

## v0.47.0 (2024-04-23)

### Feature

* **utils/thread_checker:** Util class to check the thread leakage for closeEvent in qt ([`71cb80d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/71cb80d544c5f4ef499379a431ce0c17907c7ce8))

## v0.46.7 (2024-04-21)

### Fix

* **plot/image:** Monitors are now validated with current bec session ([`67a99a1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/67a99a1a19c261f9a1f09635f274cd9fbfe53639))

## v0.46.6 (2024-04-19)

### Fix

* **cli:** Fixed support for devices as cli input ([`1111610`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1111610f3206c5c46db6b4bd1e8827f1a4cd9e3f))

## v0.46.5 (2024-04-19)

### Fix

* **widgets/figure:** Individual cleanup disabled, making stuck rpc ([`ff52100`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ff52100e234debdfb5ccc0869352cfafde52ac93))
* **plots/waveform:** Colormap is correctly passed from BECFigure ([`026c079`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/026c0792bee25723013fffe57ccff10d9b652913))

## v0.46.4 (2024-04-16)

### Fix

* Renaming of bec_client to bec_ipython_client ([`4da625e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4da625e4398bdd937c2b788592f15f7530148292))
* **plots/motor_map:** User can get data as dict from BECMotorMap ([`c12f2ce`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c12f2cee80b13137a2b70e2d121a079e20d124e2))
* **plots/image:** User can get data as np.ndarray from BECImageItem ([`c2c583f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c2c583fce6f28981990c504dd065705124e40e44))
* **rpc/server:** Server can accept client or dispatcher ([`ecdf0f1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ecdf0f122b628ee378b80793d498cedafe50fbf8))

## v0.46.3 (2024-04-11)

### Fix

* **test_fake_redis:** TestMessage fixed to pydantic BaseModel ([`0b86a00`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0b86a0009d9366b710294a3ab55cb9f4894472c0))
* **plots/motor_map:** Removed single callback flag for connecting device_readback motors ([`49327a8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/49327a8dbde270c67bc0ce7c757fd4a3eae118b4))
* **cli/client_utils:** Print_log is buffered; add output processing thread ([`285bf01`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/285bf0164b6deb91678f03ab2a190680b6d83a02))
* Producer->connector ([`9def373`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9def3734afb361ac2d5cc933661766cdc440e09d))

## v0.46.2 (2024-04-10)

### Fix

* **widget/plots:** Added "get_config" to all children of `BECConnector` to USER_ACCESS ([`ee617b7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ee617b73a2fcad8194394182fcecb0dd4f583a8e))

## v0.46.1 (2024-04-10)

### Fix

* **rpc/client:** Correct name for RPC class BECWaveform (instead of BECWaveform1D) ([`cf29035`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cf29035e283e55efa547cbac88e8b622190dfc4d))

## v0.46.0 (2024-04-09)

### Feature

* **plot/waveform1d:** BECWaveform1D can show z data of scatter coded to different detector like BECMonitor2DScatter; BECWaveform1D name changed to BECWaveform ([`3d399ba`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3d399ba1f5d85bc67964febcf8921355f9f1c285))

## v0.45.0 (2024-03-26)

### Feature

* **plots/bec_figure:** Motor Map integrated to BECFigure ([`b8519e8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b8519e8770f8ffc46a1255c18119fc7978ff1d39))
* **plots/bec_motor_map:** BECMotorMap build on BECPlotBase ([`0f69c34`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0f69c346cd24b7afcd23f444525a170e062b0368))

### Documentation

* Added api reference; closes #123 ([`88014d2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/88014d24c1c272a6deea7436a6fa058bdb06fb57))

## v0.44.5 (2024-03-25)

### Fix

* Circular imports ([`c5826f8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c5826f8887ed44d15d05c8ed0e337080b3146c5a))

## v0.44.4 (2024-03-22)

### Fix

* **cli/server:** Thread heartbeat replaced with QTimer ([`e6b0657`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e6b065767c8605aaef6ed6032ba893d3900b552c))
* **cli/server:** Removed BECFigure.start(), the QApplication event loop is started by server.py ([`f3a96de`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f3a96dedd7ba49f9a1b713f6a5565f2b3dbb141e))

## v0.44.3 (2024-03-21)

### Fix

* **cli:** Don't call user script if gui is not alive ([`a92aead`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a92aead7698fa98d6f7f582d030845d0b940ea2d))
* **cli:** Added gui heartbeat ([`882cf55`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/882cf55fc5266a2cfb610702e834badff3ad0428))

## v0.44.2 (2024-03-20)

### Fix

* **utils/bec_dispatcher:** Try/except to start client, to avoid crash when redis is not running ([`9ccd4ea`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9ccd4ea235be4c4332045b7a7f09d6cc6291f7ff))
* **utils/bec_dispatcher:** Bec_dispatcher adjusted to the new BECClient; dropped support to inject bec_config.yaml, instead BECClient can be passed as arg ([`86416d5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/86416d50cb850b42d312fe17fc46f0b4743dc940))

## v0.44.1 (2024-03-19)

### Fix

* **examples/motor_compilation:** Motor_control_compilations.py do not have any hardcoded config anymore ([`14f901f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/14f901f1bea2ba7b79903c4743e37384e11533d3))

## v0.44.0 (2024-03-18)

### Feature

* **cli:** Added update script to BECFigure ([`9049e0d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9049e0d27fe9a3860e21ffc3b350eb69e567b71c))

### Fix

* **cli:** Removed hard-coded signal ([`203ae09`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/203ae0960688608fb609a742a23e5994bfe9805c))
* **cli:** Fixed cleanup procedure ([`2d39c5e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2d39c5e4d18bbb66a5f3340fce7f8944dd4ba19f))

## v0.43.2 (2024-03-18)

### Fix

* **cli/server:** Added QApplications to enter separate QT event loop ensuring that QT objects are not deleted ([`d0f9bf1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d0f9bf17339296a60301e5e6ffe602db369c6c7c))

## v0.43.1 (2024-03-15)

### Fix

* **plots/image:** Same access pattern for image and image_item for setting up parameters, autorange of z scale disabled by default ([`b8d4e69`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b8d4e697ac2a5929a1374ce1778046efc3f8187a))
* **widget/various:** Corrected USER_ACCESS methods for children widgets to include inherited methods to RPC ([`4664661`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4664661cfb4e8bd4a6adb71f2050b25d0b4f3d36))
* **widgets/figure:** Added widgets can be accessed as a list (fig.axes) or as a dictionary (fig.widgets) ([`fcf918c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fcf918c48862d069b9fe69cbba7dbecbe7429790))

## v0.43.0 (2024-03-14)

### Feature

* **plots/image:** Image processor can run in threaded or non-threaded version ([`4865b10`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4865b10ced6b321974e7b4b4db12786fe21fd916))
* **plots/image:** Change stream processor to QThread with connector.get_last; cleanup method for BECFigure to kill all threads if App is closed during acquisition ([`7ffedd9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7ffedd9cebb382fc22f24a6b0b46823db6378d89))
* **plots/image:** Basic image visualisation, getting data are based on stream_connector (deprecated) ([`9ad0055`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9ad0055336dba50886504a616db6f9f63b23beb3))

### Fix

* **plots/waveform1d:** Curves_data access disabled ([`598479b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/598479bb555a6cd077d5a137052d91314e5af6b7))
* **cli:** Find_widget_by_id for BECImageShow changed to be compatible with RPC logic ([`4ef6ae9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4ef6ae90f2afd5e2442465c11ce5165517cd4218))
* **plots/image:** Access pattern for ImageItems in BECImageShow ([`3362fab`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3362fabed7ccd611b35f524c1970aeefbf3a9faf))
* **cli:** Fix cli connector.send to set_and_publish for gui_instruction_response ([`4076698`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/407669853097b40e6fba7d43da001f083140ad74))

## v0.42.1 (2024-03-10)

### Fix

* **various:** Repo cleanup, removed - [plot_app, one_plot, scan_plot, scan2d_plot, crosshair_example, qtplugins], tests adjusted ([`f3b3c2f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f3b3c2f526d66687b3cc596a5877921953dd0803))

## v0.42.0 (2024-03-07)

### Feature

* **utils/bec_dispatcher:** BECDispatcher can register redis stream ([`4c0a7bb`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4c0a7bbec7abafc7d04a8aaf10dabd7e668fa908))

## v0.41.4 (2024-03-07)

### Fix

* **utils/bec_dispatcher:** BECDispatcher can accept new EndpointInfo dataclass. ([`c319dac`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c319dacb24e64930af258a81484feeadcb1bc341))

## v0.41.3 (2024-03-01)

### Fix

* **cli/generate_cli:** Typing.get_overloads are only used if the python version is higher than 3.11 ([`f386563`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f386563aa162eaca9202af16574860bf3eb5a092))
* **cli/generate_cli:** Added automatic black formatting; added black as a dependency ([`d89f596`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d89f596a5d0f0674b1ef3268a9cfee5e32b64ba5))

## v0.41.2 (2024-02-28)

### Fix

* **utils/bec_dispatcher:** Msg is unp[acked from dict before accessing .content ([`bb1f066`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bb1f066c3c5e5076a8906e309030cfb47a6cad12))

## v0.41.1 (2024-02-26)

### Fix

* **bec_dispatcher:** Handle redis connection errors more gracefully ([`a2ed2eb`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a2ed2ebe00c623eb183b03f8182ffd672fbf9e1e))
* **bec_dispatcher:** Adapt code to redis connector refactoring ([`8127fc2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8127fc2960bebd3e862dbe55ac9401af4a6dccb6))

## v0.41.0 (2024-02-26)

### Feature

* **widgets/waveform1d:** Data can be exported from rendered curve ([`5fc8047`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5fc8047c8ff971cdc2807d02743eae56d288f4d7))
* **widgets/figure:** Clear_all method for BECFigure ([`0363fd5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0363fd5194320a7ea868ef883f8022ea464d0298))
* **widgets/Waveform1D:** Waveform1D can be fully constructed by config ([`9a5c86e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9a5c86ea35178b9cab270fc35e668dd22f3ec8da))
* **widgets/figure.py:** Dark/light theme changer ([`08534a4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/08534a4739ec8e85d82a00ab639411dd0198e9d8))
* **utils/entry_validator:** Possibility to validate add_scan_curve with current BEC session ([`1db77b9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1db77b969bcf9b38716ae3d38bf4695b2b8c1f37))
* **cli:** Added cli interface, rebased ([`a61bf36`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a61bf36df5d54ad44f78479c2474c4e38e68ed26))
* Curve can be modified after adding to the plot ([`684592a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/684592ae37e9dd5328a96018c78ca242e10395b2))
* Waveform1d.py curves can be removed by identifier by order(int) or by curve_id(str) ([`f0ed243`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f0ed243c9197b7d1aab0d99a15e9ba175708ec90))
* Waveform1d.py curves can be stylised; access scan history by index or scanID ([`cba3863`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cba3863e5a9ac1187ea643be67db6cfc36b44ee2))
* Start method for BECFigure, jupyter console .ui added to git ([`1d26b23`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1d26b2322147d9ea5a6a245e1648c00986f80881))
* Added @user_access from bec_lib.utils ([`b827e9e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b827e9eaa77f8b64433bb7a54e40ab5ccd86f4b6))
* Plot can be removed from BECFigure ([`60d150a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/60d150a41193aa7659285cf3612965f1a3c57244))
* Figure.py create widget factory ([`c781b1b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c781b1b4e4121c4ec6fc8871a4cdf6f494913138))
* Waveform1d.py draft ([`565e475`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/565e475ace72ccc103d71ea98af1dcaf04f37861))
* Rpc decorator to add methods to USER_ACCESS ([`b676877`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b6768772424a3ad5ee7e271de19131f8065eef09))
* BECFigure and BECPlotBase created ([`9ef331c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9ef331c272b88f725de9b8497fdf906056c0738b))
* BECConnector -> mixin class for all BEC Widget to hook them to BEC client ([`91447a2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/91447a2d6234de1e8f2bac792e822bfda556abba))

### Fix

* **cli/client_utils:** "__rpc__" pop from msg_results ([`ebb36f6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ebb36f62ddc1c5013435f9e7727648b977b6b732))
* **tests:** BECDispatcher fixture putted back ([`644f103`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/644f1031f6ff27064111565b0882cb8b2544aa2f))
* **cli/rpc:** Rpc client can return any type of object + config dict of the widgets ([`fd711b4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fd711b475f268fbdb59739da0a428f0355b25bac))
* **cli/rpc:** Server access children widget.find_widget_by_id(gui_id) ([`57132a4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/57132a472165c55bf99e1994d09f5fe3586c24da))
* **cli:** Fixed property access, rebased ([`f71dc5c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f71dc5c5abdd6b8b585cb9b502b11ef513d7813e))
* **rpc_server:** Fixed gui_id lookup ([`4630d78`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4630d78fc28109da7daf53e49dd3cdb9b8084941))
* **cli:** Fixed rpc construction of nested widgets ([`da640e8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/da640e888d575b536fdd5d7adbf1df3eda802219))
* **plots/waveform1d:** Pandas import clean up, export curves with none skipped ([`35cd4fd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/35cd4fd6f176ba670fad5d9fec44b305094280d6))
* **widgets/plots:** Added placeholder for cleanup method to BECPlotBase ([`24c7737`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/24c77376b232c3846a1d6be360ec46acc077b48d))
* **widget/figure:** Add cleanup method to disconnect all slots before removing Waveform1D from layout ([`a28b9c8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a28b9c8981d1058e4dc4146463f16c53413e8db9))
* **rpc:** Added annotations to pass py3.9 tests ([`c6bdf0b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c6bdf0b6a5b12c054863b101a3944efc366686cb))
* **rpc:** Connection to on_rpc_update done through bec_dispatcher ([`1c2fb8b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1c2fb8b972d4cb28cead11989461aea010c4571d))
* After removing plot from BECFigure, the coordinates are correctly resigned ([`d678a85`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d678a85957c13c1fda2b52692c0d3b9b7ff40834))
* Removed DI references, fixed set when adding plot by fig ([`7c15d75`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7c15d750117aec9e75111853074630a44dca87ae))

## v0.40.1 (2024-02-23)

### Fix

* **utils/bec_dispatcher:** _do_disconnect_slot will shutdown consumer of slots/signals which were already disconnected ([`feca7a3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/feca7a3dcde6d0befa415db64fc8f9bbf0c06e52))

## v0.40.0 (2024-02-16)

### Feature

* **utils.colors:** Golden_angle_color utility can return colors as a  list of QColor, RGB or HEC ([`5125909`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/51259097fa23ff861eac3f7c63624ea591bf1bd3))

## v0.39.0 (2024-02-12)

### Feature

* Added full app with all motor movement related widgets into motor_control_compilations.py ([`fa4ca93`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fa4ca935bb39fdba4c6500ce9569d47400190e65))
* MotorCoordinateTable mode_switch added for "Individual" and "Start/Stop" modes ([`2f96e10`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2f96e10b9deb76eedd8f6b6e201ba3b0e526a6f0))
* Motor_control.py MotorCoordinateTable added basic version to store coordinates and show them in motor_map.py ([`031cb09`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/031cb094e7f8a7be4a295bea99b7ca8e095db8d7))
* Active motors from motor_map.py can be changed by slot without changing the whole config ([`17f1458`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/17f14581d7c4662a2f5814ea477dfae8ef6de555))
* Control panels compilations ([`8361736`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/83617366796ce2926650e38a1a9cec296befd3c6))
* Comboboxes of motor selection are changed to orange if the motors are not connected yet ([`0b9927f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0b9927fcf5f46410d05187b2e5a83f97a6ca9246))
* Motor_control.py MotorControl widgets - Absolute + Relative movement, MotorSelection, ErrorMessage popups ([`6fe08e6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6fe08e6b8206bcaaa292b7ff0e6b0d32b883f24f))

## v0.38.2 (2024-02-07)

### Fix

* Adapt code to BEC 1.0 ([`b36131e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b36131eed5c3a3ea58c0fa4d083e63a3717cdf22))

## v0.38.1 (2024-01-26)

### Fix

* Monitor.py replots last scan after changing config with new signals; config_dialog.py checks if the new config is valid with BEC ([`ab275b8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ab275b8e5f226d6c5d22a844c4c0fae0fdc66108))

### Documentation

* 2D waveform scatter plot changed to 2D scatter plot ([`812ffaf`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/812ffaf8eafc3f8c3a6973717149e4befba2c395))
* Documentation for example apps and widgets updated ([`f7a4967`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f7a496723c3fd113867a712928e06636e3212e1a))

## v0.38.0 (2024-01-23)

### Feature

* BECMonitor2DScatter for plotting x/y/z signal as a mesh of scatter plot ([`75090b8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/75090b857526fa642218986806d0daeb1dec0914))

### Fix

* Monitor_scatter_2D.py changed to new BECDispatcher definition ([`747e97e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/747e97e0c924cdedb85e9fe7d47512002b791b10))

## v0.37.1 (2024-01-23)

### Fix

* **tests:** Ensure BEC service is shutdown after bec dispatcher test ([`4664568`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/46645686725a2acb7196dbd1a504c98dbf2e4b5d))
* **tests:** Ensure threads started during plot tests are properly stopped ([`3fb6644`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3fb6644543b4065236216b70a583641956a09a60))

## v0.37.0 (2024-01-17)

### Feature

* Independent motor_map widget ([`1a429b3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1a429b3024e76446ed530bee71ed797c20843fba))

## v0.36.2 (2024-01-17)

### Fix

* Bec_dispatcher.py can partially disconnect topics from slot ([`7607d7a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7607d7a3b64b3861f4833c9b8f5afc360f31b38d))
* Bec_dispatcher.py can connect multiple topics to one callback slot ([`e51be04`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e51be04b95f1a9549a4a3b00d76944aa58b0526a))

## v0.36.1 (2024-01-15)

### Fix

* Motor_example.py fix to the new .read() structure from bec_lib ([`f9c5c82`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f9c5c82381907a19582bf9132740fe27b48d48cc))

## v0.36.0 (2024-01-12)

### Feature

* Bec_dispatcher can link multiple endpoints topics for one qt slot ([`58721be`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/58721bea1a2b4b06220ef0e3b2dcec8c1656213d))

## v0.35.0 (2024-01-12)

### Feature

* Monitor.py can access custom data send through redis ([`6e4775a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6e4775a1248153f6027be754054f3f43c18514d1))
* Monitor.py access data directly from scan storage ([`26c07c3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/26c07c3205debaf88a346410a8ebab0a3ab7a5d9))

### Fix

* Monitor.py clear command from BECPlotter CLI clear now flush database and clear the plots ([`ebd4fcc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ebd4fccda2321aa0dc108a5436fb4cc717911d4b))
* Monitor.py crosshair enabled by default ([`97dcc5a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/97dcc5ac768cc4f0122382591238fd5a9d035270))
* Monitor.py change import of ConfigDialog from relative to absolute in order to make BECPlotter be able to open it ([`6061b31`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6061b3150e990141eafb8d5b17c7e931c7bf8631))
* Monitor_config_validator.py changed to check .describe() instead of signals ([`5ab82bc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5ab82bc13340adb992c921a7211e8e2265861f7a))
* Monitor.py fixed not updating config changes after receiving refresh from BECPlotter ([`00ef3ae`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/00ef3ae9256a368f4842c1dc38a407131181ec1d))
* Monitor_config_validator.py valid color is Literal['black','white'] ([`86c5f25`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/86c5f25205dbaa45b7b2efd255f3a3cb2d3eb0b1))
* Monitor.py fixed scan mode ([`a706da2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a706da2490f4cce80e9515633e8437b3667b0db0))
* Motor_config_validation changed to new monitor config structure ([`d67bdd2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d67bdd26167dca6c65627192dbd098af08355d06))

## v0.34.1 (2023-12-12)

### Fix

* Formatter and tests fixed ([`186c42d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/186c42d6676a495bc2f66d8b7ed37dbf7d0be747))

### Documentation

* Readdocs updated ([`af995a7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/af995a74f34d59eeaff5d9100117f103ec79765d))
* Readme.md updated ([`cba8131`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cba81313671acfee0a40410753c1974008316d07))
* Gitlab templates for issues and merge requests from main bec repo ([`831eddc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/831eddc13600cc06b67de92d39509af37bb05002))

## v0.34.0 (2023-12-08)

### Feature

* Monitor.py error message popup ([`a3b24f9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a3b24f92420420c8968ef4793342c3857c826e57))

### Fix

* Monitor_config_validator.py - Signal validation changed from field_validator to model_validator to check first name and then entry ([`0868047`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/086804780d19956331d8385381d2f7f9c181e77c))
* Monitor_config_validator.py fix entry validation executed only if name validator is successful ([`af71e35`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/af71e35e73733472228c4be0061faefaf655b769))

## v0.33.0 (2023-12-07)

### Feature

* Added axis_width and axis_color as optional plot settings ([`504944f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/504944f696a7b2881adec06d29c271fec7e2c981))

### Fix

* Fixed default config options ([`03bdf98`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/03bdf980bcfc37e217cde1beb258d11cee97e0eb))
* Added hooks to react to incoming config messages and instructions ([`1084bc0`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1084bc0a803ff73cfa2ab53819bc9809588fa622))

## v0.32.2 (2023-12-06)

### Fix

* Changed exec_ to exec for all apps ([`080c258`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/080c258d1542aaace093bca74225297b30453f77))
* Yaml_dialog.py changed to use native solution of OS -> should prevent crashing on py3.11 ([`5adde23`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5adde23a457bbd3ae1488b77d4b927b5bded0473))

## v0.32.1 (2023-12-06)

### Fix

* Widget_io print_widget_hierarchy fix comboboxes ([`d1f9979`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d1f9979ab1372c2f650c8aff12ccb17d668b52eb))
* WidgetIO combobox fixed for qt6 distributions ([`4f70097`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4f700976ddd78a6f06e358950786b731ef9051ce))

## v0.32.0 (2023-11-30)

### Feature

* Jupyter rich console added as alternative to default QTextEdit terminal output ([`016b26f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/016b26f5cf05e90da144487a9359ac2a54c8e549))
* Editor.py basic signature calltip ([`045b1ba`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/045b1baa60a93d2266800821940d7aa29bd8bbe1))
* Editor.py jedi autocomplete hooked ([`fb555b2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fb555b278a5139f180592280408742d34dc5fa84))
* Editor.py added splitter between editor and terminal ([`c70ddb3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c70ddb3cb19fecf7ce14b551d7d265e2e0cff357))
* Toolbar.py proof-of-concept ([`286e62d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/286e62df92927d2efe0b4ab07995f7b5e36a0435))
* Basic text editor + running terminal output ([`9487844`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/94878448c8f39a69e9e65df2789da029a9acfc0e))

### Fix

* Added missing dependency jedi ([`d978740`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d978740f9879580d01e092ad1fead46786d3ed5c))
* Editor.py switch to disable docstring ([`3cc05cd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3cc05cde147cd520b98f0896beb64781ea47d816))
* Editor.py compact signature on tooltip ([`f96cacc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f96caccfcb43c904887ebfc0b34fd779ffff8bf1))
* Editor.py removed automatic background behind edited text ([`d865e2f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d865e2f1af6eb3d5fb31f9c53088b629a232343f))
* Toolbar.py automatic initialisation works ([`8ad3059`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8ad305959257a58b297896218baae06d09520ee1))
* Terminal output as QThread ([`a0d172e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a0d172e3dc35bdc2d7e1b43185e31bb9a3629631))

## v0.31.0 (2023-11-13)

### Feature

* Pydantic validation module for monitor.py ([`7fec0c7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7fec0c7e4411c221413d69aeeb4d68ade10d502b))

### Documentation

* Pydantic validation module docs ([`92a5325`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/92a5325aad02fe308caaf9088a3c4386ca055124))

## v0.30.0 (2023-11-10)

### Feature

* WidgetIO support for QLabel ([`aa4c7c3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/aa4c7c3385f52e4bbc805ee2aced181929943a89))
* Scan_control.py added option to limit scan selection from list of strings as init parameter ([`0fe06ad`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0fe06ade5b44d13a9188aef474364b36baa480ef))
* Scan_control.py a general widget which can generate GUI for scan input ([`088fa51`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/088fa516a8876d112a98cd60aa2a5701dff6b97c))

### Fix

* Added imports to __init__.py in widget for ScanControl class ([`b85cc89`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b85cc898d521df1c99a65e579b8fe853bb04cc32))
* Scan_control.py args_size_max fixed ([`da9025e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/da9025e032c2bc9b34cf359a20745e3156d2f731))
* Scan_control.py default spinBox limits increases ([`5c67026`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5c67026637472d9c77185a59e1bf9a24cfe01307))
* Scan_control.py supports minimum and maximum number of args ([`ee2f36f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ee2f36fb402d626c300a018afacbd57eff14a665))
* Scan_control.py wipe table and reinitialise devices when scan is changed ([`5ac3526`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5ac3526384b9ee0eb94568bac035b348eaa52abd))
* Widget_IO.py added handler for QCheckBox ([`18a7025`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/18a702572f6bed41081d368e39c8fc69122c6203))
* Scan_control.py scan can be executed from GUI ([`2e42ba1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2e42ba174f7abe1590b9afb099dc2d068eb848ae))
* Scan_control.py all kwargs are rendered ([`4b7592c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4b7592c2795a26591b3e30870c73aa406316588d))
* Scan_control.py kwargs and args are added to the correct layouts ([`b311069`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b311069722226b95a7902f42815d2c1e219e9584))

## v0.29.0 (2023-10-31)

### Feature

* Widget_hierarchy.py tool to inspect hierarchy of the widget ([`cda8dae`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cda8daeb35b36692316173a19fb29f1cc0dbdb7c))
* Yaml_dialog.py interactive QFileDialog window to load/save .yaml files to/from dict ([`2b29b6c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2b29b6cfe2ea94a974da4a332c47473176ddddff))
* Qt_utils custom class for class where one can delete the row with backspace or delete ([`a6616f5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a6616f5986d59ad8d065105234f5b704731cce71))
* Modular_app.py, device_monitor.py, config_dialog.py linked together, plot configuration can be done through GUI ([`bf2a09e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bf2a09e6307da63ecf02a1286095a19e5f1dcab4))
* Config_dialog.py interactive editor of plot settings ([`c9e5dd5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c9e5dd542c9eb7c9069d1c0f1256a634a166eb40))

### Fix

* Yaml_dialog.py added support for .yml files ([`10539f0`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/10539f0ba59be716102b2c0577ea62f5c4a3136a))
* Yaml_dialog.py added return None if no file path is specified ([`ff1d918`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ff1d918d43f0f2e5fe8d78c6de9051c50e0e12c1))
* Wrong __init__.py in modular_app ([`d52aa15`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d52aa15aac42f09487c828836e377c78596037bd))
* Test_bec_monitor.py config loaded fresh in the test function to avoid parameter leak ([`3866d7c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3866d7ce4de3391fe57ef872808f7620562eeeb0))
* Test_bec_monitor.py setup_monitor help function changed to pytest.fixture ([`989cd51`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/989cd51162147805db1229b50b330af29f275204))
* Test_config_dialog.py - QApplication removed ([`1cdd760`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1cdd760e4062de1f19837737766ce05edc9ac2da))
* Test_config_dialog.py - test_add_new_plot_and_modify qtbot action .click() changed -> function called directly ([`1333e6c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1333e6cbca18943b0a61206dc1ba63720b031b40))
* Test_config_dialog.py disabled ([`4e710dd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4e710dda5e88b2e82ec87db350e8b1fe6aa09181))
* Test_bec_monitor.py QApplication instance removed ([`77e1d09`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/77e1d0925db2dc6669159fbe3fb08daf330cb5c8))
* Test_config_dialog.py QApplication instance added ([`60e864b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/60e864b2590d121e1b0ad645d39d1a028abe8d7b))
* Device_monitor.py BECDeviceMonitor can be promoted in the QtDesigner and then setup in the modular app ([`afab283`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/afab283988a1acc008bc53ae5a56a8f67504da81))
* Device_monitor.py crosshairs can be attached again ([`644a97a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/644a97aee848c973125375d5f28d3edf2ffc20cf))
* Config_dialog.py prevents to add one scan twice ([`12469c8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/12469c8c1e45f83cc0c65708bd412103a8ec1838))
* Config_dialog.py export to .yaml fixed ([`7e99920`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7e99920fc565acd59cb3a4286ac5ee40597d8af4))
* Config_dialog.py scan_type structure implemented ([`e41d81c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e41d81cbd9371f8633c1e7de82c8f9b64fcb721b))
* Config_dialog.py config from default mode can be exported to dict ([`55b5ca7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/55b5ca7381dc33119baac0f48c76fc9d9e8215ae))
* Config_dialog.py tabs for scans and plots are closable now ([`ec88564`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ec88564e6577cd6579c30f36193c4a0e5fcbc483))
* Modular_app.py configs are linked to the actual version of the state of the device monitor ([`d78940d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d78940da3f114062aa397b87c169f26cbc131a5f))
* Config_dialog.py can load the current configuration of the plot ([`f94a29b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f94a29bf4be0a883abc200821746c3d81a0c00d4))

### Documentation

* Config_dialog.py comments added to example cases ([`4a6e73f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4a6e73f4f791d2152ff29680a4e28529a8df0b47))
* Device_monitor.py update docstrings ([`a785bca`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a785bca8806613f9e1e4b67380e72867b581fe6e))
* Added sphinx base structure ([`9d36b96`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9d36b9686e31b2c4b4206ad47b385c8f2769c641))

## v0.28.1 (2023-10-19)

### Fix

* Stream_plot.py on_dap_update data dict opened correctly ([`28908dd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/28908dd07c1eef8a9d3213a581393e665b310d1b))

## v0.28.0 (2023-10-13)

### Feature

* BECDeviceMonitor modular class which can be used to replace placeholder in .ui file. ([`f3f55a7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f3f55a7ee0ad58aab74526a24f27436fd2bef61d))
* Placeholders initialised ([`75af040`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/75af0404b3aa5f454528255e8971af07c4e8b39b))

### Fix

* Scan_mode for BECDeviceMonitor fixed init_ui ([`59bba14`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/59bba1429c1f8aeeb562b539583e71303506bd58))

## v0.27.2 (2023-10-12)

### Fix

* Scan_plot tests ([`f7cbdbc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f7cbdbc5ca318d60a9501df3fa03c7dea15b5b21))

## v0.27.1 (2023-10-10)

### Fix

* Extreme.py default config file changed to the config_example.yaml ([`5814113`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5814113f73fb1c4552bb715b27d3330decd9c878))
* Extreme.py retry action fixed in ErrorHandler ([`5162270`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5162270d28ca8eab4eac9d9665e2fb4c5e8a33a3))
* Extreme.py advanced error handling with possibility to reload different config ([`51c3a9e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/51c3a9e9ee3d75c8324300afac366dcdb9adb876))
* Extreme.py error in configuration are displayed as messagebox ([`9750039`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9750039097c9e4b9a45603dcefe76e5b2e8920fd))
* Extreme.py validation function to check config key component structure ([`824ce82`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/824ce821cd5f060f2c550b970afb1f3479a006ef))
* Extreme.py improved error handling for scan types mode ([`fbd299c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fbd299c7e7cf548886e2b1787d8e188c708ee8cd))
* Extreme.py init_ui changed > to >= for setting number of columns ([`6c773c7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6c773c7c94e5eee700b74a792657978be86dbbf4))
* Extreme.py init_plot_background error handling ([`c525eba`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c525eba88576e0094063019d00fba6a43c52b42e))
* Extreme.py ui is initialised for the first scan of config in scan mode ([`fc60984`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fc6098414e328e14ec9ab6006538f46e36f17723))
* Extreme.py client and device manager initialisation ([`ae79faa`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ae79faa7ed8e9d8f680e1be1afefe43706305d9a))
* Extreme.py default config file changed to the config_example.yaml ([`d356cf7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d356cf734b81fd7ed2c9b48ee85a1722af179d83))
* Extreme.py retry action fixed in ErrorHandler ([`b76df1b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b76df1b583a5922229f97876f9e65e0cad64c88e))
* Extreme.py advanced error handling with possibility to reload different config ([`d623cf9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/d623cf95391adfc89837cd54ca1b2a1b6e491a3c))
* Extreme.py error in configuration are displayed as messagebox ([`89a52a0`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/89a52a0948ee300e57bb7198eac339ee771bff06))
* Extreme.py validation function to check config key component structure ([`5a7ac86`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5a7ac860a8cf5cef53ae699b2869e649c1721f9d))
* Extreme.py improved error handling for scan types mode ([`ece1859`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ece1859a63b83b1d56b33cc610efea6876dd9e1f))
* Extreme.py init_ui changed > to >= for setting number of columns ([`a0a89fe`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a0a89fe704db6c11a99a26a080051af1c677ba7a))
* Extreme.py init_plot_background error handling ([`dafb6fa`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/dafb6fae7a526d5b311ded1d0424ac4dbb3c8b74))
* Extreme.py ui is initialised for the first scan of config in scan mode ([`82bebe6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/82bebe6b41004befcb1b54db141e20ff844f76e5))
* Extreme.py client and device manager initialisation ([`cf15163`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cf15163bd91291e9851662c147b2e799ae022b9e))
* Formatter fixed ([`153c5f4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/153c5f4f9d168f433380bd2deddd2b17a45916a3))

## v0.27.0 (2023-09-25)

### Feature

* Motor_example.py in start/end mode new button allowing user to go to end position ([`65b045e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/65b045e1a26a0f799311e9dca25e2a9dfd7f7147))

### Fix

* Epics removed from requirements ([`44cc881`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/44cc881ac9e69c68f1f5296fea62a14daa55d4e3))
* Motor_example.py load .csv logic fixed ([`b78152b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b78152b14999ba5c07d7cd2ef2e3309df1ba5ca6))
* Motor_example.py export .csv logic fixed ([`85841cd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/85841cdf1fc44472cfcc7e3e6529a41018140896))
* Motor_example.py precision in duplicate table fixed ([`05f48de`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/05f48de3f1f6793de3f6a8bc2c5e3ad3261dfcf0))
* Motor_example.py duplicate table fixed ([`401fec8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/401fec85395886ea2816b6993bf8084b6e652967))
* Motor_example.py manual changing coordinates in start/stop works again ([`b13509e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b13509e9eb88b55a59b141b0cec06f3c8a983151))
* Motor_example.py replot points logic simplified ([`a15860a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a15860abac984328382868b0a953960c44792c41))
* Motor_example.py new independent mapping relying on the table ([`673ed32`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/673ed325d1f56505035899549ea555497823a31f))
* Extreme.py formatting fixed ([`63f52fc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/63f52fc8419cd53856a32af6be3f548f8e077cd1))
* Line_plot.py ROI interactions fixed ([`e4f23f5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e4f23f51012b54cde5cd41bb9ab356a277ef4b2f))
* Online changes e21543 ([`b41d63e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b41d63ea4d6e15c80a7baab7a70c607079152d0a))
* Motor_example.py user is blocked to duplicate last entry in start/end mode if end coordinate was not defined ([`418480f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/418480f1fcdc72c05887e8b73c24f76e1e8475b2))
* Motor_example.py - new more robust logic for getting coordinates for table go buttons ([`08f508f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/08f508f4c3c3e1f3c2d4c6dda0d8e6693e9331b5))

### Performance

* Motor_example.py replot logic optimizes ([`a4fb6bd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a4fb6bd1d2c819740077cdc7291daf28a9e4abdd))

## v0.26.7 (2023-09-19)

### Fix

* Eiger_plot_hist.py removed ([`abe35bf`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/abe35bf96757a38395733bddbd8702a29fd26f42))

## v0.26.6 (2023-09-19)

### Fix

* Extreme.py saved to .yaml works correctly for different scans configurations ([`cb144c7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cb144c7c2cba50fc49ba53b0a9e3293b549665be))
* Extreme.py fixed logic of loading new config.yaml during app operation ([`4287ac8`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4287ac888591abf27a4e4ce8c23f94d54bc6c2a9))

### Documentation

* Extreme.py updated documentation ([`7ff72b4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7ff72b4086e5e340d591d130f011f83fc8370315))

## v0.26.5 (2023-09-13)

### Fix

* Motor_example.py help extended ([`a5c6ffa`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a5c6ffaa024a0dd6901976c81ea9146e5be016ec))

## v0.26.4 (2023-09-12)

### Fix

* Logic fixed ([`7cb56e9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7cb56e9e7f2cbeee5a141c4a52a3489c26963839))

## v0.26.3 (2023-09-12)

### Fix

* Import works for both modes ([`b867f25`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b867f25c780ba97393ca65fe76c1cb492f365ded))

## v0.26.2 (2023-09-12)

### Fix

* Import with start/stop mode works again ([`cacc076`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/cacc076959cdd55218b74de2974d890e583c3d94))

## v0.26.1 (2023-09-12)

### Fix

* Removed scipy from eiger_plot.py ([`0e634ee`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0e634ee2ac58b8be43b7f4e64fbc08ef08675aa1))

## v0.26.0 (2023-09-12)

### Feature

* Plot different signals and plot configurations based on different scans ([`57e6990`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/57e69907d55f7693e97d48026f3bb426adfb4870))

## v0.25.1 (2023-09-12)

### Fix

* Specific config for csaxs ([`8ff983f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8ff983f16e78d881582d4aaaa0261e10d9d62bf2))
* Mode lock in config to disable changing the mode for users ([`10ccf0c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/10ccf0cc977cae30c0c185a920e15b9cf2def58f))

## v0.25.0 (2023-09-12)

### Feature

* ComboBox to switch between entries mode ([`f2fde2c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f2fde2cf5c4b219520eb0257c1c8e02ce66cde87))

### Fix

* Extra columns works again ([`2123361`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2123361ada9767333792d34de56d6f1447f67cda))
* Resize table is user controlled ([`63e3896`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/63e389672560e505159de2014846d1506b05633f))

## v0.24.2 (2023-09-12)

### Fix

* Changes e20643 ([`2657440`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/265744076cc53bd054b45c12de3bb24b23e1845c))

## v0.24.1 (2023-09-08)

### Fix

* Typo fixed in mca_plot.py ([`3b12f1b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3b12f1bc1d65772fc3613f62013809445dcead7a))

## v0.24.0 (2023-09-08)

### Feature

* HistogramLUT for mca_plot ([`ae04072`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ae040727fc60160de8b50ac1af51fba676106e52))

## v0.23.0 (2023-09-08)

### Feature

* Added key bindings and help dialog ([`ade893d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ade893d33d07f1190994de19b84d4021586bcbcb))

## v0.22.0 (2023-09-08)

### Feature

* Added FFT ([`b984f0f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b984f0f36e2178690eaaec091d4a7b9443f2378f))

## v0.21.2 (2023-09-08)

### Fix

* Moved mask as a last step of image processing ([`87d5467`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/87d546764318679cd80e56d17d590f0e31e51504))

## v0.21.1 (2023-09-08)

### Fix

* Update_signal typo fixed ([`43f03b5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/43f03b543083da9b743828139a92f87732187dd9))

## v0.21.0 (2023-09-08)

### Feature

* Added functionality to load mask ([`33d1193`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/33d1193c9623b157cc74883184677a727b8e33ce))

### Fix

* Path to mask fixed ([`ef42921`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ef42921c9a585bce8a97fc8bb251e27a9455a771))

## v0.20.0 (2023-09-08)

### Feature

* Added rotate and transpose logic ([`acd7a3b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/acd7a3bc92746c7e56dc8699c4378d2ab778267f))

### Fix

* Added missing .ui file to git ([`ae8fc94`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/ae8fc9497954ca49c16d76eaeea7ecc7659c1269))

## v0.19.2 (2023-09-08)

### Fix

* Rotation logic fixed ([`6733371`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6733371c2ccb4e233d9aa9421e21d627978925d7))

## v0.19.1 (2023-09-08)

### Fix

* Rotation always counter-clockwise ([`00385ab`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/00385abbf98add7945af170b292774d377473a70))

## v0.19.0 (2023-09-08)

### Feature

* Rotation of the image to the left/right by 90, 180, 270 degree ([`327f6b3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/327f6b3df300d1f88b475973a86175379688aa9b))
* Simulation stream with Gaussian peak in 1st quadrant ([`4fa8d46`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4fa8d46631ff822d5465564434d173dd766a6b1a))
* Eiger_plot.py in example folder with new GUI ([`5cbedec`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5cbedec5d9f6a6ae763e2cb336ecb40c4d3e1ed1))

## v0.18.1 (2023-09-08)

### Fix

* Online changes ([`29c983f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/29c983fb268bb2dbcfe552453501ff42442f075f))

## v0.18.0 (2023-09-08)

### Feature

* Eigerplot added ([`70d74c7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/70d74c774d2b318d99c049f0f03743e77812df98))

## v0.17.1 (2023-09-08)

### Fix

* Start_device_consumer changed from EP device_status to scan_status ([`46a3981`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/46a3981e7dfd5ded7b7f325301d2a25c47abd16f))

## v0.17.0 (2023-09-07)

### Feature

* Console arguments added for Redis port, device, and sub_device tag ([`fb52b2a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fb52b2a8e59fca556764e0dc32bd4edc167e31d3))
* Plot flips every second row ([`c368871`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c36887191914d23e85a1b480dac324be0eefb963))
* Device_consumer is getting scanID and initialise stream_consumer ([`9271b91`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9271b91113a3bbd46f0bffdaef7b50b629e4f44f))
* Simulation and simple 2D plot for mca card stream ([`bfef713`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bfef71382e6a1180d750d2c800650942c5da7a21))

## v0.16.4 (2023-09-06)

### Fix

* Self.limit_map_data fixed to be initialised only with integers from limits ([`b62509a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b62509a28e970358c3ffd4f7d55c2a6bbef35970))

## v0.16.3 (2023-09-06)

### Fix

* Limit spinBoxes morphed to doubleSpinBoxes ([`a1264fe`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a1264fe4e2e0c864c68786d6db16550f489b00fa))

### Documentation

* PyqtGraph controls in help ([`2397af1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2397af140f2f9ee23ed5e62ef9bdf4d0aba249a1))

## v0.16.2 (2023-09-06)

### Fix

* X and y motor can be linked again ([`f45512e`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f45512e0ae9c189a1d26456333c5b348cd681ce7))

## v0.16.1 (2023-09-06)

### Fix

* Default values fixed from .yaml ([`8a6e2da`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8a6e2daaf95cb5417951cbe3cca0cb3e909b08b4))

## v0.16.0 (2023-09-06)

### Feature

* Added help button ([`2087d19`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2087d19d3c2349e160327880210a5cf129852f09))
* Table can be loaded from .csv ([`15d995f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/15d995f66b892f55526bd8b0954b6886d8f861ea))
* Table can be exported to csv ([`772f18f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/772f18fa09bef54c849d2fdd58e02e8dada84a4e))
* Additional extra rows takes values from previous row ([`1235294`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1235294b034dae50ff9a2ea93bc1a318383cbbf5))
* Additional columns can be added through .yaml ([`fa76acb`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fa76acbd6dda1695add1c1159c4a96c33741a4c7))

### Fix

* Help extended ([`9fba033`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9fba0334a0389f66344b84dd434d4d9a39b1565e))
* Table loads number of columns correctly ([`bf12963`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bf129632471da2e6dc5d637a5b02c321d8d3dcac))
* Content always aligned to centre ([`74884a3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/74884a37076cd047e2dc75e07246f73e5f93167e))

## v0.15.0 (2023-09-06)

### Feature

* Step for x and y can be linked or separated ([`16ab746`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/16ab746f54007ee0647b6602b7d74a4a59401705))
* User can choose if to save coordinates when moving to absolute coordinates ([`6324199`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/632419929921fbe4e970149ce8d4e617566f71fc))

### Fix

* Table checkbox fixed ([`7e6244c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7e6244c5d3698e6fea944b9501064470b6c884c7))
* Partial fix to table checkBox ([`75f5c8f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/75f5c8fcd6e80288e1f3bc1b9c0c0b3edd1335bc))
* Coordinates markers are updated on the map, if X, Y in table manually is changed ([`0aa667b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0aa667b70d48356bdda59b879baa3862c5e2e756))
* Added float validator to the table ([`be1bd81`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/be1bd81d60373a0d9e776dc3f0d879d1bf905f7a))
* Table bug, when deleted multiple rows ([`9d83a45`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9d83a455e899e3018364123707064882076c4eb0))
* Table bug, when user deleted row and wanted to go to the previous position ([`63e6d61`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/63e6d61c2e6f9cbc069c9d55c7006d18b6b34b4d))

## v0.14.2 (2023-09-05)

### Fix

* Bec_config initialisation by command line argument ([`b7a1b8b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b7a1b8bca1b89df859c9ed0ed17862bb6d533de7))

## v0.14.1 (2023-09-05)

### Fix

* Gui default tab changed to coordinates table ([`3c74fa5`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3c74fa59b7b83976b13afc821c1333868e62a686))

## v0.14.0 (2023-09-05)

### Feature

* Enable gui button, in the case that motor movement is not finished ([`84155d2`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/84155d22640e229820fa5104975d2675f63cef31))
* Saved coordinates are shown on the map ([`0ca665a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0ca665a1e91d9c5dee9af0218c2e211de8304b26))

### Fix

* Motor position points can be switched on/off if points were deleted ([`5b30dfd`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5b30dfd43fcbe4b9941e26cab76005ffeb21d95f))
* Highlight disapear with new motor ([`3fb8651`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/3fb8651dd5777861488928b414d5bdacb517d0e9))
* New points do not make invisible points visible again ([`fb10551`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fb105513e52bcd9c62dfead16e91b45ecd817612))
* Checkbox visibility toggle is working. ([`a178c43`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a178c434b1d9efc1795b6f5115e2a8b9685ccdf2))
* Saved coordinates can be removed from table and from the map again ([`c32e95a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/c32e95a57d3faec46652b413581d830698855367))

## v0.13.0 (2023-09-05)

### Feature

* Crosshair highlight at motor position ([`9228e5a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/9228e5aea3d5e4192733539643654fd635c63559))
* Increase step size double with key bindings ([`e9ef1e3`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e9ef1e315bc7222c38c1f2f3f410f5cdff994f08))
* Go, set, save current coordinates and keyboard shortcuts ([`5d6a328`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/5d6a328728a017eb4f1d191c96d2659800d41941))

### Fix

* Spinbox limits in ui file ([`8de08cf`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8de08cf9ccb092b3cfa5cf751f69fbf5edd2b217))
* Precision updated correctly ([`172ccc6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/172ccc69056380abcddf572f668a4ddbd5d34eec))

## v0.12.0 (2023-09-04)

### Feature

* Config from .yaml file ([`1a67758`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/1a677584708e1c91491fe84db169103bdda488e5))
* Removal of motor configurations from user ([`34212d4`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/34212d4d45c88a7bba75f289a25e5488ff95fc73))

### Fix

* Error message if motor do not have limits attribute ([`bf93b02`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/bf93b02cdc82086b32e2bd16f4b506c1bb76c65d))

### Documentation

* Added documentation to all classes and methods ([`4afaa1b`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/4afaa1b0ce1f29e4193e6999ecc13b1f0f662213))

## v0.11.0 (2023-09-04)

### Feature

* Colorbutton next to each curve in the table to be able to set up colors ([`2c6719c`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2c6719cf390e6638cadbc814eb0c085bb45c3c6c))

### Fix

* User selected colors are preserved with the new scan ([`8e7885f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/8e7885f36dd2812e3285c4d2d101212055644c7b))
* Colorbutton change now symbols as well ([`6d2e1c9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/6d2e1c9d08595a45f502287c6490905e8df3db10))

## v0.10.0 (2023-09-01)

### Feature

* Load and export configuration into .yaml from GUI ([`e527353`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/e5273539741a1261e69b1bf76af78c7c1ab0d901))
* Error messages if name or entry is wrong ([`415c4ee`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/415c4ee3f232c02ee5a00a82352c7fbb0d324449))
* Number of columns can be dynamically changed ([`65bfccc`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/65bfccce8fce158150652fead769721de805d99e))
* Multi window interface created for extreme BL ([`69c38d6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/69c38d67e4e9b8a30767f6f67defce6c5c2e5b16))

### Fix

* Check if num_columns is not higher that actual number of plots ([`aac6e17`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/aac6e172f6e4583e751bee00db6f381aaff8ac69))
* Add max number of columns according to the number of plots ([`fbd71c1`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/fbd71c131386508a9ec7bb5963afefc13f8b1618))
* More specific error messages ([`583e643`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/583e643dacac3d7aaa744751baef2da69f6f892e))
* Bec_dispatcher.py can take multiple workers as a list ([`7bcf88d`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/7bcf88d5eb139aa3cf491185b9fb3f45aa5e39a2))
* Config.yaml can be passed as a console argument to extreme.py ([`b8aa373`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/b8aa37321d6ac0ebd9f2237c8d2ed6594b614b57))
* Columns span generalised for any number of columns ([`2d851b6`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2d851b6b4eb0002e32908c2effbfb79122f18c24))

### Documentation

* Updated documentation and TODOs ([`0ebe35a`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0ebe35ac7a144db84c323f9ecb85dfdf6de66c21))
* Fixed documentation ([`2f7c1b9`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/2f7c1b92a9624741f6dea44fc8f3c19a8a506fd9))

## v0.9.0 (2023-08-29)

### Feature

* Migrate to .yaml config file instead of argparse ([`a9f1688`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/a9f16884b0b274e36fdb531b56a26343692a78f5))
* Better color coding of curves ([`0eff18f`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/0eff18f5a074ea806d43d52ae72bf87f0187a26d))

## v0.8.1 (2023-08-29)

### Fix

* Added missing local .ui file ([`f0589b7`](https://gitlab.psi.ch/bec/bec-widgets/-/commit/f0589b79ec7f50ee9d040b911d1874b4232659d5))

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
