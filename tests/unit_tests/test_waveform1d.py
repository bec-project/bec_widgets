# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
from unittest import mock

import numpy as np
import pytest

from bec_widgets.widgets.figure.plots.waveform.waveform_curve import CurveConfig, Signal, SignalData

from .client_mocks import mocked_client
from .test_bec_figure import bec_figure


def test_adding_curve_to_waveform(bec_figure):
    w1 = bec_figure.plot()

    # adding curve which is in bec - only names
    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")
    assert c1.config.label == "bpm4i-bpm4i"

    # adding curve which is in bec - names and entry
    c2 = w1.add_curve_scan(x_name="samx", x_entry="samx", y_name="bpm3a", y_entry="bpm3a")
    assert c2.config.label == "bpm3a-bpm3a"

    # adding curve which is not in bec
    with pytest.raises(ValueError) as excinfo:
        w1.add_curve_scan(x_name="non_existent_device", y_name="non_existent_device")
    assert "Device 'non_existent_device' not found in current BEC session" in str(excinfo.value)

    # adding wrong entry for samx
    with pytest.raises(ValueError) as excinfo:
        w1.add_curve_scan(
            x_name="samx", x_entry="non_existent_entry", y_name="bpm3a", y_entry="bpm3a"
        )
    assert "Entry 'non_existent_entry' not found in device 'samx' signals" in str(excinfo.value)

    # adding wrong device with validation switched off
    c3 = w1.add_curve_scan(x_name="samx", y_name="non_existent_device", validate_bec=False)
    assert c3.config.label == "non_existent_device-non_existent_device"


def test_adding_curve_with_same_id(bec_figure):
    w1 = bec_figure.plot()
    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i", gui_id="test_curve")

    with pytest.raises(ValueError) as excinfo:
        w1.add_curve_scan(x_name="samx", y_name="bpm4i", gui_id="test_curve")
        assert "Curve with ID 'test_curve' already exists." in str(excinfo.value)


def test_create_waveform1D_by_config(bec_figure):
    w1_config_input = {
        "widget_class": "BECWaveform",
        "gui_id": "widget_1",
        "parent_id": "BECFigure_1708689320.788527",
        "row": 0,
        "col": 0,
        "axis": {
            "title": "Widget 1",
            "title_size": None,
            "x_label": None,
            "x_label_size": None,
            "y_label": None,
            "y_label_size": None,
            "legend_label_size": None,
            "x_scale": "linear",
            "y_scale": "linear",
            "x_lim": (1, 10),
            "y_lim": None,
            "x_grid": False,
            "y_grid": False,
        },
        "color_palette": "plasma",
        "curves": {
            "bpm4i-bpm4i": {
                "widget_class": "BECCurve",
                "gui_id": "BECCurve_1708689321.226847",
                "parent_id": "widget_1",
                "label": "bpm4i-bpm4i",
                "color": "#cc4778",
                "color_map_z": "plasma",
                "symbol": "o",
                "symbol_color": None,
                "symbol_size": 5,
                "pen_width": 2,
                "pen_style": "dash",
                "source": "scan_segment",
                "signals": {
                    "dap": None,
                    "source": "scan_segment",
                    "x": {
                        "name": "samx",
                        "entry": "samx",
                        "unit": None,
                        "modifier": None,
                        "limits": None,
                    },
                    "y": {
                        "name": "bpm4i",
                        "entry": "bpm4i",
                        "unit": None,
                        "modifier": None,
                        "limits": None,
                    },
                    "z": None,
                },
            },
            "curve-custom": {
                "widget_class": "BECCurve",
                "gui_id": "BECCurve_1708689321.22867",
                "parent_id": "widget_1",
                "label": "curve-custom",
                "color": "blue",
                "color_map_z": "plasma",
                "symbol": "o",
                "symbol_color": None,
                "symbol_size": 5,
                "pen_width": 2,
                "pen_style": "dashdot",
                "source": "custom",
                "signals": None,
            },
        },
    }

    w1 = bec_figure.plot(config=w1_config_input)

    w1_config_output = w1.get_config()
    w1_config_input["gui_id"] = w1.gui_id

    assert w1_config_input == w1_config_output
    assert w1.plot_item.titleLabel.text == "Widget 1"
    assert w1.config.axis.title == "Widget 1"


