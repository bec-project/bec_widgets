from __future__ import annotations

import pyqtgraph as pg
from pyqtgraph import TextItem, mkPen
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QColorDialog,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import BECConnector, ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


class LabelAdorner:
    """Manages a TextItem label on top of any ROI, keeping it aligned."""

    def __init__(self, roi, anchor=(0, 1), padding=2, bg_color=(0, 0, 0, 100), text_color="white"):
        self.roi = roi
        self.label = TextItem(anchor=anchor)
        self.padding = padding
        self.bg_rgba = bg_color
        self.text_color = text_color
        roi.addItem(self.label) if hasattr(roi, "addItem") else self.label.setParentItem(roi)
        # initial draw
        self._update_html(roi.name)
        self._reposition()
        # reconnect on geometry/name changes
        roi.sigRegionChanged.connect(self._reposition)
        if hasattr(roi, "nameChanged"):
            roi.nameChanged.connect(self._update_html)

    def _update_html(self, text):
        html = (
            f'<div style="background: rgba{self.bg_rgba}; '
            f"font-weight:bold; color:{self.text_color}; "
            f'padding:{self.padding}px;">{text}</div>'
        )
        self.label.setHtml(html)

    def _reposition(self, *args):
        # put at top-left corner of ROI’s bounding rect
        size = self.roi.state["size"]
        # size = [width, height]
        height = size[1]
        self.label.setPos(0, height)


class BaseROI(BECConnector):
    """Mixin providing name plus line color/width properties."""

    RPC = True
    PLUGIN = False

    nameChanged = Signal(str)
    penChanged = Signal()
    USER_ACCESS = [
        "name",
        "name.setter",
        "line_color",
        "line_color.setter",
        "line_width",
        "line_width.setter",
        "get_coordinates",
        "get_data_from_image",
    ]

    def __init__(
        self,
        *,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: BECConnector | None = None,
        # ROI-specific
        name: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
        # all remaining pg.*ROI kwargs (pos, size, pen, …)
        **pg_kwargs,
    ):
        """Base class for all modular ROIs.

        Args:
            name (str): Human-readable name shown in ROI Manager and labels.
            line_color (str | None, optional): Initial pen color. Defaults to None.
                Controller may override color later.
            line_width (int, optional): Initial pen width. Defaults to 15.
                Controller may override width later.
            config (ConnectionConfig | None, optional): Standard BECConnector argument. Defaults to None.
            gui_id (str | None, optional): Standard BECConnector argument. Defaults to None.
            parent_image (BECConnector | None, optional): Standard BECConnector argument. Defaults to None.
        """
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        self.config = config

        if parent_image is not None:
            self.set_parent(parent_image)
        else:
            self.parent_image = None
        object_name = name.replace("-", "_").replace(" ", "_") if name else None
        super().__init__(object_name=object_name, config=config, gui_id=gui_id, **pg_kwargs)

        self._name = name or f"ROI {self.__class__.__name__}"
        self._line_color = line_color or "#ffffff"
        self._line_width = line_width
        self.setPen(mkPen(self._line_color, width=self._line_width))

    def set_parent(self, parent: BECConnector):
        self.parent_image = parent

    def parent(self):
        return self.parent_image

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new: str):
        if new != self._name:
            self._name = new
            self.nameChanged.emit(new)

    @property
    def line_color(self) -> str:
        return self._line_color

    @line_color.setter
    def line_color(self, value: str):
        if value != self._line_color:
            self._line_color = value
            # update pen but preserve width
            self.setPen(mkPen(value, width=self._line_width))
            self.penChanged.emit()

    @property
    def line_width(self) -> int:
        return self._line_width

    @line_width.setter
    def line_width(self, value: int):
        if value != self._line_width and value > 0:
            self._line_width = value
            self.setPen(mkPen(self._line_color, width=value))
            self.penChanged.emit()

    def get_coordinates(self):
        raise NotImplementedError("Subclasses must implement get_coordinates()")

    def get_data_from_image(self, image: "np.ndarray | None" = None):
        """
        Return a NumPy array of pixels inside the ROI.
        If *image* is None, the method tries to locate the first pg.ImageItem
        in the same graphics scene and uses its `.image` array.
        """
        raise NotImplementedError


