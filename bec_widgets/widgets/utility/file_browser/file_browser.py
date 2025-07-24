from PySide6.QtWidgets import QVBoxLayout
from qtpy.QtCore import QDir
from qtpy.QtWidgets import QApplication, QFileSystemModel, QHeaderView, QTreeView, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar


class FileBrowser(BECWidget, QWidget):
    """
    A simple file browser widget.
    """

    PLUGIN = True
    ICON_NAME = "folder_open"

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeView(self)

        self.model = QFileSystemModel()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(QDir.rootPath()))
        self.model.setRootPath(QDir.rootPath())

        self._allow_changing_root = True
        self._original_root_path = QDir.rootPath()

        self.toolbar = ModularToolBar(parent=self, orientation="horizontal")

        self._go_back_action = MaterialIconAction("arrow_back", "Go Back", parent=self)
        self.toolbar.components.add_safe("go_back", self._go_back_action)
        self.toolbar.components.add_safe(
            "refresh", MaterialIconAction("refresh", "Refresh", parent=self)
        )
        self.toolbar.components.add_safe(
            "open", MaterialIconAction("folder_open", "Open File", parent=self)
        )
        bundle = ToolbarBundle("file_io", self.toolbar.components)
        bundle.add_action("go_back")
        bundle.add_action("refresh")
        bundle.add_action("open")
        self.toolbar.add_bundle(bundle)

        self.toolbar.show_bundles(["file_io"])

        layout.addWidget(self.toolbar)
        layout.addWidget(self.tree)
        self.setLayout(layout)

        self._show_hidden_files = False
        self._go_back_action.action.setEnabled(False)
        self._go_back_action.action.triggered.connect(self._on_go_back)

        self.tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree.doubleClicked.connect(self._on_double_click)

    def _on_double_click(self, index):
        """
        Handle double-click events on the file browser.
        Opens the selected file or directory.
        """
        if not index.isValid():
            return

        path = self.model.filePath(index)
        if self.model.isDir(index) and self._allow_changing_root:
            self.tree.setRootIndex(index)
            if path != self._original_root_path:
                self._go_back_action.action.setEnabled(True)
            else:
                self._go_back_action.action.setEnabled(False)
            return
        print(f"Opening file: {path}")

    def _on_go_back(self):
        """
        Handle the go back action.
        Navigates to the previous directory in the file browser.
        """
        if self._allow_changing_root and self.tree.rootIndex().isValid():
            parent_index = self.tree.rootIndex().parent()
            if parent_index.isValid():
                self.tree.setRootIndex(parent_index)
                if parent_index != self.model.index(self._original_root_path):
                    self._go_back_action.action.setEnabled(True)
                else:
                    self._go_back_action.action.setEnabled(False)

    @SafeProperty(bool)
    def show_toolbar(self):
        """
        Get whether the toolbar is shown in the file browser.
        """
        return not self.toolbar.isHidden()

    @show_toolbar.setter
    def show_toolbar(self, show: bool):
        """
        Set whether the toolbar is shown in the file browser.
        """
        self.toolbar.setVisible(show)

    @SafeProperty(bool)
    def show_hidden_files(self):
        """
        Get whether hidden files are shown in the file browser.
        """
        return self._show_hidden_files

    @show_hidden_files.setter
    def show_hidden_files(self, show: bool):
        """
        Set whether hidden files are shown in the file browser.
        """
        self._show_hidden_files = show
        if show:
            self.model.setFilter(
                QDir.Filter.AllDirs
                | QDir.Filter.Files
                | QDir.Filter.NoDotAndDotDot
                | QDir.Filter.Hidden
            )
        else:
            self.model.setFilter(
                QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
            )
        self.tree.setRootIndex(self.model.index(self.model.rootPath()))

    @SafeProperty(bool)
    def allow_changing_root(self):
        """
        Get whether changing the root path is allowed.
        """
        return self._allow_changing_root

    @allow_changing_root.setter
    def allow_changing_root(self, allow: bool):
        """
        Set whether changing the root path is allowed.
        """
        self._allow_changing_root = allow

    @SafeProperty(bool)
    def show_file_size(self):
        """
        Get whether the file size is shown in the file browser.
        """
        index = self._section_index("Size")
        return not self.tree.header().isSectionHidden(index)

    @show_file_size.setter
    def show_file_size(self, show: bool):
        """
        Set whether the file size is shown in the file browser.
        """
        index = self._section_index("Size")
        self.tree.header().setSectionHidden(index, not show)
        self.tree.header().repaint()

    @SafeProperty(bool)
    def show_file_kind(self):
        """
        Get whether the file kind is shown in the file browser.
        """
        index = self._section_index("Kind")
        return not self.tree.header().isSectionHidden(index)

    @show_file_kind.setter
    def show_file_kind(self, show: bool):
        """
        Set whether the file kind is shown in the file browser.
        """
        index = self._section_index("Kind")
        self.tree.header().setSectionHidden(index, not show)
        self.tree.setRootIndex(self.model.index(self.model.rootPath()))

    @SafeProperty(bool)
    def show_file_timestamp(self):
        """
        Get whether the file timestamp is shown in the file browser.
        """
        index = self._section_index("Date Modified")
        return not self.tree.header().isSectionHidden(index)

    @show_file_timestamp.setter
    def show_file_timestamp(self, show: bool):
        """
        Set whether the file timestamp is shown in the file browser.
        """
        index = self._section_index("Date Modified")
        self.tree.header().setSectionHidden(index, not show)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setRootIndex(self.model.index(self.model.rootPath()))

    @SafeProperty(str)
    def root_path(self):
        """
        Get the root path of the file browser.
        """
        return self.model.rootPath()

    @root_path.setter
    def root_path(self, path: str):
        """
        Set the root path of the file browser.
        """
        self.model.setRootPath(path)
        self.tree.setRootIndex(self.model.index(path))
        self._original_root_path = path

    @SafeProperty(bool)
    def show_header(self):
        """
        Get whether the header is shown in the file browser.
        """
        return not self.tree.header().isHidden()

    @show_header.setter
    def show_header(self, show: bool):
        """
        Set whether the header is shown in the file browser.
        """
        self.tree.setHeaderHidden(not show)
        self.tree.setRootIndex(self.model.index(self.model.rootPath()))

    def _section_index(self, label: str) -> int:
        header = self.tree.header()
        model = self.tree.model()
        for i in range(model.columnCount()):
            if model.headerData(i, header.orientation()) == label:
                return i
        print(f"Section '{label}' not found in header.")
        return -1


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    file_browser = FileBrowser()
    file_browser.root_path = "/Users/wakonig_k/software/work/bec-widgets/bec_widgets"
    file_browser.show_file_size = False
    file_browser.show_file_kind = False
    file_browser.show_file_timestamp = False
    file_browser.show_hidden_files = True
    file_browser.show_header = False
    file_browser.show()
    sys.exit(app.exec_())
