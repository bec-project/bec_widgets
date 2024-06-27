import pytest

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform


def test_rpc_register_list_connections(rpc_server_figure):
    fig = BECFigure(rpc_server_figure)

    plt = fig.plot(x_name="samx", y_name="bpm4i")
    im = fig.image("eiger")
    motor_map = fig.motor_map("samx", "samy")
    plt_z = fig.plot(x_name="samx", y_name="samy", z_name="bpm4i", new=True)

    # keep only class names from objects, since objects on server and client are different
    # so the best we can do is to compare types (rpc register is unit-tested elsewhere)
    all_connections = {obj_id: type(obj).__name__ for obj_id, obj in fig.get_all_rpc().items()}

    all_subwidgets_expected = {wid: type(widget).__name__ for wid, widget in fig.widgets.items()}
    curve_1D = fig.widgets[plt.rpc_id]
    curve_2D = fig.widgets[plt_z.rpc_id]
    curves_expected = {
        curve_1D.rpc_id: type(curve_1D).__name__,
        curve_2D.rpc_id: type(curve_2D).__name__,
    }
    curves_expected.update({curve._gui_id: type(curve).__name__ for curve in curve_1D.curves})
    curves_expected.update({curve._gui_id: type(curve).__name__ for curve in curve_2D.curves})
    fig_expected = {fig.rpc_id: type(fig).__name__}
    image_item_expected = {
        fig.widgets[im.rpc_id].images[0].rpc_id: type(fig.widgets[im.rpc_id].images[0]).__name__
    }

    all_connections_expected = {
        **all_subwidgets_expected,
        **curves_expected,
        **fig_expected,
        **image_item_expected,
    }

    assert len(all_connections) == 8
    assert all_connections == all_connections_expected
