from unittest import mock

import pytest

from bec_widgets.widgets.dap_combo_box.dap_combo_box import DapComboBox

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture(scope="function")
def dap_combobox(qtbot, mocked_client):
    """DapComboBox fixture."""
    models = ["GaussianModel", "LorentzModel", "SineModel"]
    mocked_client.dap._available_dap_plugins.keys.return_value = models
    widget = create_widget(qtbot, DapComboBox, client=mocked_client)
    return widget


def test_dap_combobox_init(dap_combobox):
    """Test DapComboBox init."""
    assert dap_combobox.combobox.currentText() == "GaussianModel"
    assert dap_combobox.available_models == ["GaussianModel", "LorentzModel", "SineModel"]
    assert dap_combobox._validate_dap_model("GaussianModel") is True
    assert dap_combobox._validate_dap_model("somemodel") is False
    assert dap_combobox._validate_dap_model(None) is False


def test_dap_combobox_set_axis(dap_combobox):
    """Test DapComboBox set axis."""
    # Container to store the messages
    container = []

    def my_callback(msg: str):
        """Calback function to store the messages."""
        container.append(msg)

    dap_combobox.update_x_axis.connect(my_callback)
    dap_combobox.update_y_axis.connect(my_callback)
    dap_combobox.select_x_axis("x_axis")
    assert dap_combobox.x_axis == "x_axis"
    dap_combobox.select_y_axis("y_axis")
    assert dap_combobox.y_axis == "y_axis"
    assert container[0] == "x_axis"
    assert container[1] == "y_axis"


def test_dap_combobox_select_fit(dap_combobox):
    """Test DapComboBox select fit."""
    # Container to store the messages
    container = []

    def my_callback(msg: str):
        """Calback function to store the messages."""
        container.append(msg)

    dap_combobox.update_fit_model.connect(my_callback)
    dap_combobox.select_fit("LorentzModel")
    assert dap_combobox.combobox.currentText() == "LorentzModel"
    assert container[0] == "LorentzModel"


def test_dap_combobox_currentTextchanged(dap_combobox):
    """Test DapComboBox currentTextChanged."""
    # Container to store the messages
    container = []

    def my_callback(msg: str):
        """Calback function to store the messages."""
        container.append(msg)

    assert dap_combobox.combobox.currentText() == "GaussianModel"
    dap_combobox.update_fit_model.connect(my_callback)
    dap_combobox.combobox.setCurrentText("SineModel")
    assert container[0] == "SineModel"
