import pyqtgraph as pg
from pyqtgraph import TextItem, mkPen
from qtpy.QtCore import Signal, Qt
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QColorDialog,
    QTreeWidget,
    QTreeWidgetItem,
)

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


class BaseROI:
    """Mixin providing a name property to ROIs."""

    nameChanged = Signal(str)

    def __init__(self, name: str):
        # No super() call: initialization done in shape subclass
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if self._name != value:
            self._name = value
            self.nameChanged.emit(value)


class RectangularROI(BaseROI, pg.RectROI):
    """Rectangular ROI emitting its edge coordinates."""

    edgesChanged = Signal(float, float, float, float)
    edgesReleased = Signal(float, float, float, float)

    def __init__(self, name: str, pos, size, pen=None, **kwargs):
        pg.RectROI.__init__(self, pos, size, pen=pen, **kwargs)
        BaseROI.__init__(self, name)
        # Aspect-ratio handles
        self.addScaleHandle([0.5, 1], [0.5, 0.5])
        self.addScaleHandle([1, 0.5], [0.5, 0.5])
        self.addScaleHandle([1, 1], [0.5, 0.5])
        # Track continuous and finished moves
        self.sigRegionChanged.connect(self._on_region_changed)
        self.handlePen = mkPen("white", width=20)

    def _on_region_changed(self):
        x0, y0 = self.pos().x(), self.pos().y()
        w, h = self.state["size"]
        self.edgesChanged.emit(x0, y0, x0 + w, y0 + h)

    def mouseDragEvent(self, ev):
        super().mouseDragEvent(ev)
        if ev.isFinish():
            x0, y0 = self.pos().x(), self.pos().y()
            w, h = self.state["size"]
            self.edgesReleased.emit(x0, y0, x0 + w, y0 + h)


class CircularROI(BaseROI, pg.CircleROI):
    """Circular ROI emitting its center and diameter."""

    centerChanged = Signal(float, float, float)
    centerReleased = Signal(float, float, float)

    def __init__(self, name: str, pos, size, pen=None, **kwargs):
        pg.CircleROI.__init__(self, pos, size, pen=pen, **kwargs)
        BaseROI.__init__(self, name)
        self.sigRegionChanged.connect(self._on_region_changed)

    def _on_region_changed(self):
        d = self.state["size"][0]
        cx = self.pos().x() + d / 2
        cy = self.pos().y() + d / 2
        self.centerChanged.emit(cx, cy, d)

    def mouseDragEvent(self, ev):
        super().mouseDragEvent(ev)
        if ev.isFinish():
            d = self.state["size"][0]
            cx = self.pos().x() + d / 2
            cy = self.pos().y() + d / 2
            self.centerReleased.emit(cx, cy, d)


