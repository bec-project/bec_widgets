"""The symbol is dropped for dense curves; see Curve.updateItems."""

import numpy as np
import pytest

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.plots.waveform.curve import Curve, CurveConfig
from bec_widgets.widgets.plots.waveform.waveform import Waveform

from .conftest import create_widget

LIMIT = 1000


@pytest.fixture
def curve(qtbot, mocked_client):
    waveform = create_widget(qtbot, Waveform, client=mocked_client)
    waveform.plot(arg1="bpm4i")
    return waveform.curves[0]


def _data(n: int):
    x = np.arange(n, dtype=np.float64)
    return x, np.sin(x * 0.01)


def test_symbol_kept_at_or_below_limit(curve):
    curve.setData(*_data(LIMIT))
    assert curve.opts["symbol"] == "o"


def test_symbol_hidden_above_limit(curve):
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] is None


def test_config_symbol_survives_suppression(curve):
    """The configured symbol is a user setting, not something to overwrite."""
    curve.setData(*_data(LIMIT + 1))
    assert curve.config.symbol == "o"


def test_symbol_restored_when_data_shrinks(curve):
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] is None
    curve.setData(*_data(10))
    assert curve.opts["symbol"] == "o"


def test_custom_symbol_restored_not_default(curve):
    """Restoring must use the configured symbol, not a hardcoded 'o'."""
    curve.set_symbol("t")
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] is None
    curve.setData(*_data(10))
    assert curve.opts["symbol"] == "t"


def test_set_symbol_while_dense_defers_until_sparse(curve):
    curve.setData(*_data(LIMIT + 1))
    curve.set_symbol("x")
    # still dense: the request is recorded but not shown
    assert curve.config.symbol == "x"
    assert curve.opts["symbol"] is None
    curve.setData(*_data(10))
    assert curve.opts["symbol"] == "x"


def test_apply_config_does_not_resurrect_symbol_while_dense(curve):
    curve.setData(*_data(LIMIT + 1))
    curve.apply_config()
    assert curve.opts["symbol"] is None


def test_limit_none_keeps_symbol_at_any_size(qtbot, mocked_client):
    waveform = create_widget(qtbot, Waveform, client=mocked_client)
    waveform.plot(arg1="bpm4i")
    curve = waveform.curves[0]
    curve.config.symbol_point_limit = None
    curve.setData(*_data(50_000))
    assert curve.opts["symbol"] == "o"


def test_custom_limit_is_honoured(curve):
    curve.config.symbol_point_limit = 10
    curve.setData(*_data(11))
    assert curve.opts["symbol"] is None
    curve.setData(*_data(10))
    assert curve.opts["symbol"] == "o"


def test_default_limit_is_1000():
    assert CurveConfig(widget_class="Curve").symbol_point_limit == LIMIT


def test_shrinking_never_redraws_dense_data_with_symbols(curve):
    """The restored symbol must arrive together with the small dataset."""
    curve.setData(*_data(50_000))
    seen = []
    original = curve.scatter.setData

    def spy(*args, **kwargs):
        seen.append(len(kwargs["x"]) if kwargs.get("x") is not None else 0)
        return original(*args, **kwargs)

    curve.scatter.setData = spy
    curve.setData(*_data(5))
    assert curve.opts["symbol"] == "o"
    assert seen and max(seen) == 5


def test_limit_none_after_suppression_restores_symbol(curve):
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] is None
    curve.config.symbol_point_limit = None
    curve.apply_config()
    assert curve.opts["symbol"] == "o"
    curve.setData(*_data(5))
    assert curve.opts["symbol"] == "o"


def test_limit_none_restores_on_next_data(curve):
    """Without apply_config, the next setData recomputes from the new limit."""
    curve.setData(*_data(LIMIT + 1))
    curve.config.symbol_point_limit = None
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] == "o"


def test_apply_config_hides_symbol_when_limit_drops_below_data(curve):
    curve.setData(*_data(20))
    curve.config.symbol_point_limit = 10
    curve.apply_config()
    assert curve.opts["symbol"] is None
    curve.setData(*_data(5))
    assert curve.opts["symbol"] == "o"


@pytest.mark.parametrize("style", [{"symbolSize": 5}, {"symbolBrush": "r"}, {"symbol": "t"}])
def test_style_keywords_cannot_bypass_limit(curve, style):
    """pyqtgraph defaults to an "o" symbol when symbolSize/Pen/Brush come without one."""
    curve.setData(*_data(LIMIT + 1), **style)
    assert curve.opts["symbol"] is None
    curve.setData(*_data(LIMIT + 2))
    assert curve.opts["symbol"] is None


def _call_forms(n: int):
    """Every setData input form pyqtgraph accepts, each plotting n points."""
    x, y = _data(n)
    return {
        "y only": ((y,), {}),
        "x and y": ((x, y), {}),
        "list": ((list(y),), {}),
        "Nx2 array": ((np.column_stack([x, y]),), {}),
        "dict": (({"x": x, "y": y},), {}),
        "dict y only": (({"y": list(y)},), {}),
        "list of dicts": (([{"x": a, "y": b} for a, b in zip(x, y)],), {}),
        "keywords": ((), {"x": x, "y": y}),
        "keyword y overrides positional": ((np.arange(3.0),), {"y": y}),
    }


@pytest.mark.parametrize("form", list(_call_forms(1)))
def test_every_input_form_crosses_the_limit_both_ways(curve, form):
    """The limit counts the points pyqtgraph actually plots, whatever the input form."""
    args, kwargs = _call_forms(LIMIT + 1)[form]
    curve.setData(*args, **kwargs)
    assert len(curve.yData) == LIMIT + 1
    assert curve.opts["symbol"] is None
    args, kwargs = _call_forms(2)[form]
    curve.setData(*args, **kwargs)
    assert len(curve.yData) == 2
    assert curve.opts["symbol"] == "o"
    args, kwargs = _call_forms(LIMIT + 1)[form]
    curve.setData(*args, **kwargs)
    assert curve.opts["symbol"] is None


def test_clearing_a_dense_curve_restores_the_symbol(curve):
    curve.setData(*_data(LIMIT + 1))
    curve.setData()
    assert curve.opts["symbol"] == "o"


def test_set_symbol_none_on_dense_curve_stays_none_when_sparse(curve):
    curve.setData(*_data(LIMIT + 1))
    curve.set_symbol(None)
    curve.setData(*_data(5))
    assert curve.opts["symbol"] is None


def test_set_symbol_point_limit_restores_the_symbol_at_once(curve):
    """The limit of an existing curve can be changed through set(), e.g. from the client."""
    curve.setData(*_data(LIMIT + 1))
    assert curve.opts["symbol"] is None
    curve.set(symbol_point_limit=None)
    assert curve.config.symbol_point_limit is None
    assert curve.opts["symbol"] == "o"


def test_set_symbol_point_limit_hides_the_symbol_at_once(curve):
    curve.setData(*_data(20))
    curve.set(symbol_point_limit=10)
    assert curve.opts["symbol"] is None
    curve.set(symbol_point_limit=20)
    assert curve.opts["symbol"] == "o"
