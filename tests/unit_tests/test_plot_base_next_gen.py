from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase

from .client_mocks import mocked_client
from .conftest import create_widget


def test_init_plot_base(qtbot, mocked_client):
    """
    Test that PlotBase initializes without error and has expected default states.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    assert pb.objectName() == "PlotBase"
    # The default title/labels should be empty
    assert pb.title == ""
    assert pb.x_label == ""
    assert pb.y_label == ""
    # By default, no crosshair or FPS monitor
    assert pb.crosshair is None
    assert pb.fps_monitor is None
    # The side panel was created
    assert pb.side_panel is not None
    # The toolbar was created
    assert pb.toolbar is not None


def test_set_title_emits_signal(qtbot, mocked_client):
    """
    Test that setting the title updates the plot and emits a property_changed signal.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)

    with qtbot.waitSignal(pb.property_changed, timeout=500) as signal:
        pb.title = "My Plot Title"
    # The signal should carry ("title", "My Plot Title")
    assert signal.args == ["title", "My Plot Title"]
    assert pb.plot_item.titleLabel.text == "My Plot Title"

    # Get the property back from the object
    assert pb.title == "My Plot Title"


def test_set_x_label_emits_signal(qtbot, mocked_client):
    """
    Test setting x_label updates the plot and emits a property_changed signal.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    with qtbot.waitSignal(pb.property_changed, timeout=500) as signal:
        pb.x_label = "Voltage (V)"
    assert signal.args == ["x_label", "Voltage (V)"]
    assert pb.x_label == "Voltage (V)"
    assert pb.plot_item.getAxis("bottom").labelText == "Voltage (V)"


def test_set_y_label_emits_signal(qtbot, mocked_client):
    """
    Test setting y_label updates the plot and emits a property_changed signal.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    with qtbot.waitSignal(pb.property_changed, timeout=500) as signal:
        pb.y_label = "Current (A)"
    assert signal.args == ["y_label", "Current (A)"]
    assert pb.y_label == "Current (A)"
    assert pb.plot_item.getAxis("left").labelText == "Current (A)"


def test_set_x_min_max(qtbot, mocked_client):
    """
    Test setting x_min, x_max changes the actual X-range of the plot
    and emits signals.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    # Set x_max
    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_max:
        pb.x_max = 50
    assert pb.x_max == 50.0

    # Set x_min
    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_min:
        pb.x_min = 5
    assert pb.x_min == 5.0

    # Confirm the actual ViewBox range in pyqtgraph
    assert pb.plot_item.vb.viewRange()[0] == [5.0, 50.0]


def test_set_y_min_max(qtbot, mocked_client):
    """
    Test setting y_min, y_max changes the actual Y-range of the plot
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_max:
        pb.y_max = 100
    assert pb.y_max == 100.0

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_min:
        pb.y_min = 10
    assert pb.y_min == 10.0

    # Confirm the actual ViewBox range
    assert pb.plot_item.vb.viewRange()[1] == [10.0, 100.0]


def test_auto_range_x_y(qtbot, mocked_client):
    """
    Test enabling and disabling autoRange for x and y axes.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    # auto_range_x = True
    pb.auto_range_x = True
    assert pb.plot_item.vb.state["autoRange"][0] is True
    pb.auto_range_y = True
    assert pb.plot_item.vb.state["autoRange"][1] is True
    # Turn off
    pb.auto_range_x = False
    assert pb.plot_item.vb.state["autoRange"][0] is False
    pb.auto_range_y = False
    assert pb.plot_item.vb.state["autoRange"][1] is False


def test_x_log_y_log(qtbot, mocked_client):
    """
    Test toggling log scale on x and y axes.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig1:
        pb.x_log = True
    assert pb.plot_item.vb.state["logMode"][0] is True

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig2:
        pb.x_log = False
    assert pb.plot_item.vb.state["logMode"][0] is False

    # Y log
    pb.y_log = True
    assert pb.plot_item.vb.state["logMode"][1] is True
    pb.y_log = False
    assert pb.plot_item.vb.state["logMode"][1] is False


def test_grid(qtbot, mocked_client):
    """
    Test x_grid and y_grid toggles.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    # By default, might be off
    with qtbot.waitSignal(pb.property_changed, timeout=500) as sigx:
        pb.x_grid = True
    assert sigx.args == ["x_grid", True]
    # Confirm in pyqtgraph
    assert pb.plot_item.ctrl.xGridCheck.isChecked() is True

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sigy:
        pb.y_grid = True
    assert sigy.args == ["y_grid", True]
    assert pb.plot_item.ctrl.yGridCheck.isChecked() is True


def test_lock_aspect_ratio(qtbot, mocked_client):
    """
    Test locking and unlocking the aspect ratio.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    # default is unlocked
    assert bool(pb.plot_item.vb.getState()["aspectLocked"]) is False

    pb.lock_aspect_ratio = True
    assert bool(pb.plot_item.vb.getState()["aspectLocked"]) is True

    pb.lock_aspect_ratio = False
    assert bool(pb.plot_item.vb.getState()["aspectLocked"]) is False


def test_inner_axes_toggle(qtbot, mocked_client):
    """
    Test the 'inner_axes' property, which shows/hides bottom and left axes.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_off:
        pb.inner_axes = False
    assert sig_off.args == ["inner_axes", False]
    assert pb.plot_item.getAxis("bottom").isVisible() is False
    assert pb.plot_item.getAxis("left").isVisible() is False

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_on:
        pb.inner_axes = True
    assert sig_on.args == ["inner_axes", True]
    assert pb.plot_item.getAxis("bottom").isVisible() is True
    assert pb.plot_item.getAxis("left").isVisible() is True


def test_outer_axes_toggle(qtbot, mocked_client):
    """
    Test the 'outer_axes' property, which shows/hides top and right axes.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_on:
        pb.outer_axes = True
    assert sig_on.args == ["outer_axes", True]
    assert pb.plot_item.getAxis("top").isVisible() is True
    assert pb.plot_item.getAxis("right").isVisible() is True

    with qtbot.waitSignal(pb.property_changed, timeout=500) as sig_off:
        pb.outer_axes = False
    assert sig_off.args == ["outer_axes", False]
    assert pb.plot_item.getAxis("top").isVisible() is False
    assert pb.plot_item.getAxis("right").isVisible() is False


def test_crosshair_hook_unhook(qtbot, mocked_client):
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    assert pb.crosshair is None
    # Hook
    pb.hook_crosshair()
    assert pb.crosshair is not None
    # Unhook
    pb.unhook_crosshair()
    assert pb.crosshair is None

    # toggle
    pb.toggle_crosshair()
    assert pb.crosshair is not None
    pb.toggle_crosshair()
    assert pb.crosshair is None


def test_set_method(qtbot, mocked_client):
    """
    Test using the set(...) convenience method to update multiple properties at once.
    """
    pb = create_widget(qtbot, PlotBase, client=mocked_client)
    pb.set(
        title="Multi Set Title",
        x_label="Voltage",
        y_label="Current",
        x_grid=True,
        y_grid=True,
        x_log=True,
        outer_axes=True,
    )

    assert pb.title == "Multi Set Title"
    assert pb.x_label == "Voltage"
    assert pb.y_label == "Current"
    assert pb.x_grid is True
    assert pb.y_grid is True
    assert pb.x_log is True
    assert pb.outer_axes is True