class RectangularROI(BaseROI, pg.RectROI):
    """Rectangle emitting edge signals and auto-labeled."""

    edgesChanged = Signal(float, float, float, float)
    edgesReleased = Signal(float, float, float, float)

    def __init__(
        self,
        *,
        # pg.RectROI kwargs
        pos,
        size,
        pen=None,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: BECConnector | None = None,
        # ROI specifics
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
        **extra_pg,
    ):
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            name=label,
            line_color=line_color,
            line_width=line_width,
            pos=pos,
            size=size,
            pen=pen,
            **extra_pg,
        )

        self.addScaleHandle([0.5, 1], [0.5, 0.5])
        self.addScaleHandle([1, 0.5], [0.5, 0.5])
        self.addScaleHandle([1, 1], [0.5, 0.5])
        self.sigRegionChanged.connect(self._on_region_changed)
        self.handlePen = mkPen("white", width=20)
        self.handleHoverPen = mkPen("white", width=30)  # TODO not sure if this works
        # attach the auto-aligning label
        self._adorner = LabelAdorner(self)

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

    def get_coordinates(self, *, typed: bool = False):
        """Return (x0, y0, x1, y1) or a typed dict if *typed* is True."""
        x0, y0 = self.pos().x(), self.pos().y()
        w, h = self.state["size"]
        coords = (x0, y0, x0 + w, y0 + h)
        if typed:
            return {"left": coords[0], "top": coords[1], "right": coords[2], "bottom": coords[3]}
        return coords

    def get_data_from_image(self, image=None):
        import numpy as np

        if image is None:
            image = self._lookup_scene_image()
        if image is None:
            raise RuntimeError("No image available to extract ROI data.")
        x0, y0, x1, y1 = map(int, self.get_coordinates())
        y0 = max(0, y0)
        y1 = min(image.shape[0], y1)
        x0 = max(0, x0)
        x1 = min(image.shape[1], x1)
        return image[y0:y1, x0:x1]

    # helper
    def _lookup_scene_image(self):
        for it in self.scene().items():
            if isinstance(it, pg.ImageItem) and it.image is not None:
                return it.image
        return None


class CircularROI(BaseROI, pg.CircleROI):
    """Circle emitting center/diameter signals and auto-labeled."""

    centerChanged = Signal(float, float, float)
    centerReleased = Signal(float, float, float)

    def __init__(
        self,
        *,
        pos,
        size,
        pen=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: BECConnector | None = None,
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
        **extra_pg,
    ):
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            name=label,
            line_color=line_color,
            line_width=line_width,
            pos=pos,
            size=size,
            pen=pen,
            **extra_pg,
        )
        self.sigRegionChanged.connect(self._on_region_changed)
        self._adorner = LabelAdorner(self)

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

    def get_coordinates(self, *, typed: bool = False):
        """Return (cx, cy, diameter) or a typed dict if *typed* is True."""
        d = self.state["size"][0]
        cx = self.pos().x() + d / 2
        cy = self.pos().y() + d / 2
        if typed:
            return {"center_x": cx, "center_y": cy, "diameter": d}
        return (cx, cy, d)

    def get_data_from_image(self, image=None):
        import numpy as np

        if image is None:
            image = self._lookup_scene_image()
        if image is None:
            raise RuntimeError("No image available to extract ROI data.")
        cx, cy, d = self.get_coordinates()
        r = d / 2
        x0, x1 = int(max(0, cx - r)), int(min(image.shape[1], cx + r))
        y0, y1 = int(max(0, cy - r)), int(min(image.shape[0], cy + r))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
        return image[y0:y1, x0:x1][mask]

    def _lookup_scene_image(self):
        for it in self.scene().items():
            if isinstance(it, pg.ImageItem) and it.image is not None:
                return it.image
        return None


