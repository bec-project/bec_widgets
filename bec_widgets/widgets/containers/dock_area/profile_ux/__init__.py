"""Reworked profile management windows for the dock area, in a QWidget and a QML version.

``BEC_PROFILE_UI=qwidget`` or ``BEC_PROFILE_UI=qml`` opts into them; the default keeps the
previous dialogs. Both versions share the rules and actions in :mod:`.common`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.widgets.containers.dock_area.profile_ux.common import (
    POLICY,
    UI_ENV,
    NameMode,
    ProfileActions,
    ProfilePolicy,
    UiMode,
    profile_ui_mode,
)

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtWidgets import QDialog, QWidget

    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

__all__ = [
    "POLICY",
    "UI_ENV",
    "ProfileActions",
    "ProfilePolicy",
    "ask_profile_name",
    "confirm_revert",
    "create_profile_library",
    "profile_ui_mode",
]


def _views(ui: UiMode | None):
    ui = ui or profile_ui_mode()
    if ui == "qml":
        from bec_widgets.widgets.containers.dock_area.profile_ux import profile_qml as views
    else:
        from bec_widgets.widgets.containers.dock_area.profile_ux import profile_qwidget as views
    return views


def create_profile_library(
    dock_area: BECDockArea, parent: QWidget | None = None, ui: UiMode | None = None
) -> QDialog:
    """
    Create the non-modal profile library window for *dock_area*.

    Args:
        dock_area(BECDockArea): The dock area the library acts on.
        parent(QWidget | None): Parent of the window; defaults to the dock area.
        ui(UiMode | None): ``qwidget`` or ``qml``; defaults to ``BEC_PROFILE_UI``.
    """
    views = _views(ui)
    return views.ProfileLibraryDialog(ProfileActions(dock_area), parent or dock_area)


def ask_profile_name(
    dock_area: BECDockArea,
    mode: NameMode,
    original: str = "",
    parent: QWidget | None = None,
    ui: UiMode | None = None,
) -> str | None:
    """
    Ask for a name and save, rename or duplicate a profile of *dock_area*.

    Args:
        dock_area(BECDockArea): The dock area the request comes from.
        mode(NameMode): ``save``, ``rename`` or ``duplicate``.
        original(str): The profile to rename or duplicate.
        parent(QWidget | None): Dialog parent; defaults to the dock area.
        ui(UiMode | None): ``qwidget`` or ``qml``; defaults to ``BEC_PROFILE_UI``.

    Returns:
        str | None: The resulting profile name, or None when cancelled.
    """
    views = _views(ui)
    return views.run_name_flow(ProfileActions(dock_area), mode, original, parent or dock_area)


def confirm_revert(
    dock_area: BECDockArea, name: str, parent: QWidget | None = None, ui: UiMode | None = None
) -> bool:
    """
    Ask whether to revert *name* to its saved layout.

    Returns:
        bool: True when the user confirmed; the caller performs the revert.
    """
    views = _views(ui)
    return views.run_revert_flow(ProfileActions(dock_area), name, parent or dock_area)
