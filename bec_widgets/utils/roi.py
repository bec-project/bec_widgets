import pyqtgraph as pg
from pyqtgraph import TextItem, mkPen
from qtpy.QtCore import Signal

# ----------- ROI Manager Tree Imports -----------
from qtpy.QtWidgets import QTreeWidget, QTreeWidgetItem

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


# Reusable rectangular ROI with custom aspect-ratio handles and edge-coordinate signals.


class RectangularROI(pg.RectROI):
    """Reusable rectangular ROI with custom aspect-ratio handles and edge-coordinate signals."""

    edgesChanged = Signal(float, float, float, float)
    edgesReleased = Signal(float, float, float, float)

    def __init__(self, pos, size, pen=None, **kwargs):
        super().__init__(pos, size, pen=pen, **kwargs)
        # Add three scale handles: horizontal, vertical, and both
        self.addScaleHandle([0.5, 1], [0.5, 0.5])  # top-center
        self.addScaleHandle([1, 0.5], [0.5, 0.5])  # center-right
        self.addScaleHandle([1, 1], [0.5, 0.5])  # top-right
        # Connect continuous region changes
        self.sigRegionChanged.connect(self._on_region_changed)
        self.handlePen = mkPen("white", width=20)

    def _on_region_changed(self):
        pos = self.pos()
        size = self.state["size"]
        x0, y0 = pos.x(), pos.y()
        w, h = size
        self.edgesChanged.emit(x0, y0, x0 + w, y0 + h)

    def mouseDragEvent(self, ev):
        super().mouseDragEvent(ev)
        if ev.isFinish():
            pos = self.pos()
            size = self.state["size"]
            x0, y0 = pos.x(), pos.y()
            w, h = size
            self.edgesReleased.emit(x0, y0, x0 + w, y0 + h)


# ----------- Circular ROI -----------
class CircularROI(pg.CircleROI):
    """Circular ROI emitting center and diameter signals."""

    centerChanged = Signal(float, float, float)
    centerReleased = Signal(float, float, float)

    def __init__(self, pos, size, pen=None, **kwargs):
        super().__init__(pos, size, pen=pen, **kwargs)
        self.sigRegionChanged.connect(self._on_region_changed)

    def _on_region_changed(self):
        pos = self.pos()
        d = self.state["size"][0]
        cx = pos.x() + d / 2
        cy = pos.y() + d / 2
        self.centerChanged.emit(cx, cy, d)

    def mouseDragEvent(self, ev):
        super().mouseDragEvent(ev)
        if ev.isFinish():
            pos = self.pos()
            d = self.state["size"][0]
            cx = pos.x() + d / 2
            cy = pos.y() + d / 2
            self.centerReleased.emit(cx, cy, d)


from qtpy.QtCore import Qt

# ------------------ ROI Manager Tree ------------------
from qtpy.QtWidgets import QColorDialog, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget


