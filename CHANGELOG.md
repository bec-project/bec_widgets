# CHANGELOG

## v0.99.12 (2024-08-29)

### Fix

* fix(toolbar): widget action added ([`2efd487`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2efd48736cbe04e84533f7933c552ea8274e2162))

* fix(reset_button): reset button added ([`6ed1efc`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/6ed1efc6af193908f70aa37fb73157d2ca6a62f4))

* fix(abort_button): abort button added; some minor fixes ([`a568633`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/a568633c3206a8c26069d140f2d9a548bf4124b0))

## v0.99.11 (2024-08-29)

### Fix

* fix(resume_button): resume button added ([`8be8295`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/8be8295b2b38f36da210ab36c5da6d0a00e330cc))

### Refactor

* refactor(icons): general app icon changed; jupyter app icon changed to material icon ([`5d73fe4`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5d73fe455a568ad40a9fadc5ce6e249d782ad20d))

* refactor: add option to select scan and hide arg bundle buttons ([`7dadab1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/7dadab1f14aa41876ad39e8cdc7f7732248cc643))

## v0.99.10 (2024-08-29)

### Fix

* fix(stop_button): queue logic scan changed to halt instead of abort and reset ([`4a89028`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4a890281f7eaef02d0ec9f4c5bf080be11fe0fe3))

### Refactor

* refactor(stop_button): stop button changed to QWidget and adapted for toolbar ([`097946f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/097946fd688b8faf770e7cc0e689ea668206bc7a))

* refactor: added hide option for device selection button ([`cdd1752`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cdd175207e922904b2efbb2d9ecf7c556c617f2e))

## v0.99.9 (2024-08-28)

### Fix

* fix: fixed build process and excluded docs and tests from tarballs and wheels ([`719254c`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/719254cf0a48e1fc4bd541edba239570778bcfea))

## v0.99.8 (2024-08-28)

### Fix

* fix(website): fixed designer integration for website widget ([`5f37e86`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/5f37e862c95ac7173b6918ad39bcaef938dad698))

### Refactor

* refactor(website): changed inheritance of website widget to simple qwidget; closes #325 ([`9925bbd`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/9925bbdb48b55eacbbce9fd6a1555a21b84221f9))

## v0.99.7 (2024-08-28)

### Fix

* fix(toolbar): material icons can accept color as kwarg ([`ffc871e`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ffc871ebbd3b68abc3e151bb8f5849e6c50e775e))

## v0.99.6 (2024-08-28)

### Documentation

* docs: various bugs fixed ([`c31e9a3`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c31e9a3aff3ee8e984674dee0965ee7f1b6e2b8f))

### Fix

* fix(toolbar): use of native qt separators ([`09c6c93`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/09c6c93c397ce4a21c293f6c79106c74b2db65ca))

## v0.99.5 (2024-08-28)

### Documentation

* docs(index): index page is centered ([`02239de`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/02239de0a36fcd6cbf97990b0dec1ddf7ecf6ba6))

### Fix

* fix(dock_area): dark button added ([`e6f204b`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e6f204b6aa295747a68769f43af2e549149b401a))

## v0.99.4 (2024-08-28)

### Documentation

* docs(buttons): added missing buttons docs ([`4e5520a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4e5520aee2115d2fc0cebb3865433478a5ec8253))

* docs(developer): tutorial for BECWidget base class ([`ac2cb51`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/ac2cb5197deef4d51e26ee5beb070eba3ffc210d))

### Fix

* fix(theme): apply theme to all pyqtgraph widgets on manual updates ([`c550186`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c5501860e8e07a53f4bce144d44ed39eda6290ef))

### Refactor

* refactor(buttons): changed grid and thumbnail fig in gallery ([`4591ba8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/4591ba8f73e22aba7258cad93c073f1387cb74a0))

* refactor(icons): removed toolbar icons from assets ([`f335763`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/f335763280adb1d83ba31f073ce206e4cb5d15ef))

* refactor(icons): moved widget icons to class attribute ICON_NAME ([`e890091`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/e890091d862e42317c7a54fc414ba37c85f268b0))

## v0.99.3 (2024-08-27)

### Build

* build: updated min version of bec qthemes ([`d482434`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/d48243483ef8228cc5eb85e40a6b8f5da3b45520))

### Fix

* fix(cmaps): unified all defaults to magma cmap ([`1ca9499`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/1ca9499edd334c19fe1e7aac71d3940a80a1ec95))

* fix(color maps): color maps should take the background color into account; fixed min colors to 10 ([`060935f`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/060935ffc5472a958c337bf60834c5291f104ece))

## v0.99.2 (2024-08-27)

### Ci

* ci: additional tests are not allowed to fail ([`bb385f0`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/bb385f07ca18904461a541b5cadde05398c84438))

### Fix

* fix(widgets): fixed default theme for widgets

If not theme is set, the init of the BECWidget base class sets the default theme to &#34;dark&#34; ([`cf28730`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cf28730515e3c2d5914e0205768734c578711e5c))

## v0.99.1 (2024-08-27)

### Fix

* fix(crosshair): emit all crosshair events, not just line coordinates ([`2265458`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2265458dcc57970db18c62619f5877d542d72e81))

## v0.99.0 (2024-08-25)

### Documentation

* docs(darkmodebutton): added dark mode button docs ([`406c263`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/406c263746f0e809c1a4d98356c48f40428c23d7))

### Feature

* feat(darkmodebutton): added button to toggle between dark and light mode ([`cc8c166`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/cc8c166b5c1d37e0f64c83801b2347a54a6550b6))

### Fix

* fix(toggle): emit state change ([`c4f3308`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c4f3308dc0c3e4b2064760ccd7372d71b3e49f96))

### Refactor

* refactor(darkmodebutton): renamed set_dark_mode_enabled to toggle_dark_mode ([`c70724a`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/c70724a456900bcb06b040407a2c5d497e49ce77))

### Test

* test(dark_mode_button): added tests for dark mode button ([`df35aab`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/df35aabff30c5d00b1c441132bd370446653741e))

## v0.98.0 (2024-08-25)

### Fix

* fix(toolbar): removed hardcoded color values ([`afdf4e8`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/afdf4e8782a22566932180224fa1c924d24c810f))

* fix: transitioning to material icons ([`2a82032`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/2a82032644a84e38df04e2035a6aa63f4a046360))

* fix(dock_area): transitioned to MaterialIconAction ([`88a2f66`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/88a2f667588e9aeb34ae556fa327898824052bc3))

* fix: fix color palette if qtheme was not called ([`3f3b207`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/3f3b207295ebd406ebaeecee465c774965161b8b))

### Refactor

* refactor(waveform): use set theme for demo ([`44cfda1`](https://gitlab.psi.ch/bec/bec_widgets/-/commit/44cfda1c07306669c9a4e09706d95e6b91dee370))
