# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import base64
import os
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtCore import QSettings, Qt, QTimer
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QDialog, QMessageBox, QWidget

import bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area as basic_dock_module
import bec_widgets.widgets.containers.advanced_dock_area.profile_utils as profile_utils
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import (
    AdvancedDockArea,
    SaveProfileDialog,
)
from bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area import (
    DockAreaWidget,
    DockSettingsDialog,
)
from bec_widgets.widgets.containers.advanced_dock_area.profile_utils import (
    SETTINGS_KEYS,
    default_profile_path,
    get_profile_info,
    is_profile_read_only,
    is_quick_select,
    list_profiles,
    load_default_profile_screenshot,
    load_user_profile_screenshot,
    open_default_settings,
    open_user_settings,
    plugin_profiles_dir,
    read_manifest,
    restore_user_from_default,
    set_quick_select,
    user_profile_path,
    write_manifest,
)
from bec_widgets.widgets.containers.advanced_dock_area.settings.dialogs import (
    PreviewPanel,
    RestoreProfileDialog,
)
from bec_widgets.widgets.containers.advanced_dock_area.settings.workspace_manager import (
    WorkSpaceManager,
)

from .client_mocks import mocked_client


@pytest.fixture
def advanced_dock_area(qtbot, mocked_client):
    """Create an AdvancedDockArea instance for testing."""
    widget = AdvancedDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture(autouse=True)
def isolate_profile_storage(tmp_path, monkeypatch):
    """Ensure each test writes profiles into a unique temporary directory."""
    root = tmp_path / "profiles_root"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(root))
    yield


@pytest.fixture
def temp_profile_dir():
    """Return the current temporary profile directory."""
    return os.environ["BECWIDGETS_PROFILE_DIR"]


@pytest.fixture
def module_profile_factory(monkeypatch, tmp_path):
    """Provide a helper to create synthetic module-level (read-only) profiles."""
    module_dir = tmp_path / "module_profiles"
    module_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(profile_utils, "module_profiles_dir", lambda: str(module_dir))
    monkeypatch.setattr(profile_utils, "plugin_profiles_dir", lambda: None)

    def _create(name="readonly_profile", content="[profile]\n"):
        path = module_dir / f"{name}.ini"
        path.write_text(content)
        return name

    return _create


@pytest.fixture
def workspace_manager_target():
    class _Signal:
        def __init__(self):
            self._slot = None

        def connect(self, slot):
            self._slot = slot

        def emit(self, value):
            if self._slot:
                self._slot(value)

    class _Combo:
        def __init__(self):
            self.current_text = ""

        def setCurrentText(self, text):
            self.current_text = text

    class _Action:
        def __init__(self, widget):
            self.widget = widget

    class _Components:
        def __init__(self, combo):
            self._combo = combo

        def get_action(self, name):
            return _Action(self._combo)

    class _Toolbar:
        def __init__(self, combo):
            self.components = _Components(combo)

    class _Target:
        def __init__(self):
            self.profile_changed = _Signal()
            self._combo = _Combo()
            self.toolbar = _Toolbar(self._combo)
            self._current_profile_name = None
            self.load_profile_calls = []
            self.save_called = False
            self.refresh_calls = 0

        def load_profile(self, name):
            self.load_profile_calls.append(name)
            self._current_profile_name = name

        def save_profile(self):
            self.save_called = True

        def save_profile_dialog(self, name: str | None = None):
            """Mock save_profile_dialog that sets save_called flag."""
            self.save_called = True

        def _refresh_workspace_list(self):
            self.refresh_calls += 1

        def delete_profile(self, name: str, show_dialog: bool = False) -> bool:
            """Mock delete_profile that performs actual file deletion."""
            from qtpy.QtWidgets import QMessageBox

            from bec_widgets.widgets.containers.advanced_dock_area.profile_utils import (
                delete_profile_files,
                is_profile_read_only,
            )

            if is_profile_read_only(name):
                if show_dialog:
                    QMessageBox.information(
                        None,
                        "Delete Profile",
                        f"Profile '{name}' is read-only and cannot be deleted.",
                    )
                    return False
                raise ValueError(f"Profile '{name}' is read-only.")
            delete_profile_files(name)
            if self._current_profile_name == name:
                self._current_profile_name = None
            self._refresh_workspace_list()
            return True

    def _factory():
        return _Target()

    return _factory


@pytest.fixture
def basic_dock_area(qtbot, mocked_client):
    """Create a namesake DockAreaWidget without the advanced toolbar."""
    widget = DockAreaWidget(client=mocked_client, title="Test Dock Area")
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


class _NamespaceProfiles:
    """Helper that routes profile file helpers through a namespace."""

    def __init__(self, widget: AdvancedDockArea):
        self.namespace = widget.profile_namespace

    def open_user(self, name: str):
        return open_user_settings(name, namespace=self.namespace)

    def open_default(self, name: str):
        return open_default_settings(name, namespace=self.namespace)

    def user_path(self, name: str) -> str:
        return user_profile_path(name, namespace=self.namespace)

    def default_path(self, name: str) -> str:
        return default_profile_path(name, namespace=self.namespace)

    def list_profiles(self) -> list[str]:
        return list_profiles(namespace=self.namespace)

    def set_quick_select(self, name: str, enabled: bool):
        set_quick_select(name, enabled, namespace=self.namespace)

    def is_quick_select(self, name: str) -> bool:
        return is_quick_select(name, namespace=self.namespace)


def profile_helper(widget: AdvancedDockArea) -> _NamespaceProfiles:
    """Return a helper wired to the widget's profile namespace."""
    return _NamespaceProfiles(widget)


