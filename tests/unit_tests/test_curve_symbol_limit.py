"""The symbol is dropped for dense curves; see Curve.setData."""

import numpy as np
import pytest

from bec_widgets.widgets.plots.waveform.curve import Curve, CurveConfig, _incoming_length
from bec_widgets.widgets.plots.waveform.waveform import Waveform

from .client_mocks import mocked_client
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


@pytest.mark.parametrize(
    "args,kwargs,expected",
    [
        ((np.arange(5),), {}, 5),
        ((np.arange(5), np.arange(5)), {}, 5),
        (((1, 2, 3),), {}, 3),
        (([1, 2, 3, 4],), {}, 4),
        ((), {"y": np.arange(7)}, 7),
        ((), {"x": np.arange(7)}, 7),
        ((), {}, 0),
        (({"x": [1], "y": [2]},), {}, None),
        (([{"pos": (0, 0)}],), {}, None),
    ],
)
def test_incoming_length(args, kwargs, expected):
    assert _incoming_length(args, kwargs) == expected


def test_unresolvable_length_leaves_symbol_untouched(curve):
    """A shape we cannot measure must not silently flip the symbol."""
    curve.setData(*_data(10))
    assert curve.opts["symbol"] == "o"
    curve.setData({"x": np.arange(5000), "y": np.arange(5000)})
    assert curve.opts["symbol"] == "o"