from qtpy.QtCore import QObject, Signal


class ROIController(QObject):
    """Manages a list of ROIs, headlessly, with palette-based coloring."""

    roiAdded = Signal(object)  # emits the new ROI instance
    roiRemoved = Signal(object)  # emits the removed ROI instance
    cleared = Signal()  # emits when all ROIs are removed
    paletteChanged = Signal(str)  # emits new colormap name

    def __init__(self, colormap="viridis"):
        super().__init__()
        self.colormap = colormap
        self._rois: list[BaseROI] = []
        self._colors: list[str] = []
        self._rebuild_color_buffer()

    def _rebuild_color_buffer(self):
        n = len(self._rois) + 1
        self._colors = Colors.golden_angle_color(colormap=self.colormap, num=n, format="HEX")

    def add_roi(self, roi: BaseROI):
        """Register an externally created ROI (rect or circle)."""
        self._rois.append(roi)
        self._rebuild_color_buffer()
        idx = len(self._rois) - 1
        color = self._colors[idx]
        roi.line_color = color
        # ensure line width default is at least 3 if not previously set
        if getattr(roi, "line_width", 0) < 1:
            roi.line_width = 3
        self.roiAdded.emit(roi)

    def remove_roi(self, roi: BaseROI):
        if roi in self._rois:
            self._rois.remove(roi)
            self._rebuild_color_buffer()
            self.roiRemoved.emit(roi)

    # Convenience helpers -------------------------------------------------
    def get_roi(self, index: int) -> BaseROI | None:
        """Return ROI at *index* or None if out of range."""
        if 0 <= index < len(self._rois):
            return self._rois[index]
        return None

    def get_roi_by_name(self, name: str) -> BaseROI | None:
        """Return first ROI whose .name matches *name* (case‑sensitive)."""
        for r in self._rois:
            if r.name == name:
                return r
        return None

    def remove_roi_by_index(self, index: int):
        """Remove ROI at *index* if it exists."""
        roi = self.get_roi(index)
        if roi is not None:
            self.remove_roi(roi)

    def remove_roi_by_name(self, name: str):
        """Remove ROI with matching name."""
        roi = self.get_roi_by_name(name)
        if roi is not None:
            self.remove_roi(roi)

    def clear(self):
        for roi in list(self._rois):
            self.remove_roi(roi)
        self.cleared.emit()

    def renormalize_colors(self):
        """Reassign palette colors to all ROIs in order."""
        self._rebuild_color_buffer()
        for idx, roi in enumerate(self._rois):
            roi.line_color = self._colors[idx]

    # TODO can be property with validation
    def set_colormap(self, cmap: str):
        self.colormap = cmap
        self.paletteChanged.emit(cmap)
        self.renormalize_colors()

    @property
    def rois(self) -> list[BaseROI]:
        return list(self._rois)