#     from qtpy.QtCore import Qt
#     from qtpy.QtWidgets import QDockWidget, QFileSystemModel, QTreeView

#     class ExplorerDock(QWidget):
#         def __init__(self, cpath, themes):
#             super().__init__()
#             self._themes = themes
#             self.setWindowTitle("Explorer")
#             self.tree = QTreeView(self)
#             self.model = QFileSystemModel()
#             self.tree.setModel(self.model)
#             self.tree.setRootIndex(self.model.index(cpath))
#             self.model.setRootPath(cpath)

#             layout = QVBoxLayout(self)
#             layout.setContentsMargins(0, 0, 0, 0)
#             layout.addWidget(self.tree)

#     app = QApplication([])
#     explorer = ExplorerDock(
#         cpath="/Users/wakonig_k/software/work/csaxs_bec/csaxs_bec", themes={"sidebar_bg": "#2E2E2E"}
#     )
#     explorer.show()
#     app.exec_()


# # self.dock = QDockWidget("Explorer", self)
# #         self.dock.setMinimumWidth(200)
# #         self.dock.visibilityChanged.connect(
# #             lambda visible: self.onExplorerDockVisibilityChanged(visible)
# #         )
# #         self.dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
# #         tree_view = QTreeView()

# #         self.model = QFileSystemModel()
# #         bg = self._themes["sidebar_bg"]
# #         tree_view.setStyleSheet(
# #             f"QTreeView {{background-color: {bg}; color: white; border: none; }}"
# #         )
# #         tree_view.setModel(self.model)
# #         tree_view.setRootIndex(self.model.index(cpath))
# #         self.model.setRootPath(cpath)