class TestBasicDockArea:
    """Focused coverage for the lightweight DockAreaWidget base."""

    def test_new_widget_instance_registers_in_maps(self, basic_dock_area):
        panel = QWidget(parent=basic_dock_area)
        panel.setObjectName("basic_panel")

        dock = basic_dock_area.new(panel, return_dock=True)

        assert dock.objectName() == "basic_panel"
        assert basic_dock_area.dock_map()["basic_panel"] is dock
        assert basic_dock_area.widget_map()["basic_panel"] is panel

    def test_new_widget_string_creates_widget(self, basic_dock_area, qtbot):
        basic_dock_area.new("DarkModeButton")
        qtbot.waitUntil(lambda: len(basic_dock_area.dock_list()) > 0, timeout=1000)

        assert basic_dock_area.widget_list()

    def test_custom_close_handler_invoked(self, basic_dock_area, qtbot):
        class CloseAwareWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setObjectName("closable")
                self.closed = False

            def handle_dock_close(self, dock, widget):  # pragma: no cover - exercised via signal
                self.closed = True
                dock.closeDockWidget()
                dock.deleteDockWidget()

        widget = CloseAwareWidget(parent=basic_dock_area)
        dock = basic_dock_area.new(widget, return_dock=True)

        dock.closeRequested.emit()
        qtbot.waitUntil(lambda: widget.closed, timeout=1000)

        assert widget.closed is True
        assert "closable" not in basic_dock_area.dock_map()

    def test_attach_all_and_delete_all(self, basic_dock_area):
        first = QWidget(parent=basic_dock_area)
        first.setObjectName("floating_one")
        second = QWidget(parent=basic_dock_area)
        second.setObjectName("floating_two")

        dock_one = basic_dock_area.new(first, return_dock=True, start_floating=True)
        dock_two = basic_dock_area.new(second, return_dock=True, start_floating=True)
        assert dock_one.isFloating() and dock_two.isFloating()

        basic_dock_area.attach_all()

        assert not dock_one.isFloating()
        assert not dock_two.isFloating()

        basic_dock_area.delete_all()
        assert basic_dock_area.dock_list() == []

    def test_remove_widget_by_object_name(self, basic_dock_area, qtbot):
        """Test remove_widget removes widget by object name."""
        panel_one = QWidget(parent=basic_dock_area)
        panel_one.setObjectName("panel_one")
        panel_two = QWidget(parent=basic_dock_area)
        panel_two.setObjectName("panel_two")

        basic_dock_area.new(panel_one, return_dock=True)
        basic_dock_area.new(panel_two, return_dock=True)

        assert len(basic_dock_area.dock_list()) == 2
        assert "panel_one" in basic_dock_area.dock_map()
        assert "panel_two" in basic_dock_area.dock_map()

        # Remove panel_one
        result = basic_dock_area.remove_widget("panel_one")
        qtbot.wait(100)

        assert result is True
        assert len(basic_dock_area.dock_list()) == 1
        assert "panel_one" not in basic_dock_area.dock_map()
        assert "panel_two" in basic_dock_area.dock_map()

    def test_manifest_serialization_includes_floating_geometry(
        self, basic_dock_area, qtbot, tmp_path
    ):
        anchored = QWidget(parent=basic_dock_area)
        anchored.setObjectName("anchored_widget")
        floating = QWidget(parent=basic_dock_area)
        floating.setObjectName("floating_widget")

        basic_dock_area.new(anchored, return_dock=True)
        dock_floating = basic_dock_area.new(floating, return_dock=True, start_floating=True)
        qtbot.waitUntil(lambda: dock_floating.isFloating(), timeout=2000)

        settings_path = tmp_path / "manifest.ini"
        settings = QSettings(str(settings_path), QSettings.IniFormat)
        write_manifest(settings, basic_dock_area.dock_list())
        settings.sync()

        manifest_entries = read_manifest(settings)
        assert len(manifest_entries) == 2
        assert manifest_entries[0]["object_name"] == "floating_widget"
        assert manifest_entries[0]["floating"] is True
        assert manifest_entries[0]["floating_relative"] is not None
        assert manifest_entries[1]["object_name"] == "anchored_widget"
        assert manifest_entries[1]["floating"] is False

    def test_splitter_weight_coercion_supports_aliases(self, basic_dock_area):
        weights = {"default": 0.5, "left": 2, "center": 3, "right": 4}

        result = basic_dock_area._coerce_weights(weights, 3, Qt.Orientation.Horizontal)

        assert result == [2.0, 3.0, 4.0]
        assert basic_dock_area._coerce_weights([0.0], 3, Qt.Orientation.Vertical) == [0.0, 1.0, 1.0]
        assert basic_dock_area._coerce_weights([0.0, 0.0], 2, Qt.Orientation.Vertical) == [1.0, 1.0]

    def test_splitter_override_keys_are_normalized(self, basic_dock_area):
        overrides = {0: [1, 2], (1, 0): [3, 4], "2.1": [5], " / ": [6]}

        normalized = basic_dock_area._normalize_override_keys(overrides)

        assert normalized == {(0,): [1, 2], (1, 0): [3, 4], (2, 1): [5], (): [6]}

    def test_schedule_splitter_weights_sets_sizes(self, basic_dock_area, monkeypatch):
        monkeypatch.setattr(QTimer, "singleShot", lambda *_args: _args[-1]())

        class DummySplitter:
            def __init__(self):
                self._children = [object(), object(), object()]
                self.sizes = None
                self.stretch = []

            def count(self):
                return len(self._children)

            def orientation(self):
                return Qt.Orientation.Horizontal

            def width(self):
                return 300

            def height(self):
                return 120

            def setSizes(self, sizes):
                self.sizes = sizes

            def setStretchFactor(self, idx, value):
                self.stretch.append((idx, value))

        splitter = DummySplitter()

        basic_dock_area._schedule_splitter_weights(splitter, [1, 2, 1])

        assert splitter.sizes == [75, 150, 75]
        assert splitter.stretch == [(0, 100), (1, 200), (2, 100)]

    def test_apply_splitter_tree_honors_overrides(self, basic_dock_area, monkeypatch):
        class DummySplitter:
            def __init__(self, orientation, children=None, label="splitter"):
                self._orientation = orientation
                self._children = list(children or [])
                self.label = label

            def count(self):
                return len(self._children)

            def orientation(self):
                return self._orientation

            def widget(self, idx):
                return self._children[idx]

        monkeypatch.setattr(basic_dock_module.QtAds, "CDockSplitter", DummySplitter)

        leaf = DummySplitter(Qt.Orientation.Horizontal, [], label="leaf")
        column_one = DummySplitter(Qt.Orientation.Vertical, [leaf], label="column_one")
        column_zero = DummySplitter(Qt.Orientation.Vertical, [], label="column_zero")
        root = DummySplitter(Qt.Orientation.Horizontal, [column_zero, column_one], label="root")

        calls = []

        def fake_schedule(self, splitter, weights):
            calls.append((splitter.label, weights))

        monkeypatch.setattr(DockAreaWidget, "_schedule_splitter_weights", fake_schedule)

        overrides = {(): ["root_override"], (0,): ["column_override"]}

        basic_dock_area._apply_splitter_tree(
            root, (), horizontal=[1, 2], vertical=[3, 4], overrides=overrides
        )

        assert calls[0] == ("root", ["root_override"])
        assert calls[1] == ("column_zero", ["column_override"])
        assert calls[2] == ("column_one", [3, 4])
        assert calls[3] == ("leaf", ["column_override"])

    def test_set_layout_ratios_normalizes_and_applies(self, basic_dock_area, monkeypatch):
        class DummyContainer:
            def __init__(self, splitter):
                self._splitter = splitter

            def rootSplitter(self):
                return self._splitter

        root_one = object()
        root_two = object()
        containers = [DummyContainer(root_one), DummyContainer(None), DummyContainer(root_two)]

        monkeypatch.setattr(basic_dock_area.dock_manager, "dockContainers", lambda: containers)

        calls = []

        def fake_apply(self, splitter, path, horizontal, vertical, overrides):
            calls.append((splitter, path, horizontal, vertical, overrides))

        monkeypatch.setattr(DockAreaWidget, "_apply_splitter_tree", fake_apply)

        basic_dock_area.set_layout_ratios(
            horizontal=[1, 1, 1], vertical=[2, 3], splitter_overrides={"1/0": [5, 5], "": [9]}
        )

        assert len(calls) == 2
        for splitter, path, horizontal, vertical, overrides in calls:
            assert splitter in {root_one, root_two}
            assert path == ()
            assert horizontal == [1, 1, 1]
            assert vertical == [2, 3]
            assert overrides == {(): [9], (1, 0): [5, 5]}

    def test_show_settings_action_defaults_disabled(self, basic_dock_area):
        widget = QWidget(parent=basic_dock_area)
        widget.setObjectName("settings_default")

        dock = basic_dock_area.new(widget, return_dock=True)

        assert dock._dock_preferences.get("show_settings_action") is False
        assert not hasattr(dock, "setting_action")

    def test_show_settings_action_can_be_enabled(self, basic_dock_area):
        widget = QWidget(parent=basic_dock_area)
        widget.setObjectName("settings_enabled")

        dock = basic_dock_area.new(widget, return_dock=True, show_settings_action=True)

        assert dock._dock_preferences.get("show_settings_action") is True
        assert hasattr(dock, "setting_action")
        assert dock.setting_action.toolTip() == "Dock settings"

    def test_collect_splitter_info_describes_children(self, basic_dock_area, monkeypatch):
        class DummyDockWidget:
            def __init__(self, name):
                self._name = name

            def objectName(self):
                return self._name

        class DummyDockArea:
            def __init__(self, dock_names):
                self._docks = [DummyDockWidget(name) for name in dock_names]

            def dockWidgets(self):
                return self._docks

        class DummySplitter:
            def __init__(self, orientation, children=None):
                self._orientation = orientation
                self._children = list(children or [])

            def orientation(self):
                return self._orientation

            def count(self):
                return len(self._children)

            def widget(self, idx):
                return self._children[idx]

        class Spacer:
            pass

        monkeypatch.setattr(basic_dock_module, "CDockSplitter", DummySplitter)
        monkeypatch.setattr(basic_dock_module, "CDockAreaWidget", DummyDockArea)
        monkeypatch.setattr(basic_dock_module, "CDockWidget", DummyDockWidget)

        nested_splitter = DummySplitter(Qt.Orientation.Horizontal)
        dock_area_child = DummyDockArea(["left", "right"])
        dock_child = DummyDockWidget("solo")
        spacer = Spacer()
        root_splitter = DummySplitter(
            Qt.Orientation.Vertical, [nested_splitter, dock_area_child, dock_child, spacer]
        )

        results = []

        basic_dock_area._collect_splitter_info(root_splitter, (2,), results, container_index=5)

        assert len(results) == 2
        root_entry = results[0]
        assert root_entry["container"] == 5
        assert root_entry["path"] == (2,)
        assert root_entry["orientation"] == "vertical"
        assert root_entry["children"] == [
            {"index": 0, "type": "splitter"},
            {"index": 1, "type": "dock_area", "docks": ["left", "right"]},
            {"index": 2, "type": "dock", "name": "solo"},
            {"index": 3, "type": "Spacer"},
        ]
        nested_entry = results[1]
        assert nested_entry["path"] == (2, 0)
        assert nested_entry["orientation"] == "horizontal"

    def test_describe_layout_aggregates_containers(self, basic_dock_area, monkeypatch):
        class DummyContainer:
            def __init__(self, splitter):
                self._splitter = splitter

            def rootSplitter(self):
                return self._splitter

        containers = [DummyContainer("root0"), DummyContainer(None), DummyContainer("root2")]
        monkeypatch.setattr(basic_dock_area.dock_manager, "dockContainers", lambda: containers)

        calls = []

        def recorder(self, splitter, path, results, container_index):
            entry = {"container": container_index, "splitter": splitter, "path": path}
            results.append(entry)
            calls.append(entry)

        monkeypatch.setattr(DockAreaWidget, "_collect_splitter_info", recorder)

        info = basic_dock_area.describe_layout()

        assert info == calls
        assert [entry["splitter"] for entry in info] == ["root0", "root2"]
        assert [entry["container"] for entry in info] == [0, 2]
        assert all(entry["path"] == () for entry in info)

    def test_print_layout_structure_formats_output(self, basic_dock_area, monkeypatch, capsys):
        entries = [
            {
                "container": 1,
                "path": (0,),
                "orientation": "horizontal",
                "children": [
                    {"index": 0, "type": "dock_area", "docks": ["alpha", "beta"]},
                    {"index": 1, "type": "dock", "name": "solo"},
                    {"index": 2, "type": "splitter"},
                    {"index": 3, "type": "Placeholder"},
                ],
            }
        ]

        monkeypatch.setattr(DockAreaWidget, "describe_layout", lambda self: entries)

        basic_dock_area.print_layout_structure()

        captured = capsys.readouterr().out.strip().splitlines()
        assert captured == [
            "container=1 path=(0,) orientation=horizontal -> "
            "[0:dock_area[alpha, beta], 1:dock(solo), 2:splitter, 3:Placeholder]"
        ]


