from __future__ import annotations

import math
from typing import TYPE_CHECKING

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QColorDialog,
    QHeaderView,
    QSpinBox,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import BECWidget
from bec_widgets.utils import BECDispatcher, ConnectionConfig
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.plots.roi.image_roi import (
    BaseROI,
    CircularROI,
    RectangularROI,
    ROIController,
)
from bec_widgets.widgets.utility.visual.color_button_native.color_button_native import (
    ColorButtonNative,
)
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

if TYPE_CHECKING:
    from bec_widgets.widgets.plots.image.image import Image


class ROIPropertyTree(BECWidget, QWidget):
    """
    Two-column tree:  [ROI]  [Properties]

    - Top-level: ROI name (editable) + color button.
    - Children: type, line-width (spin box), coordinates (auto-updating).

    Args:
        image_widget (Image): The main Image widget that displays the ImageItem.
            Provides ``plot_item`` and owns an ROIController already.
        controller (ROIController, optional): Optionally pass an external controller.
            If None, the manager uses ``image_widget.roi_controller``.
        parent (QWidget, optional): Parent widget. Defaults to None.
    """

    PLUGIN = False
    RPC = False

    COL_ACTION, COL_ROI, COL_PROPS = range(3)
    DELETE_BUTTON_COLOR = "#CC181E"

    def __init__(
        self,
        *,
        parent: QWidget = None,
        image_widget: Image,
        controller: ROIController | None = None,
    ):

        super().__init__(
            parent=parent, config=ConnectionConfig(widget_class=self.__class__.__name__)
        )

        if controller is None:
            # Use the controller already belonging to the Image widget
            controller = getattr(image_widget, "roi_controller", None)
            if controller is None:
                controller = ROIController()
                image_widget.roi_controller = controller

        self.image_widget = image_widget
        self.plot = image_widget.plot_item
        self.controller = controller
        self.roi_items: dict[BaseROI, QTreeWidgetItem] = {}

        self.layout = QVBoxLayout(self)
        self._init_toolbar()
        self._init_tree()

        # connect controller
        self.controller.roiAdded.connect(self._on_roi_added)
        self.controller.roiRemoved.connect(self._on_roi_removed)
        self.controller.cleared.connect(self.tree.clear)

        # initial load
        for r in self.controller.rois:
            self._on_roi_added(r)

        self.tree.collapseAll()

    # --------------------------------------------------------------------- UI
    def _init_toolbar(self):
        tb = ModularToolBar(self, self, orientation="horizontal")
        # --- ROI draw actions (toggleable) ---
        self.add_rect_action = MaterialIconAction("add_box", "Add Rect ROI", True, self)
        self.add_circle_action = MaterialIconAction("add_circle", "Add Circle ROI", True, self)
        tb.add_action("Add Rect ROI", self.add_rect_action, self)
        tb.add_action("Add Circle ROI", self.add_circle_action, self)

        # Expand/Collapse toggle
        self.expand_toggle = MaterialIconAction(
            "unfold_more", "Expand/Collapse", checkable=True, parent=self  # icon when collapsed
        )
        tb.add_action("Expand/Collapse", self.expand_toggle, self)

        def _exp_toggled(on: bool):
            if on:
                # switched to expanded state
                self.tree.expandAll()
                new_icon = material_icon("unfold_less", size=(20, 20), convert_to_pixmap=False)
            else:
                # collapsed state
                self.tree.collapseAll()
                new_icon = material_icon("unfold_more", size=(20, 20), convert_to_pixmap=False)
            self.expand_toggle.action.setIcon(new_icon)

        self.expand_toggle.action.toggled.connect(_exp_toggled)

        self.expand_toggle.action.setChecked(False)
        # colormap widget
        self.cmap = BECColorMapWidget(cmap=self.controller.colormap)
        tb.addWidget(QWidget())  # spacer
        tb.addWidget(self.cmap)
        self.cmap.colormap_changed_signal.connect(self.controller.set_colormap)
        self.layout.addWidget(tb)
        self.controller.paletteChanged.connect(lambda cmap: setattr(self.cmap, "colormap", cmap))

        # ROI drawing state
        self._roi_draw_mode = None  # 'rect' | 'circle' | None
        self._roi_start_pos = None  # QPointF in image coords
        self._temp_roi = None  # live ROI being resized while dragging

        # toggle handlers
        self.add_rect_action.action.toggled.connect(
            lambda on: self._set_roi_draw_mode("rect" if on else None)
        )
        self.add_circle_action.action.toggled.connect(
            lambda on: self._set_roi_draw_mode("circle" if on else None)
        )
        # capture mouse events on the plot scene
        self.plot.scene().installEventFilter(self)

    def _init_tree(self):
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Actions", "ROI", "Properties"])
        self.tree.header().setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeToContents)
        self.tree.headerItem().setText(self.COL_ACTION, "Actions")  # blank header text
        self.tree.itemChanged.connect(self._on_item_edited)
        self.layout.addWidget(self.tree)

    ################################################################################
    # Helper functions
    ################################################################################

    # --------------------------------------------------------------------- formatting
    @staticmethod
    def _format_coord_text(value) -> str:
        """
        Consistently format a coordinate value for display.
        """
        if isinstance(value, (tuple, list)):
            return "(" + ", ".join(f"{v:.2f}" for v in value) + ")"
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)

    def _set_roi_draw_mode(self, mode: str | None):
        # Ensure only the selected action is toggled on
        if mode == "rect":
            self.add_rect_action.action.setChecked(True)
            self.add_circle_action.action.setChecked(False)
        elif mode == "circle":
            self.add_rect_action.action.setChecked(False)
            self.add_circle_action.action.setChecked(True)
        else:
            self.add_rect_action.action.setChecked(False)
            self.add_circle_action.action.setChecked(False)
        self._roi_draw_mode = mode
        self._roi_start_pos = None
        # remove any unfinished temp ROI
        if self._temp_roi is not None:
            self.plot.removeItem(self._temp_roi)
            self._temp_roi = None

    def eventFilter(self, obj, event):
        if self._roi_draw_mode is None:
            return super().eventFilter(obj, event)
        if event.type() == QEvent.GraphicsSceneMousePress and event.button() == Qt.LeftButton:
            self._roi_start_pos = self.plot.vb.mapSceneToView(event.scenePos())
            if self._roi_draw_mode == "rect":
                self._temp_roi = RectangularROI(
                    pos=[self._roi_start_pos.x(), self._roi_start_pos.y()],
                    size=[5, 5],
                    parent_image=self.image_widget,
                    resize_handles=False,
                )
            if self._roi_draw_mode == "circle":
                self._temp_roi = CircularROI(
                    pos=[self._roi_start_pos.x() - 2.5, self._roi_start_pos.y() - 2.5],
                    size=[5, 5],
                    parent_image=self.image_widget,
                )
            self.plot.addItem(self._temp_roi)
            return True
        elif event.type() == QEvent.GraphicsSceneMouseMove and self._temp_roi is not None:
            pos = self.plot.vb.mapSceneToView(event.scenePos())
            dx = pos.x() - self._roi_start_pos.x()
            dy = pos.y() - self._roi_start_pos.y()

            if self._roi_draw_mode == "rect":
                self._temp_roi.setSize([dx, dy])
            if self._roi_draw_mode == "circle":
                r = max(
                    1, math.hypot(dx, dy)
                )  # radius never smaller than 1 for safety of handle mapping, otherwise SEGFAULT
                d = 2 * r  # diameter
                self._temp_roi.setPos(self._roi_start_pos.x() - r, self._roi_start_pos.y() - r)
                self._temp_roi.setSize([d, d])
            return True
        elif (
            event.type() == QEvent.GraphicsSceneMouseRelease
            and event.button() == Qt.LeftButton
            and self._temp_roi is not None
        ):
            # finalize ROI
            final_roi = self._temp_roi
            self._temp_roi = None
            self._set_roi_draw_mode(None)
            # register via controller
            final_roi.add_scale_handle()
            self.controller.add_roi(final_roi)
            return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------- controller slots
    def _on_roi_added(self, roi: BaseROI):
        # parent row with blank action column, name in ROI column
        parent = QTreeWidgetItem(self.tree, ["", "", ""])
        parent.setText(self.COL_ROI, roi.label)
        parent.setFlags(parent.flags() | Qt.ItemIsEditable)
        # --- delete button in actions column ---
        del_btn = QToolButton()
        delete_icon = material_icon(
            "delete",
            size=(20, 20),
            convert_to_pixmap=False,
            filled=False,
            color=self.DELETE_BUTTON_COLOR,
        )
        del_btn.setIcon(delete_icon)
        self.tree.setItemWidget(parent, self.COL_ACTION, del_btn)
        del_btn.clicked.connect(lambda _=None, r=roi: self._delete_roi(r))
        # color button
        color_btn = ColorButtonNative(parent=self, color=roi.line_color)
        self.tree.setItemWidget(parent, self.COL_PROPS, color_btn)
        color_btn.clicked.connect(lambda: self._pick_color(roi, color_btn))

        # child rows (3 columns: action, ROI, properties)
        QTreeWidgetItem(parent, ["", "Type", roi.__class__.__name__])
        width_item = QTreeWidgetItem(parent, ["", "Line width", ""])
        width_spin = QSpinBox()
        width_spin.setRange(1, 50)
        width_spin.setValue(roi.line_width)
        self.tree.setItemWidget(width_item, self.COL_PROPS, width_spin)
        width_spin.valueChanged.connect(lambda v, r=roi: setattr(r, "line_width", v))

        # --- Step 2: Insert separate coordinate rows (one per value)
        coord_rows = {}
        coords = roi.get_coordinates(typed=True)

        for key, value in coords.items():
            # Human-readable label: “center x” from “center_x”, etc.
            label = key.replace("_", " ").title()
            val_text = self._format_coord_text(value)
            row = QTreeWidgetItem(parent, ["", label, val_text])
            coord_rows[key] = row

        # keep dict refs
        self.roi_items[roi] = parent

        # --- Step 3: Update coordinates on ROI movement
        def _update_coords():
            c_dict = roi.get_coordinates(typed=True)
            for k, row in coord_rows.items():
                if k in c_dict:
                    val = c_dict[k]
                    row.setText(self.COL_PROPS, self._format_coord_text(val))

        if isinstance(roi, RectangularROI):
            roi.edgesChanged.connect(_update_coords)
        else:
            roi.centerChanged.connect(_update_coords)

        # sync width edits back to spinbox
        roi.penChanged.connect(lambda r=roi, sp=width_spin: sp.setValue(r.line_width))
        roi.nameChanged.connect(lambda n, itm=parent: itm.setText(self.COL_ROI, n))

        # color changes
        roi.penChanged.connect(lambda r=roi, b=color_btn: b.set_color(r.line_color))

        for c in range(3):
            self.tree.resizeColumnToContents(c)

    def _on_roi_removed(self, roi: BaseROI):
        item = self.roi_items.pop(roi, None)
        if item:
            idx = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(idx)

    # ---------------------------------------------------------- event handlers
    def _pick_color(self, roi: BaseROI, btn: "ColorButtonNative"):
        clr = QColorDialog.getColor(QColor(roi.line_color), self, "Select ROI Color")
        if clr.isValid():
            roi.line_color = clr.name()
            btn.set_color(clr)

    def _on_item_edited(self, item: QTreeWidgetItem, col: int):
        if col != self.COL_ROI:
            return
        # find which roi
        for r, it in self.roi_items.items():
            if it is item:
                r.label = item.text(self.COL_ROI)
                break

    def _delete_roi(self, roi):
        self.controller.remove_roi(roi)

    def cleanup(self):
        self.cmap.close()
        self.cmap.deleteLater()
        super().cleanup()


# Demo
if __name__ == "__main__":  # pragma: no cover
    import sys

    import numpy as np
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

    from bec_widgets.widgets.plots.image.image import Image

    app = QApplication(sys.argv)

    bec_dispatcher = BECDispatcher(gui_id="roi_tree_demo")
    client = bec_dispatcher.client
    client.start()

    image_widget = Image(popups=False)
    image_widget.main_image.set_data(np.random.normal(size=(200, 200)))

    win = QWidget()
    win.setWindowTitle("Modular ROI Demo")
    ml = QHBoxLayout(win)

    # Add the image widget on the left
    ml.addWidget(image_widget)

    # ROI manager linked to that image
    mgr = ROIPropertyTree(parent=image_widget, image_widget=image_widget)
    mgr.setFixedWidth(350)
    ml.addWidget(mgr)

    win.resize(1500, 600)
    win.show()
    sys.exit(app.exec_())