def test_change_gui_id(bec_figure):
    w1 = bec_figure.plot()
    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")
    w1.change_gui_id("new_id")

    assert w1.config.gui_id == "new_id"
    assert c1.config.parent_id == "new_id"


def test_getting_curve(bec_figure):
    w1 = bec_figure.plot()
    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i", gui_id="test_curve")
    c1_expected_config = CurveConfig(
        widget_class="BECCurve",
        gui_id="test_curve",
        parent_id=w1.gui_id,
        label="bpm4i-bpm4i",
        color="#cc4778",
        symbol="o",
        symbol_color=None,
        symbol_size=5,
        pen_width=2,
        pen_style="solid",
        source="scan_segment",
        signals=Signal(
            source="scan_segment",
            x=SignalData(name="samx", entry="samx", unit=None, modifier=None),
            y=SignalData(name="bpm4i", entry="bpm4i", unit=None, modifier=None),
        ),
    )

    assert w1.curves[0].config == c1_expected_config
    assert w1._curves_data["scan_segment"]["bpm4i-bpm4i"].config == c1_expected_config
    assert w1.get_curve(0).config == c1_expected_config
    assert w1.get_curve("bpm4i-bpm4i").config == c1_expected_config
    assert c1.get_config(False) == c1_expected_config
    assert c1.get_config() == c1_expected_config.model_dump()


def test_getting_curve_errors(bec_figure):
    w1 = bec_figure.plot()
    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i", gui_id="test_curve")

    with pytest.raises(ValueError) as excinfo:
        w1.get_curve("non_existent_curve")
        assert "Curve with ID 'non_existent_curve' not found." in str(excinfo.value)
    with pytest.raises(IndexError) as excinfo:
        w1.get_curve(1)
        assert "list index out of range" in str(excinfo.value)
    with pytest.raises(ValueError) as excinfo:
        w1.get_curve(1.2)
        assert "Identifier must be either an integer (index) or a string (curve_id)." in str(
            excinfo.value
        )


def test_add_curve(bec_figure):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")

    assert len(w1.curves) == 1
    assert w1._curves_data["scan_segment"] == {"bpm4i-bpm4i": c1}
    assert c1.config.label == "bpm4i-bpm4i"
    assert c1.config.source == "scan_segment"


def test_change_legend_font_size(bec_figure):
    plot = bec_figure.plot()

    w1 = plot.add_curve_scan(x_name="samx", y_name="bpm4i")
    my_func = plot.plot_item.legend
    with mock.patch.object(my_func, "setScale") as mock_set_scale:
        plot.set_legend_label_size(18)
        assert plot.config.axis.legend_label_size == 18
        assert mock_set_scale.call_count == 1
        assert mock_set_scale.call_args == mock.call(2)


def test_remove_curve(bec_figure):
    w1 = bec_figure.plot()

    w1.add_curve_scan(x_name="samx", y_name="bpm4i")
    w1.add_curve_scan(x_name="samx", y_name="bpm3a")
    w1.remove_curve(0)
    w1.remove_curve("bpm3a-bpm3a")

    assert len(w1.plot_item.curves) == 0
    assert w1._curves_data["scan_segment"] == {}

    with pytest.raises(ValueError) as excinfo:
        w1.remove_curve(1.2)
        assert "Each identifier must be either an integer (index) or a string (curve_id)." in str(
            excinfo.value
        )