class ROIManagerTree(BECWidget, QWidget):
    """Tree-based GUI for managing BaseROI instances."""

    PLUGIN = False
    RPC = False

    def __init__(self, plot, parent=None, config: ConnectionConfig = None, **kwargs):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, **kwargs)
        self.plot = plot
        self.color_palette = "viridis"
        self.color_buffer: list[str] = []
        self.all_rois: list[BaseROI] = []
        self.roi_items: dict[BaseROI, QTreeWidgetItem] = {}

        # Layout
        layout = self.layout() or QVBoxLayout(self)
        if self.layout() is None:
            self.setLayout(layout)

        self._init_toolbar()
        self._init_tree()

    def _init_toolbar(self):
        tb = ModularToolBar(parent=self, target_widget=self, orientation="horizontal")
        add_rect = MaterialIconAction(
            icon_name="add_box", tooltip="Add Rect ROI", checkable=False, parent=self
        )
        add_circle = MaterialIconAction(
            icon_name="panorama_fish_eye", tooltip="Add Circle ROI", checkable=False, parent=self
        )
        expand = MaterialIconAction(
            icon_name="unfold_more", tooltip="Expand All", checkable=False, parent=self
        )
        collapse = MaterialIconAction(
            icon_name="unfold_less", tooltip="Collapse All", checkable=False, parent=self
        )
        renorm = MaterialIconAction(
            icon_name="palette", tooltip="Renormalize Colors", checkable=False, parent=self
        )
        tb.add_action("add_rect", add_rect, self)
        tb.add_action("add_circle", add_circle, self)
        tb.add_action("expand", expand, self)
        tb.add_action("collapse", collapse, self)
        tb.add_action("renorm", renorm, self)
        tb.addWidget(QWidget())  # spacer
        cmap = BECColorMapWidget(cmap=self.color_palette)
        tb.addWidget(cmap)
        add_rect.action.triggered.connect(lambda: self.add_new_roi("rect"))
        add_circle.action.triggered.connect(lambda: self.add_new_roi("circle"))
        expand.action.triggered.connect(lambda: self.tree.expandAll())
        collapse.action.triggered.connect(lambda: self.tree.collapseAll())
        renorm.action.triggered.connect(self.renormalize_colors)
        cmap.colormap_changed_signal.connect(self._on_colormap_changed)
        self.layout().addWidget(tb)
        self.toolbar = tb

    def _init_tree(self):
        tw = QTreeWidget()
        tw.setColumnCount(4)
        tw.setHeaderLabels(["Name", "Print", "Color", "Remove"])
        tw.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        tw.itemChanged.connect(self._on_item_changed)
        self.layout().addWidget(tw)
        self.tree = tw

    def _ensure_color_buffer(self):
        n = len(self.all_rois) + 1
        self.color_buffer = Colors.golden_angle_color(
            colormap=self.color_palette, num=n, format="HEX"
        )

    def add_new_roi(self, kind: str = "rect"):
        idx = len(self.all_rois) + 1
        name = f"ROI {idx}"
        if kind == "rect":
            roi = RectangularROI(name, pos=[10, 10], size=[50, 50], pen=None)
        else:
            roi = CircularROI(name, pos=[10, 10], size=[50, 50], pen=None)
        self.plot.addItem(roi)
        self.all_rois.append(roi)
        self._ensure_color_buffer()
        color = self.color_buffer[idx - 1]
        roi.setPen(mkPen(color, width=3))
        # Label on top-left
        html = f'<div style="background: rgba(0,0,0,0.5); font-weight:bold; color:white; padding:2px;">{roi.name}</div>'
        lbl = TextItem(anchor=(0, 1))
        lbl.setHtml(html)
        lbl.setParentItem(roi)
        size = roi.state["size"]
        lbl.setPos(0, size[1])
        roi._label = lbl
        roi.sigRegionChanged.connect(lambda *args, r=roi: r._label.setPos(0, r.state["size"][1]))
        # Connect rename
        roi.nameChanged.connect(lambda new, r=roi, item=None: None)
        self._add_roi_item(roi)

    def _add_roi_item(self, roi: BaseROI):
        item = QTreeWidgetItem(self.tree, [roi.name])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        pb, cb, rb = QToolButton(self), QToolButton(self), QToolButton(self)
        pb.setText("📐")
        cb.setText("🎨")
        rb.setText("✖")
        self.tree.setItemWidget(item, 1, pb)
        self.tree.setItemWidget(item, 2, cb)
        self.tree.setItemWidget(item, 3, rb)
        self.roi_items[roi] = item
        # Print
        if isinstance(roi, RectangularROI):
            roi.edgesChanged.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(f"{name} moved: {x0},{y0} -> {x1},{y1}")
            )
            roi.edgesReleased.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(
                    f"{name} released: {x0},{y0} -> {x1},{y1}"
                )
            )
        else:
            roi.centerChanged.connect(
                lambda cx, cy, d, name=roi.name: print(
                    f"{name} moved: center=({cx:.1f},{cy:.1f}), d={d:.1f}"
                )
            )
            roi.centerReleased.connect(
                lambda cx, cy, d, name=roi.name: print(
                    f"{name} released: center=({cx:.1f},{cy:.1f}), d={d:.1f}"
                )
            )
        # Buttons
        pb.clicked.connect(lambda _, r=roi: self._print_roi(r))
        cb.clicked.connect(lambda _, r=roi: self._change_color(r))
        rb.clicked.connect(lambda _, r=roi: self._remove_roi(r))
        for c in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(c)

    def _on_item_changed(self, item, col):
        if col != 0:
            return
        new = item.text(0)
        for roi, it in self.roi_items.items():
            if it is item:
                roi.name = new
                html = f'<div style="background: rgba(0,0,0,0.5); font-weight:bold; color:white; padding:2px;">{new}</div>'
                roi._label.setHtml(html)
                break

    def _print_roi(self, roi):
        if isinstance(roi, RectangularROI):
            x0, y0 = roi.pos().x(), roi.pos().y()
            w, h = roi.state["size"]
            print(f"Edges: {x0},{y0} -> {x0+w},{y0+h}")
        else:
            d = roi.state["size"][0]
            cx, cy = roi.pos().x() + d / 2, roi.pos().y() + d / 2
            print(f"Center: {cx},{cy}, diameter: {d}")

    def _change_color(self, roi):
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            roi.setPen(mkPen(c.name(), width=3))
            self.renormalize_colors()

    def _remove_roi(self, roi):
        self.plot.removeItem(roi)
        item = self.roi_items.pop(roi)
        self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self.all_rois.remove(roi)

    def renormalize_colors(self):
        self._ensure_color_buffer()
        for i, roi in enumerate(self.all_rois):
            col = self.color_buffer[i]
            roi.setPen(mkPen(col, width=3))

    def _on_colormap_changed(self, cmap):
        self.color_palette = cmap
        self.renormalize_colors()

    def clear(self):
        for roi in list(self.all_rois):
            self._remove_roi(roi)


# Demo
if __name__ == "__main__":
    import sys, numpy as np
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QPushButton

    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("Modular ROI Demo")
    ml = QHBoxLayout(win)
    left = QWidget()
    vl = QVBoxLayout(left)
    view = pg.GraphicsLayoutWidget()
    vl.addWidget(view)
    plot = view.addPlot()
    img = pg.ImageItem()
    plot.addItem(img)
    img.setImage(np.random.normal(size=(200, 200)))
    ml.addWidget(left)
    mgr = ROIManagerTree(plot)
    mgr.setFixedWidth(350)
    ml.addWidget(mgr)
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec_())
