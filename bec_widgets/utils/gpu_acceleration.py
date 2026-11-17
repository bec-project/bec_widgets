"""OpenGL viewport support for BEC plots.

pyqtgraph 0.14 renders :class:`~pyqtgraph.PlotCurveItem` and
:class:`~pyqtgraph.PColorMeshItem` through a shader program whenever the
:class:`~pyqtgraph.GraphicsView` viewport is a ``QOpenGLWidget``. Every other
item -- notably ``ImageItem``, ``ScatterPlotItem``, ``TextItem`` and the ROIs --
keeps going through ``QPainter``, so only curve-heavy plots gain from it.

Acceleration is therefore opt-in per widget, and is additionally gated on the
context actually being hardware backed: a remote beamline session that lands on
a software rasteriser (llvmpipe/swrast) renders *slower* through OpenGL than
through the raster path.

The ``BEC_WIDGETS_OPENGL`` environment variable overrides the decision:

``auto`` (default)
    Use OpenGL for widgets that ask for it, unless the renderer is software.
``1`` / ``on`` / ``true``
    Force OpenGL on, even for a software renderer.
``0`` / ``off`` / ``false``
    Never use OpenGL.
"""

from __future__ import annotations

import os
from functools import lru_cache

from bec_lib import bec_logger
from pyqtgraph import GraphicsView
from qtpy.QtCore import QPoint, QRectF, Qt
from qtpy.QtGui import QOffscreenSurface, QOpenGLContext, QPainter, QPixmap
from qtpy.QtOpenGLWidgets import QOpenGLWidget
from qtpy.QtWidgets import QApplication, QWidget

logger = bec_logger.logger

ENV_VAR = "BEC_WIDGETS_OPENGL"

# Substrings identifying a renderer that is not backed by a GPU. Mesa reports
# these when a session has no direct rendering, which is the common case for
# X-forwarded or VNC beamline consoles.
_SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast", "software rasterizer", "gallium, swr")

_GL_VENDOR = 0x1F00
_GL_RENDERER = 0x1F01
_GL_VERSION = 0x1F02


@lru_cache(maxsize=1)
def opengl_info() -> dict[str, str] | None:
    """Query the OpenGL implementation backing this session.

    Creates a throwaway context on an offscreen surface. The result is cached,
    so the cost is paid once per process.

    Returns:
        dict[str, str] | None: ``vendor``/``renderer``/``version`` strings, or
        None if no usable context could be created.
    """
    if QApplication.instance() is None:
        # A context needs a QApplication; asking this early is a caller bug, but
        # it must not take the GUI down.
        logger.warning("OpenGL probed before a QApplication exists; assuming unavailable")
        return None

    surface = QOffscreenSurface()
    surface.create()
    context = QOpenGLContext()
    if not context.create() or not context.makeCurrent(surface):
        logger.info("No usable OpenGL context; plots will use the raster viewport")
        return None
    try:
        functions = context.functions()
        info = {
            "vendor": str(functions.glGetString(_GL_VENDOR)),
            "renderer": str(functions.glGetString(_GL_RENDERER)),
            "version": str(functions.glGetString(_GL_VERSION)),
        }
    finally:
        context.doneCurrent()
    logger.info(f"OpenGL renderer: {info['renderer']} ({info['vendor']}, {info['version']})")
    return info


def is_software_renderer() -> bool:
    """Whether the OpenGL context is served by a software rasteriser."""
    info = opengl_info()
    if info is None:
        return False
    renderer = info["renderer"].lower()
    return any(marker in renderer for marker in _SOFTWARE_RENDERERS)


def _env_override() -> bool | None:
    """Read ``BEC_WIDGETS_OPENGL``; None when unset or set to ``auto``."""
    # Read on every call rather than caching, so tests and the launcher can flip
    # it after bec_widgets has been imported.
    raw = os.environ.get(ENV_VAR, "").strip().lower()
    if raw in ("", "auto"):
        return None
    if raw in ("1", "on", "true", "yes"):
        return True
    if raw in ("0", "off", "false", "no"):
        return False
    logger.warning(f"Ignoring unrecognised {ENV_VAR}={raw!r}; expected auto, 1 or 0")
    return None


