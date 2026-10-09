# BEC UI kit

One set of design tokens and controls for every redesigned BEC widget, in two technologies:

| Layer | QML | QWidget |
| --- | --- | --- |
| Tokens | `theme.<token>` context property (`QmlTheme`) | `ThemeTokens.current()` |
| Controls | `import BecUi` (`utils/quick/qml/BecUi/`) | `bec_widgets.utils.ux_kit` |
| Hosting | `create_quick_widget(...)` (`utils/quick/host.py`) | plain widgets |

Both read their colours from `app.theme` (`bec_qthemes`) and switch live between light and dark.
A widget written with the QML controls and its QWidget twin written with `ux_kit` look the same,
so the two versions of each port can be compared side by side.

See it all at once:

```bash
python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery            # QML | QWidget
python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery --theme light
python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery --screenshots ./shots
```

## Tokens

Defined once in `tokens.py`. Base colours come from the theme XML of `bec_qthemes`; everything
else is derived there, so there is exactly one place that decides what "muted text" or "warning
tint" means.

| QML (`theme.`) | Python (`ThemeTokens`) | Meaning |
| --- | --- | --- |
| `bg` | `bg` | window background (`BG`) |
| `card` | `card` | surfaces: cards, popups (`CARD_BG`) |
| `sunken` | `sunken` | nested sections and the segmented-control track |
| `field` | `field` | input backgrounds (`FIELD_BG`) |
| `border`, `separator` | `border`, `separator` | outlines and hairlines |
| `fg`, `fgMuted`, `fgSubtle` | `fg`, `fg_muted`, `fg_subtle` | text: primary, secondary, placeholder |
| `hover`, `pressed`, `track` | `hover`, `pressed`, `track` | interaction fills, empty progress track |
| `primary`, `onPrimary` | `primary`, `on_primary` | main action colour and text on it |
| `info`, `success`, `warning`, `danger`, `highlight` | same | status colours (`ACCENT_*`) |
| `<tone>Text` | `<tone>_text` | status colour adjusted to stay readable as text on cards |
| `<tone>Tint` | `<tone>_tint` | soft status fill for chips and banners |
| `dark`, `name` | `dark`, `name` | theme flag and name |
| `radiusSmall` 6, `radiusLarge` 10 | `metrics[...]` | controls / cards |
| `controlHeight` 32, `controlHeightCompact` 28 | `metrics[...]` | buttons, fields |
| `spacing` 8, `padding` 12 | `metrics[...]` | layout rhythm |
| `fontCaption` 11, `fontSmall` 12, `fontBody` 13, `fontTitle` 15, `fontHeadline` 20, `fontDisplay` 28 | `metrics[...]` | type scale in px |
| `monoFamily` | `mono_family` | fixed-width font for values and logs |

**Tones.** Status colours are addressed by name everywhere: `neutral`, `subtle`, `primary`,
`info`, `success`, `warning`, `danger`, `highlight`. The names of the first ports are aliases:
`busy`→`info`, `ok`→`success`, `warn`→`warning`, `err`/`error`/`emergency`→`danger`,
`stale`→`subtle`. In QML use `theme.tone(name)`, `theme.toneText(name)`, `theme.toneTint(name)`;
in Python `tokens.tone(name)`, `tokens.tone_text(name)`, `tokens.tone_tint(name)`. When a QML
binding calls one of these, write it as `(theme.name, theme.toneText(tone))` so it re-evaluates on
a theme switch.

**Aliases for existing ports.** `QmlTheme` also answers to the token names used on the earlier
branches, so their QML runs unchanged when they switch to this host: `muted`, `faint`, `text`,
`foreground`, `background`, `accent`, `busy`, `ok`, `warn`, `err`, `emergency`, `isDark`,
`busyText`, `okText`, `warnText`, `errText`, `busyTint`, `okTint`, `warnTint`, `errTint`,
`window`, `base`, `button`, `onAccent` and `c` (the raw `bec_qthemes` palette as a map, e.g.
`theme.c.ACCENT_DEFAULT`). New code uses the canonical names. One difference to note: on the
positioner-box branch `accent` meant the selection colour; here it is `ACCENT_DEFAULT`, so use
`primary` where that branch used `accent`.

## Controls

Every control exists in both technologies with the same name and the same states.