class TestAdvancedDockAreaInit:
    """Test initialization and basic properties."""

    def test_init(self, advanced_dock_area):
        assert advanced_dock_area is not None
        assert isinstance(advanced_dock_area, AdvancedDockArea)
        assert advanced_dock_area.mode == "creator"
        assert hasattr(advanced_dock_area, "dock_manager")
        assert hasattr(advanced_dock_area, "toolbar")
        assert hasattr(advanced_dock_area, "dark_mode_button")
        assert hasattr(advanced_dock_area, "state_manager")

    def test_rpc_and_plugin_flags(self):
        assert AdvancedDockArea.RPC is True
        assert AdvancedDockArea.PLUGIN is False

    def test_user_access_list(self):
        expected_methods = [
            "new",
            "widget_map",
            "widget_list",
            "lock_workspace",
            "attach_all",
            "delete_all",
        ]
        for method in expected_methods:
            assert method in AdvancedDockArea.USER_ACCESS


class TestDockManagement:
    """Test dock creation, management, and manipulation."""

    def test_new_widget_string(self, advanced_dock_area, qtbot):
        """Test creating a new widget from string."""
        initial_count = len(advanced_dock_area.dock_list())

        # Create a widget by string name
        widget = advanced_dock_area.new("DarkModeButton")

        # Wait for the dock to be created (since it's async)
        qtbot.wait(200)

        # Check that dock was actually created
        assert len(advanced_dock_area.dock_list()) == initial_count + 1

        # Check widget was returned
        assert widget is not None
        assert hasattr(widget, "name_established")

    def test_new_widget_instance(self, advanced_dock_area, qtbot):
        """Test creating dock with existing widget instance."""
        from bec_widgets.widgets.plots.waveform.waveform import Waveform

        initial_count = len(advanced_dock_area.dock_list())

        # Create widget instance
        widget_instance = Waveform(parent=advanced_dock_area, client=advanced_dock_area.client)
        widget_instance.setObjectName("test_widget")

        # Add it to dock area
        result = advanced_dock_area.new(widget_instance)

        # Should return the same instance
        assert result == widget_instance

        qtbot.wait(200)

        assert len(advanced_dock_area.dock_list()) == initial_count + 1

    def test_dock_map(self, advanced_dock_area, qtbot):
        """Test dock_map returns correct mapping."""
        # Initially empty
        dock_map = advanced_dock_area.dock_map()
        assert isinstance(dock_map, dict)
        initial_count = len(dock_map)

        # Create a widget
        advanced_dock_area.new("Waveform")
        qtbot.wait(200)

        # Check dock map updated
        new_dock_map = advanced_dock_area.dock_map()
        assert len(new_dock_map) == initial_count + 1

    def test_dock_list(self, advanced_dock_area, qtbot):
        """Test dock_list returns list of docks."""
        dock_list = advanced_dock_area.dock_list()
        assert isinstance(dock_list, list)
        initial_count = len(dock_list)

        # Create a widget
        advanced_dock_area.new("Waveform")
        qtbot.wait(200)

        # Check dock list updated
        new_dock_list = advanced_dock_area.dock_list()
        assert len(new_dock_list) == initial_count + 1

    def test_widget_map(self, advanced_dock_area, qtbot):
        """Test widget_map returns widget mapping."""
        widget_map = advanced_dock_area.widget_map()
        assert isinstance(widget_map, dict)
        initial_count = len(widget_map)

        # Create a widget
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Check widget map updated
        new_widget_map = advanced_dock_area.widget_map()
        assert len(new_widget_map) == initial_count + 1

    def test_widget_list(self, advanced_dock_area, qtbot):
        """Test widget_list returns list of widgets."""
        widget_list = advanced_dock_area.widget_list()
        assert isinstance(widget_list, list)
        initial_count = len(widget_list)

        # Create a widget
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Check widget list updated
        new_widget_list = advanced_dock_area.widget_list()
        assert len(new_widget_list) == initial_count + 1

    def test_delete_all(self, advanced_dock_area, qtbot):
        """Test delete_all functionality."""
        # Create multiple widgets
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")

        # Wait for docks to be created
        qtbot.wait(200)

        initial_count = len(advanced_dock_area.dock_list())
        assert initial_count >= 2

        # Delete all
        advanced_dock_area.delete_all()

        # Wait for deletion to complete
        qtbot.wait(200)

        # Should have no docks
        assert len(advanced_dock_area.dock_list()) == 0


class TestAdvancedDockSettingsAction:
    """Ensure AdvancedDockArea exposes dock settings actions by default."""

    def test_settings_action_installed_by_default(self, advanced_dock_area):
        widget = QWidget(parent=advanced_dock_area)
        widget.setObjectName("advanced_default_settings")

        dock = advanced_dock_area.new(widget, return_dock=True)

        assert hasattr(dock, "setting_action")
        assert dock.setting_action.toolTip() == "Dock settings"
        assert dock._dock_preferences.get("show_settings_action") is True

    def test_settings_action_can_be_disabled(self, advanced_dock_area):
        widget = QWidget(parent=advanced_dock_area)
        widget.setObjectName("advanced_settings_off")

        dock = advanced_dock_area.new(widget, return_dock=True, show_settings_action=False)

        assert not hasattr(dock, "setting_action")
        assert dock._dock_preferences.get("show_settings_action") is False


class TestWorkspaceLocking:
    """Test workspace locking functionality."""

    def test_lock_workspace_property_getter(self, advanced_dock_area):
        """Test lock_workspace property getter."""
        # Initially unlocked
        assert advanced_dock_area.lock_workspace is False

        # Set locked state directly
        advanced_dock_area._locked = True
        assert advanced_dock_area.lock_workspace is True

    def test_lock_workspace_property_setter(self, advanced_dock_area, qtbot):
        """Test lock_workspace property setter."""
        # Create a dock first
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Initially unlocked
        assert advanced_dock_area.lock_workspace is False

        # Lock workspace
        advanced_dock_area.lock_workspace = True
        assert advanced_dock_area._locked is True
        assert advanced_dock_area.lock_workspace is True

        # Unlock workspace
        advanced_dock_area.lock_workspace = False
        assert advanced_dock_area._locked is False
        assert advanced_dock_area.lock_workspace is False


class TestDeveloperMode:
    """Test developer mode functionality."""

    def test_developer_mode_toggle(self, advanced_dock_area):
        """Test developer mode toggle functionality."""
        # Check initial state
        initial_editable = advanced_dock_area._editable

        # Toggle developer mode
        advanced_dock_area._on_developer_mode_toggled(True)
        assert advanced_dock_area._editable is True
        assert advanced_dock_area.lock_workspace is False

        advanced_dock_area._on_developer_mode_toggled(False)
        assert advanced_dock_area._editable is False
        assert advanced_dock_area.lock_workspace is True

    def test_set_editable(self, advanced_dock_area):
        """Test _set_editable functionality."""
        # Test setting editable to True
        advanced_dock_area._set_editable(True)
        assert advanced_dock_area.lock_workspace is False
        assert advanced_dock_area._editable is True

        # Test setting editable to False
        advanced_dock_area._set_editable(False)
        assert advanced_dock_area.lock_workspace is True
        assert advanced_dock_area._editable is False