def test_change_curve_appearance_methods(bec_figure, qtbot):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")

    c1.set_color("#0000ff")
    c1.set_symbol("x")
    c1.set_symbol_color("#ff0000")
    c1.set_symbol_size(10)
    c1.set_pen_width(3)
    c1.set_pen_style("dashdot")

    qtbot.wait(500)
    assert c1.config.color == "#0000ff"
    assert c1.config.symbol == "x"
    assert c1.config.symbol_color == "#ff0000"
    assert c1.config.symbol_size == 10
    assert c1.config.pen_width == 3
    assert c1.config.pen_style == "dashdot"
    assert c1.config.source == "scan_segment"
    assert c1.config.signals.model_dump() == {
        "dap": None,
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
        "z": None,
    }


def test_change_curve_appearance_args(bec_figure):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")

    c1.set(
        color="#0000ff",
        symbol="x",
        symbol_color="#ff0000",
        symbol_size=10,
        pen_width=3,
        pen_style="dashdot",
    )

    assert c1.config.color == "#0000ff"
    assert c1.config.symbol == "x"
    assert c1.config.symbol_color == "#ff0000"
    assert c1.config.symbol_size == 10
    assert c1.config.pen_width == 3
    assert c1.config.pen_style == "dashdot"
    assert c1.config.source == "scan_segment"
    assert c1.config.signals.model_dump() == {
        "dap": None,
        "source": "scan_segment",
        "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
        "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
        "z": None,
    }


def test_set_custom_curve_data(bec_figure, qtbot):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_custom(
        x=[1, 2, 3],
        y=[4, 5, 6],
        label="custom_curve",
        color="#0000ff",
        symbol="x",
        symbol_color="#ff0000",
        symbol_size=10,
        pen_width=3,
        pen_style="dashdot",
    )

    x_init, y_init = c1.get_data()

    assert np.array_equal(x_init, [1, 2, 3])
    assert np.array_equal(y_init, [4, 5, 6])
    assert c1.config.label == "custom_curve"
    assert c1.config.color == "#0000ff"
    assert c1.config.symbol == "x"
    assert c1.config.symbol_color == "#ff0000"
    assert c1.config.symbol_size == 10
    assert c1.config.pen_width == 3
    assert c1.config.pen_style == "dashdot"
    assert c1.config.source == "custom"
    assert c1.config.signals == None

    c1.set_data(x=[4, 5, 6], y=[7, 8, 9])

    x_new, y_new = c1.get_data()
    assert np.array_equal(x_new, [4, 5, 6])
    assert np.array_equal(y_new, [7, 8, 9])


def test_custom_data_2D_array(bec_figure, qtbot):

    data = np.random.rand(10, 2)

    plt = bec_figure.plot(data)

    x, y = plt.curves[0].get_data()

    assert np.array_equal(x, data[:, 0])
    assert np.array_equal(y, data[:, 1])


def test_get_all_data(bec_figure):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_custom(
        x=[1, 2, 3],
        y=[4, 5, 6],
        label="custom_curve-1",
        color="#0000ff",
        symbol="x",
        symbol_color="#ff0000",
        symbol_size=10,
        pen_width=3,
        pen_style="dashdot",
    )

    c2 = w1.add_curve_custom(
        x=[4, 5, 6],
        y=[7, 8, 9],
        label="custom_curve-2",
        color="#00ff00",
        symbol="o",
        symbol_color="#00ff00",
        symbol_size=20,
        pen_width=4,
        pen_style="dash",
    )

    all_data = w1.get_all_data()

    assert all_data == {
        "custom_curve-1": {"x": [1, 2, 3], "y": [4, 5, 6]},
        "custom_curve-2": {"x": [4, 5, 6], "y": [7, 8, 9]},
    }


