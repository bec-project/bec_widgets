"""
OpenGL 3D view of the VolumePlot widget, built on pyqtgraph.opengl.

The scene lives in voxel-index space (voxel ``i`` spans ``[i, i + 1)``): the volume, the
current cut, pinned cuts, projections on the walls, a bounding box and labels. One scene
matrix maps that space into the view: it centres the box, scales it to the display box
and turns the volume's up axis upwards.

OpenGL is optional. :func:`opengl_status` checks once whether a usable desktop OpenGL
context exists; without one the view shows a short note instead of the 3D scene, and the
widget keeps working with its 2D cut.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from dataclasses import dataclass

import numpy as np
from bec_lib import bec_logger
from qtpy.QtCore import QPointF, Qt, Signal
from qtpy.QtGui import QColor, QMatrix4x4, QVector4D
from qtpy.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget

from bec_widgets.widgets.plots.volume_plot.volume_data import VolumeData

logger = bec_logger.logger

#: Set to 1 to never create the 3D view, for example on a remote display without OpenGL.
DISABLE_ENV = "BEC_WIDGETS_DISABLE_OPENGL"

_STATUS: tuple[bool, str] | None = None


@dataclass(frozen=True)
class GLInfo:
    """What the OpenGL check found."""

    available: bool
    message: str
    software: bool = False


def opengl_status(refresh: bool = False) -> GLInfo:
    """
    Check whether the 3D view can run here.

    It needs PyOpenGL and a desktop OpenGL 2.1 (or OpenGL ES) context. The answer is cached
    for the process; ``refresh`` checks again.

    Args:
        refresh (bool): Ignore the cached answer.

    Returns:
        GLInfo: Availability, a short message for the user and whether the renderer is a
        software one (llvmpipe, softpipe, swrast), which is slow for large volumes.
    """
    global _STATUS
    if os.environ.get(DISABLE_ENV, "").strip() not in ("", "0"):
        return GLInfo(False, f"3D view turned off ({DISABLE_ENV} is set).")
    if os.environ.get("LIBGL_ALWAYS_INDIRECT", "").strip() not in ("", "0"):
        # Indirect GLX offers OpenGL 1.4 at best, and creating a context through it can
        # take the X connection down (seen with Xvfb +iglx), so do not even try.
        return GLInfo(False, "3D view is off: LIBGL_ALWAYS_INDIRECT is set (indirect GLX).")
    if _STATUS is not None and not refresh:
        return GLInfo(*_STATUS)
    info = _probe_opengl()
    _STATUS = (info.available, info.message, info.software)
    return info


def _current_egl_context() -> bool:
    """
    Whether the current OpenGL context is an EGL one (Linux only).

    Qt picks EGL on Wayland and, on X11, when the X server has no GLX (some VNC and remote
    setups). PyOpenGL must then use its EGL platform as well, or every call fails with
    "no valid context".
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        egl = ctypes.CDLL(ctypes.util.find_library("EGL") or "libEGL.so.1")
        egl.eglGetCurrentContext.restype = ctypes.c_void_p
        return bool(egl.eglGetCurrentContext())
    except (OSError, AttributeError):
        return False


def _probe_opengl() -> GLInfo:
    from qtpy.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext

    platform = QGuiApplication.platformName()
    if platform in ("offscreen", "minimal"):
        return GLInfo(False, f"3D view needs OpenGL; the Qt '{platform}' platform has none.")
    context = QOpenGLContext()
    if not context.create():
        return GLInfo(False, "3D view needs OpenGL; this display gives no OpenGL context.")
    surface = QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    if not context.makeCurrent(surface):
        return GLInfo(False, "3D view needs OpenGL; the OpenGL context does not start.")
    try:
        if _current_egl_context() and "OpenGL" not in sys.modules:
            # PyOpenGL chooses its platform once, at import; make it match Qt's.
            os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
        try:
            import pyqtgraph.opengl  # noqa: F401  pylint: disable=unused-import
            from OpenGL import GL
            from OpenGL import platform as gl_platform
        except Exception as exc:  # ImportError, or a broken libGL
            return GLInfo(False, f"3D view needs PyOpenGL ({exc.__class__.__name__}).")
        if not gl_platform.PLATFORM.GetCurrentContext():
            name = os.environ.get("PYOPENGL_PLATFORM", "default")
            return GLInfo(
                False,
                "3D view needs OpenGL; Qt and PyOpenGL use different OpenGL platforms "
                f"(PYOPENGL_PLATFORM={name}).",
            )
        version = context.format().version()
        renderer = GL.glGetString(GL.GL_RENDERER)
        renderer = renderer.decode(errors="replace") if isinstance(renderer, bytes) else ""
    except Exception as exc:  # pragma: no cover - driver specific
        return GLInfo(False, f"3D view needs OpenGL; probing failed ({exc}).")
    finally:
        context.doneCurrent()
    if not context.isOpenGLES() and tuple(version) < (2, 1):
        return GLInfo(
            False, f"3D view needs OpenGL 2.1; this display has {version[0]}.{version[1]}."
        )
    software = any(name in renderer.lower() for name in ("llvmpipe", "softpipe", "swrast"))
    return GLInfo(True, f"OpenGL {version[0]}.{version[1]}, {renderer}", software)


