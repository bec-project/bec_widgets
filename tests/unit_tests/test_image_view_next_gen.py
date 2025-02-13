import numpy as np
import pyqtgraph as pg
import pytest

from bec_widgets.widgets.plots_next_gen.image.image import Image
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget

##################################################
# Image widget base functionality tests
##################################################


def test_initialization_defaults(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    assert bec_image_view.color_map == "magma"
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.config.lock_aspect_ratio is True
    assert bec_image_view.main_image is not None
    assert bec_image_view._color_bar is None


def test_setting_color_map(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.color_map = "viridis"
    assert bec_image_view.color_map == "viridis"
    assert bec_image_view.config.color_map == "viridis"


def test_invalid_color_map_handling(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    previous_colormap = bec_image_view.color_map
    bec_image_view.color_map = "invalid_colormap_name"
    assert bec_image_view.color_map == previous_colormap
    assert bec_image_view.main_image.color_map == previous_colormap


def test_toggle_autorange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.autorange = False
    assert bec_image_view.autorange is False

    bec_image_view.toggle_autorange(True, "max")
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "max"

    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "max"
    assert bec_image_view.main_image.config.autorange is True
    assert bec_image_view.main_image.config.autorange_mode == "max"


def test_lock_aspect_ratio(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.lock_aspect_ratio = True
    assert bec_image_view.lock_aspect_ratio is True
    assert bool(bec_image_view.plot_item.getViewBox().state["aspectLocked"]) is True
    assert bec_image_view.config.lock_aspect_ratio is True


def test_set_vrange(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.vrange = (10, 100)
    assert bec_image_view.vrange == (10, 100)
    assert bec_image_view.main_image.levels == (10, 100)
    assert bec_image_view.main_image.config.v_range == (10, 100)


def test_enable_simple_colorbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_simple_colorbar = True
    assert bec_image_view.enable_simple_colorbar is True
    assert bec_image_view.config.color_bar == "simple"
    assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)

    # Enabling color bar should not cancel autorange
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "mean"


def test_enable_full_colorbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_full_colorbar = True
    assert bec_image_view.enable_full_colorbar is True
    assert bec_image_view.config.color_bar == "full"
    assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)

    # Enabling color bar should not cancel autorange
    assert bec_image_view.autorange is True
    assert bec_image_view.autorange_mode == "mean"
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.main_image.autorange_mode == "mean"


@pytest.mark.parametrize("colorbar_type", ["simple", "full"])
def test_enable_colorbar_with_vrange(qtbot, mocked_client, colorbar_type):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.enable_colorbar(True, colorbar_type, (0, 100))

    if colorbar_type == "simple":
        assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)
        assert bec_image_view.enable_simple_colorbar is True
    else:
        assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)
        assert bec_image_view.enable_full_colorbar is True
    assert bec_image_view.config.color_bar == colorbar_type
    assert bec_image_view.vrange == (0, 100)
    assert bec_image_view.main_image.levels == (0, 100)
    assert bec_image_view._color_bar is not None


def test_image_setup_image_2d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="2d")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.main_image.config.source == "device_monitor_2d"
    assert bec_image_view.main_image.config.monitor_type == "2d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_setup_image_1d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="1d")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.main_image.config.source == "device_monitor_1d"
    assert bec_image_view.main_image.config.monitor_type == "1d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_setup_image_auto(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.image(monitor="eiger", monitor_type="auto")
    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.main_image.config.source == "auto"
    assert bec_image_view.main_image.config.monitor_type == "auto"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_data_update_2d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    test_data = np.random.rand(20, 30)
    message = {"data": test_data}
    metadata = {}

    bec_image_view.on_image_update_2d(message, metadata)

    np.testing.assert_array_equal(bec_image_view._main_image.image, test_data)