def opengl_available(requested: bool = True) -> bool:
    """Decide whether a widget that asked for OpenGL should actually get it.

    Args:
        requested(bool): Whether the widget wants the OpenGL viewport at all.

    Returns:
        bool: True if the OpenGL viewport should be installed.
    """
    override = _env_override()
    if override is False:
        return False
    if not requested and override is not True:
        return False
    if opengl_info() is None:
        return False
    if override is True:
        return True
    if is_software_renderer():
        logger.info(
            "OpenGL is available but software rendered; keeping the raster viewport. "
            f"Set {ENV_VAR}=1 to override."
        )
        return False
    return True


def _release_gl_state(view: GraphicsView) -> None:
    """Drop the cached ``OpenGLState`` of every item in ``view``'s scene.

    pyqtgraph creates that state once per item and parents it to the *viewport*
    widget. Swapping the viewport deletes it on the C++ side while the item
    keeps a stale Python reference, so the next ``paintGL`` raises
    ``RuntimeError: Signal source has been deleted``. ``PlotCurveItem.paint``
    swallows it, which shows up as a silently missing curve rather than a
    crash. Clearing the reference makes the item rebuild its state against the
    new context.
    """
    scene = view.scene()
    if scene is None:
        return
    for item in scene.items():
        # PlotDataItem delegates drawing to a PlotCurveItem held in .curve, which
        # is itself in the scene; check both so nothing is missed.
        for target in {item, getattr(item, "curve", None)}:
            if target is None or getattr(target, "glstate", None) is None:
                continue
            signal = getattr(target, "sigPlotChanged", None)
            if signal is not None:
                try:
                    signal.disconnect(target.glstate.verticesChanged)
                except (RuntimeError, TypeError):
                    # not connected, or the C++ side is already gone
                    pass
            target.glstate = None


def set_view_opengl(view: GraphicsView, enabled: bool) -> bool:
    """Switch ``view`` between the OpenGL and raster viewport at runtime.

    Args:
        view(GraphicsView): The view whose viewport should be swapped.
        enabled(bool): Whether the OpenGL viewport is wanted.

    Returns:
        bool: Whether the OpenGL viewport is active afterwards.
    """
    if isinstance(view.viewport(), QOpenGLWidget) is enabled:
        return enabled
    _release_gl_state(view)
    view.useOpenGL(enabled)
    return isinstance(view.viewport(), QOpenGLWidget)


def _accelerated_views(widget: QWidget) -> list[GraphicsView]:
    """GraphicsView descendants of ``widget`` that are on an OpenGL viewport."""
    views = widget.findChildren(GraphicsView)
    if isinstance(widget, GraphicsView):
        views.append(widget)
    return [v for v in views if v.isVisible() and isinstance(v.viewport(), QOpenGLWidget)]


def grab_widget(widget: QWidget) -> QPixmap:
    """Grab ``widget`` including any plots drawn on an OpenGL viewport.

    ``QWidget.grab`` renders the widget tree through ``QPainter`` and never
    reaches a ``QOpenGLWidget``, so a plot on the OpenGL viewport comes back
    blank. ``QOpenGLWidget.grabFramebuffer`` is not a reliable substitute
    either -- on macOS the framebuffer is not retained after compositing.

    Instead, each affected view re-renders its *scene* through ``QPainter``
    into the grabbed pixmap. That is the same raster path the non-accelerated
    plots already use, so the output matches, and no OpenGL state is touched.

    Args:
        widget(QWidget): The widget to capture.

    Returns:
        QPixmap: The captured pixmap, or the plain ``grab()`` result when no
        OpenGL-backed plot is present.
    """
    pixmap = widget.grab()
    views = _accelerated_views(widget)
    if not views or pixmap.isNull():
        return pixmap

    painter = QPainter(pixmap)
    try:
        for view in views:
            viewport = view.viewport()
            # GraphicsView.render forwards to QGraphicsView.render, which stretches
            # the scene across the whole painter unless target and source are given.
            origin = viewport.mapTo(widget, QPoint(0, 0))
            source = viewport.rect()
            target = QRectF(origin.x(), origin.y(), source.width(), source.height())
            try:
                view.render(painter, target, source, Qt.AspectRatioMode.IgnoreAspectRatio)
            except Exception:  # pragma: no cover - rendering must never break a screenshot
                logger.warning(f"Failed to render {view!r} into screenshot", exc_info=True)
    finally:
        painter.end()
    return pixmap
