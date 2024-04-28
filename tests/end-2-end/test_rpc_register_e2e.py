import pytest

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform


def find_deepest_value(d: dict):
    """
    Recursively find the deepest value in a dictionary
    Args:
        d(dict): Dictionary to search

    Returns:
        The deepest value in the dictionary.
    """
    if isinstance(d, dict):
        if d:
            return find_deepest_value(next(iter(d.values())))
    return d


def test_rpc_register_list_connections(rpc_server, rpc_register, qtbot):
    fig = BECFigure(rpc_server.gui_id)
    fig_server = rpc_server.fig

    plt = fig.plot("samx", "bpm4i")
    im = fig.image("eiger")
    motor_map = fig.motor_map("samx", "samy")
    plt_z = fig.add_plot("samx", "samy", "bpm4i")

    all_connections = rpc_register.list_all_connections()

    # Construct dict of all rpc items manually
    all_subwidgets_expected = dict(fig_server.widgets)
    curve_1D = find_deepest_value(fig_server.widgets[plt.rpc_id]._curves_data)
    curve_2D = find_deepest_value(fig_server.widgets[plt_z.rpc_id]._curves_data)
    curves_expected = {curve_1D.rpc_id: curve_1D, curve_2D.rpc_id: curve_2D}
    fig_expected = {fig.rpc_id: fig_server}
    image_item_expected = {
        fig_server.widgets[im.rpc_id].images[0].rpc_id: fig_server.widgets[im.rpc_id].images[0]
    }

    all_connections_expected = {
        **all_subwidgets_expected,
        **curves_expected,
        **fig_expected,
        **image_item_expected,
    }

    assert len(all_connections) == 8
    assert all_connections == all_connections_expected
