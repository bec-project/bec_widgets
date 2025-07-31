"""
This module provides a revised property editor with a dark theme that groups
properties by their originating class.  Each group uses a header row and
alternating row colours to resemble Qt Designer.  Dynamic properties are
listed separately.  Enumeration and flag properties are displayed as read-only
strings using QMetaEnum conversion functions.
"""

from __future__ import annotations

import sys
from qtpy.QtCore import Qt, QSettings, QByteArray
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QFileDialog,
)
from qtpy.QtGui import QColor, QBrush


class WidgetStateManager:
    def __init__(self, widget: QWidget) -> None:
        self.widget = widget

    def save_state(self, filename: str | None = None) -> None:
        if not filename:
            filename, _ = QFileDialog.getSaveFileName(
                self.widget, "Save Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._save_widget_state_qsettings(self.widget, settings)

    def load_state(self, filename: str | None = None) -> None:
        if not filename:
            filename, _ = QFileDialog.getOpenFileName(
                self.widget, "Load Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._load_widget_state_qsettings(self.widget, settings)

    def _save_widget_state_qsettings(self, widget: QWidget, settings: QSettings) -> None:
        if widget.property("skip_settings") is True:
            return
        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if (
                name == "objectName"
                or not prop.isReadable()
                or not prop.isWritable()
                or not prop.isStored()
            ):
                continue
            value = widget.property(name)
            settings.setValue(name, value)
        settings.endGroup()
        for prop_name in widget.dynamicPropertyNames():
            name_str = (
                bytes(prop_name).decode()
                if isinstance(prop_name, (bytes, bytearray, QByteArray))
                else str(prop_name)
            )
            key = f"{widget_name}/{name_str}"
            value = widget.property(name_str)
            settings.setValue(key, value)
        for child in widget.children():
            if (
                child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._save_widget_state_qsettings(child, settings)

    def _load_widget_state_qsettings(self, widget: QWidget, settings: QSettings) -> None:
        if widget.property("skip_settings") is True:
            return
        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if settings.contains(name):
                value = settings.value(name)
                widget.setProperty(name, value)
        settings.endGroup()
        prefix = widget_name + "/"
        for key in settings.allKeys():
            if key.startswith(prefix):
                name = key[len(prefix) :]
                value = settings.value(key)
                widget.setProperty(name, value)
        for child in widget.children():
            if (
                child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._load_widget_state_qsettings(child, settings)

    def _get_full_widget_name(self, widget: QWidget) -> str:
        name = widget.objectName() or widget.metaObject().className()
        parent = widget.parent()
        while parent:
            parent_name = parent.objectName() or parent.metaObject().className()
            name = f"{parent_name}.{name}"
            parent = parent.parent()
        return name


class PropertyEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target: QWidget | None = None
        layout = QVBoxLayout(self)
        self.header_label = QLabel(self)
        self.header_label.setStyleSheet(
            "QLabel { background-color: #323a45; color: #ffffff; font-weight: bold; padding: 4px; }"
        )
        layout.addWidget(self.header_label)
        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Property", "Value"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setStyleSheet(
            "QTreeWidget { background-color: #1e1e1e; alternate-background-color: #252526; color: #d4d4d4; }"
            "QHeaderView::section { background-color: #2d2d30; color: #f0f0f0; padding-left: 4px; }"
            "QTreeWidget::item { padding: 2px; }"
        )
        layout.addWidget(self._tree)

    def set_target(self, widget: QWidget | None) -> None:
        self._tree.clear()
        self._target = widget
        if widget is None:
            self.header_label.setText("")
            return
        obj_name = widget.objectName() or widget.metaObject().className()
        class_name = widget.metaObject().className()
        self.header_label.setText(f"{obj_name} : {class_name}")
        meta_objs = []
        meta = widget.metaObject()
        while meta:
            meta_objs.append(meta)
            meta = meta.superClass()
        prop_starts = {m: m.propertyOffset() for m in meta_objs}
        for index in range(len(meta_objs) - 1, -1, -1):
            current_meta = meta_objs[index]
            if index > 0:
                next_meta = meta_objs[index - 1]
                start = prop_starts[current_meta]
                end = prop_starts[next_meta] - 1
            else:
                start = prop_starts[current_meta]
                end = current_meta.propertyCount() - 1
            properties_added = False
            group_item = QTreeWidgetItem([current_meta.className(), ""])
            group_item.setFirstColumnSpanned(True)
            group_brush = QBrush(QColor(45, 49, 55))
            for col in range(2):
                group_item.setBackground(col, group_brush)
                group_item.setForeground(col, QBrush(QColor(255, 255, 255)))
            for prop_index in range(start, end + 1):
                prop = current_meta.property(prop_index)
                name = prop.name()
                # NOTE: call isDesignable(widget) rather than isDesignable() alone.
                if (
                    name == "objectName"
                    or not prop.isReadable()
                    or not prop.isWritable()
                    or not prop.isStored()
                    or not prop.isDesignable()
                ):
                    continue
                value = widget.property(name)
                editable = True
                if prop.isEnumType() or prop.isFlagType():
                    enumerator = prop.enumerator()
                    try:
                        ivalue = int(value)
                    except Exception:
                        ivalue = 0
                    display_value = (
                        enumerator.valueToKeys(ivalue)
                        if prop.isFlagType()
                        else enumerator.valueToKey(ivalue)
                    ) or str(value)
                    editable = False
                    self._add_property_row(group_item, name, display_value, editable)
                else:
                    self._add_property_row(group_item, name, value, editable)
                properties_added = True
            if properties_added:
                self._tree.addTopLevelItem(group_item)
        dyn_names = [
            (bytes(p).decode() if isinstance(p, (bytes, bytearray, QByteArray)) else str(p))
            for p in widget.dynamicPropertyNames()
        ]
        if dyn_names:
            dyn_group = QTreeWidgetItem(["Dynamic Properties", ""])
            dyn_group.setFirstColumnSpanned(True)
            dyn_brush = QBrush(QColor(60, 65, 72))
            for col in range(2):
                dyn_group.setBackground(col, dyn_brush)
                dyn_group.setForeground(col, QBrush(QColor(255, 255, 255)))
            for name_str in dyn_names:
                value = widget.property(name_str)
                self._add_property_row(dyn_group, name_str, value, True)
            self._tree.addTopLevelItem(dyn_group)

    def _add_property_row(
        self, parent: QTreeWidgetItem, name: str, value: object, editable: bool = True
    ) -> None:
        if self._target is None:
            return
        item = QTreeWidgetItem(parent, [name, ""])
        editor: QWidget | None = None
        if editable:
            if isinstance(value, bool):
                editor = QCheckBox(self)
                editor.setChecked(value)
                editor.stateChanged.connect(
                    lambda state, prop=name, w=self._target: w.setProperty(prop, bool(state))
                )
            elif isinstance(value, int) and not isinstance(value, bool):
                spin = QSpinBox(self)
                spin.setRange(-2147483648, 2147483647)
                spin.setValue(int(value))
                spin.valueChanged.connect(
                    lambda val, prop=name, w=self._target: w.setProperty(prop, int(val))
                )
                editor = spin
            elif isinstance(value, float):
                dspin = QDoubleSpinBox(self)
                dspin.setDecimals(6)
                dspin.setRange(-1e12, 1e12)
                dspin.setValue(float(value))
                dspin.valueChanged.connect(
                    lambda val, prop=name, w=self._target: w.setProperty(prop, float(val))
                )
                editor = dspin
            elif isinstance(value, str):
                line = QLineEdit(self)
                line.setText(value)
                line.textChanged.connect(
                    lambda text, prop=name, w=self._target: w.setProperty(prop, str(text))
                )
                editor = line
        # Always use self._tree to assign the editor widget
        if editor:
            self._tree.setItemWidget(item, 1, editor)
        else:
            item.setText(1, str(value))
        item.setForeground(0, QBrush(QColor(200, 200, 200)))


class ExampleApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Property Manager Demo")
        self.setObjectName("DemoWindow")
        main_layout = QVBoxLayout(self)
        selector_layout = QHBoxLayout()
        selector_label = QLabel("Select widget:")
        self.selector = QComboBox()
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.selector)
        main_layout.addLayout(selector_layout)
        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("DemoLineEdit")
        self.line_edit.setText("Hello")
        self.spin_box = QSpinBox()
        self.spin_box.setObjectName("DemoSpinBox")
        self.spin_box.setValue(42)
        self.check_box = QCheckBox("Check me")
        self.check_box.setObjectName("DemoCheckBox")
        self.check_box.setChecked(True)
        self.widgets = {
            "Line Edit": self.line_edit,
            "Spin Box": self.spin_box,
            "Check Box": self.check_box,
        }
        for name in self.widgets:
            self.selector.addItem(name)
        self.property_editor = PropertyEditor()
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Properties")
        self.load_btn = QPushButton("Load Properties")
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        main_layout.addWidget(self.line_edit)
        main_layout.addWidget(self.spin_box)
        main_layout.addWidget(self.check_box)
        main_layout.addWidget(self.property_editor)
        main_layout.addLayout(btn_layout)
        self.selector.currentTextChanged.connect(self.on_widget_selected)
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.load_btn.clicked.connect(self.on_load_clicked)
        if self.selector.count() > 0:
            self.on_widget_selected(self.selector.currentText())

    def on_widget_selected(self, name: str) -> None:
        widget = self.widgets.get(name)
        self.property_editor.set_target(widget)

    def on_save_clicked(self) -> None:
        name = self.selector.currentText()
        widget = self.widgets.get(name)
        if widget is not None:
            manager = WidgetStateManager(widget)
            manager.save_state()

    def on_load_clicked(self) -> None:
        name = self.selector.currentText()
        widget = self.widgets.get(name)
        if widget is not None:
            manager = WidgetStateManager(widget)
            manager.load_state()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = ExampleApp()
    demo.resize(500, 500)
    demo.show()
    sys.exit(app.exec_())