| Control | QML properties | QWidget (`ux_kit`) | Use for |
| --- | --- | --- | --- |
| `Icon` | `name`, `color`, `size`, `filled` | `material_icon(...)` from `bec_qthemes` | Material icons via `image://material/<name>` |
| `IconButton` | `iconName`, `tip`, `danger`, `compact`, `checkable`, `iconSize` | `IconButton(icon_name, tip, danger=, compact=)` | toolbar and row actions; `tip` is the tooltip and accessible name, never leave it empty |
| `TextButton` | `text`, `variant`, `iconName`, `busy`, `compact`, `tip` | `TextButton(text, variant, icon_name, compact=)`, `set_busy()` | labelled actions. Variants: `primary`, `success`, `danger` (solid), `neutral` (outlined), `dangerOutline`, `ghost` |
| `Spinner` | `running`, `size`, `color` | `Spinner(size=)`, `set_running()` | short waits inside a row |
| `StatusPill` | `text`, `tone`, `iconName`, `pulse`, `outlined` | `StatusPill(text=, tone=, icon_name=, pulse=, outlined=)`, `set_status()` | state of a device, scan or service. `tone` is a name or a colour; `pulse` for live states |
| `Badge` | `count`, `tone`, `solid`, `showZero`, `maximum` | `Badge(count=, tone=)`, `set_count()` | unread counts, filter counts |
| `LinearProgress` | `value` (0..1), `indeterminate`, `tone`, `thickness` | `LinearProgress(tone=)`, `set_value()`, `set_indeterminate()` | progress inside rows and cards |
| `Card` | `title`, `subtitle`, `iconName`, `titleStyle`, `collapsible`, `expanded`, `headerExtras`, `fillContent` | `Card(title, title_style=, collapsible=, surface=)`, `.body`, `add_header_widget()` | every grouped surface. `titleStyle: "caption"` for form sections |
| `Divider` | `vertical` | `Divider(vertical=)` | hairlines |
| `Banner` | `tone`, `title`, `text`, `actionText`, `closable` | `Banner(tone, title, text, action_text=, closable=)` | inline errors, warnings and confirmations that belong to a place in the UI |
| `EmptyState` | `iconName`, `title`, `text`, `actionText`, `compact` | `EmptyState(icon_name, title, text, action_text=)` | empty lists and views: say what will appear and how to get it |
| `FieldFrame` | `focused`, `invalid`, `hovered` | `field_qss(tokens)`, `set_invalid()` | background of all inputs |
| `InputField` | `suffix`, `iconName`, `invalid`, `monospace` | `SuffixLineEdit`, `set_suffix()`, `set_icon_name()` | text and numeric entry with units |
| `SearchField` | `shortcutHint`, `cleared()` | `SearchField(placeholder=, shortcut_hint=)` | filtering lists; Escape clears |
| `SelectField` | `invalid`, `placeholder`, `editable` | `QComboBox` + `field_qss` | choosing from a list |
| `SwitchField` | `text`, `checked` | `ToggleSwitch` | booleans |
| `SegmentedControl` | `model`, `currentIndex`, `compact`, `activated(index)` | `SegmentedControl(items)`, `activated`, `set_count()` | 2–5 exclusive filters or views |
| `FormField` | `label`, `required`, `unit`, `helper`, `error` | `FormField(label, control, required=, helper=, unit=)`, `set_error()` | label, helper and validation message around any input |

QWidget controls follow `app.theme` by themselves. `refresh_kit_theme(root)` re-themes a subtree
created before a theme was applied. `PortedPropertiesMixin` keeps the `SafeProperty` settings of
the class a port replaces in saved profiles.

## Hosting QML

```python
from bec_widgets.utils.quick import create_quick_widget, release_quick_widget

self.view = create_quick_widget(self, QML_FILE, properties={"backend": self._backend})
layout.addWidget(self.view)
...
def cleanup(self):
    release_quick_widget(self.view)   # unload the scene before the backend dies
    super().cleanup()
```

* All views share one `QQmlEngine` (`quick_engine()`), so the second and later QML widgets cost
  little memory. Hand state to the view with `properties` (initial properties of the root item).
* `context={"name": obj}` still works for the first ports, but gives the view its own engine,
  because context properties on the shared engine would leak into every other view.
* `background` is `"window"` (default), `"card"` or `"transparent"` and follows theme switches.
* `raise_on_error=True` turns QML load errors into a `RuntimeError`; use it in tests.
* `DictListModel(roles)` feeds a list of dicts to a QML `ListView`, updating rows in place so
  delegates and their animations survive refreshes.
* Icons: `image://material/<name>?color=%23rrggbb&filled=1`. The colour may also be `rrggbb`
  without `#`, `#aarrggbb` or a colour name. `Icon { name: ...; color: ... }` builds the URL.

## Rules the controls already follow

* Every interactive control shows keyboard focus with a 2 px primary ring.
* Icon-only buttons always carry a tooltip, which is also their accessible name.
* Colour never carries meaning alone: pills and banners pair the tone with a word or an icon.
* Status text uses the `<tone>Text` colours, which stay readable on both themes (the light
  theme's yellow is darkened for text).
* Destructive actions use `danger` only when they are the main action of a dialog; elsewhere
  `dangerOutline` or an `IconButton { danger: true }`.

## Adding a control

1. Add `BecUi/<Name>.qml` and list it in `BecUi/qmldir`.
2. Add the QWidget twin to `ux_kit.py` (inherit `_ThemeFollower` and implement
   `refresh_theme(tokens)`), with the same name and states.
3. Show both in `examples/ui_kit_gallery` and add a test to `tests/unit_tests/test_ui_kit.py`;
   the tests fail when a QML control is missing from `qmldir` or the gallery.