def test_curve_add_by_config(bec_figure):
    w1 = bec_figure.plot()

    c1_config_input = {
        "widget_class": "BECCurve",
        "gui_id": "BECCurve_1708689321.226847",
        "parent_id": "widget_1",
        "label": "bpm4i-bpm4i",
        "color": "#cc4778",
        "color_map_z": "plasma",
        "symbol": "o",
        "symbol_color": None,
        "symbol_size": 5,
        "pen_width": 2,
        "pen_style": "dash",
        "source": "scan_segment",
        "signals": {
            "dap": None,
            "source": "scan_segment",
            "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
            "y": {
                "name": "bpm4i",
                "entry": "bpm4i",
                "unit": None,
                "modifier": None,
                "limits": None,
            },
            "z": None,
        },
    }

    c1 = w1.add_curve_by_config(c1_config_input)

    c1_config_dict = c1.get_config()

    assert c1_config_dict == c1_config_input
    assert c1.config == CurveConfig(**c1_config_input)
    assert c1.get_config(False) == CurveConfig(**c1_config_input)


def test_scan_update(bec_figure, qtbot):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")

    msg_waveform = {
        "data": {
            "samx": {"samx": {"value": 10}},
            "bpm4i": {"bpm4i": {"value": 5}},
            "gauss_bpm": {"gauss_bpm": {"value": 6}},
            "gauss_adc1": {"gauss_adc1": {"value": 8}},
            "gauss_adc2": {"gauss_adc2": {"value": 9}},
        },
        "scan_id": 1,
    }
    # Mock scan_storage.find_scan_by_ID
    mock_scan_data_waveform = mock.MagicMock()
    mock_scan_data_waveform.data = {
        device_name: {
            entry: mock.MagicMock(val=[msg_waveform["data"][device_name][entry]["value"]])
            for entry in msg_waveform["data"][device_name]
        }
        for device_name in msg_waveform["data"]
    }

    metadata_waveform = {"scan_name": "line_scan"}

    w1.queue.scan_storage.find_scan_by_ID.return_value = mock_scan_data_waveform

    w1.on_scan_segment(msg_waveform, metadata_waveform)
    qtbot.wait(500)
    assert c1.get_data() == ([10], [5])


def test_scan_history_with_val_access(bec_figure, qtbot):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="bpm4i")

    mock_scan_data = {
        "samx": {"samx": mock.MagicMock(val=np.array([1, 2, 3]))},  # Use mock.MagicMock for .val
        "bpm4i": {"bpm4i": mock.MagicMock(val=np.array([4, 5, 6]))},  # Use mock.MagicMock for .val
    }

    mock_scan_storage = mock.MagicMock()
    mock_scan_storage.find_scan_by_ID.return_value = mock.MagicMock(data=mock_scan_data)
    w1.queue.scan_storage = mock_scan_storage

    fake_scan_id = "fake_scan_id"
    w1.scan_history(scan_id=fake_scan_id)

    qtbot.wait(500)

    x_data, y_data = c1.get_data()

    assert np.array_equal(x_data, [1, 2, 3])
    assert np.array_equal(y_data, [4, 5, 6])


def test_scatter_2d_update(bec_figure, qtbot):
    w1 = bec_figure.plot()

    c1 = w1.add_curve_scan(x_name="samx", y_name="samx", z_name="bpm4i")

    msg = {
        "data": {
            "samx": {"samx": {"value": [1, 2, 3]}},
            "samy": {"samy": {"value": [4, 5, 6]}},
            "bpm4i": {"bpm4i": {"value": [1, 3, 2]}},
        },
        "scan_id": 1,
    }
    msg_metadata = {"scan_name": "line_scan"}

    mock_scan_data = mock.MagicMock()
    mock_scan_data.data = {
        device_name: {
            entry: mock.MagicMock(val=msg["data"][device_name][entry]["value"])
            for entry in msg["data"][device_name]
        }
        for device_name in msg["data"]
    }

    w1.queue.scan_storage.find_scan_by_ID.return_value = mock_scan_data

    w1.on_scan_segment(msg, msg_metadata)
    qtbot.wait(500)

    data = c1.get_data()
    expected_x_y_data = ([1, 2, 3], [1, 2, 3])
    expected_z_colors = w1._make_z_gradient([1, 3, 2], "plasma")

    scatter_points = c1.scatter.points()
    colors = [point.brush().color() for point in scatter_points]

    assert np.array_equal(data, expected_x_y_data)
    assert colors == expected_z_colors