class TestToolbarFunctionality:
    """Test toolbar setup and functionality."""

    def test_toolbar_setup(self, advanced_dock_area):
        """Test toolbar is properly set up."""
        assert hasattr(advanced_dock_area, "toolbar")
        assert hasattr(advanced_dock_area, "_ACTION_MAPPINGS")

        # Check that action mappings are properly set
        assert "menu_plots" in advanced_dock_area._ACTION_MAPPINGS
        assert "menu_devices" in advanced_dock_area._ACTION_MAPPINGS
        assert "menu_utils" in advanced_dock_area._ACTION_MAPPINGS

    def test_toolbar_plot_actions(self, advanced_dock_area):
        """Test plot toolbar actions trigger widget creation."""
        plot_actions = [
            "waveform",
            "scatter_waveform",
            "multi_waveform",
            "image",
            "motor_map",
            "heatmap",
        ]

        for action_name in plot_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_plots = advanced_dock_area.toolbar.components.get_action("menu_plots")
                action = menu_plots.actions[action_name].action

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_plots"][action_name][2]

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_toolbar_device_actions(self, advanced_dock_area):
        """Test device toolbar actions trigger widget creation."""
        device_actions = ["scan_control", "positioner_box"]

        for action_name in device_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_devices = advanced_dock_area.toolbar.components.get_action("menu_devices")
                action = menu_devices.actions[action_name].action

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_devices"][action_name][2]

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_toolbar_utils_actions(self, advanced_dock_area):
        """Test utils toolbar actions trigger widget creation."""
        utils_actions = ["queue", "terminal", "status", "progress_bar", "sbb_monitor"]

        for action_name in utils_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_utils = advanced_dock_area.toolbar.components.get_action("menu_utils")
                action = menu_utils.actions[action_name].action

                # Skip log_panel as it's disabled
                if action_name == "log_panel":
                    assert not action.isEnabled()
                    continue

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_utils"][action_name][2]

                action.trigger()
                if action_name == "terminal":
                    mock_new.assert_called_once_with(
                        widget="WebConsole", closable=True, startup_cmd=None
                    )
                else:
                    mock_new.assert_called_once_with(widget=widget_type)

    def test_attach_all_action(self, advanced_dock_area, qtbot):
        """Test attach_all toolbar action."""
        # Create floating docks
        advanced_dock_area.new("DarkModeButton", start_floating=True)
        advanced_dock_area.new("DarkModeButton", start_floating=True)

        qtbot.wait(200)

        initial_floating = len(advanced_dock_area.dock_manager.floatingWidgets())

        # Trigger attach all action
        action = advanced_dock_area.toolbar.components.get_action("attach_all").action
        action.trigger()

        # Wait a bit for the operation
        qtbot.wait(200)

        # Should have fewer or same floating widgets
        final_floating = len(advanced_dock_area.dock_manager.floatingWidgets())
        assert final_floating <= initial_floating

    def test_load_profile_restores_floating_dock(self, advanced_dock_area, qtbot):
        helper = profile_helper(advanced_dock_area)
        settings = helper.open_user("floating_profile")
        settings.clear()

        settings.setValue("profile/created_at", "2025-11-23T00:00:00Z")
        settings.beginWriteArray(SETTINGS_KEYS["manifest"], 2)

        # Floating entry
        settings.setArrayIndex(0)
        settings.setValue("object_name", "FloatingWaveform")
        settings.setValue("widget_class", "DarkModeButton")
        settings.setValue("closable", True)
        settings.setValue("floatable", True)
        settings.setValue("movable", True)
        settings.setValue("floating", True)
        settings.setValue("floating_screen", "")
        settings.setValue("floating_rel_x", 0.1)
        settings.setValue("floating_rel_y", 0.1)
        settings.setValue("floating_rel_w", 0.2)
        settings.setValue("floating_rel_h", 0.2)
        settings.setValue("floating_abs_x", 50)
        settings.setValue("floating_abs_y", 50)
        settings.setValue("floating_abs_w", 200)
        settings.setValue("floating_abs_h", 150)

        # Anchored entry
        settings.setArrayIndex(1)
        settings.setValue("object_name", "EmbeddedWaveform")
        settings.setValue("widget_class", "DarkModeButton")
        settings.setValue("closable", True)
        settings.setValue("floatable", True)
        settings.setValue("movable", True)
        settings.setValue("floating", False)
        settings.setValue("floating_screen", "")
        settings.setValue("floating_rel_x", 0.0)
        settings.setValue("floating_rel_y", 0.0)
        settings.setValue("floating_rel_w", 0.0)
        settings.setValue("floating_rel_h", 0.0)
        settings.setValue("floating_abs_x", 0)
        settings.setValue("floating_abs_y", 0)
        settings.setValue("floating_abs_w", 0)
        settings.setValue("floating_abs_h", 0)
        settings.endArray()
        settings.sync()

        advanced_dock_area.delete_all()
        advanced_dock_area.load_profile("floating_profile")

        qtbot.waitUntil(lambda: "FloatingWaveform" in advanced_dock_area.dock_map(), timeout=3000)
        floating_dock = advanced_dock_area.dock_map()["FloatingWaveform"]
        assert floating_dock.isFloating()

    def test_screenshot_action(self, advanced_dock_area, tmpdir):
        """Test screenshot toolbar action."""
        # Create a test screenshot file path in tmpdir
        screenshot_path = tmpdir.join("test_screenshot.png")

        # Mock the QFileDialog.getSaveFileName to return a test filename
        with mock.patch("bec_widgets.utils.bec_widget.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = (str(screenshot_path), "PNG Files (*.png)")

            # Mock the screenshot.save method
            with mock.patch.object(advanced_dock_area, "grab") as mock_grab:
                mock_screenshot = mock.MagicMock()
                mock_grab.return_value = mock_screenshot

                # Trigger the screenshot action
                action = advanced_dock_area.toolbar.components.get_action("screenshot").action
                action.trigger()

                # Verify the dialog was called
                mock_dialog.assert_called_once()

                # Verify grab was called
                mock_grab.assert_called_once()

                # Verify save was called with the filename
                mock_screenshot.save.assert_called_once_with(str(screenshot_path))


class TestDockSettingsDialog:
    """Test dock settings dialog functionality."""

    def test_dock_settings_dialog_init(self, advanced_dock_area):
        """Test DockSettingsDialog initialization."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget
        mock_widget = DarkModeButton(parent=advanced_dock_area)
        dialog = DockSettingsDialog(advanced_dock_area, mock_widget)

        assert dialog.windowTitle() == "Dock Settings"
        assert dialog.isModal()
        assert hasattr(dialog, "prop_editor")

    def test_open_dock_settings_dialog(self, advanced_dock_area, qtbot):
        """Test opening dock settings dialog."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        # Create a real dock
        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        # Mock dialog exec to avoid blocking
        with patch.object(DockSettingsDialog, "exec") as mock_exec:
            mock_exec.return_value = QDialog.Accepted

            # Call the method
            advanced_dock_area._open_dock_settings_dialog(dock, widget)

            # Verify dialog was created and exec called
            mock_exec.assert_called_once()


class TestSaveProfileDialog:
    """Test save profile dialog functionality."""

    def test_save_profile_dialog_init(self, qtbot):
        """Test SaveProfileDialog initialization."""
        dialog = SaveProfileDialog(None, "test_profile")
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == "Save Workspace Profile"
        assert dialog.isModal()
        assert dialog.name_edit.text() == "test_profile"

    def test_save_profile_dialog_get_values(self, qtbot):
        """Test getting values from SaveProfileDialog."""
        dialog = SaveProfileDialog(None)
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("my_profile")
        dialog.quick_select_checkbox.setChecked(True)

        assert dialog.get_profile_name() == "my_profile"
        assert dialog.is_quick_select() is True

    def test_save_button_enabled_state(self, qtbot):
        """Test save button is enabled/disabled based on name input."""
        dialog = SaveProfileDialog(None)
        qtbot.addWidget(dialog)

        # Initially should be disabled (empty name)
        assert not dialog.save_btn.isEnabled()

        # Should be enabled when name is entered
        dialog.name_edit.setText("test")
        assert dialog.save_btn.isEnabled()

        # Should be disabled when name is cleared
        dialog.name_edit.setText("")
        assert not dialog.save_btn.isEnabled()

    def test_accept_blocks_empty_name(self, qtbot):
        dialog = SaveProfileDialog(None)
        qtbot.addWidget(dialog)
        dialog.name_edit.clear()

        dialog.accept()

        assert dialog.result() == QDialog.Rejected
        assert dialog.overwrite_existing is False

    def test_accept_readonly_suggests_unique_name(self, qtbot, monkeypatch):
        info_calls = []
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda *args, **kwargs: info_calls.append((args, kwargs)) or QMessageBox.Ok,
        )

        dialog = SaveProfileDialog(
            None,
            name_exists=lambda name: name == "readonly_custom",
            profile_origin=lambda name: "module" if name == "readonly" else "unknown",
            origin_label=lambda name: "ModuleDefaults",
        )
        qtbot.addWidget(dialog)
        dialog.name_edit.setText("readonly")

        dialog.accept()

        assert dialog.result() == QDialog.Rejected
        assert dialog.name_edit.text().startswith("readonly_custom")
        assert dialog.overwrite_checkbox.isChecked() is False
        assert info_calls, "Expected informational prompt for read-only profile"

    def test_accept_existing_profile_confirm_yes(self, qtbot, monkeypatch):
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        dialog = SaveProfileDialog(
            None,
            current_profile_name="profile_a",
            name_exists=lambda name: name == "profile_a",
            profile_origin=lambda name: "settings" if name == "profile_a" else "unknown",
        )
        qtbot.addWidget(dialog)
        dialog.name_edit.setText("profile_a")

        dialog.accept()

        assert dialog.result() == QDialog.Accepted
        assert dialog.overwrite_existing is True

    def test_accept_existing_profile_confirm_no(self, qtbot, monkeypatch):
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.No)

        dialog = SaveProfileDialog(
            None,
            current_profile_name="profile_a",
            name_exists=lambda name: False,
            profile_origin=lambda name: "settings" if name == "profile_a" else "unknown",
        )
        qtbot.addWidget(dialog)
        dialog.name_edit.setText("profile_a")

        dialog.accept()

        assert dialog.result() == QDialog.Rejected
        assert dialog.name_edit.text().startswith("profile_a_custom")
        assert dialog.overwrite_existing is False
        assert dialog.overwrite_checkbox.isChecked() is False

    def test_overwrite_toggle_sets_and_restores_name(self, qtbot):
        dialog = SaveProfileDialog(
            None, current_name="custom_name", current_profile_name="existing_profile"
        )
        qtbot.addWidget(dialog)

        dialog.overwrite_checkbox.setChecked(True)
        assert dialog.name_edit.text() == "existing_profile"
        dialog.name_edit.setText("existing_profile")
        dialog.overwrite_checkbox.setChecked(False)
        assert dialog.name_edit.text() == "custom_name"


