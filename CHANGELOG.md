# Changelog

<!--next-version-placeholder-->

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
