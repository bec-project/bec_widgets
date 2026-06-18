"""Colorbar items with a BEC-specific right-click context menu.

pyqtgraph's :class:`~pyqtgraph.HistogramLUTItem` renders the colorbar histogram
as an ordinary plot, so right-clicking it shows the generic plot context menu
(``View All``, ``X/Y Axis``, ``Mouse Mode`` …). That is confusing for a colorbar,
where the only ranges that matter are the image color levels and the histogram
display range. :class:`BECHistogramLUTItem` replaces that menu on the histogram
view with a focused one and leaves the gradient (colormap) menu untouched.

:class:`BECColorBarItem` gives the simple colorbar (:class:`~pyqtgraph.ColorBarItem`)
the same focused menu (minus the histogram-specific entries), replacing pyqtgraph's
built-in colormap-only menu which would bypass the widget's colormap handling.
"""

from __future__ import annotations

from typing import Callable

import pyqtgraph as pg
from pyqtgraph.widgets.ColorMapMenu import ColorMapMenu
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLayout,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox


def _graphics_item_dialog_parent(item: pg.GraphicsObject) -> QWidget | None:
    """Return a QWidget to parent modal dialogs to (the item's host graphics view).

    Args:
        item (pg.GraphicsObject): The graphics item requesting a dialog.

    Returns:
        QWidget | None: The graphics view hosting the item, or None if unavailable.
    """
    scene = item.scene()
    if scene is not None:
        views = scene.views()
        if views:
            return views[0]
    return None


def _make_bec_colormap_menu(on_triggered: Callable) -> ColorMapMenu:
    """Create the "Select colormap" submenu used by the BEC colorbar menus.

    Args:
        on_triggered(Callable) : Slot connected to the menu's ``sigColorMapTriggered``.

    Returns:
        ColorMapMenu: The colormap submenu (entries are built lazily by pyqtgraph).
    """
    colormap_menu = ColorMapMenu(showColorMapSubMenus=True)
    colormap_menu.setTitle("Select colormap")
    colormap_menu.sigColorMapTriggered.connect(on_triggered)
    # The 'None' entry clears the colormap in plain pyqtgraph; BEC always keeps a
    # valid named colormap, so hide it to avoid a no-op menu entry.
    for action in colormap_menu.actions():
        if action.text() == "None":
            action.setVisible(False)
            break
    return colormap_menu


