from pathlib import Path

import pytest
from qtpy.QtCore import QModelIndex, QPoint, Qt
from qtpy.QtWidgets import QAbstractItemView, QInputDialog, QMenu

from bec_widgets.widgets.containers.explorer.file_browser_tree_widget import FileBrowserTreeWidget


@pytest.fixture
def file_browser_tree(qtbot, tmpdir):
    """Create a FileBrowserTreeWidget rooted at tmpdir."""
    (Path(tmpdir) / "test_file.py").touch()
    (Path(tmpdir) / "__init__.py").touch()
    (Path(tmpdir) / "test_dir").mkdir()
    (Path(tmpdir) / "test_dir" / "nested_file.py").touch()
    (Path(tmpdir) / "__pycache__").mkdir()
    (Path(tmpdir) / "__pycache__" / "ignored.py").touch()

    widget = FileBrowserTreeWidget(directory=str(tmpdir))
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_file_browser_tree_set_directory(file_browser_tree, tmpdir):
    """Test setting the directory."""
    assert file_browser_tree.directory == str(tmpdir)


def test_file_browser_tree_hides_filtered_entries(file_browser_tree, qtbot):
    """Test that filtered cache/init entries are hidden from the browser."""

    def visible_names():
        root_index = file_browser_tree.tree.rootIndex()
        return [
            file_browser_tree.proxy_model.data(
                file_browser_tree.proxy_model.index(i, 0, root_index)
            )
            for i in range(file_browser_tree.proxy_model.rowCount(root_index))
        ]

    qtbot.waitUntil(lambda: "test_file.py" in visible_names(), timeout=5000)
    assert "__pycache__" not in visible_names()
    assert "__init__.py" not in visible_names()


def test_file_browser_tree_native_browser_configuration(file_browser_tree):
    """Test that the tree is configured like a plain native file browser."""
    assert file_browser_tree.model.isReadOnly() is False
    assert file_browser_tree.tree.alternatingRowColors() is False
    assert file_browser_tree.tree.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove
    assert file_browser_tree.tree.defaultDropAction() == Qt.DropAction.MoveAction
    assert (
        file_browser_tree.tree.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    )


def test_file_browser_tree_set_readonly(file_browser_tree):
    """Test toggling read-only mode on the file browser."""
    file_browser_tree.set_readonly(True)
    assert file_browser_tree.model.isReadOnly() is True
    assert file_browser_tree.tree.dragDropMode() == QAbstractItemView.DragDropMode.NoDragDrop

    file_browser_tree.set_readonly(False)
    assert file_browser_tree.model.isReadOnly() is False
    assert file_browser_tree.tree.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove


@pytest.mark.timeout(10)
def test_file_browser_tree_on_item_clicked(file_browser_tree, qtbot):
    """Test that clicks and double-clicks emit the expected file signals."""
    file_selected_signals = []
    file_open_requested_signals = []

    def on_file_selected(file_path):
        file_selected_signals.append(file_path)

    def on_file_open_requested(file_path):
        file_open_requested_signals.append(file_path)

    file_browser_tree.file_selected.connect(on_file_selected)
    file_browser_tree.file_open_requested.connect(on_file_open_requested)

    def has_py_file():
        nonlocal py_file_index
        root_index = file_browser_tree.tree.rootIndex()
        for i in range(file_browser_tree.proxy_model.rowCount(root_index)):
            index = file_browser_tree.proxy_model.index(i, 0, root_index)
            if file_browser_tree.proxy_model.data(index) == "test_file.py":
                py_file_index = index
                return True
        return False

    py_file_index = None
    qtbot.waitUntil(has_py_file)

    file_browser_tree._on_item_clicked(py_file_index)
    qtbot.wait(100)

    py_file_index = None
    qtbot.waitUntil(has_py_file)

    file_browser_tree._on_item_double_clicked(py_file_index)
    qtbot.wait(100)

    assert len(file_selected_signals) == 1
    assert Path(file_selected_signals[0]).name == "test_file.py"
    assert len(file_open_requested_signals) == 1
    assert Path(file_open_requested_signals[0]).name == "test_file.py"


def test_file_browser_tree_delete_request_emits_selected_file(file_browser_tree, qtbot):
    """Test that delete requests emit the currently selected file path."""
    delete_requests = []

    def on_delete_requested(file_path):
        delete_requests.append(file_path)

    file_browser_tree.file_delete_requested.connect(on_delete_requested)

    def get_test_file_index():
        root_index = file_browser_tree.tree.rootIndex()
        for i in range(file_browser_tree.proxy_model.rowCount(root_index)):
            index = file_browser_tree.proxy_model.index(i, 0, root_index)
            if file_browser_tree.proxy_model.data(index) == "test_file.py":
                return index
        return None

    qtbot.waitUntil(lambda: get_test_file_index() is not None, timeout=5000)
    file_index = get_test_file_index()
    assert file_index is not None
    file_browser_tree.tree.setCurrentIndex(file_index)
    file_browser_tree._on_file_delete_requested()
    qtbot.wait(100)

    assert len(delete_requests) == 1
    assert Path(delete_requests[0]).name == "test_file.py"