class ROIManagerTree(BECWidget, QWidget):
    """A tree-based manager for RectangularROIs, with toolbar controls and colormap-based colors."""

    PLUGIN = False
    RPC = False

    def __init__(
        self, plot, parent=None, config: ConnectionConfig = None, client=None, gui_id=None, **kwargs
    ):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self.plot = plot
        self.color_palette = "viridis"
        self.color_buffer: list[str] = []
        self.roi_items: dict[RectangularROI, QTreeWidgetItem] = {}
        self.all_rois: list[RectangularROI] = []

        # Layout
        lay = self.layout() if self.layout() else QVBoxLayout(self)
        if not self.layout():
            self.setLayout(lay)

        self._init_toolbar()
        self._init_tree()

    def _init_toolbar(self):
        self.toolbar = ModularToolBar(parent=self, target_widget=self, orientation="horizontal")
        add_action = MaterialIconAction(
            icon_name="add_box", tooltip="Add ROI", checkable=False, parent=self
        )
        expand_action = MaterialIconAction(
            icon_name="unfold_more", tooltip="Expand All", checkable=False, parent=self
        )
        collapse_action = MaterialIconAction(
            icon_name="unfold_less", tooltip="Collapse All", checkable=False, parent=self
        )
        renorm_action = MaterialIconAction(
            icon_name="palette", tooltip="Renormalize Colors", checkable=False, parent=self
        )

        self.toolbar.add_action("add", add_action, self)
        # Add circle ROI action after rectangle
        circle_action = MaterialIconAction(
            icon_name="panorama_fish_eye", tooltip="Add Circle ROI", checkable=False, parent=self
        )
        self.toolbar.add_action("add_circle", circle_action, self)
        circle_action.action.triggered.connect(lambda: self.add_new_circle_roi())

        self.toolbar.add_action("expand_all", expand_action, self)
        self.toolbar.add_action("collapse_all", collapse_action, self)
        # self.toolbar.add_separator()
        self.toolbar.add_action("renorm", renorm_action, self)
        self.spacer = QWidget()
        # self.spacer.setSizePolicy(self.spacer.Expanding, self.spacer.Expanding)
        self.toolbar.addWidget(self.spacer)
        self.colormap_widget = BECColorMapWidget(cmap=self.color_palette)
        self.toolbar.addWidget(self.colormap_widget)

        add_action.action.triggered.connect(lambda: self.add_new_roi())
        expand_action.action.triggered.connect(lambda: self.tree.expandAll())
        collapse_action.action.triggered.connect(lambda: self.tree.collapseAll())
        renorm_action.action.triggered.connect(lambda: self.renormalize_colors())
        self.colormap_widget.colormap_changed_signal.connect(self._colormap_changed)
        self.layout().addWidget(self.toolbar)

    def _init_tree(self):
        self.tree = QTreeWidget()
        # Allow inline renaming of ROI names
        self.tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["ROI", "Print", "Color", "Remove"])
        self.tree.setRootIsDecorated(False)
        self.layout().addWidget(self.tree)
        # Auto-size columns to their contents
        self.tree.resizeColumnToContents(0)

    def _ensure_color_buffer(self):
        n = len(self.all_rois) + 1
        self.color_buffer = Colors.golden_angle_color(
            colormap=self.color_palette, num=n, format="HEX"
        )

    def add_new_roi(self, pos=[10, 10], size=[50, 50]):
        roi = RectangularROI(pos=pos, size=size, pen=None)
        self.plot.addItem(roi)
        self.all_rois.append(roi)
        self._ensure_color_buffer()
        idx = len(self.all_rois) - 1
        color = self.color_buffer[idx]
        roi.setPen(mkPen(color, width=10))
        # Add a contrasting label with semi-transparent background
        name = f"ROI {len(self.all_rois)}"
        html = (
            f'<div style="background: rgba(0,0,0,0.5); '
            f'font-weight:bold; color:white; padding:2px;">{name}</div>'
        )
        label_item = TextItem(anchor=(0, 1))
        label_item.setHtml(html)
        label_item.setParentItem(roi)
        # Position label at the ROI's top-left corner
        w, h = roi.state["size"]
        label_item.setPos(0, h)
        roi._label_item = label_item
        # Keep label aligned at top-left when ROI is resized
        roi.sigRegionChanged.connect(
            lambda *args, roi=roi: roi._label_item.setPos(0, roi.state["size"][1])
        )
        self._add_roi_item(roi)

    def add_new_circle_roi(self, pos=[10, 10], diameter=50):
        roi = CircularROI(pos=pos, size=[diameter, diameter], pen=None)
        self.plot.addItem(roi)
        self.all_rois.append(roi)
        self._ensure_color_buffer()
        idx = len(self.all_rois) - 1
        color = self.color_buffer[idx]
        roi.setPen(mkPen(color, width=10))
        # Label at top-left, same as rectangular ROI
        name = f"ROI {len(self.all_rois)}"
        html = (
            f'<div style="background: rgba(0,0,0,0.5); '
            f'font-weight:bold; color:white; padding:2px;">{name}</div>'
        )
        label_item = TextItem(anchor=(0, 1))
        label_item.setHtml(html)
        label_item.setParentItem(roi)
        d = roi.state["size"][0]
        # Position at top-left corner
        label_item.setPos(0, d)
        roi._label_item = label_item
        # Keep aligned on resize
        roi.sigRegionChanged.connect(
            lambda *args, roi=roi: roi._label_item.setPos(0, roi.state["size"][0])
        )
        self._add_roi_item(roi)

    def _add_roi_item(self, roi):
        name = f"ROI {len(self.all_rois)}"
        item = QTreeWidgetItem(self.tree)
        item.setText(0, name)
        # Make the name editable inline
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        # Print to console when ROI moves or is released
        if isinstance(roi, CircularROI):
            roi.centerChanged.connect(
                lambda cx, cy, d, name=name: print(
                    f"{name} moved: center=({cx:.1f},{cy:.1f}), diameter={d:.1f}"
                )
            )
            roi.centerReleased.connect(
                lambda cx, cy, d, name=name: print(
                    f"{name} released: center=({cx:.1f},{cy:.1f}), diameter={d:.1f}"
                )
            )
        else:
            roi.edgesChanged.connect(
                lambda x0, y0, x1, y1, name=name: print(f"{name} moved: {x0},{y0} -> {x1},{y1}")
            )
            roi.edgesReleased.connect(
                lambda x0, y0, x1, y1, name=name: print(f"{name} released: {x0},{y0} -> {x1},{y1}")
            )
        # Create buttons
        print_btn = QToolButton(self)
        print_btn.setText("📐")
        color_btn = QToolButton(self)
        color_btn.setText("🎨")
        remove_btn = QToolButton(self)
        remove_btn.setText("✖")
        self.tree.setItemWidget(item, 1, print_btn)
        self.tree.setItemWidget(item, 2, color_btn)
        self.tree.setItemWidget(item, 3, remove_btn)
        self.roi_items[roi] = item

        print_btn.clicked.connect(lambda: self._print_roi(roi))
        color_btn.clicked.connect(lambda: self._change_color(roi))
        remove_btn.clicked.connect(lambda: self._remove_roi(roi))
        # Resize all columns to fit their content
        for col in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(col)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Update the on-ROI label when the user renames it."""
        if column != 0:
            return
        new_name = item.text(0)
        # Find the matching ROI
        for roi, it in self.roi_items.items():
            if it is item:
                # Update the HTML label
                html = (
                    f'<div style="background: rgba(0,0,0,0.5); '
                    f'font-weight:bold; color:white; padding:2px;">{new_name}</div>'
                )
                roi._label_item.setHtml(html)
                break

    def _print_roi(self, roi):
        pos = roi.pos()
        size = roi.state["size"]
        x0, y0 = pos.x(), pos.y()
        w, h = size
        print(f"Edges: {x0}, {y0}, {x0+w}, {y0+h}")

    def _change_color(self, roi):
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            roi.setPen(mkPen(c.name(), width=10))
            self.renormalize_colors()

    def _remove_roi(self, roi):
        self.plot.removeItem(roi)
        item = self.roi_items.pop(roi)
        idx = self.tree.indexOfTopLevelItem(item)
        if idx != -1:
            self.tree.takeTopLevelItem(idx)
        self.all_rois.remove(roi)

    def renormalize_colors(self):
        self._ensure_color_buffer()
        for idx, roi in enumerate(self.all_rois):
            col = self.color_buffer[idx]
            roi.setPen(mkPen(col, width=10))

    def _colormap_changed(self, cmap):
        self.color_palette = cmap
        self.renormalize_colors()

    def clear(self):
        for roi in list(self.all_rois):
            self._remove_roi(roi)


# ------------------ DEMO BLOCK ------------------
if __name__ == "__main__":
    import sys

    import numpy as np
    import pyqtgraph as pg
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("RectangularROI Demo")
    main_layout = QHBoxLayout(window)

    # Left side: image and control buttons
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)

    # Image display area
    view = pg.GraphicsLayoutWidget()
    left_layout.addWidget(view)
    plot = view.addPlot()
    img = pg.ImageItem()
    plot.addItem(img)
    # Demo image
    data = np.random.normal(size=(200, 200))
    img.setImage(data)

    # ROI Manager Tree widget
    manager_panel = ROIManagerTree(plot)
    manager_panel.setFixedWidth(350)

    # Add panels to main layout
    main_layout.addWidget(left_panel)
    main_layout.addWidget(manager_panel)

    window.resize(600, 600)
    window.show()
    sys.exit(app.exec_())
