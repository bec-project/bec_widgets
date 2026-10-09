"""Tabbed workspaces: several dock areas side by side, one per tab, each showing a profile."""

from __future__ import annotations

from typing import Any

from bec_lib import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import QPoint, Qt, Signal
from qtpy.QtWidgets import (
    QInputDialog,
    QMenu,
    QMessageBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea, StartupProfile
from bec_widgets.widgets.containers.dock_area.profile_utils import (
    get_open_workspaces,
    is_profile_read_only,
    list_profiles,
    profile_origin,
    set_open_workspaces,
)

logger = bec_logger.logger

UNTITLED_WORKSPACE = "Untitled"


class WorkspacePage(QWidget):
    """
    One tab of :class:`WorkspaceTabs`. The dock area is created on first activation, so
    restored tabs that are never opened cost nothing at startup.

    Args:
        parent(QWidget | None): Parent widget.
        profile(str | None): Profile the tab shows, or None for an unsaved empty workspace.
        startup_profile(StartupProfile): Startup profile passed to the dock area; defaults
            to ``profile``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        profile: str | None = None,
        startup_profile: StartupProfile = None,
    ):
        super().__init__(parent)
        self._pending_profile = profile
        self._startup_profile = startup_profile if startup_profile is not None else profile
        self.dock_area: BECDockArea | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    @property
    def profile(self) -> str | None:
        """Profile shown in this tab, or None for an unsaved workspace."""
        if self.dock_area is None:
            return self._pending_profile
        return self.dock_area._current_profile_name  # pylint: disable=protected-access

    @property
    def is_materialized(self) -> bool:
        """Whether the dock area of this tab has been created."""
        return self.dock_area is not None

    def materialize(self, **dock_area_kwargs: Any) -> BECDockArea:
        """
        Create the dock area of this tab if it does not exist yet.

        Args:
            **dock_area_kwargs: Keyword arguments for :class:`BECDockArea`.

        Returns:
            BECDockArea: The dock area of this tab.
        """
        if self.dock_area is None:
            self.dock_area = BECDockArea(
                self, startup_profile=self._startup_profile, **dock_area_kwargs
            )
            self.layout().addWidget(self.dock_area)
        return self.dock_area


class WorkspaceTabs(QTabWidget):
    """
    Tab widget hosting one :class:`BECDockArea` per workspace.

    Each tab shows one workspace profile. Tabs can be created, renamed, switched, reordered
    and closed. Closing a tab autosaves its profile and keeps it on disk. The set of open
    tabs is stored with the profiles and restored on the next start.

    Args:
        parent(QWidget | None): Parent widget.
        profile_namespace(str): Profile namespace shared by all tabs.
        restore(bool): Restore the tabs that were open last time.
        **dock_area_kwargs: Extra keyword arguments for every :class:`BECDockArea`.
    """

    current_dock_area_changed = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        profile_namespace: str = "bec",
        restore: bool = True,
        **dock_area_kwargs: Any,
    ):
        super().__init__(parent)
        self.setObjectName("WorkspaceTabs")
        self.profile_namespace = profile_namespace
        self._dock_area_kwargs = {
            "profile_namespace": profile_namespace,
            "auto_profile_namespace": False,
            "object_name": "DockArea",
            **dock_area_kwargs,
        }
        self._closing = False
        self._restoring = False

        self.setDocumentMode(True)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        # Size tabs to their titles; the app theme stretches tab bars to full width by default.
        self.tabBar().setObjectName("WorkspaceTabBar")
        self.setStyleSheet("QTabBar#WorkspaceTabBar { qproperty-expanding: false; }")
        self.tabCloseRequested.connect(self.close_workspace)
        self.currentChanged.connect(self._on_current_changed)
        self.tabBar().tabMoved.connect(lambda *_: self._persist())
        self.tabBar().tabBarDoubleClicked.connect(self._on_tab_double_clicked)
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._show_tab_menu)

        self.new_workspace_button = QToolButton(self)
        self.new_workspace_button.setObjectName("NewWorkspaceButton")
        self.new_workspace_button.setIcon(material_icon("add"))
        self.new_workspace_button.setAutoRaise(True)
        self.new_workspace_button.setToolTip("New workspace (click) or open a saved one (arrow)")
        self.new_workspace_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._open_menu = QMenu(self.new_workspace_button)
        self._open_menu.aboutToShow.connect(self._populate_open_menu)
        self.new_workspace_button.setMenu(self._open_menu)
        self.new_workspace_button.clicked.connect(self.new_workspace)
        self.setCornerWidget(self.new_workspace_button, Qt.Corner.TopRightCorner)

        if restore:
            self._restore_tabs()

    ################################################################################
    # Public API
    ################################################################################

    def pages(self) -> list[WorkspacePage]:
        """Return the workspace pages in tab order."""
        return [self.widget(i) for i in range(self.count())]

    def dock_areas(self) -> list[BECDockArea]:
        """Return the dock areas that have been created, in tab order."""
        return [page.dock_area for page in self.pages() if page.dock_area is not None]

    def current_dock_area(self) -> BECDockArea | None:
        """Return the dock area of the current tab, creating it if needed."""
        page = self.currentWidget()
        if page is None:
            return None
        return self._materialize(page)

    def workspace_names(self) -> list[str | None]:
        """Return the profile of every tab in order; None marks an unsaved workspace."""
        return [page.profile for page in self.pages()]

    def find_workspace(self, profile: str) -> int:
        """
        Return the tab index showing *profile*, or -1 if it is not open.

        Args:
            profile(str): The profile name.
        """
        for index, page in enumerate(self.pages()):
            if page.profile == profile:
                return index
        return -1

    def add_workspace(
        self,
        profile: str | None = None,
        *,
        activate: bool = True,
        startup_profile: StartupProfile = None,
    ) -> WorkspacePage:
        """
        Add a workspace tab.

        Args:
            profile(str | None): Profile to show, or None for a new empty workspace.
            activate(bool): Make the new tab current.
            startup_profile(StartupProfile): Override the dock area startup profile,
                e.g. ``"restore"`` to reopen the last used profile.

        Returns:
            WorkspacePage: The new tab page.
        """
        page = WorkspacePage(self, profile=profile, startup_profile=startup_profile)
        index = self.addTab(page, self._tab_title(profile))
        self.setTabToolTip(index, self._tab_tooltip(profile))
        if activate:
            self.setCurrentIndex(index)
            self._materialize(page)
        self._persist()
        return page

    @SafeSlot()
    def new_workspace(self) -> WorkspacePage:
        """Open a new empty workspace in a new tab."""
        return self.add_workspace(None)

    @SafeSlot(str)
    def open_workspace(self, profile: str) -> WorkspacePage:
        """
        Show *profile* in a tab, switching to its tab when it is already open.

        Args:
            profile(str): The profile name.

        Returns:
            WorkspacePage: The tab page showing the profile.
        """
        index = self.find_workspace(profile)
        if index >= 0:
            self.setCurrentIndex(index)
            return self.widget(index)
        return self.add_workspace(profile)

    @SafeSlot(int)
    def close_workspace(self, index: int, confirm: bool = True) -> bool:
        """
        Close the tab at *index*. Its profile is autosaved and kept on disk.

        Closing the last tab leaves a new empty workspace behind.

        Args:
            index(int): The tab index.
            confirm(bool): Ask before discarding an unsaved workspace that has widgets.

        Returns:
            bool: True if the tab was closed.
        """
        page = self.widget(index)
        if page is None:
            return False
        dock_area = page.dock_area
        if (
            confirm
            and dock_area is not None
            and page.profile is None
            and dock_area.dock_list()
            and not self._confirm_close_unsaved()
        ):
            return False

        self.removeTab(index)
        if dock_area is not None:
            dock_area.close()
            dock_area.deleteLater()
        page.deleteLater()
        if self.count() == 0 and not self._closing:
            self.new_workspace()
        self._persist()
        return True

    @SafeSlot()
    @SafeSlot(int)
    def rename_workspace(self, index: int | None = None, name: str | None = None) -> bool:
        """
        Rename the workspace of the tab at *index* (the current tab by default).

        The layout is saved under the new profile name. The previous profile stays in the
        profile library untouched, so renaming never removes anything from disk.

        Args:
            index(int | None): The tab index; defaults to the current tab.
            name(str | None): The new name; when None, the user is asked for one.

        Returns:
            bool: True if the workspace now has the new name.
        """
        if index is None or index < 0:
            index = self.currentIndex()
        page = self.widget(index)
        if page is None:
            return False
        current = page.profile

        if name is None:
            name, ok = QInputDialog.getText(
                self, "Rename Workspace", "Workspace name:", text=current or ""
            )
            if not ok:
                return False
        name = (name or "").strip()
        if not name or name == current:
            return False

        if not self._may_rename_to(name):
            return False

        dock_area = self._materialize(page)
        dock_area.save_profile(name, show_dialog=False)
        self._sync_tab(page)
        self._persist()
        return page.profile == name

    def cleanup(self) -> None:
        """Persist the open tabs and close every dock area (each autosaves its profile)."""
        self._persist()
        self._closing = True
        for page in self.pages():
            if page.dock_area is not None:
                page.dock_area.close()
                page.dock_area.deleteLater()

    ################################################################################
    # Internals
    ################################################################################

    def _restore_tabs(self) -> None:
        names, current = get_open_workspaces(namespace=self.profile_namespace)
        known = set(list_profiles(self.profile_namespace)) if names else set()
        names = [name for name in names if name in known]

        self._restoring = True
        try:
            if names:
                for name in names:
                    self.add_workspace(name, activate=False)
                target = self.find_workspace(current) if current else -1
                self.setCurrentIndex(max(target, 0))
            else:
                # Nothing stored yet: keep the single-workspace behaviour of reopening the
                # last used profile.
                self.add_workspace(None, activate=False, startup_profile="restore")
        finally:
            self._restoring = False
        self._materialize(self.currentWidget())
        self._persist()

    def _materialize(self, page: WorkspacePage) -> BECDockArea:
        if page.dock_area is not None:
            return page.dock_area
        dock_area = page.materialize(**self._dock_area_kwargs)
        dock_area.profile_in_use_elsewhere = lambda name, p=page: self._is_open_elsewhere(name, p)
        dock_area.profile_changed.connect(lambda _name, p=page: self._on_profile_changed(p))
        dock_area.profile_redirected.connect(self.open_workspace)
        self._sync_tab(page)
        return dock_area

    def _may_rename_to(self, name: str) -> bool:
        if self.find_workspace(name) >= 0:
            QMessageBox.information(
                self, "Rename Workspace", f"Workspace '{name}' is already open in another tab."
            )
            return False
        if is_profile_read_only(name, namespace=self.profile_namespace):
            QMessageBox.information(
                self,
                "Rename Workspace",
                f"'{name}' is a read-only bundled profile. Choose another name.",
            )
            return False
        if profile_origin(name, namespace=self.profile_namespace) != "unknown":
            reply = QMessageBox.question(
                self,
                "Rename Workspace",
                f"A saved workspace named '{name}' already exists.\n\n"
                "Replace it with the layout of this tab?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        return True

    def _is_open_elsewhere(self, name: str, page: WorkspacePage) -> bool:
        return any(other is not page and other.profile == name for other in self.pages())

    def _on_profile_changed(self, page: WorkspacePage) -> None:
        self._sync_tab(page)
        self._persist()

    def _sync_tab(self, page: WorkspacePage) -> None:
        index = self.indexOf(page)
        if index < 0:
            return
        self.setTabText(index, self._tab_title(page.profile))
        self.setTabToolTip(index, self._tab_tooltip(page.profile))

    @staticmethod
    def _tab_title(profile: str | None) -> str:
        return profile or UNTITLED_WORKSPACE

    @staticmethod
    def _tab_tooltip(profile: str | None) -> str:
        if profile is None:
            return "Unsaved workspace. Rename or save it to keep it."
        return f"Workspace profile '{profile}'"

    def _persist(self) -> None:
        if self._closing or self._restoring:
            return
        names = [name for name in self.workspace_names() if name]
        current_page = self.currentWidget()
        current = current_page.profile if current_page is not None else None
        set_open_workspaces(names, current, namespace=self.profile_namespace)

    def _on_current_changed(self, index: int) -> None:
        if self._closing or self._restoring or index < 0:
            return
        dock_area = self._materialize(self.widget(index))
        self._persist()
        self.current_dock_area_changed.emit(dock_area)

    def _on_tab_double_clicked(self, index: int) -> None:
        if index >= 0:
            self.rename_workspace(index)

    def _confirm_close_unsaved(self) -> bool:
        reply = QMessageBox.question(
            self,
            "Close Workspace",
            "This workspace has not been saved. Close it and its widgets?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _populate_open_menu(self) -> None:
        menu = self._open_menu
        menu.clear()
        menu.addAction(material_icon("add"), "New Workspace", self.new_workspace)
        profiles = list_profiles(self.profile_namespace)
        if profiles:
            menu.addSection("Open Saved Workspace")
        open_names = set(self.workspace_names())
        for name in profiles:
            action = menu.addAction(name, lambda n=name: self.open_workspace(n))
            if name in open_names:
                action.setCheckable(True)
                action.setChecked(True)
                action.setToolTip("Already open; switches to its tab")

    def _show_tab_menu(self, pos: QPoint) -> None:
        index = self.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        menu.addAction("Rename…", lambda: self.rename_workspace(index))
        menu.addAction("Close", lambda: self.close_workspace(index))
        menu.addSeparator()
        menu.addAction("New Workspace", self.new_workspace)
        menu.exec(self.tabBar().mapToGlobal(pos))
