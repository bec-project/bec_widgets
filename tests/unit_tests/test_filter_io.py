import pytest

from bec_widgets.utils.filter_io import FilterIO
from bec_widgets.widgets.dap_combo_box.dap_combo_box import DapComboBox
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture(scope="function")
def dap_mock(qtbot, mocked_client):
    """Fixture for QLineEdit widget"""
    models = ["GaussianModel", "LorentzModel", "SineModel"]
    mocked_client.dap._available_dap_plugins.keys.return_value = models
    widget = create_widget(qtbot, DapComboBox, client=mocked_client)
    return widget


@pytest.fixture(scope="function")
def line_edit_mock(qtbot, mocked_client):
    """Fixture for QLineEdit widget"""
    widget = create_widget(qtbot, DeviceLineEdit, client=mocked_client)
    return widget


def test_set_selection_combo_box(dap_mock):
    """Test set selection for QComboBox using DapComboBox"""
    assert dap_mock.fit_model_combobox.count() == 3
    FilterIO.set_selection(dap_mock.fit_model_combobox, selection=["testA", "testB"])
    assert dap_mock.fit_model_combobox.count() == 2
    assert FilterIO.check_input(widget=dap_mock.fit_model_combobox, text="testA") is True


def test_set_selection_line_edit(line_edit_mock):
    """Test set selection for QComboBox using DapComboBox"""
    FilterIO.set_selection(line_edit_mock, selection=["testA", "testB"])
    assert line_edit_mock.completer.model().rowCount() == 2
    model = line_edit_mock.completer.model()
    model_data = [model.data(model.index(i)) for i in range(model.rowCount())]
    assert model_data == ["testA", "testB"]
    assert FilterIO.check_input(widget=line_edit_mock, text="testA") is True
    FilterIO.set_selection(line_edit_mock, selection=["testC"])
    assert FilterIO.check_input(widget=line_edit_mock, text="testA") is False
    assert FilterIO.check_input(widget=line_edit_mock, text="testC") is True