def remote_x11_display() -> bool:
    """Whether the X display is forwarded over SSH (ssh -X): every frame crosses the network."""
    display = os.environ.get("DISPLAY", "")
    return bool(os.environ.get("SSH_CONNECTION")) and bool(display) and not display.startswith(":")


def volume_rgba(
    normalized: np.ndarray, lut: np.ndarray, opacity: float = 0.5, threshold: float = 0.05
) -> np.ndarray:
    """
    Colour a normalized volume for GLVolumeItem.

    Args:
        normalized (np.ndarray): Values in 0..1 of shape (nx, ny, nz).
        lut (np.ndarray): Colour table of shape (256, 3 or 4), uint8.
        opacity (float): Opacity of the brightest voxel, 0..1.
        threshold (float): Values below it are fully transparent.

    Returns:
        np.ndarray: RGBA array of shape (nx, ny, nz, 4), uint8.
    """
    index = np.clip((normalized * 255).astype(np.int32), 0, 255)
    rgba = np.empty(normalized.shape + (4,), dtype=np.ubyte)
    rgba[..., :3] = lut[index, :3]
    scaled = np.clip((normalized - threshold) / max(1.0 - threshold, 1e-6), 0.0, 1.0)
    rgba[..., 3] = (scaled**1.5 * opacity * 255).astype(np.ubyte)
    return rgba


def plane_rgba(normalized: np.ndarray, lut: np.ndarray, floor: int = 70) -> np.ndarray:
    """
    Colour a normalized 2D cut for GLImageItem.

    Low values are drawn faint (alpha ``floor``) so the cut reads as a tinted sheet that
    does not hide the volume behind it; voxels without data stay transparent.
    """
    finite = np.isfinite(normalized)
    values = np.nan_to_num(normalized)
    index = np.clip((values * 255).astype(np.int32), 0, 255)
    rgba = np.empty(normalized.shape + (4,), dtype=np.ubyte)
    rgba[..., :3] = lut[index, :3]
    alpha = floor + (255 - floor) * np.sqrt(np.clip(values, 0.0, 1.0))
    rgba[..., 3] = np.where(finite, alpha, 0).astype(np.ubyte)
    return rgba


def glow_rgba(normalized: np.ndarray, color: QColor, strength: float = 0.75) -> np.ndarray:
    """A projection drawn as a glow of one colour whose alpha follows the value."""
    rgba = np.empty(normalized.shape + (4,), dtype=np.ubyte)
    rgba[..., 0] = color.red()
    rgba[..., 1] = color.green()
    rgba[..., 2] = color.blue()
    rgba[..., 3] = (np.clip(np.nan_to_num(normalized), 0, 1) ** 1.6 * strength * 255).astype(
        np.ubyte
    )
    return rgba


#: Data axis -> scene axis with sign, per up axis. Proper rotations, so nothing is mirrored.
#: With y up (beam along z) the beam runs left to right seen from the default camera.
_SCENE_AXES = {
    2: ((0, 1.0), (1, 1.0), (2, 1.0)),
    1: ((0, -1.0), (2, 1.0), (1, 1.0)),
    0: ((2, 1.0), (0, 1.0), (1, 1.0)),
}

#: Default camera: from the +X side, a little upstream and above.
DEFAULT_CAMERA = {"elevation": 18.0, "azimuth": -28.0}

#: Edge length of the display box's longest side, in scene units.
BOX_SIZE = 10.0


def plane_matrix(axis: int, offset: float) -> QMatrix4x4:
    """
    Map an image's local (u, v) plane onto the cut perpendicular to ``axis``.

    The image's first array axis runs along the first remaining data axis, its second
    along the second one, as :meth:`VolumeData.slice` returns them.
    """
    p, q = VolumeData.plane_axes(axis)
    m = np.zeros((4, 4))
    m[p, 0] = 1.0
    m[q, 1] = 1.0
    m[axis, 2] = 1.0
    m[axis, 3] = offset
    m[3, 3] = 1.0
    return QMatrix4x4(*m.flatten().tolist())


