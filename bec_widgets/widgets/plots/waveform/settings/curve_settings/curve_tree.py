from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from bec_qthemes._icon.material_icons import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import SafeSlot
from bec_widgets.utils import ConnectionConfig, EntryValidator
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.dap.dap_combo_box.dap_combo_box import DapComboBox
from bec_widgets.widgets.plots.waveform.curve import CurveConfig, DeviceSignal
from bec_widgets.widgets.utility.visual.color_button_native.color_button_native import (
    ColorButtonNative,
)
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform


logger = bec_logger.logger


class CurveRow(QTreeWidgetItem):
    DELETE_BUTTON_COLOR = "#CC181E"
    """A unified row that can represent either a device or a DAP curve.

    Columns:
      0: Actions (delete or "Add DAP" if source=device)
      1..2: DeviceLineEdit and QLineEdit if source=device, or "Model" label and DapComboBox if source=dap
      3: ColorButton
      4: Style QComboBox
      5: Pen width QSpinBox
      6: Symbol size QSpinBox
    """

    def __init__(
        self,
        tree: QTreeWidget,
        parent_item: QTreeWidgetItem | None = None,
        config: CurveConfig | None = None,
        device_manager=None,
    ):
        if parent_item:
            super().__init__(parent_item)
        else:
            # A top-level device row.
            super().__init__(tree)

        self.tree = tree
        self.parent_item = parent_item
        self.curve_tree = tree.parent()  # The CurveTree widget
        self.curve_tree.all_items.append(self)  # Track stable ordering

        # BEC user input
        self.device_edit = None
        self.dap_combo = None

        self.dev = device_manager
        self.entry_validator = EntryValidator(self.dev)

        self.config = config or CurveConfig()
        self.source = self.config.source
        self.dap_rows = []

        # Create column 0 (Actions)
        self._init_actions()
        # Create columns 1..2, depending on source
        self._init_source_ui()
        # Create columns 3..6 (color, style, width, symbol)
        self._init_style_controls()

    def _init_actions(self):
        """Create the actions widget in column 0, including a delete button and maybe 'Add DAP'."""
        self.actions_widget = QWidget()
        actions_layout = QHBoxLayout(self.actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(0)

        # Delete button
        self.delete_button = QToolButton()
        delete_icon = material_icon(
            "delete",
            size=(20, 20),
            convert_to_pixmap=False,
            filled=False,
            color=self.DELETE_BUTTON_COLOR,
        )
        self.delete_button.setIcon(delete_icon)
        self.delete_button.clicked.connect(lambda: self.remove_self())
        actions_layout.addWidget(self.delete_button)

        # If device row, add "Add DAP" button
        if self.source == "device":
            self.add_dap_button = QPushButton("DAP")
            self.add_dap_button.clicked.connect(lambda: self.add_dap_row())
            actions_layout.addWidget(self.add_dap_button)

        self.tree.setItemWidget(self, 0, self.actions_widget)

    def _init_source_ui(self):
        """Create columns 1 and 2. For device rows, we have device/entry edits; for dap rows, label/model combo."""
        if self.source == "device":
            # Device row: columns 1..2 are device line edits
            self.device_edit = DeviceComboBox(parent=self.tree)
            self.device_edit.insertItem(0, "")
            self.device_edit.setEditable(True)
            self.entry_edit = SignalComboBox(parent=self.tree)
            self.entry_edit.include_config_signals = False
            self.entry_edit.insertItem(0, "")
            self.entry_edit.setEditable(True)
            self.device_edit.currentTextChanged.connect(self.entry_edit.set_device)
            self.device_edit.device_reset.connect(self.entry_edit.reset_selection)
            if self.config.signal:
                device_index = self.device_edit.findText(self.config.signal.name or "")
                if device_index >= 0:
                    self.device_edit.setCurrentIndex(device_index)
                    # Force the entry_edit to update based on the device name
                    self.device_edit.currentTextChanged.emit(self.device_edit.currentText())
                else:
                    # If the device name is not found, set the first enabled item
                    self.device_edit.setCurrentIndex(0)

                for i in range(self.entry_edit.count()):
                    entry_data = self.entry_edit.itemData(i)
                    if entry_data and entry_data.get("obj_name") == self.config.signal.entry:
                        # If the device name matches an object name, set it
                        self.entry_edit.setCurrentIndex(i)
                        break
                else:
                    # If no match found, set the first enabled item
                    for i in range(self.entry_edit.count()):
                        model = self.entry_edit.model()
                        if model.flags(model.index(i, 0)) & Qt.ItemIsEnabled:
                            self.entry_edit.setCurrentIndex(i)
                            break
                    else:
                        self.entry_edit.setCurrentIndex(0)

            self.tree.setItemWidget(self, 1, self.device_edit)
            self.tree.setItemWidget(self, 2, self.entry_edit)

        else:
            # DAP row: column1= "Model" label, column2= DapComboBox
            self.label_widget = QLabel("Model")
            self.tree.setItemWidget(self, 1, self.label_widget)
            self.dap_combo = DapComboBox(parent=self.tree)
            self.dap_combo.populate_fit_model_combobox()
            # If config.signal has a dap
            if self.config.signal and self.config.signal.dap:
                dap_value = self.config.signal.dap
                idx = self.dap_combo.fit_model_combobox.findText(dap_value)
                if idx >= 0:
                    self.dap_combo.fit_model_combobox.setCurrentIndex(idx)
            else:
                self.dap_combo.select_fit_model("GaussianModel")  # default

            self.tree.setItemWidget(self, 2, self.dap_combo)

    def _init_style_controls(self):
        """Create columns 3..6: color button, style combo, width spin, symbol spin."""
        # Color in col 3
        self.color_button = ColorButtonNative(color=self.config.color)
        self.color_button.color_changed.connect(self._on_color_changed)
        self.tree.setItemWidget(self, 3, self.color_button)

        # Style in col 4
        self.style_combo = QComboBox()
        self.style_combo.addItems(["solid", "dash", "dot", "dashdot"])
        idx = self.style_combo.findText(self.config.pen_style)
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        self.tree.setItemWidget(self, 4, self.style_combo)

        # Pen width in col 5
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20)
        self.width_spin.setValue(self.config.pen_width)
        self.tree.setItemWidget(self, 5, self.width_spin)

        # Symbol size in col 6
        self.symbol_spin = QSpinBox()
        self.symbol_spin.setRange(1, 20)
        self.symbol_spin.setValue(self.config.symbol_size)
        self.tree.setItemWidget(self, 6, self.symbol_spin)

    @SafeSlot(str, verify_sender=True)
    def _on_color_changed(self, new_color: str):
        """
        Update configuration when the color button emits a change.

        Args:
            new_color (str): The new color in hex format.
        """
        self.config.color = new_color
        self.config.symbol_color = new_color

    def add_dap_row(self):
        """Create a new DAP row as a child. Only valid if source='device'."""
        if self.source != "device":
            return
        curve_tree = self.tree.parent()
        parent_label = self.config.label

        # Inherit device name/entry
        dev_name = ""
        dev_entry = ""
        if self.config.signal:
            dev_name = self.config.signal.name
            dev_entry = self.config.signal.entry

        # Create a new config for the DAP row
        dap_cfg = CurveConfig(
            widget_class="Curve",
            source="dap",
            parent_label=parent_label,
            signal=DeviceSignal(name=dev_name, entry=dev_entry),
        )
        new_dap = CurveRow(self.tree, parent_item=self, config=dap_cfg, device_manager=self.dev)
        # Expand device row to show new child
        self.tree.expandItem(self)

        # Give the new row a color from the buffer:
        curve_tree._ensure_color_buffer_size()
        idx = len(curve_tree.all_items) - 1
        new_col = curve_tree.color_buffer[idx]
        new_dap.color_button.set_color(new_col)
        new_dap.config.color = new_col
        new_dap.config.symbol_color = new_col

    def remove_self(self):
        """Remove this row from the tree and from the parent's item list."""
        # Recursively remove all child rows first
        for i in reversed(range(self.childCount())):
            child = self.child(i)
            if isinstance(child, CurveRow):
                child.remove_self()

        # Clean up the widget references if they still exist
        if getattr(self, "device_edit", None) is not None:
            self.device_edit.close()
            self.device_edit.deleteLater()
            self.device_edit = None

        if getattr(self, "dap_combo", None) is not None:
            self.dap_combo.close()
            self.dap_combo.deleteLater()
            self.dap_combo = None

        if getattr(self, "color_button", None) is not None:
            self.color_button.close()
            self.color_button.deleteLater()
            self.color_button = None

        # Remove the item from the tree widget
        index = self.tree.indexOfTopLevelItem(self)
        if index != -1:
            self.tree.takeTopLevelItem(index)
        elif self.parent_item:
            self.parent_item.removeChild(self)

        # Finally, remove self from the registration list in the curve tree
        curve_tree = self.tree.parent()
        if self in curve_tree.all_items:
            curve_tree.all_items.remove(self)

    def export_data(self) -> dict:
        """Collect data from the GUI widgets, update config, and return as a dict.

        Returns:
            dict: The serialized config based on the GUI state.
        """
        if self.source == "device":
            # Gather device name/entry
            device_name = ""
            device_entry = ""

            ## TODO: Move this to itemData
            if hasattr(self, "device_edit"):
                device_name = self.device_edit.currentText()
            if hasattr(self, "entry_edit"):
                device_entry = self.entry_edit.currentText()
                index = self.entry_edit.findText(device_entry)
                if index > -1:
                    device_entry_info = self.entry_edit.itemData(index)
                    if device_entry_info:
                        device_entry = device_entry_info.get("obj_name", device_entry)
                else:
                    device_entry = self.entry_validator.validate_signal(
                        name=device_name, entry=device_entry
                    )

            self.config.signal = DeviceSignal(name=device_name, entry=device_entry)
            self.config.source = "device"
            self.config.label = f"{device_name}-{device_entry}"
        else:
            # DAP logic
            parent_conf_dict = {}
            if self.parent_item:
                parent_conf_dict = self.parent_item.export_data()
            parent_conf = CurveConfig(**parent_conf_dict)
            dev_name = ""
            dev_entry = ""
            if parent_conf.signal:
                dev_name = parent_conf.signal.name
                dev_entry = parent_conf.signal.entry
            # Dap from the DapComboBox
            new_dap = "GaussianModel"
            if hasattr(self, "dap_combo"):
                new_dap = self.dap_combo.fit_model_combobox.currentText()
            self.config.signal = DeviceSignal(name=dev_name, entry=dev_entry, dap=new_dap)
            self.config.source = "dap"
            self.config.parent_label = parent_conf.label
            self.config.label = f"{parent_conf.label}-{new_dap}"

        # Common style fields
        self.config.color = self.color_button.color
        self.config.symbol_color = self.color_button.color
        self.config.pen_style = self.style_combo.currentText()
        self.config.pen_width = self.width_spin.value()
        self.config.symbol_size = self.symbol_spin.value()

        return self.config.model_dump()

    def closeEvent(self, event) -> None:
        logger.info(f"CurveRow closeEvent: {self.config.label}")
        return super().closeEvent(event)


