"""
Picture-only live view for JPEG preview frames.

The frame is decoded by Qt into a QImage on the thread that receives Redis messages and drawn
as a pixmap. There is no numpy data on the GUI side, so there are no levels, histogram, ROI or
pixel values; a grayscale frame can still be coloured through an 8-bit colour table.
"""

from __future__ import annotations

import time

from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QRectF, Qt, Signal
from qtpy.QtGui import QColor, QImage, QPainter, QPixmap
from qtpy.QtWidgets import (
    QComboBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.jpeg_frames import qimage_preview

COLORMAPS = ("gray", "magma", "viridis", "plasma", "inferno")


class _ZoomView(QGraphicsView):
    """Graphics view with wheel zoom around the cursor."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setBackgroundBrush(QColor(20, 20, 20))
        self.fit_on_next_frame = True

    def wheelEvent(self, event):  # pylint: disable=invalid-name
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)
        self.fit_on_next_frame = False


class JpegView(BECWidget, QWidget):
    """Live view that shows preview frames as a Qt picture, without decoding to numpy."""

    frame_shown = Signal()

    def __init__(self, parent=None, device: str | None = None, signal: str = "preview", **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._device = None
        self._signal = signal
        self._color_table: list[int] | None = None
        self.last_frame_metadata: dict = {}
        self.last_update_ms = 0.0

        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self._scene.addItem(self._pixmap_item)
        self.view = _ZoomView(self._scene, self)

        self.colormap_box = QComboBox(self)
        self.colormap_box.addItems(COLORMAPS)
        self.colormap_box.setToolTip("Colour table for grayscale frames (colour JPEGs ignore it)")
        self.colormap_box.currentTextChanged.connect(self.set_colormap)
        fit_button = QPushButton("Fit", self)
        fit_button.clicked.connect(self.fit)
        self.info_label = QLabel("No frame yet", self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Colormap", self))
        bar.addWidget(self.colormap_box)
        bar.addWidget(fit_button)
        bar.addStretch(1)
        bar.addWidget(self.info_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.view)

        if device:
            self.set_source(device, signal)

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
        self.view.fit_on_next_frame = True
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
        """Fit the whole frame into the view."""
        self.view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

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
        new_size = pixmap.size() != self._pixmap_item.pixmap().size()
        self._pixmap_item.setPixmap(pixmap)
        if new_size:
            self._scene.setSceneRect(QRectF(pixmap.rect()))
        if new_size or self.view.fit_on_next_frame:
            self.view.fit_on_next_frame = False
            self.fit()
        self.last_update_ms = (time.perf_counter() - t0) * 1e3
        self.last_frame_metadata = metadata
        encoding = metadata.get("encoding", "raw")
        self.info_label.setText(f"{qimage.width()} x {qimage.height()}  {encoding}")
        self.frame_shown.emit()