class ROIManagerTree(BECWidget, QWidget):
    """Tree-based GUI for managing BaseROI instances."""

    PLUGIN = False
    RPC = False

    def __init__(
        self,
        plot,
        controller: ROIController | None = None,
        parent=None,
        config: ConnectionConfig = None,
        **kwargs,
    ):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, **kwargs)
        self.plot = plot
        if controller is None:
            controller = ROIController()
        self.controller = controller
        # no longer maintain self.all_rois or color_buffer here

        # Ensure the widget has a layout before building children
        if self.layout() is None:
            self.setLayout(QVBoxLayout())
        # container mapping ROI -> tree item
        self.roi_items: dict[BaseROI, QTreeWidgetItem] = {}

        # build toolbar + tree as before
        self._init_toolbar()
        self._init_tree()

        # subscribe to the headless controller:
        ctrl = self.controller
        ctrl.roiAdded.connect(self._on_roi_added)
        ctrl.roiRemoved.connect(self._on_roi_removed)
        ctrl.cleared.connect(self.clear)
        ctrl.paletteChanged.connect(lambda cmap: self.controller.renormalize_colors())

        # initial population
        for roi in ctrl.rois:
            self._add_roi_item(roi)

    @property
    def all_rois(self):
        return self.controller.rois

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
        cmap = BECColorMapWidget(cmap=self.controller.colormap)
        tb.addWidget(cmap)
        add_rect.action.triggered.connect(lambda: self.add_new_roi("rect"))
        add_circle.action.triggered.connect(lambda: self.add_new_roi("circle"))
        expand.action.triggered.connect(lambda: self.tree.expandAll())
        collapse.action.triggered.connect(lambda: self.tree.collapseAll())
        renorm.action.triggered.connect(lambda: self.controller.renormalize_colors())
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

    def add_new_roi(self, kind: str = "rect"):
        idx = len(self.all_rois) + 1
        name = f"ROI {idx}"
        if kind == "rect":
            roi = RectangularROI(pos=[10, 10], size=[50, 50], line_width=3, label=name)
        else:
            roi = CircularROI(pos=[10, 10], size=[50, 50], line_width=3, label=name)
        self.controller.add_roi(roi)

    def _on_roi_added(self, roi):
        """Controller says a new ROI exists—add its row."""
        # Only add to plot if not already present
        if not hasattr(roi, "scene") or roi.scene() is None:
            self.plot.addItem(roi)
        self._add_roi_item(roi)

    def _on_roi_removed(self, roi):
        """Controller removed an ROI—remove its row."""
        item = self.roi_items.pop(roi, None)
        if item is not None:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx != -1:
                self.tree.takeTopLevelItem(idx)

    def _add_roi_item(self, roi: BaseROI):
        item = QTreeWidgetItem(self.tree, [roi.name])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        pb = QToolButton(self)
        pb.setText("📐")
        cb = QToolButton(self)
        cb.setText("🎨")
        rb = QToolButton(self)
        rb.setText("✖")
        self.tree.setItemWidget(item, 1, pb)
        self.tree.setItemWidget(item, 2, cb)
        self.tree.setItemWidget(item, 3, rb)
        self.roi_items[roi] = item

        # Hook printing on move/release
        if isinstance(roi, RectangularROI):
            roi.edgesChanged.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(f"{name} moved: {x0},{y0} → {x1},{y1}")
            )
            roi.edgesReleased.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(
                    f"{name} released: {x0},{y0} → {x1},{y1}"
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
        pb.clicked.connect(lambda *_: self._print_roi(roi))
        cb.clicked.connect(lambda *_: self._change_color(roi))
        rb.clicked.connect(lambda *_: self._remove_roi(roi))

        # adjust column widths
        for c in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(c)

    def _on_item_changed(self, item, col):
        if col != 0:
            return
        new_name = item.text(0)
        for roi, it in self.roi_items.items():
            if it is item:
                roi.name = new_name
                break

    def _print_roi(self, roi):
        coords = roi.get_coordinates()
        try:
            data = roi.get_data_from_image()  # auto-detect image
            info = f"mean={data.mean():.3g}, N={data.size}"
            data = f"data = {data}"
        except Exception as err:
            info = f"no data ({err})"
        print(coords, info, data)

    def _change_color(self, roi):
        c = QColorDialog.getColor(parent=self)
        if not c.isValid():
            return
        idx = self.controller.rois.index(roi)
        self.controller._colors[idx] = c.name()
        roi.line_color = c.name()

    def _remove_roi(self, roi):
        self.plot.removeItem(roi)
        item = self.roi_items.pop(roi)
        self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        # Remove from controller (which will update .all_rois)
        self.controller.remove_roi(roi)

    # Removed renormalize_colors; use controller.renormalize_colors instead.

    def _on_colormap_changed(self, cmap):
        self.controller.set_colormap(cmap)

    def clear(self):
        for roi in list(self.all_rois):
            self.plot.removeItem(roi)
            item = self.roi_items.pop(roi, None)
            if item is not None:
                idx = self.tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self.tree.takeTopLevelItem(idx)


# Demo
if __name__ == "__main__":
    import sys

    import numpy as np
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
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
