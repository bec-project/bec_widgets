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
