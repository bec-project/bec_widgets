"""Redesigned LMFit dialog built with plain QWidgets (comparison counterpart of the QML view)."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.dap.lmfit_dialog.fit_dialog_base import FitDialogBase
from bec_widgets.widgets.dap.lmfit_dialog.fit_summary import QUALITY_LABELS, FitSummary
from bec_widgets.widgets.dap.lmfit_dialog.fit_theme import fit_dialog_palette


class LMFitDialogQWidget(FitDialogBase):
    """Fit summary and parameters of LMFit DAP processes, drawn with QWidgets."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._curve_buttons: dict[str, QToolButton] = {}
        self._curve_key: tuple = ()
        self._move_buttons: dict[str, QPushButton] = {}
        self._param_rows: list[tuple[QLabel, QLabel, QLabel, QToolButton]] = []
        self._param_key: tuple | None = None
        self._build_ui()
        self.apply_theme(get_theme_name())
        self._render()

    ################################################################################
    # Layout

    def _build_ui(self):
        self.setObjectName("FitDialog")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.curve_bar = QWidget(self)
        self.curve_bar_layout = QHBoxLayout(self.curve_bar)
        self.curve_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.curve_bar_layout.setSpacing(4)
        self.curve_group = QButtonGroup(self)
        self.curve_group.setExclusive(True)
        root.addWidget(self.curve_bar)

        self.empty_label = QLabel(
            "No fit results yet.\nAdd a fit model to a curve to see its parameters here.", self
        )
        self.empty_label.setObjectName("FitEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label, 1)

        self.body = QWidget(self)
        body_layout = QHBoxLayout(self.body) if self.compact else QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        root.addWidget(self.body, 1)

        # Summary card
        self.summary_card = QFrame(self.body)
        self.summary_card.setObjectName("FitCard")
        card = QVBoxLayout(self.summary_card)
        card.setContentsMargins(12, 10, 12, 10)
        card.setSpacing(6)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.model_label = QLabel(self.summary_card)
        self.model_label.setObjectName("FitModel")
        self.quality_pill = QLabel(self.summary_card)
        self.quality_pill.setObjectName("FitPill")
        header.addWidget(self.model_label, 1)
        header.addWidget(self.quality_pill, 0, Qt.AlignmentFlag.AlignRight)
        card.addLayout(header)
        self.details_label = QLabel(self.summary_card)
        self.details_label.setObjectName("FitMuted")
        self.details_label.setWordWrap(True)
        card.addWidget(self.details_label)
        metrics = QHBoxLayout()
        metrics.setSpacing(6)
        self.metric_values: list[QLabel] = []
        self.metric_names: list[QLabel] = []
        for _ in range(3):
            tile = QFrame(self.summary_card)
            tile.setObjectName("FitTile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(8, 4, 8, 4)
            tile_layout.setSpacing(0)
            name = QLabel(tile)
            name.setObjectName("FitMuted")
            value = QLabel(tile)
            value.setObjectName("FitMetric")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            tile_layout.addWidget(name)
            tile_layout.addWidget(value)
            metrics.addWidget(tile, 1)
            self.metric_names.append(name)
            self.metric_values.append(value)
        card.addLayout(metrics)
        self.message_label = QLabel(self.summary_card)
        self.message_label.setObjectName("FitWarning")
        self.message_label.setWordWrap(True)
        card.addWidget(self.message_label)
        if self.compact:
            card.addStretch(1)
            self.summary_card.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
            )
        body_layout.addWidget(self.summary_card, 2 if self.compact else 0)

        # Parameter table
        self.param_card = QFrame(self.body)
        self.param_card.setObjectName("FitCard")
        param_outer = QVBoxLayout(self.param_card)
        param_outer.setContentsMargins(0, 6, 0, 6)
        param_outer.setSpacing(0)
        title = QLabel("Parameters", self.param_card)
        title.setObjectName("FitSection")
        title.setContentsMargins(12, 0, 12, 4)
        param_outer.addWidget(title)
        self.param_scroll = QScrollArea(self.param_card)
        self.param_scroll.setWidgetResizable(True)
        self.param_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.param_scroll.setObjectName("FitScroll")
        self.param_host = QWidget()
        self.param_host.setObjectName("FitParamHost")
        self.param_grid = QGridLayout(self.param_host)
        self.param_grid.setContentsMargins(12, 0, 12, 0)
        self.param_grid.setHorizontalSpacing(10)
        self.param_grid.setVerticalSpacing(2)
        self.param_scroll.setWidget(self.param_host)
        param_outer.addWidget(self.param_scroll, 1)
        body_layout.addWidget(self.param_card, 3 if self.compact else 1)

    ################################################################################
    # Rendering

    def _render(self):
        if not hasattr(self, "param_grid"):
            return
        self._render_curves()
        summary = self.current_summary
        has_data = summary is not None
        self.empty_label.setVisible(not has_data)
        self.body.setVisible(has_data)
        if not has_data:
            return
        self.summary_card.setVisible(not self.hide_summary)
        self.param_card.setVisible(not self.hide_parameters)
        self._render_summary(summary)
        self._render_params(summary)

    def _render_curves(self):
        self.curve_bar.setVisible(self.show_curve_selection())
        key = tuple((cid, self.curve_quality(cid)) for cid in self.curve_ids)
        if key != self._curve_key:
            self._curve_key = key
            for button in self._curve_buttons.values():
                self.curve_group.removeButton(button)
                button.hide()
                button.deleteLater()
            self._curve_buttons = {}
            while self.curve_bar_layout.count():
                self.curve_bar_layout.takeAt(0)
            for curve_id, quality in key:
                button = QToolButton(self.curve_bar)
                button.setObjectName("FitCurveChip")
                button.setText(curve_id)
                button.setCheckable(True)
                button.setAutoRaise(True)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setIcon(
                    material_icon(
                        "circle", size=(10, 10), color=self._quality_color(quality), filled=True
                    )
                )
                button.setIconSize(QSize(10, 10))
                button.setToolTip(f"{curve_id}: {QUALITY_LABELS[quality]}")
                button.clicked.connect(lambda _=False, cid=curve_id: self.select_curve(cid))
                self.curve_group.addButton(button)
                self.curve_bar_layout.addWidget(button)
                self._curve_buttons[curve_id] = button
            self.curve_bar_layout.addStretch(1)
        for curve_id, button in self._curve_buttons.items():
            button.setChecked(curve_id == self.fit_curve_id)

    def _render_summary(self, summary: FitSummary):
        self.model_label.setText(summary.model_name)
        self.model_label.setToolTip(summary.model)
        self.quality_pill.setText(summary.quality_label)
        color = self._quality_color(summary.quality)
        self.quality_pill.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 9px; padding: 1px 8px;"
        )
        self.details_label.setText(summary.details_text)
        self.details_label.setVisible(bool(summary.details_text))
        for (name, value, tip), name_label, value_label in zip(
            summary.metrics, self.metric_names, self.metric_values
        ):
            name_label.setText(name)
            value_label.setText(value)
            name_label.parentWidget().setToolTip(tip)
        message = summary.message if summary.show_message else ""
        loose = summary.loose_params
        if not message and loose:
            message = f"Poorly constrained: {', '.join(loose)}"
        self.message_label.setText(message)
        self.message_label.setVisible(bool(message))

    def _render_params(self, summary: FitSummary):
        layout_key = tuple((p.name, p.name in self.active_action_list) for p in summary.params)
        if layout_key != self._param_key:
            self._param_key = layout_key
            self._build_param_rows(layout_key)
        for param, (name, value, error, copy) in zip(summary.params, self._param_rows):
            for label in (name, value, error):
                label.setToolTip(param.tooltip)
            value.setText(param.value_text)
            copy.setToolTip(f"Copy {param.name} = {param.value}")
            if param.state == "fixed":
                text, style = "fixed", "FitMuted"
            elif param.state == "derived":
                text, style = "derived", "FitMuted"
            elif param.state == "unknown":
                text, style = "no estimate", "FitMuted"
            else:
                rel = param.relative_error_text
                text = f"± {param.stderr_text}" + (f"  ({rel})" if rel else "")
                style = "FitWarningText" if param.state == "loose" else "FitMuted"
            error.setText(text)
            if error.objectName() != style:
                error.setObjectName(style)
                error.style().unpolish(error)
                error.style().polish(error)
        self._render_actions()

    def _build_param_rows(self, layout_key: tuple):
        while self.param_grid.count():
            item = self.param_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self._move_buttons = {}
        self._param_rows = []
        for col, text in enumerate(["Name", "Value", "Std error", ""]):
            label = QLabel(text, self.param_host)
            label.setObjectName("FitMuted")
            self.param_grid.addWidget(label, 0, col)
        for row, (param_name, movable) in enumerate(layout_key, start=1):
            name = QLabel(param_name, self.param_host)
            value = QLabel(self.param_host)
            value.setObjectName("FitValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            error = QLabel(self.param_host)
            actions = QWidget(self.param_host)
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(2)
            copy = QToolButton(actions)
            copy.setAutoRaise(True)
            copy.setIcon(
                material_icon(
                    "content_copy",
                    size=(14, 14),
                    color=self._palette["muted"],
                    convert_to_pixmap=False,
                )
            )
            copy.clicked.connect(lambda _=False, n=param_name: self._copy_param(n))
            actions_layout.addWidget(copy)
            if movable:
                move = QPushButton("Move", actions)
                move.setObjectName("FitMove")
                move.setIcon(material_icon("my_location", size=(14, 14), convert_to_pixmap=False))
                move.clicked.connect(lambda _=False, n=param_name: self.request_move(n))
                actions_layout.addWidget(move)
                self._move_buttons[param_name] = move
            self.param_grid.addWidget(name, row, 0)
            self.param_grid.addWidget(value, row, 1)
            self.param_grid.addWidget(error, row, 2)
            self.param_grid.addWidget(actions, row, 3, Qt.AlignmentFlag.AlignRight)
            self._param_rows.append((name, value, error, copy))
        self.param_grid.setColumnStretch(2, 1)
        self.param_grid.setRowStretch(len(layout_key) + 1, 1)

    def _copy_param(self, param_name: str):
        summary = self.current_summary
        if summary is None:
            return
        for param in summary.params:
            if param.name == param_name:
                self.copy_to_clipboard(str(param.value))
                return

    def _render_actions(self):
        summary = self.current_summary
        for name, button in self._move_buttons.items():
            button.setEnabled(self.enable_actions)
            if self.enable_actions and summary is not None:
                value = next((p.value_text for p in summary.params if p.name == name), "")
                button.setToolTip(f"Move to {name} = {value}")
            else:
                button.setToolTip("Moving is not available right now")

    ################################################################################
    # Theme

    def _quality_color(self, quality: str) -> str:
        return self._palette.get(f"quality_{quality}", self._palette["muted"])

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """Restyle the dialog for the given theme.

        Args:
            theme (str): "dark" or "light".
        """
        self._palette = fit_dialog_palette()
        p = self._palette
        self.setStyleSheet(f"""
            #FitCard {{ background: {p['card']}; border: 1px solid {p['border']};
                        border-radius: 8px; }}
            #FitTile {{ background: {p['field']}; border-radius: 6px; }}
            #FitModel {{ font-size: 15px; font-weight: 600; }}
            #FitSection {{ font-weight: 600; }}
            #FitMetric {{ font-size: 15px; font-weight: 600; }}
            #FitValue {{ font-weight: 600; }}
            #FitMuted, #FitEmpty {{ color: {p['muted']}; }}
            #FitWarning {{ color: {p['fg']}; background: {p['warning_bg']};
                           border-radius: 6px; padding: 4px 8px; }}
            #FitWarningText {{ color: {p['warning']}; }}
            #FitScroll, #FitParamHost {{ background: transparent; }}
            #FitCurveChip {{ border: 1px solid {p['border']}; border-radius: 12px;
                             padding: 2px 10px; }}
            #FitCurveChip:checked {{ background: {p['selection']}; border-color: {p['primary']}; }}
            #FitMove {{ background: {p['primary']}; color: {p['on_primary']}; border: none;
                        border-radius: 4px; padding: 2px 10px; }}
            #FitMove:disabled {{ background: {p['field']}; color: {p['muted']}; }}
            """)
        if hasattr(self, "param_grid"):
            self._curve_key = ()
            self._param_key = None
            self._render()