class TestPreviewPanel:
    """Test preview panel scaling behavior."""

    def test_preview_panel_without_pixmap(self, qtbot):
        panel = PreviewPanel("Current", None)
        qtbot.addWidget(panel)
        assert "No preview available" in panel.image_label.text()

    def test_preview_panel_with_pixmap(self, qtbot):
        pixmap = QPixmap(40, 20)
        pixmap.fill(Qt.red)
        panel = PreviewPanel("Current", pixmap)
        qtbot.addWidget(panel)
        assert panel.image_label.pixmap() is not None

    def test_preview_panel_set_pixmap_resets_placeholder(self, qtbot):
        panel = PreviewPanel("Current", None)
        qtbot.addWidget(panel)
        pixmap = QPixmap(30, 30)
        pixmap.fill(Qt.blue)
        panel.setPixmap(pixmap)
        assert panel.image_label.pixmap() is not None
        panel.setPixmap(None)
        assert panel.image_label.pixmap() is None or panel.image_label.pixmap().isNull()
        assert "No preview available" in panel.image_label.text()


class TestRestoreProfileDialog:
    """Test restore dialog confirmation flow."""

    def test_confirm_accepts(self, monkeypatch):
        monkeypatch.setattr(RestoreProfileDialog, "exec", lambda self: QDialog.Accepted)
        assert RestoreProfileDialog.confirm(None, QPixmap(), QPixmap()) is True

    def test_confirm_rejects(self, monkeypatch):
        monkeypatch.setattr(RestoreProfileDialog, "exec", lambda self: QDialog.Rejected)
        assert RestoreProfileDialog.confirm(None, QPixmap(), QPixmap()) is False


class TestProfileInfoAndScreenshots:
    """Tests for profile utilities metadata and screenshot helpers."""

    PNG_BYTES = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAACXBIWXMAAA9hAAAPYQGoP6dpAAAAFUlEQVQYlWP8//8/A27AhEduBEsDAKXjAxHmByO3AAAAAElFTkSuQmCC"
    )

    def _write_manifest(self, settings, count=2):
        settings.beginWriteArray(profile_utils.SETTINGS_KEYS["manifest"], count)
        for i in range(count):
            settings.setArrayIndex(i)
            settings.setValue("object_name", f"widget_{i}")
            settings.setValue("widget_class", "Dummy")
            settings.setValue("closable", True)
            settings.setValue("floatable", True)
            settings.setValue("movable", True)
        settings.endArray()
        settings.sync()

    def test_get_profile_info_user_origin(self, temp_profile_dir):
        name = "info_user"
        settings = open_user_settings(name)
        settings.setValue(profile_utils.SETTINGS_KEYS["created_at"], "2023-01-01T00:00:00Z")
        settings.setValue("profile/author", "Custom")
        set_quick_select(name, True)
        self._write_manifest(settings, count=3)

        info = get_profile_info(name)

        assert info.name == name
        assert info.origin == "settings"
        assert info.is_read_only is False
        assert info.is_quick_select is True
        assert info.widget_count == 3
        assert info.author == "User"
        assert info.user_path.endswith(f"{name}.ini")
        assert info.size_kb >= 0

    def test_get_profile_info_default_only(self, temp_profile_dir):
        name = "info_default"
        settings = open_default_settings(name)
        self._write_manifest(settings, count=1)

        user_path = user_profile_path(name)
        if os.path.exists(user_path):
            os.remove(user_path)

        info = get_profile_info(name)

        assert info.origin == "settings"
        assert info.user_path.endswith(f"{name}.ini")
        assert info.widget_count == 1

    def test_get_profile_info_module_readonly(self, module_profile_factory):
        name = module_profile_factory("info_readonly")
        info = get_profile_info(name)
        assert info.origin == "module"
        assert info.is_read_only is True
        assert info.author == "BEC Widgets"

    def test_get_profile_info_unknown_profile(self):
        name = "nonexistent_profile"
        if os.path.exists(user_profile_path(name)):
            os.remove(user_profile_path(name))
        if os.path.exists(default_profile_path(name)):
            os.remove(default_profile_path(name))

        info = get_profile_info(name)

        assert info.origin == "unknown"
        assert info.is_read_only is False
        assert info.widget_count == 0

    def test_load_user_profile_screenshot(self, temp_profile_dir):
        name = "user_screenshot"
        settings = open_user_settings(name)
        settings.setValue(profile_utils.SETTINGS_KEYS["screenshot"], self.PNG_BYTES)
        settings.sync()

        pix = load_user_profile_screenshot(name)

        assert pix is not None and not pix.isNull()

    def test_load_default_profile_screenshot(self, temp_profile_dir):
        name = "default_screenshot"
        settings = open_default_settings(name)
        settings.setValue(profile_utils.SETTINGS_KEYS["screenshot"], self.PNG_BYTES)
        settings.sync()

        pix = load_default_profile_screenshot(name)

        assert pix is not None and not pix.isNull()

    def test_load_screenshot_from_settings_invalid(self, temp_profile_dir):
        name = "invalid_screenshot"
        settings = open_user_settings(name)
        settings.setValue(profile_utils.SETTINGS_KEYS["screenshot"], "not-an-image")
        settings.sync()

        pix = profile_utils._load_screenshot_from_settings(settings)

        assert pix is None

    def test_load_screenshot_from_settings_bytes(self, temp_profile_dir):
        name = "bytes_screenshot"
        settings = open_user_settings(name)
        settings.setValue(profile_utils.SETTINGS_KEYS["screenshot"], self.PNG_BYTES)
        settings.sync()

        pix = profile_utils._load_screenshot_from_settings(settings)

        assert pix is not None and not pix.isNull()


class TestWorkSpaceManager:
    """Test workspace manager interactions."""

    @staticmethod
    def _create_profiles(names):
        for name in names:
            settings = open_user_settings(name)
            settings.setValue("meta", "value")
            settings.sync()

    def test_render_table_populates_rows(self, qtbot):
        profile_names = ["profile_a", "profile_b"]
        self._create_profiles(profile_names)

        manager = WorkSpaceManager(target_widget=None)
        qtbot.addWidget(manager)

        assert manager.profile_table.rowCount() >= len(profile_names)

    def test_switch_profile_updates_target(self, qtbot, workspace_manager_target):
        name = "profile_switch"
        self._create_profiles([name])
        target = workspace_manager_target()
        manager = WorkSpaceManager(target_widget=target)
        qtbot.addWidget(manager)

        manager.switch_profile(name)

        assert target.load_profile_calls == [name]
        assert target._combo.current_text == name
        assert manager._current_selected_profile() == name

    def test_toggle_quick_select_updates_flag(self, qtbot, workspace_manager_target):
        name = "profile_toggle"
        self._create_profiles([name])
        target = workspace_manager_target()
        manager = WorkSpaceManager(target_widget=target)
        qtbot.addWidget(manager)

        initial = is_quick_select(name)
        manager.toggle_quick_select(name)

        assert is_quick_select(name) is (not initial)
        assert target.refresh_calls >= 1

    def test_save_current_as_profile_with_target(self, qtbot, workspace_manager_target):
        name = "profile_save"
        self._create_profiles([name])
        target = workspace_manager_target()
        target._current_profile_name = name
        manager = WorkSpaceManager(target_widget=target)
        qtbot.addWidget(manager)

        manager.save_current_as_profile()

        assert target.save_called is True
        assert manager._current_selected_profile() == name

    def test_delete_profile_removes_files(self, qtbot, workspace_manager_target, monkeypatch):
        name = "profile_delete"
        self._create_profiles([name])
        target = workspace_manager_target()
        target._current_profile_name = name
        manager = WorkSpaceManager(target_widget=target)
        qtbot.addWidget(manager)

        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

        manager.delete_profile(name)

        assert not os.path.exists(user_profile_path(name))
        assert target.refresh_calls >= 1

    def test_delete_readonly_profile_shows_message(
        self, qtbot, workspace_manager_target, module_profile_factory, monkeypatch
    ):
        readonly = module_profile_factory("readonly_delete")
        list_profiles()
        monkeypatch.setattr(
            profile_utils,
            "get_profile_info",
            lambda *a, **k: profile_utils.ProfileInfo(name=readonly, is_read_only=True),
        )
        info_calls = []
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda *args, **kwargs: info_calls.append((args, kwargs)) or QMessageBox.Ok,
        )
        manager = WorkSpaceManager(target_widget=workspace_manager_target())
        qtbot.addWidget(manager)

        manager.delete_profile(readonly)

        assert info_calls, "Expected informational prompt for read-only profile"


