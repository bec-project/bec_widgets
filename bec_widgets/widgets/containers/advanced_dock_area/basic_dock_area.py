from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Sequence, cast

from bec_lib import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import QByteArray, QSettings, Qt, QTimer
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QDialog, QVBoxLayout, QWidget
from shiboken6 import isValid

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets import BECWidget, SafeSlot
from bec_widgets.cli.rpc.rpc_widget_handler import widget_handler
from bec_widgets.utils.property_editor import PropertyEditor
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.widgets.containers.qt_ads import (
    CDockAreaWidget,
    CDockManager,
    CDockSplitter,
    CDockWidget,
)

logger = bec_logger.logger


class DockSettingsDialog(QDialog):
    """Generic settings editor shown from dock title bar actions."""

    def __init__(self, parent: QWidget, target: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Dock Settings")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.prop_editor = PropertyEditor(target, self, show_only_bec=True)
        layout.addWidget(self.prop_editor)


class DockAreaWidget(BECWidget, QWidget):
    """
    Lightweight dock area that exposes the core Qt ADS docking helpers without any
    of the toolbar or workspace management features that the advanced variant offers.
    """

    RPC = True
    PLUGIN = False
    USER_ACCESS = [
        "new",
        "dock_map",
        "dock_list",
        "widget_map",
        "widget_list",
        "attach_all",
        "delete_all",
        "delete",
        "set_layout_ratios",
        "describe_layout",
        "print_layout_structure",
        "set_central_dock",
    ]

    @dataclass
    class DockCreationSpec:
        widget: QWidget
        closable: bool = True
        floatable: bool = True
        movable: bool = True
        start_floating: bool = False
        floating_state: Mapping[str, Any] | None = None
        area: QtAds.DockWidgetArea = QtAds.DockWidgetArea.RightDockWidgetArea
        on_close: Callable[[CDockWidget, QWidget], None] | None = None
        tab_with: CDockWidget | None = None
        relative_to: CDockWidget | None = None
        title_visible: bool | None = None
        title_buttons: Mapping[QtAds.ads.TitleBarButton, bool] | None = None
        show_settings_action: bool | None = False
        dock_preferences: Mapping[str, Any] | None = None
        promote_central: bool = False
        dock_icon: QIcon | None = None
        apply_widget_icon: bool = True

    def __init__(
        self,
        parent: QWidget | None = None,
        default_add_direction: Literal["left", "right", "top", "bottom"] = "right",
        title: str = "Dock Area",
        variant: Literal["cards", "compact"] = "cards",
        **kwargs,
    ):
        super().__init__(parent=parent, **kwargs)

        # Set variant property for styling

        if title:
            self.setWindowTitle(title)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.dock_manager = CDockManager(self)
        self.dock_manager.setStyleSheet("")
        self.dock_manager.setProperty("variant", variant)

        self._locked = False
        self._default_add_direction = (
            default_add_direction
            if default_add_direction in ("left", "right", "top", "bottom")
            else "right"
        )

        self._root_layout.addWidget(self.dock_manager, 1)

    ################################################################################
    # Dock Utility Helpers
    ################################################################################

    def _area_from_where(self, where: str | None) -> QtAds.DockWidgetArea:
        """Translate a direction string into a Qt ADS dock widget area."""
        direction = (where or self._default_add_direction or "right").lower()
        mapping = {
            "left": QtAds.DockWidgetArea.LeftDockWidgetArea,
            "right": QtAds.DockWidgetArea.RightDockWidgetArea,
            "top": QtAds.DockWidgetArea.TopDockWidgetArea,
            "bottom": QtAds.DockWidgetArea.BottomDockWidgetArea,
        }
        return mapping.get(direction, QtAds.DockWidgetArea.RightDockWidgetArea)

    def _customize_dock(self, dock: CDockWidget, widget: QWidget) -> None:
        """Hook for subclasses to customise the dock before it is shown."""
        prefs: Mapping[str, Any] = getattr(dock, "_dock_preferences", {}) or {}
        show_settings = prefs.get("show_settings_action")
        if show_settings:
            self._install_dock_settings_action(dock, widget)

    def _install_dock_settings_action(self, dock: CDockWidget, widget: QWidget) -> None:
        """Attach a dock-level settings action if available."""
        if getattr(dock, "setting_action", None) is not None:
            return

        action = MaterialIconAction(
            icon_name="settings", tooltip="Dock settings", filled=True, parent=self
        ).action
        action.setObjectName("dockSettingsAction")
        action.setToolTip("Dock settings")
        action.triggered.connect(lambda: self._open_dock_settings_dialog(dock, widget))

        existing = list(dock.titleBarActions())
        existing.append(action)
        dock.setTitleBarActions(existing)
        dock.setting_action = action

    def _open_dock_settings_dialog(self, dock: CDockWidget, widget: QWidget) -> None:
        """Launch the property editor dialog for the dock's widget."""
        dlg = DockSettingsDialog(self, widget)
        dlg.resize(600, 600)
        dlg.exec()

    ################################################################################
    # Dock Lifecycle
    ################################################################################

    def _default_close_handler(self, dock: CDockWidget, widget: QWidget) -> None:
        """Default dock close routine used when no custom handler is provided."""
        widget.close()
        dock.closeDockWidget()
        dock.deleteDockWidget()

    def close_dock(self, dock: CDockWidget, widget: QWidget | None = None) -> None:
        """
        Helper for custom close handlers to invoke the default close behaviour.

        Args:
            dock: Dock widget to close.
            widget: Optional widget contained in the dock; resolved automatically when not given.
        """
        target_widget = widget or dock.widget()
        if target_widget is None:
            return
        self._default_close_handler(dock, target_widget)

    def _wrap_close_candidate(
        self, candidate: Callable, widget: QWidget
    ) -> Callable[[CDockWidget], None]:
        """
        Wrap a user-provided close handler to adapt its signature.

        Args:
            candidate(Callable): User-provided close handler.
            widget(QWidget): Widget contained in the dock.

        Returns:
            Callable[[CDockWidget], None]: Wrapped close handler.
        """
        try:
            sig = inspect.signature(candidate)
            accepts_varargs = any(
                p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
            )
            positional_params = [
                p
                for p in sig.parameters.values()
                if p.kind
                in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
        except (ValueError, TypeError):
            accepts_varargs = True
            positional_params = []

        positional_count = len(positional_params)

        def invoke(dock: CDockWidget) -> None:
            try:
                if accepts_varargs or positional_count >= 2:
                    candidate(dock, widget)
                elif positional_count == 1:
                    candidate(dock)
                else:
                    candidate()
            except TypeError:
                # Best effort fallback in case the signature inspection was misleading.
                candidate(dock, widget)

        return invoke

    def _resolve_close_handler(
        self, widget: QWidget, on_close: Callable[[CDockWidget, QWidget], None] | None = None
    ) -> Callable[[CDockWidget], None]:
        """
        Determine which close handler to use for a dock.
        Priority:
          1. Explicit `on_close` callable passed to `new`.
          2. Widget attribute `handle_dock_close` or `on_dock_close` if callable.
          3. Default close handler.

        Args:
            widget(QWidget): The widget contained in the dock.
            on_close(Callable[[CDockWidget, QWidget], None] | None): Explicit close handler.

        Returns:
            Callable[[CDockWidget], None]: Resolved close handler.
        """

        candidate = on_close
        if candidate is None:
            candidate = getattr(widget, "handle_dock_close", None)
        if candidate is None:
            candidate = getattr(widget, "on_dock_close", None)

        if callable(candidate):
            return self._wrap_close_candidate(candidate, widget)

        return lambda dock: self._default_close_handler(dock, widget)

    def _make_dock(
        self,
        widget: QWidget,
        *,
        closable: bool,
        floatable: bool,
        movable: bool = True,
        area: QtAds.DockWidgetArea = QtAds.DockWidgetArea.RightDockWidgetArea,
        start_floating: bool = False,
        floating_state: Mapping[str, object] | None = None,
        on_close: Callable[[CDockWidget, QWidget], None] | None = None,
        tab_with: CDockWidget | None = None,
        relative_to: CDockWidget | None = None,
        dock_preferences: Mapping[str, Any] | None = None,
        promote_central: bool = False,
        dock_icon: QIcon | None = None,
        apply_widget_icon: bool = True,
    ) -> CDockWidget:
        """
        Create and add a new dock widget to the area.

        Args:
            widget(QWidget): The widget to dock.
            closable(bool): Whether the dock can be closed.
            floatable(bool): Whether the dock can be floated.
            movable(bool): Whether the dock can be moved.
            area(QtAds.DockWidgetArea): Target dock area.
            start_floating(bool): Whether the dock should start floating.
            floating_state(Mapping | None): Optional geometry metadata to apply when floating.
            on_close(Callable[[CDockWidget, QWidget], None] | None): Custom close handler.
            tab_with(CDockWidget | None): Optional dock to tab with.
            relative_to(CDockWidget | None): Optional dock to position relative to.
            dock_preferences(Mapping[str, Any] | None): Appearance preferences to apply.
            promote_central(bool): Whether to promote the dock to central widget.
            dock_icon(QIcon | None): Explicit icon to use for the dock.
            apply_widget_icon(bool): Whether to apply the widget's ICON_NAME as dock icon.

        Returns:
            CDockWidget: Created dock widget.
        """
        if not widget.objectName():
            widget.setObjectName(widget.__class__.__name__)

        if tab_with is not None and relative_to is not None:
            raise ValueError("Specify either 'tab_with' or 'relative_to', not both.")

        dock = CDockWidget(self.dock_manager, widget.objectName(), self)
        dock.setWidget(widget)
        dock._dock_preferences = dict(dock_preferences or {})
        dock.setFeature(CDockWidget.DockWidgetFeature.DockWidgetDeleteOnClose, True)
        dock.setFeature(CDockWidget.DockWidgetFeature.CustomCloseHandling, True)
        dock.setFeature(CDockWidget.DockWidgetFeature.DockWidgetClosable, closable)
        dock.setFeature(CDockWidget.DockWidgetFeature.DockWidgetFloatable, floatable)
        dock.setFeature(CDockWidget.DockWidgetFeature.DockWidgetMovable, movable)

        self._customize_dock(dock, widget)
        resolved_icon = self._resolve_dock_icon(widget, dock_icon, apply_widget_icon)

        close_handler = self._resolve_close_handler(widget, on_close)

        def on_widget_destroyed():
            if not isValid(dock):
                return
            dock.closeDockWidget()
            dock.deleteDockWidget()

        dock.closeRequested.connect(lambda: close_handler(dock))
        if hasattr(widget, "widget_removed"):
            widget.widget_removed.connect(on_widget_destroyed)

        dock.setMinimumSizeHintMode(CDockWidget.eMinimumSizeHintMode.MinimumSizeHintFromDockWidget)
        dock_area_widget = None
        if tab_with is not None:
            if not isValid(tab_with):
                raise ValueError("Tab target dock widget is not valid anymore.")
            dock_area_widget = tab_with.dockAreaWidget()

        if dock_area_widget is not None:
            self.dock_manager.addDockWidgetTabToArea(dock, dock_area_widget)
        else:
            target_area_widget = None
            if relative_to is not None:
                if not isValid(relative_to):
                    raise ValueError("Relative target dock widget is not valid anymore.")
                target_area_widget = relative_to.dockAreaWidget()
            self.dock_manager.addDockWidget(area, dock, target_area_widget)

        if start_floating and tab_with is None and not promote_central:
            dock.setFloating()
            if floating_state:
                self._apply_floating_state_to_dock(dock, floating_state)
        if resolved_icon is not None:
            dock.setIcon(resolved_icon)
        return dock

    def _delete_dock(self, dock: CDockWidget) -> None:
        widget = dock.widget()
        if widget and isValid(widget):
            widget.close()
            widget.deleteLater()
        if isValid(dock):
            dock.closeDockWidget()
            dock.deleteDockWidget()

    def _resolve_dock_reference(
        self, ref: CDockWidget | QWidget | str | None, *, allow_none: bool = True
    ) -> CDockWidget | None:
        """
        Resolve a dock reference from various input types.

        Args:
            ref(CDockWidget | QWidget | str | None): Dock reference.
            allow_none(bool): Whether to allow None as a valid return value.

        Returns:
            CDockWidget | None: Resolved dock widget or None.
        """
        if ref is None:
            if allow_none:
                return None
            raise ValueError("Dock reference cannot be None.")
        if isinstance(ref, CDockWidget):
            if not isValid(ref):
                raise ValueError("Dock widget reference is not valid anymore.")
            return ref
        if isinstance(ref, QWidget):
            for dock in self.dock_list():
                if dock.widget() is ref:
                    return dock
            raise ValueError("Widget reference is not associated with any dock in this area.")
        if isinstance(ref, str):
            dock_map = self.dock_map()
            dock = dock_map.get(ref)
            if dock is None:
                raise ValueError(f"No dock found with objectName '{ref}'.")
            return dock
        raise TypeError(
            "Dock reference must be a CDockWidget, QWidget, object name string, or None."
        )

    ################################################################################
    # Splitter Handling
    ################################################################################

    def _resolve_dock_icon(
        self, widget: QWidget, dock_icon: QIcon | None, apply_widget_icon: bool
    ) -> QIcon | None:
        """
        Choose an icon for the dock: prefer an explicitly provided one, otherwise
        fall back to the widget's `ICON_NAME` (material icons) when available.

        Args:
            widget(QWidget): The widget to dock.
            dock_icon(QIcon | None): Explicit icon to use for the dock.

        Returns:
            QIcon | None: Resolved dock icon, or None if not available.
        """

        if dock_icon is not None:
            return dock_icon
        if not apply_widget_icon:
            return None
        icon_name = getattr(widget, "ICON_NAME", None)
        if not icon_name:
            return None
        try:
            return material_icon(icon_name, size=(24, 24), convert_to_pixmap=False)
        except Exception:
            return None

    def _build_creation_spec(
        self,
        widget: QWidget,
        *,
        closable: bool,
        floatable: bool,
        movable: bool,
        start_floating: bool,
        floating_state: Mapping[str, object] | None,
        where: Literal["left", "right", "top", "bottom"] | None,
        on_close: Callable[[CDockWidget, QWidget], None] | None,
        tab_with: CDockWidget | QWidget | str | None,
        relative_to: CDockWidget | QWidget | str | None,
        show_title_bar: bool | None,
        title_buttons: Mapping[str, bool] | Sequence[str] | str | None,
        show_settings_action: bool | None,
        promote_central: bool,
        dock_icon: QIcon | None,
        apply_widget_icon: bool,
    ) -> DockCreationSpec:
        """
        Normalize and validate dock creation parameters into a spec object.

        Args:
            widget(QWidget): The widget to dock.
            closable(bool): Whether the dock can be closed.
            floatable(bool): Whether the dock can be floated.
            movable(bool): Whether the dock can be moved.
            start_floating(bool): Whether the dock should start floating.
            floating_state(Mapping | None): Optional floating geometry metadata.
            where(Literal["left", "right", "top", "bottom"] | None): Target dock area.
            on_close(Callable[[CDockWidget, QWidget], None] | None): Custom close handler.
            tab_with(CDockWidget | QWidget | str | None): Optional dock to tab with.
            relative_to(CDockWidget | QWidget | str | None): Optional dock to position relative to.
            show_title_bar(bool | None): Whether to show the dock title bar.
            title_buttons(Mapping[str, bool] | Sequence[str] | str | None): Title bar buttons to show/hide.
            show_settings_action(bool | None): Whether to show the dock settings action.
            promote_central(bool): Whether to promote the dock to central widget.
            dock_icon(QIcon | None): Explicit icon to use for the dock.
            apply_widget_icon(bool): Whether to apply the widget's ICON_NAME as dock icon.

        Returns:
            DockCreationSpec: Normalized dock creation specification.

        """
        normalized_buttons = self._normalize_title_buttons(title_buttons)
        resolved_tab = self._resolve_dock_reference(tab_with)
        resolved_relative = self._resolve_dock_reference(relative_to)

        if resolved_tab is not None and resolved_relative is not None:
            raise ValueError("Specify either 'tab_with' or 'relative_to', not both.")

        target_area = self._area_from_where(where)
        if resolved_relative is not None and where is None:
            inferred = self.dock_manager.dockWidgetArea(resolved_relative)
            if inferred in (
                QtAds.DockWidgetArea.InvalidDockWidgetArea,
                QtAds.DockWidgetArea.NoDockWidgetArea,
            ):
                inferred = self._area_from_where(None)
            target_area = inferred

        dock_preferences = {
            "show_title_bar": show_title_bar,
            "title_buttons": normalized_buttons if normalized_buttons else None,
            "show_settings_action": show_settings_action,
        }
        dock_preferences = {k: v for k, v in dock_preferences.items() if v is not None}

        return self.DockCreationSpec(
            widget=widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            start_floating=start_floating,
            floating_state=floating_state,
            area=target_area,
            on_close=on_close,
            tab_with=resolved_tab,
            relative_to=resolved_relative,
            title_visible=show_title_bar,
            title_buttons=normalized_buttons if normalized_buttons else None,
            show_settings_action=show_settings_action,
            dock_preferences=dock_preferences or None,
            promote_central=promote_central,
            dock_icon=dock_icon,
            apply_widget_icon=apply_widget_icon,
        )

    def _create_dock_from_spec(self, spec: DockCreationSpec) -> CDockWidget:
        """
        Create a dock from a normalized spec and apply preferences.

        Args:
            spec(DockCreationSpec): Dock creation specification.

        Returns:
            CDockWidget: Created dock widget.
        """
        dock = self._make_dock(
            spec.widget,
            closable=spec.closable,
            floatable=spec.floatable,
            movable=spec.movable,
            floating_state=spec.floating_state,
            area=spec.area,
            start_floating=spec.start_floating,
            on_close=spec.on_close,
            tab_with=spec.tab_with,
            relative_to=spec.relative_to,
            dock_preferences=spec.dock_preferences,
            promote_central=spec.promote_central,
            dock_icon=spec.dock_icon,
            apply_widget_icon=spec.apply_widget_icon,
        )
        self.dock_manager.setFocus()
        self._apply_dock_preferences(dock)
        if spec.promote_central:
            self.set_central_dock(dock)
        return dock

    def _coerce_weights(
        self,
        weights: Sequence[float] | Mapping[int | str, float] | None,
        count: int,
        orientation: Qt.Orientation,
    ) -> list[float] | None:
        """
        Normalize weight specs into a list matching splitter child count.

        Args:
            weights(Sequence[float] | Mapping[int | str, float] | None): Weight specification.
            count(int): Number of splitter children.
            orientation(Qt.Orientation): Splitter orientation.

        Returns:
            list[float] | None: Normalized weight list, or None if invalid.
        """
        if weights is None or count <= 0:
            return None

        result: list[float]
        if isinstance(weights, (list, tuple)):
            result = [float(v) for v in weights[:count]]
        elif isinstance(weights, Mapping):
            default = float(weights.get("default", 1.0))
            result = [default] * count

            alias: dict[str, int] = {}
            if count >= 1:
                alias["first"] = 0
                alias["start"] = 0
            if count >= 2:
                alias["last"] = count - 1
                alias["end"] = count - 1
            if orientation == Qt.Orientation.Horizontal:
                alias["left"] = 0
                alias["right"] = count - 1
                if count >= 3:
                    alias["center"] = count // 2
                    alias["middle"] = count // 2
            else:
                alias["top"] = 0
                alias["bottom"] = count - 1

            for key, value in weights.items():
                if key == "default":
                    continue
                idx: int | None = None
                if isinstance(key, int):
                    idx = key
                elif isinstance(key, str):
                    lowered = key.lower()
                    if lowered in alias:
                        idx = alias[lowered]
                    elif lowered.startswith("col"):
                        try:
                            idx = int(lowered[3:])
                        except ValueError:
                            idx = None
                    elif lowered.startswith("row"):
                        try:
                            idx = int(lowered[3:])
                        except ValueError:
                            idx = None
                if idx is not None and 0 <= idx < count:
                    result[idx] = float(value)
        else:
            return None

        if len(result) < count:
            result += [1.0] * (count - len(result))
        result = result[:count]
        if all(v <= 0 for v in result):
            result = [1.0] * count
        return result

    def _schedule_splitter_weights(
        self,
        splitter: QtAds.CDockSplitter,
        weights: Sequence[float] | Mapping[int | str, float] | None,
    ) -> None:
        """
        Apply weight ratios to a splitter once geometry is available.

        Args:
            splitter(QtAds.CDockSplitter): Target splitter.
            weights(Sequence[float] | Mapping[int | str, float] | None): Weight specification.
        """
        if splitter is None or weights is None:
            return

        ratios = self._coerce_weights(weights, splitter.count(), splitter.orientation())
        if not ratios:
            return

        def apply():
            count = splitter.count()
            if count != len(ratios):
                return

            orientation = splitter.orientation()
            total_px = (
                splitter.width() if orientation == Qt.Orientation.Horizontal else splitter.height()
            )
            if total_px <= count:
                QTimer.singleShot(0, apply)
                return

            total = sum(ratios)
            if total <= 0:
                return
            sizes = [max(1, int(round(total_px * (r / total)))) for r in ratios]
            diff = total_px - sum(sizes)
            if diff:
                idx = max(range(count), key=lambda i: ratios[i])
                sizes[idx] = max(1, sizes[idx] + diff)
            splitter.setSizes(sizes)
            for i, weight in enumerate(ratios):
                splitter.setStretchFactor(i, max(1, int(round(weight * 100))))

        QTimer.singleShot(0, apply)

    def _normalize_override_keys(
        self,
        overrides: Mapping[int | str | Sequence[int], Sequence[float] | Mapping[int | str, float]],
    ) -> dict[tuple[int, ...], Sequence[float] | Mapping[int | str, float]]:
        """
        Normalize various key types into tuple paths.

        Args:
            overrides(Mapping[int | str | Sequence[int], Sequence[float] | Mapping[int | str, float]]):
                Original overrides mapping.

        Returns:
            dict[tuple[int, ...], Sequence[float] | Mapping[int | str, float]]:
                Normalized overrides mapping.
        """
        normalized: dict[tuple[int, ...], Sequence[float] | Mapping[int | str, float]] = {}
        for key, value in overrides.items():
            path: tuple[int, ...] | None = None
            if isinstance(key, int):
                path = (key,)
            elif isinstance(key, (list, tuple)):
                try:
                    path = tuple(int(k) for k in key)
                except ValueError:
                    continue
            elif isinstance(key, str):
                cleaned = key.replace(" ", "").replace(".", "/")
                if cleaned in ("", "/"):
                    path = ()
                else:
                    parts = [p for p in cleaned.split("/") if p]
                    try:
                        path = tuple(int(p) for p in parts)
                    except ValueError:
                        continue
            if path is not None:
                normalized[path] = value
        return normalized

    def _apply_splitter_tree(
        self,
        splitter: QtAds.CDockSplitter,
        path: tuple[int, ...],
        horizontal: Sequence[float] | Mapping[int | str, float] | None,
        vertical: Sequence[float] | Mapping[int | str, float] | None,
        overrides: dict[tuple[int, ...], Sequence[float] | Mapping[int | str, float]],
    ) -> None:
        """Traverse splitter hierarchy and apply ratios."""
        orientation = splitter.orientation()
        base_weights = horizontal if orientation == Qt.Orientation.Horizontal else vertical

        override = None
        if overrides:
            if path in overrides:
                override = overrides[path]
            elif len(path) >= 1:
                key = (path[-1],)
                if key in overrides:
                    override = overrides[key]

        self._schedule_splitter_weights(splitter, override or base_weights)

        for idx in range(splitter.count()):
            child = splitter.widget(idx)
            if isinstance(child, QtAds.CDockSplitter):
                self._apply_splitter_tree(child, path + (idx,), horizontal, vertical, overrides)

    ################################################################################
    # Layout Inspection
    ################################################################################

    def _collect_splitter_info(
        self,
        splitter: CDockSplitter,
        path: tuple[int, ...],
        results: list[dict[str, Any]],
        container_index: int,
    ) -> None:
        orientation = (
            "horizontal" if splitter.orientation() == Qt.Orientation.Horizontal else "vertical"
        )
        entry: dict[str, Any] = {
            "container": container_index,
            "path": path,
            "orientation": orientation,
            "children": [],
        }
        results.append(entry)

        for idx in range(splitter.count()):
            child = splitter.widget(idx)
            if isinstance(child, CDockSplitter):
                entry["children"].append({"index": idx, "type": "splitter"})
                self._collect_splitter_info(child, path + (idx,), results, container_index)
            elif isinstance(child, CDockAreaWidget):
                docks = [dock.objectName() for dock in child.dockWidgets()]
                entry["children"].append({"index": idx, "type": "dock_area", "docks": docks})
            elif isinstance(child, CDockWidget):
                entry["children"].append({"index": idx, "type": "dock", "name": child.objectName()})
            else:
                entry["children"].append({"index": idx, "type": child.__class__.__name__})

    def describe_layout(self) -> list[dict[str, Any]]:
        """
        Return metadata describing splitter paths, orientations, and contained docks.

        Useful for determining the keys to use in `set_layout_ratios(splitter_overrides=...)`.
        """
        info: list[dict[str, Any]] = []
        for container_index, container in enumerate(self.dock_manager.dockContainers()):
            splitter = container.rootSplitter()
            if splitter is None:
                continue
            self._collect_splitter_info(splitter, (), info, container_index)
        return info

    def print_layout_structure(self) -> None:
        """Pretty-print the current splitter paths to stdout."""
        for entry in self.describe_layout():
            children_desc = []
            for child in entry["children"]:
                if child["type"] == "dock_area":
                    children_desc.append(
                        f"{child['index']}:dock_area[{', '.join(child['docks']) or '-'}]"
                    )
                elif child["type"] == "dock":
                    children_desc.append(f"{child['index']}:dock({child['name']})")
                else:
                    children_desc.append(f"{child['index']}:{child['type']}")
            summary = ", ".join(children_desc)
            print(
                f"container={entry['container']} path={entry['path']} "
                f"orientation={entry['orientation']} -> [{summary}]"
            )

    ################################################################################
    # State Persistence
    ################################################################################

    @staticmethod
    def _coerce_byte_array(value: Any) -> QByteArray | None:
        """Best-effort conversion of arbitrary values into a QByteArray."""
        if isinstance(value, QByteArray):
            return QByteArray(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return QByteArray(bytes(value))
        return None

    @staticmethod
    def _settings_keys(overrides: Mapping[str, str | None] | None = None) -> dict[str, str | None]:
        """
        Merge caller overrides with sensible defaults.

        Only `geom`, `state`, and `ads_state` are recognised. Missing entries default to:
          geom -> "dock_area/geometry"
          state -> None (skip writing legacy main window state)
          ads_state -> "dock_area/docking_state"
        """
        defaults: dict[str, str | None] = {
            "geom": "dock_area/geometry",
            "state": None,
            "ads_state": "dock_area/docking_state",
        }
        if overrides:
            for key, value in overrides.items():
                if key in defaults:
                    defaults[key] = value
        return defaults

    def _select_screen_for_entry(
        self, entry: Mapping[str, object], container: QtAds.CFloatingDockContainer | None
    ):
        """
        Pick the best target screen for a saved floating container.

        Args:
            entry(Mapping[str, object]): Floating window entry.
            container(QtAds.CFloatingDockContainer | None): Optional container instance.
        """
        screens = QApplication.screens() or []
        try:
            name = entry.get("screen_name") or ""
        except Exception as exc:
            logger.warning(f"Invalid screen_name in floating window entry: {exc}")
            name = ""
        if name:
            for screen in screens:
                try:
                    if screen.name() == name:
                        return screen
                except Exception as exc:
                    logger.warning(f"Error checking screen name '{name}': {exc}")
                    continue
        if container is not None and hasattr(container, "screen"):
            screen = container.screen()
            if screen is not None:
                return screen
        return screens[0] if screens else None

    def _apply_saved_floating_geometry(
        self, container: QtAds.CFloatingDockContainer, entry: Mapping[str, object]
    ) -> None:
        """
        Resize/move a floating container using saved geometry information.

        Args:
            container(QtAds.CFloatingDockContainer): Target floating container.
            entry(Mapping[str, object]): Floating window entry.
        """
        abs_geom = entry.get("absolute") if isinstance(entry, Mapping) else None
        if isinstance(abs_geom, Mapping):
            try:
                x = int(abs_geom.get("x"))
                y = int(abs_geom.get("y"))
                width = int(abs_geom.get("w"))
                height = int(abs_geom.get("h"))
            except Exception as exc:
                logger.warning(f"Invalid absolute geometry in floating window entry: {exc}")
            else:
                if width > 0 and height > 0:
                    container.setGeometry(x, y, max(width, 50), max(height, 50))
                    return

        rel = entry.get("relative") if isinstance(entry, Mapping) else None
        if not isinstance(rel, Mapping):
            return
        try:
            x_ratio = float(rel.get("x"))
            y_ratio = float(rel.get("y"))
            w_ratio = float(rel.get("w"))
            h_ratio = float(rel.get("h"))
        except Exception as exc:
            logger.warning(f"Invalid relative geometry in floating window entry: {exc}")
            return

        screen = self._select_screen_for_entry(entry, container)
        if screen is None:
            return
        geom = screen.availableGeometry()
        screen_w = geom.width()
        screen_h = geom.height()
        if screen_w <= 0 or screen_h <= 0:
            return

        min_w = 120
        min_h = 80
        width = max(min_w, int(round(screen_w * max(w_ratio, 0.05))))
        height = max(min_h, int(round(screen_h * max(h_ratio, 0.05))))
        width = min(width, screen_w)
        height = min(height, screen_h)

        x = geom.left() + int(round(screen_w * x_ratio))
        y = geom.top() + int(round(screen_h * y_ratio))
        x = max(geom.left(), min(x, geom.left() + screen_w - width))
        y = max(geom.top(), min(y, geom.top() + screen_h - height))

        container.setGeometry(x, y, width, height)

    def _apply_floating_state_to_dock(
        self, dock: CDockWidget, state: Mapping[str, object], *, attempt: int = 0
    ) -> None:
        """
        Apply saved floating geometry to a dock once its container exists.

        Args:
            dock(CDockWidget): Target dock widget.
            state(Mapping[str, object]): Saved floating state.
            attempt(int): Current attempt count for retries.
        """
        if state is None:
            return

        def schedule(next_attempt: int):
            QTimer.singleShot(
                50, lambda: self._apply_floating_state_to_dock(dock, state, attempt=next_attempt)
            )

        container = dock.floatingDockContainer()
        if container is None:
            if attempt < 10:
                schedule(attempt + 1)
            return
        entry = {
            "relative": state.get("relative") if isinstance(state, Mapping) else None,
            "absolute": state.get("absolute") if isinstance(state, Mapping) else None,
            "screen_name": state.get("screen_name") if isinstance(state, Mapping) else None,
        }
        self._apply_saved_floating_geometry(container, entry)

    def save_to_settings(
        self,
        settings: QSettings,
        *,
        keys: Mapping[str, str | None] | None = None,
        include_perspectives: bool = True,
        perspective_name: str | None = None,
    ) -> None:
        """
        Persist the current dock layout into an existing `QSettings` instance.

        Args:
            settings(QSettings): Target QSettings store (must outlive this call).
            keys(Mapping[str, str | None] | None): Optional mapping overriding the keys used for geometry/state entries.
            include_perspectives(bool): When True, save Qt ADS perspectives alongside the layout.
            perspective_name(str | None): Optional explicit name for the saved perspective.
        """
        resolved = self._settings_keys(keys)

        geom_key = resolved.get("geom")
        if geom_key:
            settings.setValue(geom_key, self.saveGeometry())

        legacy_state_key = resolved.get("state")
        if legacy_state_key:
            settings.setValue(legacy_state_key, b"")

        ads_state_key = resolved.get("ads_state")
        if ads_state_key:
            settings.setValue(ads_state_key, self.dock_manager.saveState())

        if include_perspectives:
            name = perspective_name or self.windowTitle()
            if name:
                self.dock_manager.addPerspective(name)
            self.dock_manager.savePerspectives(settings)

    def save_to_file(
        self,
        path: str,
        *,
        format: QSettings.Format = QSettings.IniFormat,
        keys: Mapping[str, str | None] | None = None,
        include_perspectives: bool = True,
        perspective_name: str | None = None,
    ) -> None:
        """
        Convenience wrapper around `save_to_settings` that opens a temporary QSettings.

        Args:
            path(str): File path to save the settings to.
            format(QSettings.Format): File format to use.
            keys(Mapping[str, str | None] | None): Optional mapping overriding the keys used for geometry/state entries.
            include_perspectives(bool): When True, save Qt ADS perspectives alongside the layout.
            perspective_name(str | None): Optional explicit name for the saved perspective.
        """
        settings = QSettings(path, format)
        self.save_to_settings(
            settings,
            keys=keys,
            include_perspectives=include_perspectives,
            perspective_name=perspective_name,
        )
        settings.sync()

    def load_from_settings(
        self,
        settings: QSettings,
        *,
        keys: Mapping[str, str | None] | None = None,
        restore_perspectives: bool = True,
    ) -> None:
        """
        Restore the dock layout from a `QSettings` instance previously populated by `save_to_settings`.

        Args:
            settings(QSettings): Source QSettings store (must outlive this call).
            keys(Mapping[str, str | None] | None): Optional mapping overriding the keys used for geometry/state entries.
            restore_perspectives(bool): When True, restore Qt ADS perspectives alongside the layout.
        """
        resolved = self._settings_keys(keys)

        geom_key = resolved.get("geom")
        if geom_key:
            geom_value = settings.value(geom_key)
            geom_bytes = self._coerce_byte_array(geom_value)
            if geom_bytes is not None:
                self.restoreGeometry(geom_bytes)

        ads_state_key = resolved.get("ads_state")
        if ads_state_key:
            dock_state = settings.value(ads_state_key)
            dock_bytes = self._coerce_byte_array(dock_state)
            if dock_bytes is not None:
                self.dock_manager.restoreState(dock_bytes)

        if restore_perspectives:
            self.dock_manager.loadPerspectives(settings)

    def load_from_file(
        self,
        path: str,
        *,
        format: QSettings.Format = QSettings.IniFormat,
        keys: Mapping[str, str | None] | None = None,
        restore_perspectives: bool = True,
    ) -> None:
        """
        Convenience wrapper around `load_from_settings` that reads from a file path.
        """
        settings = QSettings(path, format)
        self.load_from_settings(settings, keys=keys, restore_perspectives=restore_perspectives)

    def set_layout_ratios(
        self,
        *,
        horizontal: Sequence[float] | Mapping[int | str, float] | None = None,
        vertical: Sequence[float] | Mapping[int | str, float] | None = None,
        splitter_overrides: (
            Mapping[int | str | Sequence[int], Sequence[float] | Mapping[int | str, float]] | None
        ) = None,
    ) -> None:
        """
        Adjust splitter ratios in the dock layout.

        Args:
            horizontal: Weights applied to every horizontal splitter encountered.
            vertical: Weights applied to every vertical splitter encountered.
            splitter_overrides: Optional overrides targeting specific splitters identified
                by their index path (e.g. ``{0: [1, 2], (1, 0): [3, 5]}``). Paths are zero-based
                indices following the splitter hierarchy, starting from the root splitter.

        Example:
            To build three columns with custom per-column ratios::

                area.set_layout_ratios(
                    horizontal=[1, 2, 1],             # column widths
                    splitter_overrides={
                        0: [1, 2],                    # column 0 (two rows)
                        1: [3, 2, 1],                 # column 1 (three rows)
                        2: [1],                       # column 2 (single row)
                    },
                )
        """

        overrides = self._normalize_override_keys(splitter_overrides) if splitter_overrides else {}

        for container in self.dock_manager.dockContainers():
            splitter = container.rootSplitter()
            if splitter is None:
                continue
            self._apply_splitter_tree(splitter, (), horizontal, vertical, overrides)

    @staticmethod
    def _title_bar_button_enum(name: str) -> QtAds.ads.TitleBarButton | None:
        """Translate a user-friendly button name into an ADS TitleBarButton enum."""
        normalized = (name or "").lower().replace("-", "_").replace(" ", "_")
        mapping: dict[str, QtAds.ads.TitleBarButton] = {
            "menu": QtAds.ads.TitleBarButton.TitleBarButtonTabsMenu,
            "tabs_menu": QtAds.ads.TitleBarButton.TitleBarButtonTabsMenu,
            "tabs": QtAds.ads.TitleBarButton.TitleBarButtonTabsMenu,
            "undock": QtAds.ads.TitleBarButton.TitleBarButtonUndock,
            "float": QtAds.ads.TitleBarButton.TitleBarButtonUndock,
            "detach": QtAds.ads.TitleBarButton.TitleBarButtonUndock,
            "close": QtAds.ads.TitleBarButton.TitleBarButtonClose,
            "auto_hide": QtAds.ads.TitleBarButton.TitleBarButtonAutoHide,
            "autohide": QtAds.ads.TitleBarButton.TitleBarButtonAutoHide,
            "minimize": QtAds.ads.TitleBarButton.TitleBarButtonMinimize,
        }
        return mapping.get(normalized)

    def _normalize_title_buttons(
        self,
        spec: (
            Mapping[str | QtAds.ads.TitleBarButton, bool]
            | Sequence[str | QtAds.ads.TitleBarButton]
            | str
            | QtAds.ads.TitleBarButton
            | None
        ),
    ) -> dict[QtAds.ads.TitleBarButton, bool]:
        """Normalize button visibility specifications into an enum mapping."""
        if spec is None:
            return {}

        result: dict[QtAds.ads.TitleBarButton, bool] = {}
        if isinstance(spec, Mapping):
            iterator = spec.items()
        else:
            if isinstance(spec, str):
                spec = [spec]
            iterator = ((name, False) for name in spec)

        for name, visible in iterator:
            if isinstance(name, QtAds.ads.TitleBarButton):
                enum = name
            else:
                enum = self._title_bar_button_enum(str(name))
            if enum is None:
                continue
            result[enum] = bool(visible)
        return result

    def _apply_dock_preferences(self, dock: CDockWidget) -> None:
        """
        Apply deferred appearance preferences to a dock once it has been created.

        Args:
            dock(CDockWidget): Target dock widget.
        """
        prefs: Mapping[str, Any] = getattr(dock, "_dock_preferences", {})

        def apply():
            title_bar = None
            area_widget = dock.dockAreaWidget()
            if area_widget is not None and hasattr(area_widget, "titleBar"):
                title_bar = area_widget.titleBar()

            show_title_bar = prefs.get("show_title_bar")
            if title_bar is not None and show_title_bar is not None:
                title_bar.setVisible(bool(show_title_bar))

            button_prefs = prefs.get("title_buttons") or {}
            if title_bar is not None and button_prefs:
                for enum, visible in button_prefs.items():
                    try:
                        button = title_bar.button(enum)
                    except Exception:  # pragma: no cover - defensive against ADS API changes
                        button = None
                    if button is not None:
                        button.setVisible(bool(visible))

        # single shot to ensure dock is fully initialized, as widgets with their own dock manager can take a moment to initialize
        QTimer.singleShot(0, apply)

    def set_central_dock(self, dock: CDockWidget | QWidget | str) -> None:
        """
        Promote an existing dock to be the dock manager's central widget.

        Args:
            dock(CDockWidget | QWidget | str): Dock reference to promote.
        """
        resolved = self._resolve_dock_reference(dock, allow_none=False)
        self.dock_manager.setCentralWidget(resolved)
        self._apply_dock_preferences(resolved)

    ################################################################################
    # Public API
    ################################################################################

    @SafeSlot(popup_error=True)
    def new(
        self,
        widget: QWidget | str,
        *,
        closable: bool = True,
        floatable: bool = True,
        movable: bool = True,
        start_floating: bool = False,
        floating_state: Mapping[str, object] | None = None,
        where: Literal["left", "right", "top", "bottom"] | None = None,
        on_close: Callable[[CDockWidget, QWidget], None] | None = None,
        tab_with: CDockWidget | QWidget | str | None = None,
        relative_to: CDockWidget | QWidget | str | None = None,
        return_dock: bool = False,
        show_title_bar: bool | None = None,
        title_buttons: Mapping[str, bool] | Sequence[str] | str | None = None,
        show_settings_action: bool | None = False,
        promote_central: bool = False,
        dock_icon: QIcon | None = None,
        apply_widget_icon: bool = True,
        object_name: str | None = None,
        **widget_kwargs,
    ) -> QWidget | CDockWidget | BECWidget:
        """
        Create a new widget (or reuse an instance) and add it as a dock.

        Args:
            widget(QWidget | str): Instance or registered widget type string.
            closable(bool): Whether the dock is closable.
            floatable(bool): Whether the dock is floatable.
            movable(bool): Whether the dock is movable.
            start_floating(bool): Whether to start the dock floating.
            floating_state(Mapping | None): Optional floating geometry metadata to apply when floating.
            where(Literal["left", "right", "top", "bottom"] | None): Dock placement hint relative to the dock area (ignored when
                ``relative_to`` is provided without an explicit value).
            on_close(Callable[[CDockWidget, QWidget], None] | None): Optional custom close handler accepting (dock, widget).
            tab_with(CDockWidget | QWidget | str | None): Existing dock (or widget/name) to tab the new dock alongside.
            relative_to(CDockWidget | QWidget | str | None): Existing dock (or widget/name) used as the positional anchor.
                When supplied and ``where`` is ``None``, the new dock inherits the
                anchor's current dock area.
            return_dock(bool): When True, return the created dock instead of the widget.
            show_title_bar(bool | None): Explicitly show or hide the dock area's title bar.
            title_buttons(Mapping[str, bool] | Sequence[str] | str | None): Mapping or iterable describing which title bar buttons should
                remain visible. Provide a mapping of button names (``"float"``,
                ``"close"``, ``"menu"``, ``"auto_hide"``, ``"minimize"``) to booleans,
                or a sequence of button names to hide.
            show_settings_action(bool | None): Control whether a dock settings/property action should
                be installed. Defaults to ``False`` for the basic dock area; subclasses
                such as `AdvancedDockArea` override the default to ``True``.
            promote_central(bool): When True, promote the created dock to be the dock manager's
                central widget (useful for editor stacks or other root content).
            dock_icon(QIcon | None): Optional icon applied to the dock via ``CDockWidget.setIcon``.
                Provide a `QIcon` (e.g. from ``material_icon``). When ``None`` (default),
                the widget's ``ICON_NAME`` attribute is used when available.
            apply_widget_icon(bool): When False, skip automatically resolving the icon from
                the widget's ``ICON_NAME`` (useful for callers who want no icon and do not pass one explicitly).
            object_name(str | None): Optional object name to assign to the created widget.
            **widget_kwargs: Additional keyword arguments passed to the widget constructor
                when creating by type name.

        Returns:
            The widget instance by default, or the created `CDockWidget` when `return_dock` is True.
        """
        if isinstance(widget, str):
            if return_dock:
                raise ValueError(
                    "return_dock=True is not supported when creating widgets by type name."
                )
            widget = cast(
                BECWidget,
                widget_handler.create_widget(
                    widget_type=widget, parent=self, object_name=object_name, **widget_kwargs
                ),
            )

            spec = self._build_creation_spec(
                widget=widget,
                closable=closable,
                floatable=floatable,
                movable=movable,
                start_floating=start_floating,
                floating_state=floating_state,
                where=where,
                on_close=on_close,
                tab_with=tab_with,
                relative_to=relative_to,
                show_title_bar=show_title_bar,
                title_buttons=title_buttons,
                show_settings_action=show_settings_action,
                promote_central=promote_central,
                dock_icon=dock_icon,
                apply_widget_icon=apply_widget_icon,
            )

            def _on_name_established(_name: str) -> None:
                # Defer creation so BECConnector sibling name enforcement has completed.
                QTimer.singleShot(0, lambda: self._create_dock_from_spec(spec))

            widget.name_established.connect(_on_name_established)
            return widget

        spec = self._build_creation_spec(
            widget=widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            start_floating=start_floating,
            floating_state=floating_state,
            where=where,
            on_close=on_close,
            tab_with=tab_with,
            relative_to=relative_to,
            show_title_bar=show_title_bar,
            title_buttons=title_buttons,
            show_settings_action=show_settings_action,
            promote_central=promote_central,
            dock_icon=dock_icon,
            apply_widget_icon=apply_widget_icon,
        )
        dock = self._create_dock_from_spec(spec)
        return dock if return_dock else widget

    def _iter_all_docks(self) -> list[CDockWidget]:
        """Return all docks, including those hosted in floating containers."""
        docks = list(self.dock_manager.dockWidgets())
        seen = {id(d) for d in docks}
        for container in self.dock_manager.floatingWidgets():
            if container is None:
                continue
            for dock in container.dockWidgets():
                if dock is None:
                    continue
                if id(dock) in seen:
                    continue
                docks.append(dock)
                seen.add(id(dock))
        return docks

    def dock_map(self) -> dict[str, CDockWidget]:
        """Return the dock widgets map as dictionary with names as keys."""
        return {dock.objectName(): dock for dock in self._iter_all_docks() if dock.objectName()}

    def dock_list(self) -> list[CDockWidget]:
        """Return the list of dock widgets."""
        return self._iter_all_docks()

    def widget_map(self) -> dict[str, QWidget]:
        """Return a dictionary mapping widget names to their corresponding widgets."""
        return {dock.objectName(): dock.widget() for dock in self.dock_list()}

    def widget_list(self) -> list[QWidget]:
        """Return a list of all widgets contained in the dock area."""
        return [dock.widget() for dock in self.dock_list() if isinstance(dock.widget(), QWidget)]

    @SafeSlot()
    def attach_all(self):
        """Re-attach floating docks back into the dock manager."""
        for container in self.dock_manager.floatingWidgets():
            docks = container.dockWidgets()
            if not docks:
                continue
            target = docks[0]
            self.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, target)
            for dock in docks[1:]:
                self.dock_manager.addDockWidgetTab(
                    QtAds.DockWidgetArea.RightDockWidgetArea, dock, target
                )

    @SafeSlot(str)
    def delete(self, object_name: str) -> bool:
        """
        Remove a widget from the dock area by its object name.

        Args:
            object_name: The object name of the widget to remove.

        Returns:
            bool: True if the widget was found and removed, False otherwise.

        Raises:
            ValueError: If no widget with the given object name is found.

        Example:
            >>> dock_area.delete("my_widget")
            True
        """
        dock_map = self.dock_map()
        dock = dock_map.get(object_name)
        if dock is None:
            raise ValueError(f"No widget found with object name '{object_name}'.")
        self._delete_dock(dock)
        return True

    @SafeSlot()
    def delete_all(self):
        """Delete all docks and their associated widgets."""
        for dock in self.dock_list():
            self._delete_dock(dock)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton

    from bec_widgets.utils.colors import apply_theme

    class CustomCloseWidget(QWidget):
        """Example widget showcasing custom close handling via handle_dock_close."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("CustomCloseWidget")
            layout = QVBoxLayout(self)
            layout.addWidget(
                QLabel(
                    "Custom close handler – tabbed with Column 1 / Row 1.\n"
                    "Close this dock to see the stdout cleanup message.",
                    self,
                )
            )
            btn = QPushButton("Click me before closing", self)
            layout.addWidget(btn)

        def handle_dock_close(self, dock: CDockWidget, widget: QWidget) -> None:
            print(f"[CustomCloseWidget] Closing {widget.objectName()}")
            area = widget.parent()
            while area is not None and not isinstance(area, DockAreaWidget):
                area = area.parent()
            if isinstance(area, DockAreaWidget):
                area.close_dock(dock, widget)

    class LambdaCloseWidget(QWidget):
        """Example widget that relies on an explicit lambda passed to BasicDockArea.new."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("LambdaCloseWidget")
            layout = QVBoxLayout(self)
            layout.addWidget(
                QLabel(
                    "Custom lambda close handler – tabbed with Column 2 / Row 1.\n"
                    "Closing prints which dock triggered the callback.",
                    self,
                )
            )

    app = QApplication(sys.argv)
    apply_theme("dark")
    window = QMainWindow()
    area = DockAreaWidget(root_widget=True, title="Basic Dock Area Demo")
    window.setCentralWidget(area)
    window.resize(1400, 800)
    window.show()

    def make_panel(name: str, title: str, body: str = "") -> QWidget:
        panel = QWidget()
        panel.setObjectName(name)
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel(title, panel))
        if body:
            layout.addWidget(QLabel(body, panel))
        layout.addStretch(1)
        return panel

    # Column 1: plain 'where' usage
    col1_top = area.new(
        make_panel("C1R1", "Column 1 / Row 1", "Added with where='left'."),
        closable=True,
        where="left",
        return_dock=True,
        show_settings_action=True,
    )
    area.new(
        make_panel("C1R2", "Column 1 / Row 2", "Stacked via relative_to + where='bottom'."),
        closable=True,
        where="bottom",
        relative_to=col1_top,
    )

    # Column 2: relative placement and tabbing
    col2_top = area.new(
        make_panel(
            "C2R1", "Column 2 / Row 1", "Placed to the right of Column 1 using relative_to."
        ),
        closable=True,
        where="right",
        relative_to=col1_top,
        return_dock=True,
    )
    area.new(
        make_panel("C2R2", "Column 2 / Row 2", "Added beneath Column 2 / Row 1 via relative_to."),
        closable=True,
        where="bottom",
        relative_to=col2_top,
    )
    area.new(
        make_panel("C2Tabbed", "Column 2 / Tabbed", "Tabbed with Column 2 / Row 1 using tab_with."),
        closable=True,
        tab_with=col2_top,
    )

    # Column 3: mix of where, relative_to, and custom close handler
    col3_top = area.new(
        make_panel("C3R1", "Column 3 / Row 1", "Placed to the right of Column 2 via relative_to."),
        closable=True,
        where="right",
        relative_to=col2_top,
        return_dock=True,
    )
    area.new(
        make_panel(
            "C3R2", "Column 3 / Row 2", "Plain where='bottom' relative to Column 3 / Row 1."
        ),
        closable=True,
        where="bottom",
        relative_to=col3_top,
    )
    area.new(
        make_panel(
            "C3Lambda",
            "Column 3 / Tabbed Lambda",
            "Tabbed with Column 3 / Row 1. Custom close handler prints the dock name.",
        ),
        closable=True,
        tab_with=col3_top,
        on_close=lambda dock, widget: (
            print(f"[Lambda handler] Closing {widget.objectName()}"),
            area.close_dock(dock, widget),
        ),
        show_settings_action=True,
    )

    area.set_layout_ratios(
        horizontal=[1, 1.5, 1], splitter_overrides={0: [3, 2], 1: [4, 3], 2: [2, 1]}
    )

    print("\nSplitter structure (paths for splitter_overrides):")
    area.print_layout_structure()

    sys.exit(app.exec())
