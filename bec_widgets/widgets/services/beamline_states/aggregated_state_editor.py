from __future__ import annotations

import json
from typing import Any

from bec_lib import bl_states
from bec_qthemes import material_icon
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_accent_colors


class AggregatedStateConfigEditor(QWidget):
    """Compact editor and rule inspector for an aggregated beamline state."""

    changed = Signal()

    _EVALUATION_METHODS = (
        ("Any — one or more labels", "any"),
        ("All — every label", "all"),
        ("Exclusive — exactly one label", "exclusive"),
        ("Disabled — no validation", None),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self._model = bl_states.AggregatedStateConfig
        self._config: bl_states.AggregatedStateConfig | None = None
        self._baseline: dict[str, Any] = {}
        self._active_labels: set[str] = set()
        self._label_items: dict[str, QTreeWidgetItem] = {}

        self._evaluation_method = QComboBox(self)
        self._evaluation_method.setObjectName("aggregated_state_evaluation_method")
        for label, value in self._EVALUATION_METHODS:
            self._evaluation_method.addItem(label, value)
        self._evaluation_method.currentIndexChanged.connect(lambda _index: self.changed.emit())

        self._summary = QLabel(self)
        self._summary.setObjectName("aggregated_state_summary")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Evaluation", self))
        controls.addWidget(self._evaluation_method, 1)
        controls.addWidget(self._summary)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("aggregated_state_tree")
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Rule", "Expected", "Tolerance / details"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setMinimumHeight(160)
        self._tree.setMaximumHeight(360)
        self._tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        expand_button = QToolButton(self)
        expand_button.setIcon(material_icon("unfold_more", convert_to_pixmap=False))
        expand_button.setToolTip("Expand all rules")
        expand_button.clicked.connect(self._tree.expandAll)
        collapse_button = QToolButton(self)
        collapse_button.setIcon(material_icon("unfold_less", convert_to_pixmap=False))
        collapse_button.setToolTip("Collapse all rules")
        collapse_button.clicked.connect(self._tree.collapseAll)

        tree_controls = QHBoxLayout()
        tree_controls.setContentsMargins(0, 0, 0, 0)
        tree_controls.addWidget(QLabel("Configured rules", self))
        tree_controls.addStretch(1)
        tree_controls.addWidget(expand_button)
        tree_controls.addWidget(collapse_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addLayout(tree_controls)
        layout.addWidget(self._tree)

    @property
    def model(self) -> type[bl_states.AggregatedStateConfig]:
        return self._model

    @property
    def widgets(self) -> dict[str, QWidget]:
        return {"evaluation_method": self._evaluation_method}

    @property
    def tree(self) -> QTreeWidget:
        return self._tree

    def input_widget(self, name: str) -> QWidget:
        if name != "evaluation_method":
            raise KeyError(name)
        return self._evaluation_method

    def set_partial_data(self, data: dict[str, Any]) -> None:
        merged_data = self._config.model_dump() if self._config is not None else {}
        merged_data.update(data)
        config = self._model.model_validate(merged_data)
        self._config = config
        self._set_evaluation_method(config.evaluation_method)
        self._populate_tree(config)
        self.changed.emit()

    def raw_data(self) -> dict[str, Any]:
        if self._config is None:
            return {}
        data = self._config.model_dump()
        data["evaluation_method"] = self._evaluation_method.currentData()
        return data

    def raw_editable_data(self) -> dict[str, Any]:
        return {key: value for key, value in self.raw_data().items() if key != "name"}

    def model_instance(self) -> bl_states.AggregatedStateConfig:
        return self._model.model_validate(self.raw_data())

    def dirty_fields(self) -> set[str]:
        current = self.raw_data()
        fields = set(current) | set(self._baseline)
        return {field for field in fields if current.get(field) != self._baseline.get(field)}

    def mark_clean(self) -> None:
        self._baseline = self.raw_data()

    def set_active_label_text(self, label_text: str) -> None:
        configured_labels = set(self._label_items)
        self._active_labels = set(label_text.split("|")) & configured_labels
        self._apply_label_markers()

    def cleanup(self) -> None:
        self._tree.clear()
        self._label_items.clear()

    def _set_evaluation_method(self, value: str | None) -> None:
        self._evaluation_method.blockSignals(True)
        try:
            for index in range(self._evaluation_method.count()):
                if self._evaluation_method.itemData(index) == value:
                    self._evaluation_method.setCurrentIndex(index)
                    return
            raise ValueError(f"Unsupported evaluation method: {value!r}")
        finally:
            self._evaluation_method.blockSignals(False)

    def _populate_tree(self, config: bl_states.AggregatedStateConfig) -> None:
        self._tree.clear()
        self._label_items.clear()
        device_names: set[str] = set()
        requirement_count = 0

        for label, state_config in config.states.items():
            label_item = QTreeWidgetItem([label, "", ""])
            label_item.setData(0, Qt.ItemDataRole.UserRole, label)
            label_item.setFirstColumnSpanned(False)
            self._tree.addTopLevelItem(label_item)
            self._label_items[label] = label_item

            for device_name, device_config in state_config.devices.items():
                device_names.add(device_name)
                device_item = QTreeWidgetItem([device_name, "", ""])
                device_item.setIcon(0, material_icon("memory", convert_to_pixmap=False))
                label_item.addChild(device_item)
                for target, signal_config in self._requirements(device_config):
                    requirement_count += 1
                    expected = (
                        f"at: {signal_config.at}"
                        if signal_config.at is not None
                        else self._format_value(signal_config.value)
                    )
                    tolerance = f"± {signal_config.abs_tol:g}"
                    device_item.addChild(QTreeWidgetItem([target, expected, tolerance]))

            if state_config.transition_metadata:
                metadata = json.dumps(
                    state_config.transition_metadata,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                display = metadata if len(metadata) <= 100 else f"{metadata[:99]}…"
                transition_item = QTreeWidgetItem(["Transition metadata", "", display])
                transition_item.setToolTip(2, metadata)
                transition_item.setForeground(0, QBrush(self.palette().placeholderText().color()))
                transition_item.setForeground(2, QBrush(self.palette().placeholderText().color()))
                label_item.addChild(transition_item)

        self._summary.setText(
            f"{len(config.states)} labels · {len(device_names)} devices · "
            f"{requirement_count} requirements"
        )
        self._tree.collapseAll()
        self._apply_label_markers()

    @staticmethod
    def _requirements(
        device_config: bl_states.DeviceConfig | bl_states.SignalConfig,
    ) -> list[tuple[str, bl_states.SignalConfig]]:
        if isinstance(device_config, bl_states.SignalConfig):
            return [("readback", device_config)]

        requirements: list[tuple[str, bl_states.SignalConfig]] = []
        if device_config.value is not None or device_config.at is not None:
            requirements.append(
                (
                    "readback",
                    bl_states.SignalConfig(
                        value=device_config.value,
                        at=device_config.at,
                        abs_tol=device_config.abs_tol,
                    ),
                )
            )
        if device_config.low_limit is not None:
            requirements.append(("low limit", device_config.low_limit))
        if device_config.high_limit is not None:
            requirements.append(("high limit", device_config.high_limit))
        requirements.extend(
            (name, signal) for name, signal in (device_config.signals or {}).items()
        )
        return requirements

    @staticmethod
    def _format_value(value: Any) -> str:
        return repr(value) if isinstance(value, str) else str(value)

    def _apply_label_markers(self) -> None:
        active_color = get_accent_colors().success.name()
        for label, item in self._label_items.items():
            active = label in self._active_labels
            item.setIcon(
                0,
                material_icon(
                    "check_circle" if active else "radio_button_unchecked",
                    filled=active,
                    color=active_color if active else None,
                    convert_to_pixmap=False,
                ),
            )
            font = item.font(0)
            font.setBold(active)
            item.setFont(0, font)
            if active:
                item.setExpanded(True)