class TestAdvancedDockAreaRestoreAndDialogs:
    """Additional coverage for restore flows and workspace dialogs."""

    def test_restore_user_profile_from_default_confirm_true(self, advanced_dock_area, monkeypatch):
        profile_name = "profile_restore_true"
        helper = profile_helper(advanced_dock_area)
        helper.open_default(profile_name).sync()
        helper.open_user(profile_name).sync()
        advanced_dock_area._current_profile_name = profile_name
        advanced_dock_area.isVisible = lambda: False
        pix = QPixmap(8, 8)
        pix.fill(Qt.red)
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.load_user_profile_screenshot",
            lambda name, namespace=None: pix,
        )
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.load_default_profile_screenshot",
            lambda name, namespace=None: pix,
        )
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.RestoreProfileDialog.confirm",
            lambda *args, **kwargs: True,
        )

        with (
            patch(
                "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.restore_user_from_default"
            ) as mock_restore,
            patch.object(advanced_dock_area, "delete_all") as mock_delete_all,
            patch.object(advanced_dock_area, "load_profile") as mock_load_profile,
        ):
            advanced_dock_area.restore_user_profile_from_default()

        assert mock_restore.call_count == 1
        args, kwargs = mock_restore.call_args
        assert args == (profile_name,)
        assert kwargs.get("namespace") == advanced_dock_area.profile_namespace
        mock_delete_all.assert_called_once()
        mock_load_profile.assert_called_once_with(profile_name)

    def test_restore_user_profile_from_default_confirm_false(self, advanced_dock_area, monkeypatch):
        profile_name = "profile_restore_false"
        helper = profile_helper(advanced_dock_area)
        helper.open_default(profile_name).sync()
        helper.open_user(profile_name).sync()
        advanced_dock_area._current_profile_name = profile_name
        advanced_dock_area.isVisible = lambda: False
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.load_user_profile_screenshot",
            lambda name: QPixmap(),
        )
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.load_default_profile_screenshot",
            lambda name: QPixmap(),
        )
        monkeypatch.setattr(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.RestoreProfileDialog.confirm",
            lambda *args, **kwargs: False,
        )

        with patch(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.restore_user_from_default"
        ) as mock_restore:
            advanced_dock_area.restore_user_profile_from_default()

        mock_restore.assert_not_called()

    def test_restore_user_profile_from_default_no_target(self, advanced_dock_area, monkeypatch):
        advanced_dock_area._current_profile_name = None
        with patch(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.RestoreProfileDialog.confirm"
        ) as mock_confirm:
            advanced_dock_area.restore_user_profile_from_default()
        mock_confirm.assert_not_called()

    def test_refresh_workspace_list_with_refresh_profiles(self, advanced_dock_area):
        profile_name = "refresh_profile"
        helper = profile_helper(advanced_dock_area)
        helper.open_user(profile_name).sync()
        advanced_dock_area._current_profile_name = profile_name
        combo = advanced_dock_area.toolbar.components.get_action("workspace_combo").widget
        combo.refresh_profiles = MagicMock()

        advanced_dock_area._refresh_workspace_list()

        combo.refresh_profiles.assert_called_once_with(profile_name)

    def test_refresh_workspace_list_fallback(self, advanced_dock_area):
        class ComboStub:
            def __init__(self):
                self.items = []
                self.tooltip = ""
                self.block_calls = []
                self.cleared = False
                self.current_index = -1

            def blockSignals(self, value):
                self.block_calls.append(value)

            def clear(self):
                self.items.clear()
                self.cleared = True

            def addItems(self, items):
                self.items.extend(items)

            def findText(self, text):
                try:
                    return self.items.index(text)
                except ValueError:
                    return -1

            def setCurrentIndex(self, idx):
                self.current_index = idx

            def setToolTip(self, text):
                self.tooltip = text

        active = "active_profile"
        quick = "quick_profile"
        helper = profile_helper(advanced_dock_area)
        helper.open_user(active).sync()
        helper.open_user(quick).sync()
        helper.set_quick_select(quick, True)

        combo_stub = ComboStub()

        class StubAction:
            def __init__(self, widget):
                self.widget = widget

        with patch.object(
            advanced_dock_area.toolbar.components, "get_action", return_value=StubAction(combo_stub)
        ):
            advanced_dock_area._current_profile_name = active
            advanced_dock_area._refresh_workspace_list()

        assert combo_stub.block_calls == [True, False]
        assert combo_stub.items[0] == active
        assert combo_stub.tooltip == "Active profile is not in quick select"

    def test_show_workspace_manager_creates_dialog(self, qtbot, advanced_dock_area):
        action = advanced_dock_area.toolbar.components.get_action("manage_workspaces").action
        assert not action.isChecked()

        advanced_dock_area._current_profile_name = "manager_profile"
        helper = profile_helper(advanced_dock_area)
        helper.open_user("manager_profile").sync()

        advanced_dock_area.show_workspace_manager()

        assert advanced_dock_area.manage_dialog is not None
        assert advanced_dock_area.manage_dialog.isVisible()
        assert action.isChecked()
        assert isinstance(advanced_dock_area.manage_widget, WorkSpaceManager)

        advanced_dock_area.manage_dialog.close()
        qtbot.waitUntil(lambda: advanced_dock_area.manage_dialog is None)
        assert not action.isChecked()

    def test_manage_dialog_closed(self, advanced_dock_area):
        widget_mock = MagicMock()
        dialog_mock = MagicMock()
        advanced_dock_area.manage_widget = widget_mock
        advanced_dock_area.manage_dialog = dialog_mock
        action = advanced_dock_area.toolbar.components.get_action("manage_workspaces").action
        action.setChecked(True)

        advanced_dock_area._manage_dialog_closed()

        widget_mock.close.assert_called_once()
        widget_mock.deleteLater.assert_called_once()
        dialog_mock.deleteLater.assert_called_once()
        assert advanced_dock_area.manage_dialog is None
        assert not action.isChecked()


class TestProfileManagement:
    """Test profile management functionality."""

    def test_profile_path(self, temp_profile_dir):
        """Test profile path generation."""
        path = user_profile_path("test_profile")
        expected = os.path.join(temp_profile_dir, "user", "test_profile.ini")
        assert path == expected

        default_path = default_profile_path("test_profile")
        expected_default = os.path.join(temp_profile_dir, "default", "test_profile.ini")
        assert default_path == expected_default

    def test_open_settings(self, temp_profile_dir):
        """Test opening settings for a profile."""
        settings = open_user_settings("test_profile")
        assert isinstance(settings, QSettings)

    def test_list_profiles_empty(self, temp_profile_dir):
        """Test listing profiles when directory is empty."""
        try:
            module_defaults = {
                os.path.splitext(f)[0]
                for f in os.listdir(profile_utils.module_profiles_dir())
                if f.endswith(".ini")
            }
        except FileNotFoundError:
            module_defaults = set()
        profiles = list_profiles()
        assert module_defaults.issubset(set(profiles))

    def test_list_profiles_with_files(self, temp_profile_dir):
        """Test listing profiles with existing files."""
        # Create some test profile files
        profile_names = ["profile1", "profile2", "profile3"]
        for name in profile_names:
            settings = open_user_settings(name)
            settings.setValue("test", "value")
            settings.sync()

        profiles = list_profiles()
        for name in profile_names:
            assert name in profiles

    def test_readonly_profile_operations(self, temp_profile_dir, module_profile_factory):
        """Test read-only profile functionality."""
        profile_name = "user_profile"

        # Initially should not be read-only
        assert not is_profile_read_only(profile_name)

        # Create a user profile and ensure it's writable
        settings = open_user_settings(profile_name)
        settings.setValue("test", "value")
        settings.sync()
        assert not is_profile_read_only(profile_name)

        # Verify a bundled module profile is detected as read-only
        readonly_name = module_profile_factory("module_default")
        assert is_profile_read_only(readonly_name)

    def test_write_and_read_manifest(self, temp_profile_dir, advanced_dock_area, qtbot):
        """Test writing and reading dock manifest."""
        settings = open_user_settings("test_manifest")

        # Create real docks
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")

        # Wait for docks to be created
        qtbot.wait(1000)

        docks = advanced_dock_area.dock_list()

        # Write manifest
        write_manifest(settings, docks)
        settings.sync()

        # Read manifest
        items = read_manifest(settings)

        assert len(items) >= 3
        for item in items:
            assert "object_name" in item
            assert "widget_class" in item
            assert "closable" in item
            assert "floatable" in item
            assert "movable" in item

    def test_restore_preserves_quick_select(self, temp_profile_dir):
        """Ensure restoring keeps the quick select flag when it was enabled."""
        profile_name = "restorable_profile"
        default_settings = open_default_settings(profile_name)
        default_settings.setValue("test", "default")
        default_settings.sync()

        user_settings = open_user_settings(profile_name)
        user_settings.setValue("test", "user")
        user_settings.sync()

        set_quick_select(profile_name, True)
        assert is_quick_select(profile_name)

        restore_user_from_default(profile_name)

        assert is_quick_select(profile_name)