class CurveTree(BECWidget, QWidget):
    """A tree widget that manages device and DAP curves."""

    PLUGIN = False
    RPC = False

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        waveform: Waveform | None = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.waveform = waveform
        if self.waveform and hasattr(self.waveform, "color_palette"):
            self.color_palette = self.waveform.color_palette
        else:
            self.color_palette = "plasma"

        self.get_bec_shortcuts()

        self.color_buffer = []
        self.all_items = []
        self.layout = QVBoxLayout(self)
        self._init_toolbar()
        self._init_tree()
        self.refresh_from_waveform()

    def _init_toolbar(self):
        """Initialize the toolbar with actions: add, send, refresh, expand, collapse, renormalize."""
        self.toolbar = ModularToolBar(parent=self, target_widget=self, orientation="horizontal")
        add = MaterialIconAction(
            icon_name="add", tooltip="Add new curve", checkable=False, parent=self
        )
        expand = MaterialIconAction(
            icon_name="unfold_more", tooltip="Expand All DAP", checkable=False, parent=self
        )
        collapse = MaterialIconAction(
            icon_name="unfold_less", tooltip="Collapse All DAP", checkable=False, parent=self
        )

        self.toolbar.add_action("add", add, self)
        self.toolbar.add_action("expand_all", expand, self)
        self.toolbar.add_action("collapse_all", collapse, self)

        # Add colormap widget (not updating waveform's color_palette until Send is pressed)
        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(self.spacer)

        # Renormalize colors button
        renorm_action = MaterialIconAction(
            icon_name="palette", tooltip="Normalize All Colors", checkable=False, parent=self
        )
        self.toolbar.add_action("renormalize_colors", renorm_action, self)
        renorm_action.action.triggered.connect(lambda checked: self.renormalize_colors())

        self.colormap_widget = BECColorMapWidget(cmap=self.color_palette or "plasma")
        self.toolbar.addWidget(self.colormap_widget)
        self.colormap_widget.colormap_changed_signal.connect(self.handle_colormap_changed)

        add.action.triggered.connect(lambda checked: self.add_new_curve())
        expand.action.triggered.connect(lambda checked: self.expand_all_daps())
        collapse.action.triggered.connect(lambda checked: self.collapse_all_daps())

        self.layout.addWidget(self.toolbar)

    def _init_tree(self):
        """Initialize the QTreeWidget with 7 columns and compact widths."""
        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["Actions", "Name", "Entry", "Color", "Style", "Width", "Symbol"])

        header = self.tree.header()
        for idx in range(self.tree.columnCount()):
            if idx in (1, 2):  # Device name and entry should stretch
                header.setSectionResizeMode(idx, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(idx, QHeaderView.Fixed)
        header.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 90)
        self.tree.setColumnWidth(3, 70)
        self.tree.setColumnWidth(4, 80)
        self.tree.setColumnWidth(5, 50)
        self.tree.setColumnWidth(6, 50)

        self.layout.addWidget(self.tree)

    def _init_color_buffer(self, size: int):
        """
        Initializes the color buffer with a calculated set of colors based on the golden
        angle sequence.

        Args:
            size (int): The number of colors to be generated for the color buffer.
        """
        self.color_buffer = Colors.golden_angle_color(
            colormap=self.colormap_widget.colormap, num=size, format="HEX"
        )

    def _ensure_color_buffer_size(self):
        """
        Ensures that the color buffer size meets the required number of items.
        """
        current_count = len(self.color_buffer)
        color_list = Colors.golden_angle_color(
            colormap=self.color_palette, num=max(10, current_count + 1), format="HEX"
        )
        self.color_buffer = color_list

    def handle_colormap_changed(self, new_cmap: str):
        """
        Handles the updating of the color palette when the colormap is changed.

        Args:
            new_cmap: The new colormap to be set as the color palette.
        """
        self.color_palette = new_cmap

    def renormalize_colors(self):
        """Overwrite all existing rows with new colors from the buffer in their creation order."""
        total = len(self.all_items)
        self._ensure_color_buffer_size()
        for idx, item in enumerate(self.all_items):
            if hasattr(item, "color_button"):
                new_col = self.color_buffer[idx]
                item.color_button.set_color(new_col)
                if hasattr(item, "config"):
                    item.config.color = new_col
                    item.config.symbol_color = new_col

    def add_new_curve(self, name: str = None, entry: str = None):
        """Add a new device-type CurveRow with an assigned colormap color.

        Args:
            name (str, optional): Device name.
            entry (str, optional): Device entry.
            style (str, optional): Pen style. Defaults to "solid".
            width (int, optional): Pen width. Defaults to 4.
            symbol_size (int, optional): Symbol size. Defaults to 7.

        Returns:
            CurveRow: The newly created top-level row.
        """
        cfg = CurveConfig(
            widget_class="Curve",
            parent_id=self.waveform.gui_id,
            source="device",
            signal=DeviceSignal(name=name or "", entry=entry or ""),
        )
        new_row = CurveRow(self.tree, parent_item=None, config=cfg, device_manager=self.dev)

        # Assign color from the buffer ONLY to this new curve.
        total_items = len(self.all_items)
        self._ensure_color_buffer_size()
        color_idx = total_items - 1  # new row is last
        new_col = self.color_buffer[color_idx]
        new_row.color_button.set_color(new_col)
        new_row.config.color = new_col
        new_row.config.symbol_color = new_col

        return new_row

    def send_curve_json(self):
        """Send the current tree's config as JSON to the waveform, updating wavefrom.color_palette as well."""
        if self.waveform is not None:
            self.waveform.color_palette = self.color_palette
        data = self.export_all_curves()
        json_data = json.dumps(data, indent=2)
        if self.waveform is not None:
            self.waveform.curve_json = json_data

    def export_all_curves(self) -> list:
        """Recursively export data from each row.

        Returns:
            list: A list of exported config dicts for every row (device and DAP).
        """
        curves = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if isinstance(item, CurveRow):
                curves.append(item.export_data())
                for j in range(item.childCount()):
                    child = item.child(j)
                    if isinstance(child, CurveRow):
                        curves.append(child.export_data())
        return curves

    def expand_all_daps(self):
        """Expand all top-level rows to reveal child DAP rows."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.tree.expandItem(item)

    def collapse_all_daps(self):
        """Collapse all top-level rows, hiding child DAP rows."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.tree.collapseItem(item)

    def refresh_from_waveform(self):
        """Clear the tree and rebuild from the waveform's existing curves if any, else add sample rows."""
        if self.waveform is None:
            return
        self.tree.clear()
        self.all_items = []

        device_curves = [c for c in self.waveform.curves if c.config.source == "device"]
        dap_curves = [c for c in self.waveform.curves if c.config.source == "dap"]
        for dev in device_curves:
            dr = CurveRow(self.tree, parent_item=None, config=dev.config, device_manager=self.dev)
            for dap in dap_curves:
                if dap.config.parent_label == dev.config.label:
                    CurveRow(self.tree, parent_item=dr, config=dap.config, device_manager=self.dev)

    def cleanup(self):
        """Cleanup the widget."""
        all_items = list(self.all_items)
        for item in all_items:
            item.remove_self()

    def closeEvent(self, event):
        self.cleanup()
        return super().closeEvent(event)