def test_file_browser_tree_context_menu_rename_action(file_browser_tree, qtbot, monkeypatch):
    """Test that the context menu exposes a rename action for editable items."""

    def get_test_file_index():
        root_index = file_browser_tree.tree.rootIndex()
        for i in range(file_browser_tree.proxy_model.rowCount(root_index)):
            index = file_browser_tree.proxy_model.index(i, 0, root_index)
            if file_browser_tree.proxy_model.data(index) == "test_file.py":
                return index
        return None

    qtbot.waitUntil(lambda: get_test_file_index() is not None, timeout=5000)
    file_index = get_test_file_index()
    assert file_index is not None

    called = {}

    def fake_edit(index):
        called["name"] = file_browser_tree.proxy_model.data(index)
        return True

    monkeypatch.setattr(file_browser_tree.tree, "edit", fake_edit)
    menu = file_browser_tree._build_context_menu(file_index)
    assert menu is not None
    assert [action.text() for action in menu.actions()] == [
        "New Folder",
        "Open",
        "Rename",
        "Delete File",
    ]
    menu.actions()[2].trigger()

    assert called["name"] == "test_file.py"


def test_file_browser_tree_context_menu_open_action(file_browser_tree, qtbot):
    """Test that the context menu exposes an open action for files."""
    opened = []
    file_browser_tree.file_open_requested.connect(opened.append)

    def get_test_file_index():
        root_index = file_browser_tree.tree.rootIndex()
        for i in range(file_browser_tree.proxy_model.rowCount(root_index)):
            index = file_browser_tree.proxy_model.index(i, 0, root_index)
            if file_browser_tree.proxy_model.data(index) == "test_file.py":
                return index
        return None

    qtbot.waitUntil(lambda: get_test_file_index() is not None, timeout=5000)
    file_index = get_test_file_index()
    assert file_index is not None

    file_browser_tree.tree.setCurrentIndex(file_index)
    menu = file_browser_tree._build_context_menu(file_index)
    assert menu is not None
    menu.actions()[1].trigger()

    assert len(opened) == 1
    assert Path(opened[0]).name == "test_file.py"


def test_file_browser_tree_context_menu_root_allows_new_folder(file_browser_tree):
    """Test that right-clicking the root area offers folder creation."""
    menu = file_browser_tree._build_context_menu(QModelIndex())
    assert menu is not None
    assert [action.text() for action in menu.actions()] == ["New Folder"]


def test_file_browser_tree_context_menu_hidden_when_read_only(file_browser_tree, monkeypatch):
    """Test that no context menu is shown in read-only mode."""
    file_browser_tree.set_readonly(True)

    called = {"shown": False}

    def fake_exec(*_args, **_kwargs):
        called["shown"] = True
        return None

    monkeypatch.setattr(QMenu, "exec", fake_exec)
    file_browser_tree._show_context_menu(QPoint(0, 0))

    assert called["shown"] is False


def test_file_browser_tree_emits_file_renamed_signal(file_browser_tree):
    """Test that model rename notifications are emitted as full paths."""
    renamed = []
    file_browser_tree.file_renamed.connect(lambda old, new: renamed.append((old, new)))

    file_browser_tree._on_model_file_renamed(str(file_browser_tree.directory), "old.py", "new.py")

    assert renamed == [
        (
            str(Path(file_browser_tree.directory) / "old.py"),
            str(Path(file_browser_tree.directory) / "new.py"),
        )
    ]


def test_file_browser_tree_create_subdirectory_at_root(file_browser_tree, monkeypatch):
    """Test creating a subdirectory at the root level."""
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("new_root_dir", True))

    file_browser_tree._create_subdirectory(str(file_browser_tree.directory))

    assert (Path(file_browser_tree.directory) / "new_root_dir").is_dir()


def test_file_browser_tree_create_subdirectory_in_selected_directory(
    file_browser_tree, qtbot, monkeypatch
):
    """Test creating a subdirectory inside the selected directory level."""

    def get_test_dir_index():
        root_index = file_browser_tree.tree.rootIndex()
        for i in range(file_browser_tree.proxy_model.rowCount(root_index)):
            index = file_browser_tree.proxy_model.index(i, 0, root_index)
            if file_browser_tree.proxy_model.data(index) == "test_dir":
                return index
        return None

    qtbot.waitUntil(lambda: get_test_dir_index() is not None, timeout=5000)
    dir_index = get_test_dir_index()
    assert dir_index is not None
    assert file_browser_tree._get_target_directory(dir_index).endswith("test_dir")

    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("child_dir", True))
    file_browser_tree._create_subdirectory(file_browser_tree._get_target_directory(dir_index))

    assert (Path(file_browser_tree.directory) / "test_dir" / "child_dir").is_dir()
