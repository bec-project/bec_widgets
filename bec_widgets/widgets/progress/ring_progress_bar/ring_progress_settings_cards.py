from __future__ import annotations

import os
from typing import TYPE_CHECKING

from bec_qthemes._icon.material_icons import material_icon
from qtpy.QtCore import QSize
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import UILoader
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget
from bec_widgets.widgets.progress.ring_progress_bar.ring import Ring
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import (
        RingProgressBar,
        RingProgressContainerWidget,
    )


class RingCardWidget(QFrame):
    def __init__(self, ring: Ring, container: RingProgressContainerWidget, parent=None):
        super().__init__(parent)

        self.ring = ring
        self.container = container
        self.details_visible = False
        self.setProperty("skip_settings", True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("RingCardWidget")

        bg = self._get_theme_color("BORDER")
        self.setStyleSheet(f"""
            #RingCardWidget {{
                border: 1px solid {bg.name() if bg else '#CCCCCC'};
                border-radius: 4px;
            }}
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._init_header(layout)
        self._init_details(layout)

        self._init_values()
        self._connect_signals()
        self.mode_combo.setCurrentText(self._get_display_mode_string(self.ring.config.mode))
        self._set_widget_mode_enabled(self.ring.config.mode)

    def _get_theme_color(self, color_name: str) -> QColor | None:
        app = QApplication.instance()
        if not app:
            return
        if not app.theme:
            return
        return app.theme.color(color_name)

    def _init_header(self, parent_layout: QVBoxLayout):
        """Create the collapsible header with basic controls"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.expand_btn = QPushButton("▶")
        self.expand_btn.setFixedWidth(24)
        self.expand_btn.clicked.connect(self.toggle_details)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Manual", "Scan Progress", "Device Readback"])
        self.mode_combo.currentTextChanged.connect(self._update_mode)

        delete_btn = QPushButton(material_icon("delete"), "")

        color = self._get_theme_color("ACCENT_HIGHLIGHT")
        delete_btn.setStyleSheet(f"background-color: {color.name() if color else '#CC181E'}")
        delete_btn.clicked.connect(self._delete_self)

        layout.addWidget(self.expand_btn)
        layout.addWidget(QLabel("Mode"))
        layout.addWidget(self.mode_combo)
        layout.addStretch()
        layout.addWidget(delete_btn)

        parent_layout.addWidget(header)

    def _init_details(self, parent_layout: QVBoxLayout):
        """Create the collapsible details area with the UI file"""
        self.details = QWidget()
        self.details.setVisible(False)

        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)

        # Load UI file into details area
        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "ring_settings.ui"), self.details)
        details_layout.addWidget(self.ui)

        parent_layout.addWidget(self.details)

    def toggle_details(self):
        """Toggle visibility of the details area"""
        self.details_visible = not self.details_visible
        self.details.setVisible(self.details_visible)
        self.expand_btn.setText("▼" if self.details_visible else "▶")

    # --------------------------------------------------------

    def _connect_signals(self):
        """Connect UI signals to ring methods"""
        # Data connections
        self.ui.value_spin_box.valueChanged.connect(self.ring.set_value)
        self.ui.min_spin_box.valueChanged.connect(self._update_min_max)
        self.ui.max_spin_box.valueChanged.connect(self._update_min_max)

        # Config connections
        self.ui.start_angle_spin_box.valueChanged.connect(self.ring.set_start_angle)
        self.ui.direction_combo_box.currentIndexChanged.connect(self._update_direction)
        self.ui.line_width_spin_box.valueChanged.connect(self.ring.set_line_width)
        self.ui.background_color_button.color_changed.connect(self.ring.set_background)
        self.ui.ring_color_button.color_changed.connect(self._on_ring_color_changed)
        self.ui.device_combo_box.device_selected.connect(self._on_device_changed)
        self.ui.signal_combo_box.device_signal_changed.connect(self._on_signal_changed)

    def _init_values(self):
        """Initialize UI values from ring config"""
        # Data values
        self.ui.value_spin_box.setRange(-1e6, 1e6)
        self.ui.value_spin_box.setValue(self.ring.config.value)

        self.ui.min_spin_box.setRange(-1e6, 1e6)
        self.ui.min_spin_box.setValue(self.ring.config.min_value)

        self.ui.max_spin_box.setRange(-1e6, 1e6)
        self.ui.max_spin_box.setValue(self.ring.config.max_value)
        self._update_min_max()

        self.ui.device_combo_box.setEditable(True)
        self.ui.signal_combo_box.setEditable(True)

        device, signal = self.ring.config.device, self.ring.config.signal
        if device:
            self.ui.device_combo_box.set_device(device)
        if signal:
            for i in range(self.ui.signal_combo_box.count()):
                data_item = self.ui.signal_combo_box.itemData(i)
                if data_item and data_item.get("obj_name") == signal:
                    self.ui.signal_combo_box.setCurrentIndex(i)
                    break

        # Config values
        self.ui.start_angle_spin_box.setValue(self.ring.config.start_position)
        self.ui.direction_combo_box.setCurrentIndex(0 if self.ring.config.direction == -1 else 1)
        self.ui.line_width_spin_box.setRange(1, 100)
        self.ui.line_width_spin_box.setValue(self.ring.config.line_width)

        # Colors
        self.ui.ring_color_button.set_color(self.ring.color)
        self.ui.color_sync_button.setCheckable(True)
        self.ui.color_sync_button.setChecked(self.ring.config.link_colors)

        # Set initial button state based on link_colors
        if self.ring.config.link_colors:
            self.ui.color_sync_button.setIcon(material_icon("link"))
            self.ui.color_sync_button.setToolTip(
                "Colors are linked - background derives from main color"
            )
            self.ui.background_color_button.setEnabled(False)
            self.ui.background_color_label.setEnabled(False)
            # Trigger sync to ensure background color is derived from main color
            self.ring.set_color(self.ring.config.color)
            self.ui.background_color_button.set_color(self.ring.background_color)
        else:
            self.ui.color_sync_button.setIcon(material_icon("link_off"))
            self.ui.color_sync_button.setToolTip(
                "Colors are unlinked - set background independently"
            )
            self.ui.background_color_button.setEnabled(True)
            self.ui.background_color_label.setEnabled(True)
            self.ui.background_color_button.set_color(self.ring.background_color)

        self.ui.color_sync_button.toggled.connect(self._toggle_color_link)

    # --------------------------------------------------------

    def _toggle_color_link(self, checked: bool):
        """Toggle the color linking between main and background color"""
        self.ring.config.link_colors = checked

        # Update button icon and tooltip based on state
        if checked:
            self.ui.color_sync_button.setIcon(material_icon("link"))
            self.ui.color_sync_button.setToolTip(
                "Colors are linked - background derives from main color"
            )
            # Trigger background color update by calling set_color
            self.ring.set_color(self.ring.config.color)
            # Update UI to show the new background color
            self.ui.background_color_button.set_color(self.ring.background_color)
        else:
            self.ui.color_sync_button.setIcon(material_icon("link_off"))
            self.ui.color_sync_button.setToolTip(
                "Colors are unlinked - set background independently"
            )

        # Enable/disable background color controls based on link state
        self.ui.background_color_button.setEnabled(not checked)
        self.ui.background_color_label.setEnabled(not checked)

    def _on_ring_color_changed(self, color: QColor):
        """Handle ring color changes and update background if colors are linked"""
        self.ring.set_color(color)
        # If colors are linked, update the background color button to show the new derived color
        if self.ring.config.link_colors:
            self.ui.background_color_button.set_color(self.ring.background_color)

    def _update_min_max(self):
        self.ui.value_spin_box.setRange(self.ui.min_spin_box.value(), self.ui.max_spin_box.value())
        self.ring.set_min_max_values(self.ui.min_spin_box.value(), self.ui.max_spin_box.value())

    def _update_direction(self, index: int):
        self.ring.config.direction = -1 if index == 0 else 1
        self.ring.update()

    @SafeSlot(str)
    def _on_device_changed(self, device: str):
        signal = self.ui.signal_combo_box.get_signal_name()
        self.ring.set_update("device", device=device, signal=signal)
        self.ring.config.device = device

    @SafeSlot(str)
    def _on_signal_changed(self, signal: str):
        device = self.ui.device_combo_box.currentText()
        signal = self.ui.signal_combo_box.get_signal_name()
        if not device or device not in self.container.bec_dispatcher.client.device_manager.devices:
            return
        self.ring.set_update("device", device=device, signal=signal)
        self.ring.config.signal = signal

    def _unify_mode_string(self, mode: str) -> str:
        """Convert mode string to a unified format"""
        mode = mode.lower()
        if mode == "scan progress":
            return "scan"
        if mode == "device readback":
            return "device"
        return mode

    def _get_display_mode_string(self, mode: str) -> str:
        """Convert mode string to display format"""
        match mode:
            case "manual":
                return "Manual"
            case "scan":
                return "Scan Progress"
            case "device":
                return "Device Readback"
        return mode.capitalize()

    def _update_mode(self, mode: str):
        """Update the ring's mode based on combo box selection"""
        mode = self._unify_mode_string(mode)
        match mode:
            case "manual":
                self.ring.set_update("manual")
            case "scan":
                self.ring.set_update("scan")
            case "device":
                self.ring.set_update("device", device=self.ui.device_combo_box.currentText())
        self._set_widget_mode_enabled(mode)

    def _set_widget_mode_enabled(self, mode: str):
        """Show/hide controls based on the current mode"""
        mode = self._unify_mode_string(mode)
        self.ui.device_combo_box.setEnabled(mode == "device")
        self.ui.signal_combo_box.setEnabled(mode == "device")
        self.ui.device_label.setEnabled(mode == "device")
        self.ui.signal_label.setEnabled(mode == "device")
        self.ui.min_label.setEnabled(mode in ["manual", "device"])
        self.ui.max_label.setEnabled(mode in ["manual", "device"])
        self.ui.value_label.setEnabled(mode == "manual")
        self.ui.value_spin_box.setEnabled(mode == "manual")
        self.ui.min_spin_box.setEnabled(mode in ["manual", "device"])
        self.ui.max_spin_box.setEnabled(mode in ["manual", "device"])

    def _delete_self(self):
        """Delete this ring from the container"""
        if self.ring in self.container.rings:
            self.container.rings.remove(self.ring)
            self.ring.deleteLater()

        self.cleanup()

    def cleanup(self):
        """Cleanup the card widget"""
        self.ui.device_combo_box.close()
        self.ui.device_combo_box.deleteLater()
        self.ui.signal_combo_box.close()
        self.ui.signal_combo_box.deleteLater()
        self.close()
        self.deleteLater()