def test_image_data_update_1d(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    waveform1 = np.random.rand(50)
    waveform2 = np.random.rand(60)  # Different length, tests padding logic
    metadata = {"scan_id": "scan_test"}

    bec_image_view.on_image_update_1d({"data": waveform1}, metadata)
    assert bec_image_view._main_image.raw_data.shape == (1, 50)

    bec_image_view.on_image_update_1d({"data": waveform2}, metadata)
    assert bec_image_view._main_image.raw_data.shape == (2, 60)


def test_toolbar_actions_presence(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    assert "autorange_image" in bec_image_view.toolbar.bundles["roi"]
    assert "lock_aspect_ratio" in bec_image_view.toolbar.bundles["mouse_interaction"]
    assert "processing" in bec_image_view.toolbar.bundles
    assert "selection" in bec_image_view.toolbar.bundles


def test_image_processing_fft_toggle(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.fft = True
    assert bec_image_view.fft is True
    bec_image_view.fft = False
    assert bec_image_view.fft is False


def test_image_processing_log_toggle(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.log = True
    assert bec_image_view.log is True
    bec_image_view.log = False
    assert bec_image_view.log is False


def test_image_rotation_and_transpose(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.rotation = 2
    assert bec_image_view.rotation == 2

    bec_image_view.transpose = True
    assert bec_image_view.transpose is True


@pytest.mark.parametrize("colorbar_type", ["none", "simple", "full"])
def test_setting_vrange_with_colorbar(qtbot, mocked_client, colorbar_type):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    if colorbar_type == "simple":
        bec_image_view.enable_simple_colorbar = True
    elif colorbar_type == "full":
        bec_image_view.enable_full_colorbar = True

    bec_image_view.vrange = (0, 100)
    assert bec_image_view.vrange == (0, 100)
    assert bec_image_view.main_image.levels == (0, 100)
    assert bec_image_view.main_image.config.v_range == (0, 100)
    assert bec_image_view.v_min == 0
    assert bec_image_view.v_max == 100

    if colorbar_type == "simple":
        assert isinstance(bec_image_view._color_bar, pg.ColorBarItem)
        assert bec_image_view._color_bar.levels() == (0, 100)
    elif colorbar_type == "full":
        assert isinstance(bec_image_view._color_bar, pg.HistogramLUTItem)
        assert bec_image_view._color_bar.getLevels() == (0, 100)


###################################
# Toolbar Actions
###################################


def test_setup_image_from_toolbar(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.selection_bundle.device_combo_box.setCurrentText("eiger")
    bec_image_view.selection_bundle.dim_combo_box.setCurrentText("2d")

    assert bec_image_view.monitor == "eiger"
    assert bec_image_view.main_image.config.source == "device_monitor_2d"
    assert bec_image_view.main_image.config.monitor_type == "2d"
    assert bec_image_view.main_image.raw_data is None
    assert bec_image_view.main_image.image is None


def test_image_actions_interactions(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)
    bec_image_view.autorange = False  # Change the initial state to False

    bec_image_view.autorange_mean_action.action.trigger()
    assert bec_image_view.autorange is True
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.autorange_mode == "mean"

    bec_image_view.autorange_max_action.action.trigger()
    assert bec_image_view.autorange is True
    assert bec_image_view.main_image.autorange is True
    assert bec_image_view.autorange_mode == "max"

    bec_image_view.toolbar.widgets["lock_aspect_ratio"].action.trigger()
    assert bec_image_view.lock_aspect_ratio is False
    assert bool(bec_image_view.plot_item.getViewBox().state["aspectLocked"]) is False


def test_image_toggle_action_fft(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.processing_bundle.fft.action.trigger()

    assert bec_image_view.fft is True
    assert bec_image_view.main_image.fft is True
    assert bec_image_view.main_image.config.processing.fft is True


def test_image_toggle_action_log(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.processing_bundle.log.action.trigger()

    assert bec_image_view.log is True
    assert bec_image_view.main_image.log is True
    assert bec_image_view.main_image.config.processing.log is True


def test_image_toggle_action_transpose(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.processing_bundle.transpose.action.trigger()

    assert bec_image_view.transpose is True
    assert bec_image_view.main_image.transpose is True
    assert bec_image_view.main_image.config.processing.transpose is True


def test_image_toggle_action_rotate_right(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.processing_bundle.right.action.trigger()

    assert bec_image_view.rotation == 3
    assert bec_image_view.main_image.rotation == 3
    assert bec_image_view.main_image.config.processing.rotation == 3


def test_image_toggle_action_rotate_left(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    bec_image_view.processing_bundle.left.action.trigger()

    assert bec_image_view.rotation == 1
    assert bec_image_view.main_image.rotation == 1
    assert bec_image_view.main_image.config.processing.rotation == 1


def test_image_toggle_action_reset(qtbot, mocked_client):
    bec_image_view = create_widget(qtbot, Image, client=mocked_client)

    # Setup some processing
    bec_image_view.fft = True
    bec_image_view.log = True
    bec_image_view.transpose = True
    bec_image_view.rotation = 2

    bec_image_view.processing_bundle.reset.action.trigger()

    assert bec_image_view.rotation == 0
    assert bec_image_view.main_image.rotation == 0
    assert bec_image_view.main_image.config.processing.rotation == 0
    assert bec_image_view.fft is False
    assert bec_image_view.main_image.fft is False
    assert bec_image_view.log is False
    assert bec_image_view.main_image.log is False
    assert bec_image_view.transpose is False
    assert bec_image_view.main_image.transpose is False