class TestWorkspaceProfileOperations:
    """Test workspace profile save/load/delete operations."""

    def test_save_profile_readonly_conflict(
        self, advanced_dock_area, temp_profile_dir, module_profile_factory
    ):
        """Test saving profile when read-only profile exists."""
        profile_name = module_profile_factory("readonly_profile")
        new_profile = f"{profile_name}_custom"
        helper = profile_helper(advanced_dock_area)
        target_path = helper.user_path(new_profile)
        if os.path.exists(target_path):
            os.remove(target_path)

        class StubDialog:
            def __init__(self, *args, **kwargs):
                self.overwrite_existing = False

            def exec(self):
                return QDialog.Accepted

            def get_profile_name(self):
                return new_profile

            def is_quick_select(self):
                return False

        with patch(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.SaveProfileDialog",
            StubDialog,
        ):
            advanced_dock_area.save_profile(profile_name, show_dialog=True)

        assert os.path.exists(target_path)

    def test_load_profile_with_manifest(self, advanced_dock_area, temp_profile_dir, qtbot):
        """Test loading profile with widget manifest."""
        profile_name = "test_load_profile"
        helper = profile_helper(advanced_dock_area)

        # Create a profile with manifest
        settings = helper.open_user(profile_name)
        settings.beginWriteArray("manifest/widgets", 1)
        settings.setArrayIndex(0)
        settings.setValue("object_name", "test_widget")
        settings.setValue("widget_class", "DarkModeButton")
        settings.setValue("closable", True)
        settings.setValue("floatable", True)
        settings.setValue("movable", True)
        settings.endArray()
        settings.sync()

        # Load profile
        advanced_dock_area.load_profile(profile_name)

        # Wait for widget to be created
        qtbot.wait(1000)

        # Check widget was created
        widget_map = advanced_dock_area.widget_map()
        assert "test_widget" in widget_map

    def test_save_as_skips_autosave_source_profile(
        self, advanced_dock_area, temp_profile_dir, qtbot
    ):
        """Saving a new profile avoids overwriting the source profile during the switch."""
        source_profile = "autosave_source"
        new_profile = "autosave_new"
        helper = profile_helper(advanced_dock_area)

        settings = helper.open_user(source_profile)
        settings.beginWriteArray("manifest/widgets", 1)
        settings.setArrayIndex(0)
        settings.setValue("object_name", "source_widget")
        settings.setValue("widget_class", "DarkModeButton")
        settings.setValue("closable", True)
        settings.setValue("floatable", True)
        settings.setValue("movable", True)
        settings.endArray()
        settings.sync()

        advanced_dock_area.load_profile(source_profile)
        qtbot.wait(500)
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(500)

        class StubDialog:
            def __init__(self, *args, **kwargs):
                self.overwrite_existing = False

            def exec(self):
                return QDialog.Accepted

            def get_profile_name(self):
                return new_profile

            def is_quick_select(self):
                return False

        with patch(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.SaveProfileDialog",
            StubDialog,
        ):
            advanced_dock_area.save_profile(show_dialog=True)

        qtbot.wait(500)
        source_manifest = read_manifest(helper.open_user(source_profile))
        new_manifest = read_manifest(helper.open_user(new_profile))

        assert len(source_manifest) == 1
        assert len(new_manifest) == 2

    def test_switch_autosaves_previous_profile(self, advanced_dock_area, temp_profile_dir, qtbot):
        """Regular profile switches should persist the outgoing layout."""
        profile_a = "autosave_keep"
        profile_b = "autosave_target"
        helper = profile_helper(advanced_dock_area)

        for profile in (profile_a, profile_b):
            settings = helper.open_user(profile)
            settings.beginWriteArray("manifest/widgets", 1)
            settings.setArrayIndex(0)
            settings.setValue("object_name", f"{profile}_widget")
            settings.setValue("widget_class", "DarkModeButton")
            settings.setValue("closable", True)
            settings.setValue("floatable", True)
            settings.setValue("movable", True)
            settings.endArray()
            settings.sync()

        advanced_dock_area.load_profile(profile_a)
        qtbot.wait(500)
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(500)

        advanced_dock_area.load_profile(profile_b)
        qtbot.wait(500)

        manifest_a = read_manifest(helper.open_user(profile_a))
        assert len(manifest_a) == 2

    def test_delete_profile_readonly(
        self, advanced_dock_area, temp_profile_dir, module_profile_factory
    ):
        """Test deleting bundled profile removes only the writable copy."""
        profile_name = module_profile_factory("readonly_profile")
        helper = profile_helper(advanced_dock_area)
        helper.list_profiles()  # ensure default and user copies are materialized
        helper.open_default(profile_name).sync()
        settings = helper.open_user(profile_name)
        settings.setValue("test", "value")
        settings.sync()
        user_path = helper.user_path(profile_name)
        default_path = helper.default_path(profile_name)
        assert os.path.exists(user_path)
        assert os.path.exists(default_path)

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.currentText.return_value = profile_name
            mock_get_action.return_value.widget = mock_combo

            with (
                patch(
                    "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.question",
                    return_value=QMessageBox.Yes,
                ) as mock_question,
                patch(
                    "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.information",
                    return_value=None,
                ) as mock_info,
            ):
                advanced_dock_area.delete_profile(show_dialog=True)

                mock_question.assert_not_called()
                mock_info.assert_called_once()
                # Read-only profile should remain intact (user + default copies)
                assert os.path.exists(user_path)
                assert os.path.exists(default_path)

    def test_delete_profile_success(self, advanced_dock_area, temp_profile_dir):
        """Test successful profile deletion."""
        profile_name = "deletable_profile"
        helper = profile_helper(advanced_dock_area)

        # Create regular profile
        settings = helper.open_user(profile_name)
        settings.setValue("test", "value")
        settings.sync()
        user_path = helper.user_path(profile_name)
        assert os.path.exists(user_path)

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.currentText.return_value = profile_name
            mock_get_action.return_value.widget = mock_combo

            with patch(
                "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.question"
            ) as mock_question:
                mock_question.return_value = QMessageBox.Yes

                with patch.object(advanced_dock_area, "_refresh_workspace_list") as mock_refresh:
                    advanced_dock_area.delete_profile(show_dialog=True)

                    mock_question.assert_called_once()
                    mock_refresh.assert_called_once()
                    # Profile should be deleted
                    assert not os.path.exists(user_path)

    def test_delete_profile_cli_usage(self, advanced_dock_area, temp_profile_dir):
        """Test delete_profile with explicit name (CLI usage - no dialog by default)."""
        profile_name = "cli_deletable_profile"
        helper = profile_helper(advanced_dock_area)

        # Create regular profile
        settings = helper.open_user(profile_name)
        settings.setValue("test", "value")
        settings.sync()
        user_path = helper.user_path(profile_name)
        assert os.path.exists(user_path)

        # Delete without dialog (CLI usage - default behavior)
        result = advanced_dock_area.delete_profile(profile_name)

        assert result is True
        assert not os.path.exists(user_path)

    def test_refresh_workspace_list(self, advanced_dock_area, temp_profile_dir):
        """Test refreshing workspace list."""
        # Create some profiles
        helper = profile_helper(advanced_dock_area)
        for name in ["profile1", "profile2"]:
            settings = helper.open_user(name)
            settings.setValue("test", "value")
            settings.sync()

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.refresh_profiles = MagicMock()
            mock_get_action.return_value.widget = mock_combo

            advanced_dock_area._refresh_workspace_list()

            mock_combo.refresh_profiles.assert_called_once()


