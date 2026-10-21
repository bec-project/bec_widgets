"""
Picture-only live view for JPEG preview frames, with crosshair and ROIs in sensor pixels.

The frame is decoded by Qt into a QImage on the thread that receives Redis messages and drawn
as a pixmap. There is no numpy data on the GUI side, so there are no levels, histogram or pixel
values; a grayscale frame can still be coloured through an 8-bit colour table.

The pixmap sits in a pyqtgraph plot, scaled onto the sensor the preview was taken from
(``"sensor_shape"`` in the frame metadata, otherwise the frame's own size). Axes, crosshair and
ROIs are therefore in sensor pixels and stay put when the preview resolution changes. As in the
Image widget, array rows run along x and columns along y.
"""

from __future__ import annotations

import time

import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QPointF, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QImage, QPixmap, QTransform
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGraphicsPixmapItem,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.jpeg_frames import qimage_preview, sensor_shape

COLORMAPS = ("gray", "magma", "viridis", "plasma", "inferno")
ROI_COLORS = ("#ffd200", "#00d0ff", "#ff5ab4", "#7dff5a", "#ff8c1a", "#b48cff")


class JpegView(BECWidget, QWidget):
    """Live view that shows preview frames as a Qt picture, without decoding to numpy."""

    frame_shown = Signal()
    rois_changed = Signal(list)

    def __init__(self, parent=None, device: str | None = None, signal: str = "preview", **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._device = None
        self._signal = signal
        self._color_table: list[int] | None = None
        self._frame_size: tuple[int, int] | None = None
        self._sensor: tuple[int, int] | None = None
        self._encoding: str | None = None
        self._fit_on_next_frame = True
        self._rois: list[pg.ROI] = []
        self._roi_count = 0
        self.last_frame_metadata: dict = {}
        self.last_update_ms = 0.0

        self.view = pg.PlotWidget(parent=self)
        self.plot_item = self.view.getPlotItem()
        self.plot_item.setAspectLocked(True)
        self.plot_item.setLabel("bottom", "x (sensor px)")
        self.plot_item.setLabel("left", "y (sensor px)")
        self.plot_item.setMenuEnabled(False)
        self.plot_item.hideButtons()
        self.view_box: pg.ViewBox = self.plot_item.getViewBox()

        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self._pixmap_item.setZValue(-100)
        self.view_box.addItem(self._pixmap_item, ignoreBounds=True)

        pen = pg.mkPen("#ffd200", width=1, style=Qt.PenStyle.DashLine)
        self._v_line = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._h_line = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        for line in (self._v_line, self._h_line):
            line.setVisible(False)
            self.view_box.addItem(line, ignoreBounds=True)
        self.view.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self.colormap_box = QComboBox(self)
        self.colormap_box.addItems(COLORMAPS)
        self.colormap_box.setToolTip("Colour table for grayscale frames (colour JPEGs ignore it)")
        self.colormap_box.currentTextChanged.connect(self.set_colormap)
        fit_button = QPushButton("Fit", self)
        fit_button.clicked.connect(self.fit)
        self.crosshair_button = QPushButton("Crosshair", self)
        self.crosshair_button.setCheckable(True)
        self.crosshair_button.toggled.connect(self.set_crosshair)
        rect_button = QPushButton("+ Rect ROI", self)
        rect_button.clicked.connect(lambda: self.add_roi("rect"))
        circle_button = QPushButton("+ Circle ROI", self)
        circle_button.clicked.connect(lambda: self.add_roi("circle"))
        clear_button = QPushButton("Clear ROIs", self)
        clear_button.clicked.connect(self.clear_rois)
        self.info_label = QLabel("No frame yet", self)
        self.cursor_label = QLabel("", self)
        self.cursor_label.setMinimumWidth(170)

        self.roi_table = QTableWidget(0, 5, self)
        self.roi_table.setHorizontalHeaderLabels(["ROI", "x from", "x to", "y from", "y to"])
        self.roi_table.verticalHeader().setVisible(False)
        self.roi_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.roi_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.roi_table.setToolTip(
            "ROI bounds in sensor pixels. Drag the ROI to move it, its handles to resize it;"
            " right-click an ROI to remove it."
        )
        self.roi_table.setMaximumHeight(150)
        self.roi_table.setVisible(False)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Colormap", self))
        bar.addWidget(self.colormap_box)
        bar.addWidget(fit_button)
        bar.addWidget(self.crosshair_button)
        bar.addWidget(rect_button)
        bar.addWidget(circle_button)
        bar.addWidget(clear_button)
        bar.addStretch(1)
        bar.addWidget(self.cursor_label)
        bar.addWidget(self.info_label)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.view)
        splitter.addWidget(self.roi_table)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(splitter)

        if device:
            self.set_source(device, signal)

    ################################################################################
    # Source and display

    def set_source(self, device: str, signal: str = "preview") -> None:
        """
        Subscribe to a device preview signal.

        Args:
            device (str): Device name.
            signal (str): Preview signal name.
        """
        if self._device:
            self.bec_dispatcher.disconnect_slot(
                self.on_frame, MessageEndpoints.device_preview(self._device, self._signal)
            )
        self._device, self._signal = device, signal
        self._fit_on_next_frame = True
        self.bec_dispatcher.connect_slot(
            self.on_frame,
            MessageEndpoints.device_preview(device, signal),
            preprocess=qimage_preview,
            latest_only=True,
        )

    @SafeSlot(str)
    def set_colormap(self, name: str) -> None:
        """
        Colour grayscale frames through a 256-entry colour table.

        Args:
            name (str): Colormap name; "gray" shows the frame as it is.
        """
        if name == "gray":
            self._color_table = None
            return
        lut = Colors.get_colormap(name).getLookupTable(nPts=256, alpha=False)
        self._color_table = [QColor(int(r), int(g), int(b)).rgb() for r, g, b in lut]

    @SafeSlot()
    def fit(self) -> None:
        """Fit the whole sensor into the view."""
        if self._sensor is None:
            return
        rows, cols = self._sensor
        self.view_box.setRange(QRectF(0, 0, rows, cols), padding=0)

    @SafeSlot(dict, dict)
    def on_frame(self, msg: dict, metadata: dict) -> None:
        """Show a frame decoded by ``qimage_preview``."""
        qimage: QImage | None = msg.get("qimage")
        if qimage is None or qimage.isNull():
            return
        t0 = time.perf_counter()
        if self._color_table is not None and qimage.format() == QImage.Format.Format_Grayscale8:
            # Same bytes, read as palette indices: colouring costs one 256-entry table
            indexed = QImage(
                qimage.constBits(),
                qimage.width(),
                qimage.height(),
                qimage.bytesPerLine(),
                QImage.Format.Format_Indexed8,
            )
            indexed.setColorTable(self._color_table)
            pixmap = QPixmap.fromImage(indexed)
        else:
            pixmap = QPixmap.fromImage(qimage)
        frame_size = (qimage.height(), qimage.width())
        sensor = sensor_shape(metadata, frame_size)
        encoding = metadata.get("encoding", "raw")
        if (frame_size, sensor, encoding) != (self._frame_size, self._sensor, self._encoding):
            self._set_geometry(frame_size, sensor, encoding)
        self._pixmap_item.setPixmap(pixmap)
        self.last_update_ms = (time.perf_counter() - t0) * 1e3
        self.last_frame_metadata = metadata
        self.frame_shown.emit()

    def _set_geometry(
        self, frame_size: tuple[int, int], sensor: tuple[int, int], encoding: str
    ) -> None:
        """Place frame pixels on sensor pixels: pixmap (col, row) -> view (row, col)."""
        sensor_changed = sensor != self._sensor
        self._frame_size, self._sensor, self._encoding = frame_size, sensor, encoding
        scale_r, scale_c = sensor[0] / frame_size[0], sensor[1] / frame_size[1]
        self._pixmap_item.setTransform(QTransform(0, scale_c, scale_r, 0, 0, 0))
        text = f"{frame_size[1]} x {frame_size[0]} {encoding}"
        if frame_size != sensor:
            text += f", sensor {sensor[1]} x {sensor[0]}"
        self.info_label.setText(text)
        if sensor_changed or self._fit_on_next_frame:
            self._fit_on_next_frame = False
            self.fit()

    ################################################################################
    # Crosshair

    @SafeSlot(bool)
    def set_crosshair(self, enabled: bool) -> None:
        """
        Show or hide the crosshair that follows the mouse.

        Args:
            enabled (bool): Whether the crosshair is shown.
        """
        if self.crosshair_button.isChecked() != enabled:
            self.crosshair_button.setChecked(enabled)  # comes back here through toggled
            return
        if not enabled:
            for line in (self._v_line, self._h_line):
                line.setVisible(False)
            self.cursor_label.setText("")

    def _on_mouse_moved(self, scene_pos: QPointF) -> None:
        if not self.crosshair_button.isChecked():
            return
        if not self.view_box.sceneBoundingRect().contains(scene_pos):
            return
        point = self.view_box.mapSceneToView(scene_pos)
        self.update_crosshair(point.x(), point.y())

    def update_crosshair(self, x: float, y: float) -> None:
        """
        Move the crosshair to a point and show its sensor pixel.

        Args:
            x (float): x in sensor pixels (array row).
            y (float): y in sensor pixels (array column).
        """
        self._v_line.setPos(x)
        self._h_line.setPos(y)
        for line in (self._v_line, self._h_line):
            line.setVisible(True)
        if self._sensor is None:
            return
        rows, cols = self._sensor
        if 0 <= x < rows and 0 <= y < cols:
            self.cursor_label.setText(f"x {int(x)}  y {int(y)}")
        else:
            self.cursor_label.setText("outside the sensor")

    ################################################################################
    # ROIs

    def add_roi(self, shape: str = "rect") -> pg.ROI:
        """
        Add a draggable ROI in the middle of the sensor.

        Args:
            shape (str): "rect" or "circle".

        Returns:
            pg.ROI: The new ROI. Its position and size are in sensor pixels.
        """
        rows, cols = self._sensor or (100, 100)
        size = max(4, int(min(rows, cols) / 5))
        pos = (int(rows / 2 - size / 2), int(cols / 2 - size / 2))
        color = ROI_COLORS[self._roi_count % len(ROI_COLORS)]
        self._roi_count += 1
        options = {
            "pen": pg.mkPen(color, width=2),
            "removable": True,
            "snapSize": 1,
            "translateSnap": True,
            "scaleSnap": True,
        }
        if shape == "circle":
            roi = pg.CircleROI(pos, (size, size), **options)
        elif shape == "rect":
            roi = pg.RectROI(pos, (size, size), **options)
        else:
            raise ValueError(f"Unknown ROI shape {shape!r}; use 'rect' or 'circle'")
        roi.setProperty("roi_name", f"{shape} {self._roi_count}")
        roi.setProperty("roi_shape", shape)
        roi.setProperty("roi_color", color)
        roi.sigRegionChanged.connect(self._update_roi_table)
        roi.sigRemoveRequested.connect(self.remove_roi)
        self.view_box.addItem(roi, ignoreBounds=True)
        self._rois.append(roi)
        self._update_roi_table()
        return roi

    @SafeSlot(object)
    def remove_roi(self, roi: pg.ROI) -> None:
        """
        Remove one ROI.

        Args:
            roi (pg.ROI): The ROI to remove.
        """
        if roi not in self._rois:
            return
        self._rois.remove(roi)
        self.view_box.removeItem(roi)
        # pyqtgraph gives the ROI and each of its handles a parentless menu
        for item in (roi, *roi.getHandles()):
            _delete_menu(getattr(item, "menu", None))
        self._update_roi_table()

    @SafeSlot()
    def clear_rois(self) -> None:
        """Remove all ROIs."""
        for roi in list(self._rois):
            self.remove_roi(roi)

    def roi_regions(self) -> list[dict]:
        """
        ROI bounds in sensor pixels.

        Returns:
            list[dict]: One dict per ROI with ``name``, ``shape``, ``x`` and ``y`` (each a
            ``(from, to)`` pair; x runs along array rows, y along columns) and, for circles,
            ``center`` and ``radius``.
        """
        regions = []
        for roi in self._rois:
            (x0, y0), (w, h) = tuple(roi.pos()), tuple(roi.size())
            region = {
                "name": roi.property("roi_name"),
                "shape": roi.property("roi_shape"),
                "x": (x0, x0 + w),
                "y": (y0, y0 + h),
            }
            if region["shape"] == "circle":
                region["center"] = (x0 + w / 2, y0 + h / 2)
                region["radius"] = w / 2
            regions.append(region)
        return regions

    def _update_roi_table(self) -> None:
        regions = self.roi_regions()
        self.roi_table.setRowCount(len(regions))
        for row, (roi, region) in enumerate(zip(self._rois, regions)):
            name = QTableWidgetItem(region["name"])
            name.setForeground(QColor(roi.property("roi_color")))
            if region["shape"] == "circle":
                cx, cy = region["center"]
                name.setToolTip(f"centre x {cx:g}, y {cy:g}, radius {region['radius']:g}")
            self.roi_table.setItem(row, 0, name)
            values = (*region["x"], *region["y"])
            for col, value in enumerate(values, start=1):
                self.roi_table.setItem(row, col, QTableWidgetItem(f"{value:g}"))
        self.roi_table.setVisible(bool(regions))
        self.rois_changed.emit(regions)

    def cleanup(self):
        """Remove ROIs and the plot's context menus, which are top-level widgets."""
        self.clear_rois()
        _delete_menu(self.view_box.menu)
        _delete_menu(self.plot_item.ctrlMenu)
        super().cleanup()


def _delete_menu(menu) -> None:
    if menu is not None:
        menu.close()
        menu.deleteLater()
