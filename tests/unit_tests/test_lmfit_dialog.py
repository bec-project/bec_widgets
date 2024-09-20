from unittest import mock

import numpy as np
import pytest

from bec_widgets.widgets.lmfit_dialog.lmfit_dialog import LMFitDialog

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture(scope="function")
def lmfit_dialog(qtbot, mocked_client):
    """Fixture for LMFitDialog widget"""
    db = create_widget(qtbot, LMFitDialog, client=mocked_client)
    yield db


@pytest.fixture(scope="function")
def lmfit_message():
    """Fixture for lmfit summary message"""
    yield {
        "model": "Model(breit_wigner)",
        "method": "leastsq",
        "ndata": 4,
        "nvarys": 4,
        "nfree": 0,
        "chisqr": 1.2583132407517716,
        "redchi": 1.2583132407517716,
        "aic": 3.3739110606840716,
        "bic": 0.9190885051636339,
        "rsquared": 0.9650468544235619,
        "nfev": 2498,
        "max_nfev": 10000,
        "aborted": False,
        "errorbars": True,
        "success": True,
        "message": "Fit succeeded.",
        "lmdif_message": "Both actual and predicted relative reductions in the sum of squares\n  are at most 0.000000",
        "ier": 1,
        "nan_policy": "raise",
        "scale_covar": True,
        "calc_covar": True,
        "ci_out": None,
        "col_deriv": False,
        "flatchain": None,
        "call_kws": {
            "Dfun": None,
            "full_output": 1,
            "col_deriv": 0,
            "ftol": 1.5e-08,
            "xtol": 1.5e-08,
            "gtol": 0.0,
            "maxfev": 20000,
            "epsfcn": 1e-10,
            "factor": 100,
            "diag": None,
        },
        "var_names": ["amplitude", "center", "sigma", "q"],
        "user_options": None,
        "kws": {},
        "init_values": {"amplitude": 1.0, "center": 0.0, "sigma": 1.0, "q": 1.0},
        "best_values": {
            "amplitude": 1.5824142042890903,
            "center": -2.8415356591834326,
            "sigma": 0.0002550847234503717,
            "q": -259.8514775889427,
        },
        "params": [
            [
                "amplitude",
                1.5824142042890903,
                True,
                None,
                -np.inf,
                np.inf,
                None,
                1.3249185295752495,
                {
                    "center": 0.8429146627203449,
                    "sigma": -0.8362891947010586,
                    "q": -0.8362890089256452,
                },
                1.0,
                None,
            ],
            [
                "center",
                -2.8415356591834326,
                True,
                None,
                -np.inf,
                np.inf,
                None,
                0.5077201488266584,
                {
                    "amplitude": 0.8429146627203449,
                    "sigma": -0.9987662050702767,
                    "q": -0.9987662962832818,
                },
                0.0,
                None,
            ],
            [
                "sigma",
                0.0002550847234503717,
                True,
                None,
                0.0,
                np.inf,
                None,
                113.2533064536711,
                {
                    "amplitude": -0.8362891947010586,
                    "center": -0.9987662050702767,
                    "q": 0.999999999997876,
                },
                1.0,
                None,
            ],
            [
                "q",
                -259.8514775889427,
                True,
                None,
                -np.inf,
                np.inf,
                None,
                114893884.64553572,
                {
                    "amplitude": -0.8362890089256452,
                    "center": -0.9987662962832818,
                    "sigma": 0.999999999997876,
                },
                1.0,
                None,
            ],
        ],
    }


def test_fit_curve_id(lmfit_dialog):
    """Test hide_curve_selection property"""
    my_callback = mock.MagicMock()
    lmfit_dialog.selected_fit.connect(my_callback)
    assert lmfit_dialog.fit_curve_id is None
    lmfit_dialog.fit_curve_id = "test_curve_id"
    assert lmfit_dialog.fit_curve_id == "test_curve_id"
    assert my_callback.call_count == 1
    assert my_callback.call_args == mock.call("test_curve_id")


def test_remove_dap_data(lmfit_dialog):
    """Test remove_dap_data method"""
    lmfit_dialog.summary_data = {"test": "data", "test2": "data2"}
    lmfit_dialog.refresh_curve_list()
    # Only 2 items
    assert lmfit_dialog.ui.curve_list.count() == 2
    lmfit_dialog.remove_dap_data("test")
    assert lmfit_dialog.summary_data == {"test2": "data2"}
    assert lmfit_dialog.ui.curve_list.count() == 1
    # Test removing non-existing data
    # Nothing should happen
    lmfit_dialog.remove_dap_data("test_not_there")
    assert lmfit_dialog.summary_data == {"test2": "data2"}
    assert lmfit_dialog.ui.curve_list.count() == 1


def test_update_summary_tree(lmfit_dialog, lmfit_message):
    """Test display_fit_details method"""
    lmfit_dialog.active_action_list = ["center", "amplitude"]
    lmfit_dialog.update_summary_tree(data=lmfit_message, metadata={"curve_id": "test_curve_id"})
    # Check if the data is updated
    assert lmfit_dialog.summary_data == {"test_curve_id": lmfit_message}
    # Check if the curve list is updated
    assert lmfit_dialog.ui.curve_list.count() == 1
    # Check summary tree is updated
    assert lmfit_dialog.ui.summary_tree.topLevelItemCount() == 6
    assert lmfit_dialog.ui.summary_tree.topLevelItem(0).text(0) == "Model"
    assert lmfit_dialog.ui.summary_tree.topLevelItem(0).text(1) == "Model(breit_wigner)"
    # Check fit params tree is updated
    assert lmfit_dialog.ui.param_tree.topLevelItemCount() == 4
    assert lmfit_dialog.ui.param_tree.topLevelItem(0).text(0) == "amplitude"
    assert lmfit_dialog.ui.param_tree.topLevelItem(0).text(1) == "1.582"