def frame_points(shape: tuple[int, int, int], axis: int, offset: float) -> np.ndarray:
    """Corner points of the cut perpendicular to ``axis``, closed, in index space."""
    p, q = VolumeData.plane_axes(axis)
    corners = [(0, 0), (shape[p], 0), (shape[p], shape[q]), (0, shape[q]), (0, 0)]
    points = np.zeros((5, 3))
    for i, (a, b) in enumerate(corners):
        points[i, p] = a
        points[i, q] = b
        points[i, axis] = offset
    return points


def ray_box(origin: np.ndarray, direction: np.ndarray, size: np.ndarray):
    """
    Where a ray enters and leaves the box ``[0, size]``.

    Returns:
        tuple[float, float] | None: Ray parameters of entry and exit, or None on a miss.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / direction
        t1 = (0.0 - origin) * inv
        t2 = (size - origin) * inv
    t_low = np.nanmax(np.minimum(t1, t2))
    t_high = np.nanmin(np.maximum(t1, t2))
    if not np.isfinite(t_low) or not np.isfinite(t_high) or t_high < max(t_low, 0.0):
        return None
    return max(t_low, 0.0), t_high


class VolumeGLView(QWidget):
    """
    The 3D part of the VolumePlot: a pyqtgraph GLViewWidget or, without OpenGL, a note.

    Signals:
        hovered(QPointF): The pointer moved over the scene without a button pressed.
        clicked(QPointF, int): A click without dragging, with the keyboard modifiers.
    """

    hovered = Signal(QPointF)
    left = Signal()
    clicked = Signal(QPointF, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("volume_gl_view")
        self.info = opengl_status()
        self.canvas = None
        self._items: dict[str, object] = {}
        self._pinned: list[object] = []
        self._labels: list[object] = []
        self._shape = (1, 1, 1)
        self._scene = QMatrix4x4()
        self._volume_rgba: np.ndarray | None = None
        self._clip: tuple[int, int] | None = None
        self._dark = True

        layout = QStackedLayout(self)
        self.note = QLabel(self.info.message if not self.info.available else "")
        self.note.setObjectName("volume_gl_note")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setWordWrap(True)
        self.note.setProperty("variant", "muted")
        note_page = QWidget(self)
        note_layout = QVBoxLayout(note_page)
        note_layout.addWidget(self.note)
        layout.addWidget(note_page)
        if self.info.available:
            try:
                self.canvas = _GLCanvas(self)
            except Exception as exc:  # pragma: no cover - driver specific
                logger.warning(f"3D view could not start: {exc}")
                self.note.setText(f"3D view could not start: {exc}")
                self.canvas = None
        if self.canvas is not None:
            self.canvas.hovered.connect(self.hovered)
            self.canvas.left.connect(self.left)
            self.canvas.clicked.connect(self.clicked)
            layout.addWidget(self.canvas)
            layout.setCurrentWidget(self.canvas)
            self._build_items()
        # A small line in the corner: software OpenGL is the usual case over VNC and X2Go.
        self.renderer_label = QLabel(self)
        self.renderer_label.setObjectName("volume_gl_renderer")
        self.renderer_label.setProperty("variant", "muted")
        self.renderer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if self.info.available and remote_x11_display():
            self.renderer_label.setText("Forwarded display: turning may be slow")
            self.renderer_label.setToolTip(self.info.message)
        elif self.info.available and self.info.software:
            self.renderer_label.setText("Software OpenGL: turning may be slow")
            self.renderer_label.setToolTip(self.info.message)
        self.renderer_label.setVisible(bool(self.renderer_label.text()))

    # ------------------------------------------------------------------ setup
    @property
    def available(self) -> bool:
        """Whether the 3D scene is shown."""
        return self.canvas is not None

    def _build_items(self):
        import pyqtgraph.opengl as gl
        from OpenGL import GL

        translucent = {
            GL.GL_DEPTH_TEST: False,
            GL.GL_BLEND: True,
            GL.GL_CULL_FACE: False,
            "glBlendFuncSeparate": (
                GL.GL_SRC_ALPHA,
                GL.GL_ONE_MINUS_SRC_ALPHA,
                GL.GL_ONE,
                GL.GL_ONE_MINUS_SRC_ALPHA,
            ),
        }
        self._translucent = translucent
        empty3 = np.zeros((1, 1, 1, 4), dtype=np.ubyte)
        empty2 = np.zeros((1, 1, 4), dtype=np.ubyte)
        items = {
            "walls": [gl.GLImageItem(empty2, smooth=True, glOptions="additive") for _ in range(3)],
            "box": gl.GLBoxItem(),
            "volume": gl.GLVolumeItem(empty3, sliceDensity=1, smooth=True, glOptions=translucent),
            "cut": gl.GLImageItem(empty2, smooth=False, glOptions=translucent),
            "cut_frame": gl.GLLinePlotItem(width=2.0, antialias=True, glOptions="translucent"),
        }
        for depth, key in enumerate(["box", "volume", "cut", "cut_frame"]):
            items[key].setDepthValue(depth)
        for wall in items["walls"]:
            wall.setDepthValue(-1)
            wall.hide()
            self.canvas.addItem(wall)
        for key in ["box", "volume", "cut", "cut_frame"]:
            self.canvas.addItem(items[key])
        items["cut"].hide()
        items["cut_frame"].hide()
        self._items = items

    # ------------------------------------------------------------------ scene
    def set_volume(self, volume: VolumeData, rgba: np.ndarray, reset_camera: bool = True):
        """
        Show a new volume.

        Args:
            volume (VolumeData): The volume, for its shape and display box.
            rgba (np.ndarray): Coloured voxels from :func:`volume_rgba`.
            reset_camera (bool): Move the camera to the default view.
        """
        if self.canvas is None:
            return
        shape_changed = volume.shape != self._shape
        self._shape = volume.shape
        self._volume_rgba = rgba
        self._scene = self._scene_matrix(volume)
        self._apply_volume()
        box = self._items["box"]
        box.setSize(*self._shape)
        box.setTransform(self._scene)
        if reset_camera or shape_changed:
            self.reset_camera()
        self.canvas.update()

    def update_volume_rgba(self, rgba: np.ndarray):
        """Recolour the volume without moving the camera (colour map, opacity, live data)."""
        if self.canvas is None:
            return
        self._volume_rgba = rgba
        self._apply_volume()

    def _scene_matrix(self, volume: VolumeData) -> QMatrix4x4:
        lengths = np.asarray(volume.display_box()) * BOX_SIZE
        scale = lengths / np.asarray(volume.shape, dtype=float)
        m = np.zeros((4, 4))
        for data_axis, (scene_axis, sign) in enumerate(_SCENE_AXES[volume.up_axis]):
            m[scene_axis, data_axis] = sign * scale[data_axis]
            m[scene_axis, 3] = -sign * scale[data_axis] * volume.shape[data_axis] / 2.0
        m[3, 3] = 1.0
        return QMatrix4x4(*m.flatten().tolist())

    def _apply_volume(self):
        if self._volume_rgba is None:
            return
        item = self._items["volume"]
        rgba = self._volume_rgba
        offset = np.zeros(3)
        if self._clip is not None:
            axis, start = self._clip
            start = int(np.clip(start, 0, rgba.shape[axis] - 1))
            rgba = np.take(rgba, np.arange(start, rgba.shape[axis]), axis=axis)
            offset[axis] = start
        local = QMatrix4x4()
        local.translate(*offset)
        item.setTransform(self._scene * local)
        item.setData(np.ascontiguousarray(rgba))

    def set_clip(self, axis: int | None, start: int = 0):
        """
        Hide the part of the volume before voxel ``start`` along ``axis``.

        Args:
            axis (int | None): Axis to clip along; None shows the whole volume.
            start (int): First voxel that stays visible.
        """
        clip = None if axis is None else (int(axis), int(start))
        if clip == self._clip:
            return
        self._clip = clip
        if self.canvas is not None:
            self._apply_volume()

    def set_cut(self, axis: int, index: int, rgba: np.ndarray | None, color: QColor):
        """
        Show the current cut as a coloured plane with a frame.

        Args:
            axis (int): Axis the cut is perpendicular to.
            index (int): Voxel index of the cut.
            rgba (np.ndarray | None): Coloured cut from :func:`plane_rgba`; None hides it.
            color (QColor): Frame colour.
        """
        if self.canvas is None:
            return
        cut, frame = self._items["cut"], self._items["cut_frame"]
        if rgba is None:
            cut.hide()
            frame.hide()
            return
        offset = index + 0.5
        cut.setData(rgba)
        cut.setTransform(self._scene * plane_matrix(axis, offset))
        cut.show()
        frame.setData(pos=frame_points(self._shape, axis, offset), color=color.getRgbF())
        frame.setTransform(self._scene)
        frame.show()

    def set_pinned_cuts(self, cuts: list[tuple[int, int, str]], color: QColor):
        """Outline the pinned cuts, given as (axis, index, label)."""
        if self.canvas is None:
            return
        import pyqtgraph.opengl as gl

        for item in self._pinned:
            self.canvas.removeItem(item)
        self._pinned = []
        rgba = color.getRgbF()
        for axis, index, _label in cuts:
            item = gl.GLLinePlotItem(
                pos=frame_points(self._shape, axis, index + 0.5),
                color=(rgba[0], rgba[1], rgba[2], 0.45),
                width=1.0,
                antialias=True,
                glOptions="translucent",
            )
            item.setTransform(self._scene)
            item.setDepthValue(4)
            self.canvas.addItem(item)
            self._pinned.append(item)

    def set_labels(self, labels: list[tuple[int, int, str]], color: QColor):
        """Write labels above the box at the given (axis, index, text)."""
        if self.canvas is None:
            return
        import pyqtgraph.opengl as gl
        from qtpy.QtGui import QFont

        for item in self._labels:
            self.canvas.removeItem(item)
        self._labels = []
        font = QFont()
        font.setPointSizeF(max(font.pointSizeF(), 9.0))
        up = self._up_axis_of_scene()
        for row, (axis, index, text) in enumerate(labels):
            pos = np.asarray(self._shape, dtype=float) / 2.0
            pos[axis] = index + 0.5
            # every other label a line higher, so neighbours do not overlap
            pos[up] = self._shape[up] * (1.08 + 0.22 * (row % 2))
            item = gl.GLTextItem(
                pos=pos,
                text=text,
                color=color,
                font=font,
                alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            )
            item.setTransform(self._scene)
            item.setDepthValue(10)
            self.canvas.addItem(item)
            self._labels.append(item)

    def _up_axis_of_scene(self) -> int:
        m = np.array(self._scene.data()).reshape(4, 4).T  # column-major storage
        return int(np.argmax(np.abs(m[2, :3])))

    def set_projections(self, projections: dict[int, np.ndarray] | None, color: QColor):
        """
        Show projections on the far walls of the box.

        Args:
            projections (dict[int, np.ndarray] | None): Normalized projection per axis it
                was taken along; None hides them.
            color (QColor): Glow colour.
        """
        if self.canvas is None:
            return
        walls = self._items["walls"]
        for wall in walls:
            wall.hide()
        if not projections:
            return
        for axis, image in projections.items():
            wall = walls[axis]
            offset = self._far_wall_offset(axis)
            wall.setData(glow_rgba(image, color))
            wall.setTransform(self._scene * plane_matrix(axis, offset))
            wall.setGLOptions("additive" if self._dark else self._translucent)
            wall.show()

    def _far_wall_offset(self, axis: int) -> float:
        """The wall of ``axis`` away from the default camera, just outside the box."""
        m = np.array(self._scene.data()).reshape(4, 4).T
        direction = m[:3, axis]
        elev = np.radians(DEFAULT_CAMERA["elevation"])
        azim = np.radians(DEFAULT_CAMERA["azimuth"])
        camera = np.array([np.cos(elev) * np.cos(azim), np.cos(elev) * np.sin(azim), np.sin(elev)])
        gap = 0.02 * self._shape[axis]
        if float(np.dot(direction, camera)) > 0:
            return -gap
        return self._shape[axis] + gap

    def set_box_color(self, color: QColor):
        """Colour of the bounding box."""
        if self.canvas is not None:
            self._items["box"].setColor(color)

    def set_dark(self, dark: bool, background: QColor):
        """
        Follow the theme: the background, and how volume and walls blend.

        On a dark background the volume glows (additive blending, like a beam lighting up
        fog); on a light one additive blending would wash out to white, so it is blended
        as a translucent medium instead.
        """
        self._dark = dark
        if self.canvas is not None:
            self.canvas.setBackgroundColor(background)
            self._items["volume"].setGLOptions("additive" if dark else self._translucent)
            self.canvas.update()

    def reset_camera(self):
        """Look at the whole box from the default direction."""
        if self.canvas is None:
            return
        from pyqtgraph import Vector

        self.canvas.setCameraPosition(
            pos=Vector(0, 0, 0), distance=BOX_SIZE * 1.45, **DEFAULT_CAMERA
        )

    def grab_image(self):
        """Render the scene into a QImage (for screenshots and tests)."""
        if self.canvas is None:
            return self.grab().toImage()
        return self.canvas.grabFramebuffer()

    # ------------------------------------------------------------------ picking
    def ray_at(self, pos: QPointF) -> tuple[np.ndarray, np.ndarray] | None:
        """
        The ray under a widget position, in voxel-index space.

        Returns:
            tuple[np.ndarray, np.ndarray] | None: Origin and direction, or None without a view.
        """
        if self.canvas is None:
            return None
        width, height = max(self.canvas.width(), 1), max(self.canvas.height(), 1)
        viewport = (0, 0, width, height)
        mvp = self.canvas.projectionMatrix(viewport, viewport) * self.canvas.viewMatrix()
        mvp = mvp * self._scene
        inverse, ok = mvp.inverted()
        if not ok:
            return None
        ndc_x = 2.0 * pos.x() / width - 1.0
        ndc_y = 1.0 - 2.0 * pos.y() / height
        ends = []
        for depth in (-1.0, 1.0):
            v = inverse.map(QVector4D(ndc_x, ndc_y, depth, 1.0))
            if v.w() == 0:
                return None
            ends.append(np.array([v.x(), v.y(), v.z()]) / v.w())
        direction = ends[1] - ends[0]
        norm = np.linalg.norm(direction)
        if norm == 0:
            return None
        return ends[0], direction / norm

    def pick(self, pos: QPointF, volume: VolumeData, axis: int) -> int | None:
        """
        The cut index under the pointer along ``axis``.

        The ray through the pointer is sampled inside the box and the brightest voxel wins,
        so pointing at the beam picks the beam, not the empty space in front of it. Without
        any data on the ray the middle of the ray inside the box is used.

        Returns:
            int | None: Voxel index along ``axis``, or None when the pointer misses the box.
        """
        ray = self.ray_at(pos)
        if ray is None:
            return None
        origin, direction = ray
        size = np.asarray(volume.shape, dtype=float)
        hit = ray_box(origin, direction, size)
        if hit is None:
            return None
        t0, t1 = hit
        count = int(max(8, 2 * np.max(size)))
        samples = origin + np.outer(np.linspace(t0, t1, count), direction)
        best = volume.brightest_along(samples)
        point = samples[best] if best is not None else origin + 0.5 * (t0 + t1) * direction
        return int(np.clip(np.floor(point[axis]), 0, volume.shape[axis] - 1))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.renderer_label.adjustSize()
        self.renderer_label.move(8, self.height() - self.renderer_label.height() - 6)
        self.renderer_label.raise_()

    def cleanup(self):
        """Drop the GL items; the canvas goes with the widget."""
        if self.canvas is not None:
            self.canvas.clear()
            self._pinned = []
            self._labels = []


def _make_canvas_class():
    import pyqtgraph.opengl as gl

    class _Canvas(gl.GLViewWidget):
        """GLViewWidget that also reports hover and plain clicks."""

        hovered = Signal(QPointF)
        left = Signal()
        clicked = Signal(QPointF, int)

        #: A press and release closer than this (px) counts as a click, not a turn.
        CLICK_SLOP = 4.0

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMouseTracking(True)
            self._press: QPointF | None = None

        def mousePressEvent(self, ev):
            self._press = ev.position()
            super().mousePressEvent(ev)

        def mouseMoveEvent(self, ev):
            if ev.buttons() == Qt.MouseButton.NoButton:
                self.hovered.emit(ev.position())
                return
            super().mouseMoveEvent(ev)

        def mouseReleaseEvent(self, ev):
            press, self._press = self._press, None
            if press is not None and ev.button() == Qt.MouseButton.LeftButton:
                moved = ev.position() - press
                if abs(moved.x()) + abs(moved.y()) <= self.CLICK_SLOP:
                    self.clicked.emit(ev.position(), int(ev.modifiers().value))
            super().mouseReleaseEvent(ev)

        def leaveEvent(self, ev):
            self.left.emit()
            super().leaveEvent(ev)

    return _Canvas


_CANVAS_CLASS = None


def _GLCanvas(parent):  # pylint: disable=invalid-name
    """Create the GL canvas; the class is built on first use so PyOpenGL stays optional."""
    global _CANVAS_CLASS
    if _CANVAS_CLASS is None:
        _CANVAS_CLASS = _make_canvas_class()
    return _CANVAS_CLASS(parent)