# ============================================================
# Ring settings widget
# ============================================================


class RingSettings(SettingWidget):
    def __init__(
        self, parent=None, target_widget: RingProgressBar | None = None, popup=False, **kwargs
    ):
        super().__init__(parent=parent, **kwargs)

        self.setProperty("skip_settings", True)
        self.target_widget = target_widget
        self.popup = popup
        if not target_widget:
            return
        self.container: RingProgressContainerWidget = target_widget.ring_progress_bar
        self.original_num_bars = len(self.container.rings)
        self.original_configs = [ring.config.model_dump() for ring in self.container.rings]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        add_button = QPushButton(material_icon("add"), "Add Ring")
        add_button.clicked.connect(self.add_ring)

        self.center_label_edit = QLineEdit(self.container.center_label.text())
        self.center_label_edit.setPlaceholderText("Center Label")
        self.center_label_edit.textChanged.connect(self._update_center_label)

        self.colormap_toggle = QPushButton()
        self.colormap_toggle.setCheckable(True)
        self.colormap_toggle.setIcon(material_icon("palette"))
        self.colormap_toggle.setToolTip(
            f"Colormap mode is {'enabled' if self.container.color_map else 'disabled'}"
        )
        self.colormap_toggle.toggled.connect(self._toggle_colormap_mode)

        self.colormap_button = BECColorMapWidget(parent=self)
        self.colormap_button.setToolTip("Set a global colormap for all rings")
        self.colormap_button.colormap_changed_signal.connect(self._set_global_colormap)

        toolbar = QHBoxLayout()

        toolbar.addWidget(add_button)
        toolbar.addWidget(self.center_label_edit)

        toolbar.addStretch()
        toolbar.addWidget(self.colormap_toggle)
        toolbar.addWidget(self.colormap_button)

        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll)

        self.refresh_from_container()
        self.original_label = self.container.center_label.text()

    def sizeHint(self) -> QSize:
        return QSize(720, 520)

    def refresh_from_container(self):
        if not self.container:
            return

        for ring in self.container.rings:
            card = RingCardWidget(ring, self.container)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        if self.container.color_map:
            self.colormap_button.colormap = self.container.color_map
        self.colormap_toggle.setChecked(bool(self.container.color_map))

    @SafeSlot()
    def add_ring(self):
        if not self.container:
            return
        self.container.add_ring()
        ring = self.container.rings[len(self.container.rings) - 1]
        if ring:
            card = RingCardWidget(ring, self.container)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        # If a global colormap is set, apply it
        if self.container.color_map:
            self._toggle_colormap_mode(bool(self.container.color_map))

    @SafeSlot(str)
    def _update_center_label(self, text: str):
        if not self.container:
            return
        self.container.center_label.setText(text)

    @SafeSlot(bool)
    def _toggle_colormap_mode(self, enabled: bool):
        self.colormap_toggle.setToolTip(f"Colormap mode is {'enabled' if enabled else 'disabled'}")
        if enabled:
            colormap = self.colormap_button.colormap
            self._set_global_colormap(colormap)
        else:
            self.container.color_map = ""
        for i in range(self.cards_layout.count() - 1):  # -1 to exclude the stretch
            widget = self.cards_layout.itemAt(i).widget()
            if not isinstance(widget, RingCardWidget):
                continue
            widget.ui.ring_color_button.setEnabled(not enabled)
            widget.ui.ring_color_button.setToolTip(
                "Disabled in colormap mode" if enabled else "Set the ring color"
            )
            widget.ui.ring_color_label.setEnabled(not enabled)
            widget.ui.background_color_button.setEnabled(
                not enabled and not widget.ring.config.link_colors
            )
            widget.ui.color_sync_button.setEnabled(not enabled)

    @SafeSlot(str)
    def _set_global_colormap(self, colormap: str):
        if not self.container:
            return
        self.container.set_colors_from_map(colormap)

        # Update all ring card color buttons to reflect the new colors
        for i in range(self.cards_layout.count() - 1):  # -1 to exclude the stretch
            widget = self.cards_layout.itemAt(i).widget()
            if not isinstance(widget, RingCardWidget):
                continue
            widget.ui.ring_color_button.set_color(widget.ring.color)
            if widget.ring.config.link_colors:
                widget.ui.background_color_button.set_color(widget.ring.background_color)

    @SafeSlot()
    def accept_changes(self):
        if not self.container:
            return

        self.original_configs = [ring.config.model_dump() for ring in self.container.rings]

        for i, ring in enumerate(self.container.rings):
            ring.setGeometry(self.container.rect())
            ring.gap = self.container.gap * i
            ring.show()  # Ensure ring is visible
            ring.raise_()  # Bring ring to front

        self.container.center_label.setText(self.center_label_edit.text())
        self.original_label = self.container.center_label.text()
        self.original_num_bars = len(self.container.rings)

        self.container.update()

    def cleanup(self):
        """
        Cleanup the settings widget.
        """
        # Remove any rings that were added but not applied
        if not self.container:
            return
        if len(self.container.rings) > self.original_num_bars:
            remove_rings = self.container.rings[self.original_num_bars :]
            for ring in remove_rings:
                self.container.rings.remove(ring)
                ring.deleteLater()
        rings_to_add = max(0, self.original_num_bars - len(self.container.rings))
        for _ in range(rings_to_add):
            self.container.add_ring()

        # apply original configs to all rings
        for i, ring in enumerate(self.container.rings):
            ring.config = ring.config.model_validate(self.original_configs[i])

        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if not item or not item.widget():
                continue
            widget: RingCardWidget = item.widget()
            widget.cleanup()
        self.container.update()
        self.container.center_label.setText(self.original_label)