class RangeDialog(QDialog):
    """
    Modal dialog to enter a ``(min, max)`` floating point range.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        label: str,
        vmin: float,
        vmax: float,
        decimals: int = 4,
    ) -> None:
        """
        Initialize the range dialog.

        Args:
            parent (QWidget | None): The parent widget the dialog is modal to.
            title (str): The window title of the dialog.
            label (str): A description shown above the inputs. If empty, no label is shown.
            vmin (float): The initial value of the minimum spin box.
            vmax (float): The initial value of the maximum spin box.
            decimals (int): The number of decimals shown in both spin boxes.
        """
        super().__init__(parent=parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        # Fixed-size, non-resizable dialog that hugs its contents.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        if label:
            layout.addWidget(QLabel(label))

        form = QFormLayout()
        self.min_spinbox = BECSpinBox(parent=self)
        self.max_spinbox = BECSpinBox(parent=self)
        for spinbox, value in ((self.min_spinbox, vmin), (self.max_spinbox, vmax)):
            spinbox.setDecimals(decimals)
            spinbox.setValue(float(value))
        form.addRow("Minimum:", self.min_spinbox)
        form.addRow("Maximum:", self.max_spinbox)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_range(self) -> tuple[float, float]:
        """
        Return the entered range, ordered so that ``min <= max``.

        Returns:
            tuple[float, float]: The (minimum, maximum) values entered by the user.
        """
        low, high = self.min_spinbox.value(), self.max_spinbox.value()
        return (low, high) if low <= high else (high, low)

    @classmethod
    def get_new_range(
        cls,
        parent: QWidget | None,
        *,
        title: str,
        label: str,
        vmin: float,
        vmax: float,
        decimals: int = 4,
    ) -> tuple[float, float] | None:
        """
        Show the dialog modally and return the new range.

        Args:
            parent (QWidget | None): The parent widget the dialog is modal to.
            title (str): The window title of the dialog.
            label (str): A description shown above the inputs.
            vmin (float): The initial value of the minimum spin box.
            vmax (float): The initial value of the maximum spin box.
            decimals (int): The number of decimals shown in both spin boxes.

        Returns:
            tuple[float, float] | None: The new (min, max) range, or None if cancelled.
        """
        dialog = cls(parent, title=title, label=label, vmin=vmin, vmax=vmax, decimals=decimals)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.get_range()
            return None
        finally:
            dialog.deleteLater()


class BECHistogramLUTItem(pg.HistogramLUTItem):
    """
    :class:`~pyqtgraph.HistogramLUTItem` with a BEC-specific context menu.

    The default pyqtgraph context menu on the histogram view is replaced with one
    exposing the controls that matter for a colorbar:

    * **Colormap** -- a submenu (pyqtgraph's :class:`~pyqtgraph.widgets.ColorMapMenu.ColorMapMenu`)
      to pick the image colormap. The choice is emitted through
      :attr:`sigColorMapChangeRequested` so the owning image widget applies it through
      its usual colormap handling (config + multi-layer sync + colorbar).
    * **Image scaling (levels)** -- the ``LinearRegionItem`` mapping data values to
      colors. Changes are emitted through :attr:`sigColorLevelsChangeRequested` and
      :attr:`sigAutoLevelsRequested` so the owning image widget keeps autorange and
      multi-layer state consistent (rather than mutating levels here directly).
    * **Histogram display range** -- the visible range of the histogram plot, applied
      directly via :meth:`~pyqtgraph.HistogramLUTItem.setHistogramRange` /
      :meth:`~pyqtgraph.HistogramLUTItem.autoHistogramRange`.

    The gradient (colormap) context menu on the right edge is left untouched.
    """

    #: Emitted with the chosen colormap name when the user picks one from the menu.
    sigColorMapChangeRequested = Signal(str)
    #: Emitted with ``(vmin, vmax)`` when the user sets explicit color levels.
    sigColorLevelsChangeRequested = Signal(tuple)
    #: Emitted when the user requests autoscaling of the color levels.
    sigAutoLevelsRequested = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bec_menu: QMenu | None = None
        self._colormap_menu: ColorMapMenu | None = None
        self._cleaned_up_triggered = False
        self._install_bec_context_menu()

    ################################################################################
    # Context menu

    def _install_bec_context_menu(self) -> None:
        """
        Build the BEC menu and route the histogram view right-clicks to it.
        """
        menu = QMenu()

        menu.addSection("Colormap")
        self._colormap_menu = _make_bec_colormap_menu(self._on_colormap_triggered)
        menu.addMenu(self._colormap_menu)

        menu.addSection("Image scaling (levels)")
        set_levels = menu.addAction("Set levels…")
        set_levels.setToolTip("Set the data range mapped to the colormap (image scaling).")
        set_levels.triggered.connect(self._open_levels_dialog)
        auto_levels = menu.addAction("Autoscale levels")
        auto_levels.triggered.connect(self.sigAutoLevelsRequested)

        menu.addSection("Histogram display range")
        set_hist = menu.addAction("Set histogram range…")
        set_hist.setToolTip("Set the visible range of the histogram plot.")
        set_hist.triggered.connect(self._open_histogram_range_dialog)
        reset_hist = menu.addAction("Reset histogram range")
        reset_hist.triggered.connect(self.autoHistogramRange)

        self._bec_menu = menu

        # Route right-clicks on the histogram ViewBox to the BEC menu only. The
        # original ViewBoxMenu (self.vb.menu) is left in place but never shown, so
        # internal pyqtgraph calls such as updateViewLists() keep working.
        vb = self.vb
        vb.getMenu = self._vb_get_menu
        vb.getContextMenus = self._vb_get_context_menus
        vb.raiseContextMenu = self._vb_raise_context_menu

    def _vb_get_menu(self, ev):
        """
        Return the BEC menu instead of the ViewBox's default menu.

        Args:
            ev: The mouse event that requested the menu (unused).

        Returns:
            QMenu | None: The BEC context menu.
        """
        return self._bec_menu

    def _vb_get_context_menus(self, event):
        """
        Return the BEC menu actions for aggregation into child-item menus.

        Args:
            event: The mouse event that requested the menu (unused).

        Returns:
            list: The actions of the BEC context menu, or an empty list.
        """
        return self._bec_menu.actions() if self._bec_menu is not None else []

    def _vb_raise_context_menu(self, ev):
        """
        Pop up the BEC menu at the event position.

        Args:
            ev: The mouse event that triggered the context menu.
        """
        if self._bec_menu is not None:
            self._bec_menu.popup(ev.screenPos().toPoint())

    def _on_colormap_triggered(self, cmap) -> None:
        """
        Forward a colormap chosen in the submenu as a name on the BEC signal.

        Args:
            cmap (pyqtgraph.ColorMap): The colormap selected in the submenu.
        """
        name = getattr(cmap, "name", None)
        if name:
            self.sigColorMapChangeRequested.emit(name)

    ################################################################################
    # Actions

    def _open_levels_dialog(self) -> None:
        """
        Open the dialog to set the image color levels (image scaling).
        """
        vmin, vmax = (float(x) for x in self.getLevels())
        new_range = RangeDialog.get_new_range(
            _graphics_item_dialog_parent(self),
            title="Set color levels",
            label="Data values mapped to the colormap (image scaling).",
            vmin=vmin,
            vmax=vmax,
        )
        if new_range is not None:
            self.sigColorLevelsChangeRequested.emit(new_range)

    def _open_histogram_range_dialog(self) -> None:
        """
        Open the dialog to set the histogram's display range.
        """
        vmin, vmax = (float(x) for x in self.getHistogramRange())
        new_range = RangeDialog.get_new_range(
            _graphics_item_dialog_parent(self),
            title="Set histogram range",
            label="Visible range of the histogram plot.",
            vmin=vmin,
            vmax=vmax,
        )
        if new_range is not None:
            self.setHistogramRange(*new_range)

    ################################################################################
    # Cleanup

    def cleanup(self) -> None:
        """
        Tear down the BEC menu and the inherited pyqtgraph menus/dialogs.

        ``HistogramLUTItem`` owns several parentless top-level widgets (the ViewBox
        menu, the gradient ColorMapMenu and its QColorDialog). They must be closed
        explicitly, otherwise they linger as leaked top-level widgets.
        """
        # One-shot: the teardown below cannot be re-run — the inherited menus are deleted
        # without being reset to None, so a second pass would close a dead C++ object.
        if self._cleaned_up_triggered:
            return
        self._cleaned_up_triggered = True

        # Restore the patched ViewBox context-menu methods.
        vb_dict = self.vb.__dict__
        for name in ("getMenu", "getContextMenus", "raiseContextMenu"):
            vb_dict.pop(name, None)

        # Tear down the BEC context menu and its colormap submenu.
        if self._colormap_menu is not None:
            self._colormap_menu.close()
            self._colormap_menu.deleteLater()
            self._colormap_menu = None
        if self._bec_menu is not None:
            self._bec_menu.close()
            self._bec_menu.deleteLater()
            self._bec_menu = None

        # Tear down the inherited pyqtgraph menus and dialogs.
        self.vb.menu.close()
        self.vb.menu.deleteLater()
        self.gradient.menu.close()
        self.gradient.menu.deleteLater()
        self.gradient.colorDialog.close()
        self.gradient.colorDialog.deleteLater()


class BECColorBarItem(pg.ColorBarItem):
    """
    :class:`~pyqtgraph.ColorBarItem` (the "simple" colorbar) with the BEC context menu.

    pyqtgraph's built-in right-click menu on ColorBarItem only offers colormap
    selection and applies it directly to the item, bypassing the owning widget's
    colormap handling (config + multi-layer sync). This subclass replaces it with
    the same focused menu as :class:`BECHistogramLUTItem` (minus the
    histogram-specific entries) and forwards every request through signals so the
    owning image widget stays the single source of truth.
    """

    #: Emitted with the chosen colormap name when the user picks one from the menu.
    sigColorMapChangeRequested = Signal(str)
    #: Emitted with ``(vmin, vmax)`` when the user sets explicit color levels.
    sigColorLevelsChangeRequested = Signal(tuple)
    #: Emitted when the user requests autoscaling of the color levels.
    sigAutoLevelsRequested = Signal()

    def __init__(self, *args, **kwargs):
        # Disable pyqtgraph's own colormap menu; the BEC menu replaces it.
        kwargs.setdefault("colorMapMenu", False)
        super().__init__(*args, **kwargs)
        self._bec_menu: QMenu | None = None
        self._colormap_menu: ColorMapMenu | None = None
        self._cleaned_up_triggered = False
        self._install_bec_context_menu()

    ################################################################################
    # Context menu

    def _install_bec_context_menu(self) -> None:
        """
        Build the BEC menu shown on right-clicks anywhere on the colorbar.
        """
        menu = QMenu()

        menu.addSection("Colormap")
        self._colormap_menu = _make_bec_colormap_menu(self._on_colormap_triggered)
        menu.addMenu(self._colormap_menu)

        menu.addSection("Image scaling (levels)")
        set_levels = menu.addAction("Set levels…")
        set_levels.setToolTip("Set the data range mapped to the colormap (image scaling).")
        set_levels.triggered.connect(self._open_levels_dialog)
        auto_levels = menu.addAction("Autoscale levels")
        auto_levels.triggered.connect(self.sigAutoLevelsRequested)

        self._bec_menu = menu

    def mouseClickEvent(self, ev):
        """
        Show the BEC menu on right-click; defer to pyqtgraph otherwise.

        Args:
            ev: The mouse click event.
        """
        if ev.button() == Qt.MouseButton.RightButton and self._bec_menu is not None:
            ev.accept()
            self._bec_menu.popup(ev.screenPos().toPoint())
            return
        super().mouseClickEvent(ev)

    def _on_colormap_triggered(self, cmap) -> None:
        """
        Forward a colormap chosen in the submenu as a name on the BEC signal.

        Args:
            cmap (pyqtgraph.ColorMap): The colormap selected in the submenu.
        """
        name = getattr(cmap, "name", None)
        if name:
            self.sigColorMapChangeRequested.emit(name)

    def _open_levels_dialog(self) -> None:
        """
        Open the dialog to set the image color levels (image scaling).
        """
        vmin, vmax = (float(x) for x in self.levels())
        new_range = RangeDialog.get_new_range(
            _graphics_item_dialog_parent(self),
            title="Set color levels",
            label="Data values mapped to the colormap (image scaling).",
            vmin=vmin,
            vmax=vmax,
        )
        if new_range is not None:
            self.sigColorLevelsChangeRequested.emit(new_range)

    ################################################################################
    # Cleanup

    def cleanup(self) -> None:
        """
        Tear down the BEC menu and the menus inherited from :class:`~pyqtgraph.PlotItem`.

        ``ColorBarItem`` is a PlotItem, so it owns a parentless ViewBox menu and a
        plot-options (``ctrlMenu``) menu even though both are disabled; close them
        explicitly so they do not linger as leaked top-level widgets.
        """
        # One-shot: the teardown below cannot be re-run — the inherited menus are deleted
        # without being reset to None, so a second pass would close a dead C++ object.
        if self._cleaned_up_triggered:
            return
        self._cleaned_up_triggered = True

        if self._colormap_menu is not None:
            self._colormap_menu.close()
            self._colormap_menu.deleteLater()
            self._colormap_menu = None
        if self._bec_menu is not None:
            self._bec_menu.close()
            self._bec_menu.deleteLater()
            self._bec_menu = None

        # ColorBarItem disables its ViewBox menu, which leaves vb.menu as None.
        if self.vb.menu is not None:
            self.vb.menu.close()
            self.vb.menu.deleteLater()
        if self.ctrlMenu is not None:
            self.ctrlMenu.close()
            self.ctrlMenu.deleteLater()