class TestCleanupAndMisc:
    """Test cleanup and miscellaneous functionality."""

    def test_delete_dock(self, advanced_dock_area, qtbot):
        """Test _delete_dock functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        initial_count = len(advanced_dock_area.dock_list())

        # Delete the dock
        advanced_dock_area._delete_dock(dock)

        # Wait for deletion to complete
        qtbot.wait(200)

        # Verify dock was removed
        assert len(advanced_dock_area.dock_list()) == initial_count - 1

    def test_apply_dock_lock(self, advanced_dock_area, qtbot):
        """Test _apply_dock_lock functionality."""
        # Create a dock first
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Test locking
        advanced_dock_area._apply_dock_lock(True)
        # No assertion needed - just verify it doesn't crash

        # Test unlocking
        advanced_dock_area._apply_dock_lock(False)
        # No assertion needed - just verify it doesn't crash

    def test_make_dock(self, advanced_dock_area):
        """Test _make_dock functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        initial_count = len(advanced_dock_area.dock_list())

        # Create dock
        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        # Verify dock was created
        assert dock is not None
        assert len(advanced_dock_area.dock_list()) == initial_count + 1
        assert dock.widget() == widget

    def test_install_dock_settings_action(self, advanced_dock_area):
        """Test _install_dock_settings_action functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        with patch.object(advanced_dock_area, "_open_dock_settings_dialog") as mock_open_dialog:
            dock = advanced_dock_area._make_dock(
                widget, closable=True, floatable=True, movable=True
            )

            # Verify dock has settings action
            assert hasattr(dock, "setting_action")
            assert dock.setting_action is not None
            assert dock.setting_action.toolTip() == "Dock settings"

            dock.setting_action.trigger()
            mock_open_dialog.assert_called_once_with(dock, widget)


class TestModeSwitching:
    """Test mode switching functionality."""

    def test_mode_property_setter_valid_modes(self, advanced_dock_area):
        """Test setting valid modes."""
        valid_modes = ["plot", "device", "utils", "creator", "user"]

        for mode in valid_modes:
            advanced_dock_area.mode = mode
            assert advanced_dock_area.mode == mode

    def test_mode_changed_signal_emission(self, advanced_dock_area, qtbot):
        """Test that mode_changed signal is emitted when mode changes."""
        # Set up signal spy
        with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
            advanced_dock_area.mode = "plot"

        # Check signal was emitted with correct argument
        assert blocker.args == ["plot"]


class TestToolbarModeBundles:
    """Test toolbar bundle creation and visibility for different modes."""

    def test_flat_bundles_created(self, advanced_dock_area):
        """Test that flat bundles are created during toolbar setup."""
        # Check that flat bundles exist
        assert "flat_plots" in advanced_dock_area.toolbar.bundles
        assert "flat_devices" in advanced_dock_area.toolbar.bundles
        assert "flat_utils" in advanced_dock_area.toolbar.bundles

    def test_plot_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in plot mode."""
        advanced_dock_area.mode = "plot"

        # Should show only flat_plots bundle (and essential bundles in real implementation)
        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_plots" in shown_bundles

        # Should not show other flat bundles
        assert "flat_devices" not in shown_bundles
        assert "flat_utils" not in shown_bundles

        # Should not show menu bundles
        assert "menu_plots" not in shown_bundles
        assert "menu_devices" not in shown_bundles
        assert "menu_utils" not in shown_bundles

    def test_device_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in device mode."""
        advanced_dock_area.mode = "device"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_devices" in shown_bundles

        # Should not show other flat bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_utils" not in shown_bundles

    def test_utils_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in utils mode."""
        advanced_dock_area.mode = "utils"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_utils" in shown_bundles

        # Should not show other flat bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_devices" not in shown_bundles

    def test_developer_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in developer mode."""
        advanced_dock_area.mode = "creator"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles

        # Should show menu bundles
        assert "menu_plots" in shown_bundles
        assert "menu_devices" in shown_bundles
        assert "menu_utils" in shown_bundles

        # Should show essential bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

    def test_user_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in user mode."""
        advanced_dock_area.mode = "user"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles

        # Should show only essential bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

        # Should not show any widget creation bundles
        assert "menu_plots" not in shown_bundles
        assert "menu_devices" not in shown_bundles
        assert "menu_utils" not in shown_bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_devices" not in shown_bundles
        assert "flat_utils" not in shown_bundles


class TestFlatToolbarActions:
    """Test flat toolbar actions functionality."""

    def test_flat_plot_actions_created(self, advanced_dock_area):
        """Test that flat plot actions are created."""
        plot_actions = [
            "flat_waveform",
            "flat_scatter_waveform",
            "flat_multi_waveform",
            "flat_image",
            "flat_motor_map",
            "flat_heatmap",
        ]

        for action_name in plot_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_device_actions_created(self, advanced_dock_area):
        """Test that flat device actions are created."""
        device_actions = ["flat_scan_control", "flat_positioner_box"]

        for action_name in device_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_utils_actions_created(self, advanced_dock_area):
        """Test that flat utils actions are created."""
        utils_actions = [
            "flat_queue",
            "flat_status",
            "flat_progress_bar",
            "flat_terminal",
            "flat_bec_shell",
            "flat_log_panel",
            "flat_sbb_monitor",
        ]

        for action_name in utils_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_plot_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat plot actions trigger widget creation."""
        plot_action_mapping = {
            "flat_waveform": "Waveform",
            "flat_scatter_waveform": "ScatterWaveform",
            "flat_multi_waveform": "MultiWaveform",
            "flat_image": "Image",
            "flat_motor_map": "MotorMap",
            "flat_heatmap": "Heatmap",
        }

        for action_name, widget_type in plot_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action
                action.trigger()
                mock_new.assert_called_once_with(widget_type)

    def test_flat_device_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat device actions trigger widget creation."""
        device_action_mapping = {
            "flat_scan_control": "ScanControl",
            "flat_positioner_box": "PositionerBox",
        }

        for action_name, widget_type in device_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action
                action.trigger()
                mock_new.assert_called_once_with(widget_type)

    def test_flat_utils_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat utils actions trigger widget creation."""
        utils_action_mapping = {
            "flat_queue": "BECQueue",
            "flat_status": "BECStatusBox",
            "flat_progress_bar": "RingProgressBar",
            "flat_terminal": "WebConsole",
            "flat_bec_shell": "WebConsole",
            "flat_sbb_monitor": "SBBMonitor",
        }

        for action_name, widget_type in utils_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action

                # Skip log_panel as it's disabled
                if action_name == "flat_log_panel":
                    assert not action.isEnabled()
                    continue

                action.trigger()
                mock_new.assert_called_once_with(widget_type)

    def test_flat_log_panel_action_disabled(self, advanced_dock_area):
        """Test that flat log panel action is disabled."""
        action = advanced_dock_area.toolbar.components.get_action("flat_log_panel").action
        assert not action.isEnabled()


class TestModeTransitions:
    """Test mode transitions and state consistency."""

    def test_mode_transition_sequence(self, advanced_dock_area, qtbot):
        """Test sequence of mode transitions."""
        modes = ["plot", "device", "utils", "creator", "user"]

        for mode in modes:
            with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
                advanced_dock_area.mode = mode

            assert advanced_dock_area.mode == mode
            assert blocker.args == [mode]

    def test_mode_consistency_after_multiple_changes(self, advanced_dock_area):
        """Test mode consistency after multiple rapid changes."""
        # Rapidly change modes
        advanced_dock_area.mode = "plot"
        advanced_dock_area.mode = "device"
        advanced_dock_area.mode = "utils"
        advanced_dock_area.mode = "creator"
        advanced_dock_area.mode = "user"

        # Final state should be consistent
        assert advanced_dock_area.mode == "user"

        # Toolbar should show correct bundles for user mode
        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

    def test_toolbar_refresh_on_mode_change(self, advanced_dock_area):
        """Test that toolbar is properly refreshed when mode changes."""
        initial_bundles = set(advanced_dock_area.toolbar.shown_bundles)

        # Change to a different mode
        advanced_dock_area.mode = "plot"
        plot_bundles = set(advanced_dock_area.toolbar.shown_bundles)

        # Bundles should be different
        assert initial_bundles != plot_bundles
        assert "flat_plots" in plot_bundles

    def test_mode_switching_preserves_existing_docks(self, advanced_dock_area, qtbot):
        """Test that mode switching doesn't affect existing docked widgets."""
        # Create some widgets
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        initial_dock_count = len(advanced_dock_area.dock_list())
        initial_widget_count = len(advanced_dock_area.widget_list())

        # Switch modes
        advanced_dock_area.mode = "plot"
        advanced_dock_area.mode = "device"
        advanced_dock_area.mode = "user"

        # Dock and widget counts should remain the same
        assert len(advanced_dock_area.dock_list()) == initial_dock_count
        assert len(advanced_dock_area.widget_list()) == initial_widget_count


class TestModeProperty:
    """Test mode property getter and setter behavior."""

    def test_mode_property_getter(self, advanced_dock_area):
        """Test mode property getter returns correct value."""
        # Set internal mode directly and test getter
        advanced_dock_area._mode = "plot"
        assert advanced_dock_area.mode == "plot"

        advanced_dock_area._mode = "device"
        assert advanced_dock_area.mode == "device"

    def test_mode_property_setter_updates_internal_state(self, advanced_dock_area):
        """Test mode property setter updates internal state."""
        advanced_dock_area.mode = "plot"
        assert advanced_dock_area._mode == "plot"

        advanced_dock_area.mode = "utils"
        assert advanced_dock_area._mode == "utils"

    def test_mode_property_setter_triggers_toolbar_update(self, advanced_dock_area):
        """Test mode property setter triggers toolbar update."""
        with patch.object(advanced_dock_area.toolbar, "show_bundles") as mock_show_bundles:
            advanced_dock_area.mode = "plot"
            mock_show_bundles.assert_called_once()

    def test_multiple_mode_changes(self, advanced_dock_area, qtbot):
        """Test multiple rapid mode changes."""
        modes = ["plot", "device", "utils", "creator", "user"]

        for i, mode in enumerate(modes):
            with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
                advanced_dock_area.mode = mode

            assert advanced_dock_area.mode == mode
            assert blocker.args == [mode]
