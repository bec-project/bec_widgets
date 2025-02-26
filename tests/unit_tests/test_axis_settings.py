import pytest
from qtpy.QtWidgets import QDoubleSpinBox, QLineEdit

from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.setting_menus.axis_settings import AxisSettings
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget


@pytest.fixture
def axis_settings_fixture(qtbot, mocked_client):
    """
    Creates an AxisSettings widget, targeting the real PlotBase widget.
    """

    plot_base = create_widget(qtbot, PlotBase, client=mocked_client)
    axis_settings = create_widget(qtbot, AxisSettings, parent=None, target_widget=plot_base)
    return axis_settings, plot_base


def test_axis_settings_init(axis_settings_fixture):
    """
    Ensure AxisSettings constructs properly with a real PlotBase target.
    """
    axis_settings, plot_base = axis_settings_fixture
    # Verify the UI was loaded and placed in a scroll area
    assert axis_settings.ui is not None
    assert axis_settings.scroll_area is not None
    assert axis_settings.layout.count() == 1  # scroll area
    # Check the target
    assert axis_settings.target_widget == plot_base
    # Check the object name
    assert axis_settings.objectName() == "AxisSettings"


def test_change_ui_updates_plot_base(axis_settings_fixture, qtbot):
    """
    When user edits AxisSettings UI fields, verify that PlotBase's properties update.
    """
    axis_settings, plot_base = axis_settings_fixture

    # 1) Set the 'title'
    title_edit = axis_settings.ui.title
    assert isinstance(title_edit, QLineEdit)
    with qtbot.waitSignal(plot_base.property_changed, timeout=500) as signal:
        title_edit.setText("New Plot Title")

    assert signal.args == ["title", "New Plot Title"]
    assert plot_base.title == "New Plot Title"

    # 2) Set x_min spinbox
    x_max_spin = axis_settings.ui.x_max
    assert isinstance(x_max_spin, QDoubleSpinBox)
    with qtbot.waitSignal(plot_base.property_changed, timeout=500) as signal2:
        x_max_spin.setValue(123)
    assert plot_base.x_max == 123

    # # 3) Toggle grid
    x_log_toggle = axis_settings.ui.x_log
    x_log_toggle.checked = True
    with qtbot.waitSignal(plot_base.property_changed, timeout=500) as signal3:
        x_log_toggle.checked = True

    assert plot_base.x_log is True


def test_plot_base_updates_ui(axis_settings_fixture, qtbot):
    """
    When PlotBase properties change (on the Python side), AxisSettings UI should update.
    We do this by simulating that PlotBase sets properties and emits property_changed.
    (In real usage, PlotBase calls .property_changed.emit(...) in its setters.)
    """
    axis_settings, plot_base = axis_settings_fixture

    # 1) Set plot_base.title
    plot_base.title = "Plot Title from Code"
    assert axis_settings.ui.title.text() == "Plot Title from Code"

    # 2) Set x_max
    plot_base.x_max = 100
    qtbot.wait(50)
    assert axis_settings.ui.x_max.value() == 100

    # 3) Set x_log
    plot_base.x_log = True
    qtbot.wait(50)
    assert axis_settings.ui.x_log.checked is True


def test_no_crash_no_target(qtbot):
    """
    AxisSettings can be created with target_widget=None. It won't update anything,
    but it shouldn't crash on UI changes.
    """
    axis_settings = create_widget(qtbot, AxisSettings, parent=None, target_widget=None)

    axis_settings.ui.title.setText("No target")
    assert axis_settings.ui.title.text() == "No target"


def test_scroll_area_behavior(axis_settings_fixture, qtbot):
    """
    Optional: Check that the QScrollArea is set up in a resizable manner.
    """
    axis_settings, plot_base = axis_settings_fixture
    scroll_area = axis_settings.scroll_area
    assert scroll_area.widgetResizable() is True


def test_fetch_all_properties(axis_settings_fixture, qtbot):
    """
    Tests the `fetch_all_properties` method ensuring that all the properties set on
    the `plot_base` instance are correctly synchronized with the user interface (UI)
    elements of the `axis_settings` instance.
    """
    axis_settings, plot_base = axis_settings_fixture

    # Set all properties on plot_base
    plot_base.title = "Plot Title from Code"
    plot_base.x_min = 0
    plot_base.x_max = 100
    plot_base.x_label = "X Label"
    plot_base.x_log = True
    plot_base.x_grid = True

    plot_base.y_min = -50
    plot_base.y_max = 50
    plot_base.y_label = "Y Label"
    plot_base.y_log = False
    plot_base.y_grid = False

    plot_base.outer_axes = True

    # Fetch properties into the UI
    axis_settings.fetch_all_properties()

    # Verify all properties were correctly fetched
    assert axis_settings.ui.title.text() == "Plot Title from Code"

    # X axis properties
    assert axis_settings.ui.x_min.value() == 0
    assert axis_settings.ui.x_max.value() == 100
    assert axis_settings.ui.x_label.text() == "X Label"
    assert axis_settings.ui.x_log.checked is True
    assert axis_settings.ui.x_grid.checked is True

    # Y axis properties
    assert axis_settings.ui.y_min.value() == -50
    assert axis_settings.ui.y_max.value() == 50
    assert axis_settings.ui.y_label.text() == "Y Label"
    assert axis_settings.ui.y_log.checked is False
    assert axis_settings.ui.y_grid.checked is False

    # Other properties
    assert axis_settings.ui.outer_axes.checked is True


def test_accept_changes(axis_settings_fixture, qtbot):
    """
    Tests the functionality of applying user-defined changes to the axis settings
    UI and verifying the reflected changes in the plot object's properties.
    """
    axis_settings, plot_base = axis_settings_fixture

    axis_settings.ui.title.setText("New Title")
    axis_settings.ui.x_max.setValue(20)
    axis_settings.ui.x_min.setValue(10)
    axis_settings.ui.x_label.setText("New X Label")
    axis_settings.ui.x_log.checked = True
    axis_settings.ui.x_grid.checked = True

    axis_settings.accept_changes()
    qtbot.wait(200)

    assert plot_base.title == "New Title"
    assert plot_base.x_min == 10
    assert plot_base.x_max == 20
    assert plot_base.x_label == "New X Label"
    assert plot_base.x_log is True
    assert plot_base.x_grid is True
