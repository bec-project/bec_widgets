from pytestqt import qtbot

from bec_widgets import scan_plot


def test_scan_plot(qtbot):
    """Test ScanPlot"""
    plot = scan_plot.BECScanPlot()
    qtbot.addWidget(plot)
    plot.show()
    qtbot.waitForWindowShown(plot)

    plot.x_channel = "x"
    plot.y_channel_list = ["y1", "y2"]

    plot.initialize()
    plot.redraw_scan(
        {"x": {"x": {"value": 1}}, "y1": {"y1": {"value": 1}}, "y2": {"y2": {"value": 3}}}
    )
    plot.redraw_scan(
        {"x": {"x": {"value": 2}}, "y1": {"y1": {"value": 2}}, "y2": {"y2": {"value": 4}}}
    )

    assert all(plot.scan_curves["y1"].getData()[0] == [1, 2])
    assert all(plot.scan_curves["y2"].getData()[1] == [3, 4])


def test_scan_plot_clears_data(qtbot):
    """Test ScanPlot"""
    plot = scan_plot.BECScanPlot()
    qtbot.addWidget(plot)
    plot.show()
    qtbot.waitForWindowShown(plot)

    plot.x_channel = "x"
    plot.y_channel_list = ["y1", "y2"]

    plot.initialize()
    plot.redraw_scan(
        {"x": {"x": {"value": 1}}, "y1": {"y1": {"value": 1}}, "y2": {"y2": {"value": 3}}}
    )
    plot.clearData()
    plot.redraw_scan(
        {"x": {"x": {"value": 2}}, "y1": {"y1": {"value": 2}}, "y2": {"y2": {"value": 4}}}
    )

    assert all(plot.scan_curves["y1"].getData()[0] == [2])
    assert all(plot.scan_curves["y2"].getData()[1] == [4])


def test_scan_plot_redraws_dap(qtbot):
    """Test ScanPlot"""
    plot = scan_plot.BECScanPlot()
    qtbot.addWidget(plot)
    plot.show()
    qtbot.waitForWindowShown(plot)

    plot.y_channel_list = ["dap.y1", "dap.y2"]

    plot.initialize()
    plot.redraw_dap({"y1": {"x": [1], "y": [1]}, "y2": {"x": [2], "y": [2]}})

    assert all(plot.dap_curves["y1"].getData()[0] == [1])
    assert all(plot.dap_curves["y2"].getData()[1] == [2])
