from __future__ import annotations

from qtpy.QtCore import QLocale, QMetaEnum, Qt, QTimer
from qtpy.QtGui import QColor, QCursor, QFont, QIcon, QPalette
from qtpy.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class PropertyEditor(QWidget):
    def __init__(self, target: QWidget, parent: QWidget | None = None, show_only_bec: bool = True):
        super().__init__(parent)
        self._target = target
        self._bec_only = show_only_bec

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Name row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(target.objectName())
        self.name_edit.setEnabled(False)  # TODO implement with RPC broadcast
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # BEC only checkbox
        filter_row = QHBoxLayout()
        self.chk_show_qt = QCheckBox("Show Qt properties")
        self.chk_show_qt.setChecked(False)
        filter_row.addWidget(self.chk_show_qt)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)
        self.chk_show_qt.toggled.connect(lambda checked: self.set_show_only_bec(not checked))

        # Main tree widget
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        layout.addWidget(self.tree)
        self._build()

    def _class_chain(self):
        chain = []
        mo = self._target.metaObject()
        while mo is not None:
            chain.append(mo)
            mo = mo.superClass()
        return chain

    def set_show_only_bec(self, flag: bool):
        self._bec_only = flag
        self._build()

    def _set_equal_columns(self):
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        w = self.tree.viewport().width() or self.tree.width()
        if w > 0:
            half = max(1, w // 2)
            self.tree.setColumnWidth(0, half)
            self.tree.setColumnWidth(1, w - half)

    def _build(self):
        self.tree.clear()
        for mo in self._class_chain():
            class_name = mo.className()
            if self._bec_only and not self._is_bec_metaobject(mo):
                continue
            group_item = QTreeWidgetItem(self.tree, [class_name])
            group_item.setFirstColumnSpanned(True)
            start = mo.propertyOffset()
            end = mo.propertyCount()
            for i in range(start, end):
                prop = mo.property(i)
                if (
                    not prop.isReadable()
                    or not prop.isWritable()
                    or not prop.isStored()
                    or not prop.isDesignable()
                ):
                    continue
                name = prop.name()
                if name == "objectName":
                    continue
                value = self._target.property(name)
                self._add_property_row(group_item, name, value, prop)
            if group_item.childCount() == 0:
                idx = self.tree.indexOfTopLevelItem(group_item)
                self.tree.takeTopLevelItem(idx)
        self.tree.expandAll()
        QTimer.singleShot(0, self._set_equal_columns)

    def _enum_int(self, obj) -> int:
        return int(getattr(obj, "value", obj))

    def _make_sizepolicy_editor(self, name: str, sp):
        if not isinstance(sp, QSizePolicy):
            return None
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        h_combo = QComboBox(wrap)
        v_combo = QComboBox(wrap)
        hs = QSpinBox(wrap)
        vs = QSpinBox(wrap)
        for b in (hs, vs):
            b.setRange(0, 16777215)
        policies = [
            (QSizePolicy.Fixed, "Fixed"),
            (QSizePolicy.Minimum, "Minimum"),
            (QSizePolicy.Maximum, "Maximum"),
            (QSizePolicy.Preferred, "Preferred"),
            (QSizePolicy.Expanding, "Expanding"),
            (QSizePolicy.MinimumExpanding, "MinExpanding"),
            (QSizePolicy.Ignored, "Ignored"),
        ]
        for pol, text in policies:
            h_combo.addItem(text, self._enum_int(pol))
            v_combo.addItem(text, self._enum_int(pol))

        def _set_current(combo, val):
            idx = combo.findData(self._enum_int(val))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        _set_current(h_combo, sp.horizontalPolicy())
        _set_current(v_combo, sp.verticalPolicy())
        hs.setValue(sp.horizontalStretch())
        vs.setValue(sp.verticalStretch())

        def apply_changes():
            hp = QSizePolicy.Policy(h_combo.currentData())
            vp = QSizePolicy.Policy(v_combo.currentData())
            nsp = QSizePolicy(hp, vp)
            nsp.setHorizontalStretch(hs.value())
            nsp.setVerticalStretch(vs.value())
            self._target.setProperty(name, nsp)

        h_combo.currentIndexChanged.connect(lambda _=None: apply_changes())
        v_combo.currentIndexChanged.connect(lambda _=None: apply_changes())
        hs.valueChanged.connect(lambda _=None: apply_changes())
        vs.valueChanged.connect(lambda _=None: apply_changes())
        row.addWidget(h_combo)
        row.addWidget(v_combo)
        row.addWidget(hs)
        row.addWidget(vs)
        return wrap

    def _make_locale_editor(self, name: str, loc):
        if not isinstance(loc, QLocale):
            return None
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        lang_combo = QComboBox(wrap)
        country_combo = QComboBox(wrap)
        for lang in QLocale.Language:
            try:
                lang_int = self._enum_int(lang)
            except Exception:
                continue
            if lang_int < 0:
                continue
            name_txt = QLocale.languageToString(QLocale.Language(lang_int))
            lang_combo.addItem(name_txt, lang_int)

        def populate_countries():
            country_combo.blockSignals(True)
            country_combo.clear()
            for terr in QLocale.Country:
                try:
                    terr_int = self._enum_int(terr)
                except Exception:
                    continue
                if terr_int < 0:
                    continue
                text = QLocale.countryToString(QLocale.Country(terr_int))
                country_combo.addItem(text, terr_int)
            cur_country = self._enum_int(loc.country())
            idx = country_combo.findData(cur_country)
            if idx >= 0:
                country_combo.setCurrentIndex(idx)
            country_combo.blockSignals(False)

        cur_lang = self._enum_int(loc.language())
        idx = lang_combo.findData(cur_lang)
        if idx >= 0:
            lang_combo.setCurrentIndex(idx)
        populate_countries()

        def apply_locale():
            lang = QLocale.Language(int(lang_combo.currentData()))
            country = QLocale.Country(int(country_combo.currentData()))
            self._target.setProperty(name, QLocale(lang, country))

        lang_combo.currentIndexChanged.connect(lambda _=None: populate_countries())
        lang_combo.currentIndexChanged.connect(lambda _=None: apply_locale())
        country_combo.currentIndexChanged.connect(lambda _=None: apply_locale())
        row.addWidget(lang_combo)
        row.addWidget(country_combo)
        return wrap

    def _make_icon_editor(self, name: str, icon):
        btn = QPushButton(self)
        btn.setText("Choose…")
        if isinstance(icon, QIcon) and not icon.isNull():
            btn.setIcon(icon)

        def pick():
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Icon", "", "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
            )
            if path:
                ic = QIcon(path)
                self._target.setProperty(name, ic)
                btn.setIcon(ic)

        btn.clicked.connect(pick)
        return btn

    def _spin_pair(self, ints: bool = True):
        box1 = QSpinBox(self) if ints else QDoubleSpinBox(self)
        box2 = QSpinBox(self) if ints else QDoubleSpinBox(self)
        if ints:
            box1.setRange(-10_000_000, 10_000_000)
            box2.setRange(-10_000_000, 10_000_000)
        else:
            for b in (box1, box2):
                b.setDecimals(6)
                b.setRange(-1e12, 1e12)
                b.setSingleStep(0.1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        wrap = QWidget(self)
        wrap.setLayout(row)
        row.addWidget(box1)
        row.addWidget(box2)
        return wrap, box1, box2

    def _spin_quad(self, ints: bool = True):
        s = QSpinBox if ints else QDoubleSpinBox
        boxes = [s(self) for _ in range(4)]
        if ints:
            for b in boxes:
                b.setRange(-10_000_000, 10_000_000)
        else:
            for b in boxes:
                b.setDecimals(6)
                b.setRange(-1e12, 1e12)
                b.setSingleStep(0.1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        wrap = QWidget(self)
        wrap.setLayout(row)
        for b in boxes:
            row.addWidget(b)
        return wrap, boxes

    def _make_font_editor(self, name: str, value):
        btn = QPushButton(self)
        if isinstance(value, QFont):
            btn.setText(f"{value.family()}, {value.pointSize()}pt")
        else:
            btn.setText("Select font…")

        def pick():
            ok, font = QFontDialog.getFont(
                value if isinstance(value, QFont) else QFont(), self, "Select Font"
            )
            if ok:
                self._target.setProperty(name, font)
                btn.setText(f"{font.family()}, {font.pointSize()}pt")

        btn.clicked.connect(pick)
        return btn

    def _make_color_editor(self, initial: QColor, apply_cb):
        btn = QPushButton(self)
        if isinstance(initial, QColor):
            btn.setText(initial.name())
            btn.setStyleSheet(f"background:{initial.name()};")
        else:
            btn.setText("Select color…")

        def pick():
            col = QColorDialog.getColor(
                initial if isinstance(initial, QColor) else QColor(), self, "Select Color"
            )
            if col.isValid():
                apply_cb(col)
                btn.setText(col.name())
                btn.setStyleSheet(f"background:{col.name()};")

        btn.clicked.connect(pick)
        return btn

    def _apply_palette_color(
        self,
        name: str,
        pal: QPalette,
        group: QPalette.ColorGroup,
        role: QPalette.ColorRole,
        col: QColor,
    ):
        pal.setColor(group, role, col)
        self._target.setProperty(name, pal)

    def _make_palette_editor(self, name: str, pal: QPalette):
        if not isinstance(pal, QPalette):
            return None
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        group_combo = QComboBox(wrap)
        role_combo = QComboBox(wrap)
        pick_btn = self._make_color_editor(
            pal.color(QPalette.Active, QPalette.WindowText),
            lambda col: self._apply_palette_color(
                name, pal, QPalette.Active, QPalette.WindowText, col
            ),
        )
        groups = [
            (QPalette.Active, "Active"),
            (QPalette.Inactive, "Inactive"),
            (QPalette.Disabled, "Disabled"),
        ]
        for g, label in groups:
            group_combo.addItem(label, int(getattr(g, "value", g)))
        roles = [
            (QPalette.WindowText, "WindowText"),
            (QPalette.Window, "Window"),
            (QPalette.Base, "Base"),
            (QPalette.AlternateBase, "AlternateBase"),
            (QPalette.ToolTipBase, "ToolTipBase"),
            (QPalette.ToolTipText, "ToolTipText"),
            (QPalette.Text, "Text"),
            (QPalette.Button, "Button"),
            (QPalette.ButtonText, "ButtonText"),
            (QPalette.BrightText, "BrightText"),
            (QPalette.Highlight, "Highlight"),
            (QPalette.HighlightedText, "HighlightedText"),
        ]
        for r, label in roles:
            role_combo.addItem(label, int(getattr(r, "value", r)))

        def rewire_button():
            g = QPalette.ColorGroup(int(group_combo.currentData()))
            r = QPalette.ColorRole(int(role_combo.currentData()))
            col = pal.color(g, r)
            while row.count() > 2:
                w = row.takeAt(2).widget()
                if w:
                    w.deleteLater()
            btn = self._make_color_editor(
                col, lambda c: self._apply_palette_color(name, pal, g, r, c)
            )
            row.addWidget(btn)

        group_combo.currentIndexChanged.connect(lambda _: rewire_button())
        role_combo.currentIndexChanged.connect(lambda _: rewire_button())
        row.addWidget(group_combo)
        row.addWidget(role_combo)
        row.addWidget(pick_btn)
        return wrap

    def _make_cursor_editor(self, name: str, value):
        combo = QComboBox(self)
        shapes = [
            (Qt.ArrowCursor, "Arrow"),
            (Qt.IBeamCursor, "IBeam"),
            (Qt.WaitCursor, "Wait"),
            (Qt.CrossCursor, "Cross"),
            (Qt.UpArrowCursor, "UpArrow"),
            (Qt.SizeAllCursor, "SizeAll"),
            (Qt.PointingHandCursor, "PointingHand"),
            (Qt.ForbiddenCursor, "Forbidden"),
            (Qt.WhatsThisCursor, "WhatsThis"),
            (Qt.BusyCursor, "Busy"),
        ]
        current_shape = None
        if isinstance(value, QCursor):
            try:
                enum_val = value.shape()
                current_shape = int(getattr(enum_val, "value", enum_val))
            except Exception:
                current_shape = None
        for shape, text in shapes:
            combo.addItem(text, int(getattr(shape, "value", shape)))
        if current_shape is not None:
            idx = combo.findData(current_shape)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        def apply_index(i):
            shape_val = int(combo.itemData(i))
            self._target.setProperty(name, QCursor(Qt.CursorShape(shape_val)))

        combo.currentIndexChanged.connect(apply_index)
        return combo

    def _add_property_row(self, parent: QTreeWidgetItem, name: str, value, prop):
        item = QTreeWidgetItem(parent, [name, ""])
        editor = self._make_editor(name, value, prop)
        if editor is not None:
            self.tree.setItemWidget(item, 1, editor)
        else:
            item.setText(1, repr(value))

    def _is_bec_metaobject(self, mo) -> bool:
        cname = mo.className()
        for cls in type(self._target).mro():
            if getattr(cls, "__name__", None) == cname:
                mod = getattr(cls, "__module__", "")
                return mod.startswith("bec_widgets")
        return False

    def _enum_text(self, meta_enum: QMetaEnum, value_int: int) -> str:
        if not meta_enum.isFlag():
            key = meta_enum.valueToKey(value_int)
            return key.decode() if isinstance(key, (bytes, bytearray)) else (key or str(value_int))
        parts = []
        for i in range(meta_enum.keyCount()):
            k = meta_enum.key(i)
            v = meta_enum.value(i)
            if value_int & v:
                k = k.decode() if isinstance(k, (bytes, bytearray)) else k
                parts.append(k)
        return " | ".join(parts) if parts else "0"

    def _enum_value_to_int(self, meta_enum: QMetaEnum, value) -> int:
        try:
            return int(value)
        except Exception:
            pass
        v = getattr(value, "value", None)
        if isinstance(v, (int,)):
            return int(v)
        n = getattr(value, "name", None)
        if isinstance(n, str):
            res = meta_enum.keyToValue(n)
            if res != -1:
                return int(res)
        s = str(value)
        parts = [p.strip() for p in s.replace(",", "|").split("|")]
        keys = []
        for p in parts:
            if "." in p:
                p = p.split(".")[-1]
            keys.append(p)
        keystr = "|".join(keys)
        try:
            res = meta_enum.keysToValue(keystr)
            if res != -1:
                return int(res)
        except Exception:
            pass
        return 0

    def _make_enum_editor(self, name: str, value, prop):
        meta_enum = prop.enumerator()
        current = self._enum_value_to_int(meta_enum, value)

        if not meta_enum.isFlag():
            combo = QComboBox(self)
            for i in range(meta_enum.keyCount()):
                key = meta_enum.key(i)
                key = key.decode() if isinstance(key, (bytes, bytearray)) else key
                combo.addItem(key, meta_enum.value(i))
            idx = combo.findData(current)
            if idx < 0:
                txt = self._enum_text(meta_enum, current)
                idx = combo.findText(txt)
            combo.setCurrentIndex(max(idx, 0))

            def apply_index(i):
                v = combo.itemData(i)
                self._target.setProperty(name, int(v))

            combo.currentIndexChanged.connect(apply_index)
            return combo

        btn = QToolButton(self)
        btn.setText(self._enum_text(meta_enum, current))
        btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(btn)
        actions = []
        for i in range(meta_enum.keyCount()):
            key = meta_enum.key(i)
            key = key.decode() if isinstance(key, (bytes, bytearray)) else key
            act = menu.addAction(key)
            act.setCheckable(True)
            act.setChecked(bool(current & meta_enum.value(i)))
            actions.append(act)
        btn.setMenu(menu)

        def apply_flags():
            flags = 0
            for i, act in enumerate(actions):
                if act.isChecked():
                    flags |= meta_enum.value(i)
            self._target.setProperty(name, int(flags))
            btn.setText(self._enum_text(meta_enum, flags))

        menu.triggered.connect(lambda _a: apply_flags())
        return btn

    def _make_editor(self, name: str, value, prop):
        from qtpy.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF

        if prop.isEnumType():
            return self._make_enum_editor(name, value, prop)
        if isinstance(value, QColor):
            return self._make_color_editor(value, lambda col: self._target.setProperty(name, col))
        if isinstance(value, QFont):
            return self._make_font_editor(name, value)
        if isinstance(value, QPalette):
            return self._make_palette_editor(name, value)
        if isinstance(value, QCursor):
            return self._make_cursor_editor(name, value)
        if isinstance(value, QSizePolicy):
            ed = self._make_sizepolicy_editor(name, value)
            if ed is not None:
                return ed
        if isinstance(value, QLocale):
            ed = self._make_locale_editor(name, value)
            if ed is not None:
                return ed
        if isinstance(value, QIcon):
            ed = self._make_icon_editor(name, value)
            if ed is not None:
                return ed
        if isinstance(value, QSize):
            wrap, w, h = self._spin_pair(ints=True)
            w.setValue(value.width())
            h.setValue(value.height())
            w.valueChanged.connect(
                lambda _: self._target.setProperty(name, QSize(w.value(), h.value()))
            )
            h.valueChanged.connect(
                lambda _: self._target.setProperty(name, QSize(w.value(), h.value()))
            )
            return wrap
        if isinstance(value, QSizeF):
            wrap, w, h = self._spin_pair(ints=False)
            w.setValue(value.width())
            h.setValue(value.height())
            w.valueChanged.connect(
                lambda _: self._target.setProperty(name, QSizeF(w.value(), h.value()))
            )
            h.valueChanged.connect(
                lambda _: self._target.setProperty(name, QSizeF(w.value(), h.value()))
            )
            return wrap
        if isinstance(value, QPoint):
            wrap, x, y = self._spin_pair(ints=True)
            x.setValue(value.x())
            y.setValue(value.y())
            x.valueChanged.connect(
                lambda _: self._target.setProperty(name, QPoint(x.value(), y.value()))
            )
            y.valueChanged.connect(
                lambda _: self._target.setProperty(name, QPoint(x.value(), y.value()))
            )
            return wrap
        if isinstance(value, QPointF):
            wrap, x, y = self._spin_pair(ints=False)
            x.setValue(value.x())
            y.setValue(value.y())
            x.valueChanged.connect(
                lambda _: self._target.setProperty(name, QPointF(x.value(), y.value()))
            )
            y.valueChanged.connect(
                lambda _: self._target.setProperty(name, QPointF(x.value(), y.value()))
            )
            return wrap
        if isinstance(value, QRect):
            wrap, boxes = self._spin_quad(ints=True)
            for b, v in zip(boxes, (value.x(), value.y(), value.width(), value.height())):
                b.setValue(v)

            def apply_rect():
                self._target.setProperty(
                    name,
                    QRect(boxes[0].value(), boxes[1].value(), boxes[2].value(), boxes[3].value()),
                )

            for b in boxes:
                b.valueChanged.connect(lambda _=None: apply_rect())
            return wrap
        if isinstance(value, QRectF):
            wrap, boxes = self._spin_quad(ints=False)
            for b, v in zip(boxes, (value.x(), value.y(), value.width(), value.height())):
                b.setValue(v)

            def apply_rectf():
                self._target.setProperty(
                    name,
                    QRectF(boxes[0].value(), boxes[1].value(), boxes[2].value(), boxes[3].value()),
                )

            for b in boxes:
                b.valueChanged.connect(lambda _=None: apply_rectf())
            return wrap
        if isinstance(value, bool):
            w = QCheckBox(self)
            w.setChecked(bool(value))
            w.toggled.connect(lambda v: self._target.setProperty(name, v))
            return w
        if isinstance(value, int) and not isinstance(value, bool):
            w = QSpinBox(self)
            w.setRange(-10_000_000, 10_000_000)
            w.setValue(int(value))
            w.valueChanged.connect(lambda v: self._target.setProperty(name, v))
            return w
        if isinstance(value, float):
            w = QDoubleSpinBox(self)
            w.setDecimals(6)
            w.setRange(-1e12, 1e12)
            w.setSingleStep(0.1)
            w.setValue(float(value))
            w.valueChanged.connect(lambda v: self._target.setProperty(name, v))
            return w
        if isinstance(value, str):
            w = QLineEdit(self)
            w.setText(value)
            w.editingFinished.connect(lambda: self._target.setProperty(name, w.text()))
            return w
        return None


class DemoApp(QWidget):  # pragma: no cover:
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)

        # Create a BECWidget instance example
        waveform = self.create_waveform()

        # property editor for the BECWidget
        property_editor = PropertyEditor(waveform, show_only_bec=True)

        layout.addWidget(waveform)
        layout.addWidget(property_editor)

    def create_waveform(self):
        """Create a new waveform widget."""

        from bec_widgets.widgets.plots.waveform.waveform import Waveform

        waveform = Waveform(parent=self)
        waveform.title = "New Waveform"
        waveform.x_label = "X Axis"
        waveform.y_label = "Y Axis"
        return waveform


if __name__ == "__main__":  # pragma: no cover:
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    demo = DemoApp()
    demo.setWindowTitle("Property Editor Demo")
    demo.resize(1200, 800)
    demo.show()
    sys.exit(app.exec())
