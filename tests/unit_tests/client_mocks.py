# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from math import inf
from unittest.mock import MagicMock, PropertyMock, patch

import fakeredis
import pytest
from bec_lib.bec_service import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.scan_history import ScanHistory

from bec_widgets.tests.utils import FakePositioner, Positioner


@pytest.fixture(scope="function")
def mocked_client(bec_dispatcher):

    # Ensure isinstance check for Positioner passes
    original_isinstance = isinstance

    def isinstance_mock(obj, class_info):
        if class_info == Positioner and isinstance(obj, FakePositioner):
            return True
        return original_isinstance(obj, class_info)

    with patch("builtins.isinstance", new=isinstance_mock):
        yield bec_dispatcher.client
    bec_dispatcher.client.connector.shutdown()


##################################################
# Client Fixture with DAP
##################################################
@pytest.fixture(scope="function")
def dap_plugin_message():
    msg = messages.AvailableResourceMessage(
        **{
            "resource": {
                "GaussianModel": {
                    "class": "LmfitService1D",
                    "user_friendly_name": "GaussianModel",
                    "class_doc": "A model based on a Gaussian or normal distribution lineshape.\n\n    The model has three Parameters: `amplitude`, `center`, and `sigma`.\n    In addition, parameters `fwhm` and `height` are included as\n    constraints to report full width at half maximum and maximum peak\n    height, respectively.\n\n    .. math::\n\n        f(x; A, \\mu, \\sigma) = \\frac{A}{\\sigma\\sqrt{2\\pi}} e^{[{-{(x-\\mu)^2}/{{2\\sigma}^2}}]}\n\n    where the parameter `amplitude` corresponds to :math:`A`, `center` to\n    :math:`\\mu`, and `sigma` to :math:`\\sigma`. The full width at half\n    maximum is :math:`2\\sigma\\sqrt{2\\ln{2}}`, approximately\n    :math:`2.3548\\sigma`.\n\n    For more information, see: https://en.wikipedia.org/wiki/Normal_distribution\n\n    ",
                    "run_doc": "A model based on a Gaussian or normal distribution lineshape.\n\n    The model has three Parameters: `amplitude`, `center`, and `sigma`.\n    In addition, parameters `fwhm` and `height` are included as\n    constraints to report full width at half maximum and maximum peak\n    height, respectively.\n\n    .. math::\n\n        f(x; A, \\mu, \\sigma) = \\frac{A}{\\sigma\\sqrt{2\\pi}} e^{[{-{(x-\\mu)^2}/{{2\\sigma}^2}}]}\n\n    where the parameter `amplitude` corresponds to :math:`A`, `center` to\n    :math:`\\mu`, and `sigma` to :math:`\\sigma`. The full width at half\n    maximum is :math:`2\\sigma\\sqrt{2\\ln{2}}`, approximately\n    :math:`2.3548\\sigma`.\n\n    For more information, see: https://en.wikipedia.org/wiki/Normal_distribution\n\n    \n        Args:\n            scan_item (ScanItem): Scan item or scan ID\n            device_x (DeviceBase | str): Device name for x\n            signal_x (DeviceBase | str): Signal name for x\n            device_y (DeviceBase | str): Device name for y\n            signal_y (DeviceBase | str): Signal name for y\n            parameters (dict): Fit parameters\n        ",
                    "run_name": "fit",
                    "signature": [
                        {
                            "name": "args",
                            "kind": "VAR_POSITIONAL",
                            "default": "_empty",
                            "annotation": "_empty",
                        },
                        {
                            "name": "scan_item",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "ScanItem | str",
                        },
                        {
                            "name": "device_x",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "signal_x",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "device_y",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "signal_y",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "parameters",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "dict",
                        },
                        {
                            "name": "kwargs",
                            "kind": "VAR_KEYWORD",
                            "default": "_empty",
                            "annotation": "_empty",
                        },
                    ],
                    "auto_fit_supported": True,
                    "params": {
                        "amplitude": {
                            "name": "amplitude",
                            "value": 1.0,
                            "vary": True,
                            "min": -inf,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "center": {
                            "name": "center",
                            "value": 0.0,
                            "vary": True,
                            "min": -inf,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "sigma": {
                            "name": "sigma",
                            "value": 1.0,
                            "vary": True,
                            "min": 0,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "fwhm": {
                            "name": "fwhm",
                            "value": 2.35482,
                            "vary": False,
                            "min": -inf,
                            "max": inf,
                            "expr": "2.3548200*sigma",
                            "brute_step": None,
                            "user_data": None,
                        },
                        "height": {
                            "name": "height",
                            "value": 0.3989423,
                            "vary": False,
                            "min": -inf,
                            "max": inf,
                            "expr": "0.3989423*amplitude/max(1e-15, sigma)",
                            "brute_step": None,
                            "user_data": None,
                        },
                    },
                    "class_args": [],
                    "class_kwargs": {"model": "GaussianModel"},
                }
            }
        }
    )
    yield msg


@pytest.fixture(scope="function")
def mocked_client_with_dap(mocked_client, dap_plugin_message):
    dap_services = {
        "BECClient": messages.StatusMessage(name="BECClient", status=1, info={}),
        "DAPServer/LmfitService1D": messages.StatusMessage(
            name="LmfitService1D", status=1, info={}
        ),
    }
    type(mocked_client).service_status = PropertyMock(return_value=dap_services)
    mocked_client.connector.set(
        topic=MessageEndpoints.dap_available_plugins("dap"), msg=dap_plugin_message
    )

    # Patch the client's DAP attribute so that the available models include "GaussianModel"
    patched_models = {"GaussianModel": {}, "LorentzModel": {}, "SineModel": {}}
    mocked_client.dap._available_dap_plugins = patched_models

    yield mocked_client


class DummyData:
    def __init__(self, val, timestamps):
        self.val = val
        self.timestamps = timestamps

    def get(self, key, default=None):
        if key == "val":
            return self.val
        return default


def create_dummy_scan_item():
    """
    Helper to create a dummy scan item with both live_data and metadata/status_message info.
    """
    dummy_live_data = {
        "samx": {"samx": DummyData(val=[10, 20, 30], timestamps=[100, 200, 300])},
        "samy": {"samy": DummyData(val=[5, 10, 15], timestamps=[100, 200, 300])},
        "bpm4i": {"bpm4i": DummyData(val=[5, 6, 7], timestamps=[101, 201, 301])},
        "async_device": {"async_device": DummyData(val=[1, 2, 3], timestamps=[11, 21, 31])},
    }
    dummy_scan = MagicMock()
    dummy_scan.live_data = dummy_live_data
    dummy_scan.metadata = {
        "bec": {
            "scan_id": "dummy",
            "scan_report_devices": ["samx"],
            "readout_priority": {"monitored": ["bpm4i"], "async": ["async_device"]},
        }
    }
    dummy_scan.status_message.info = {
        "readout_priority": {"monitored": ["bpm4i"], "async": ["async_device"]},
        "scan_report_devices": ["samx"],
    }
    return dummy_scan


def inject_scan_history(widget, scan_history_factory, *history_args):
    """
    Helper to inject scan history messages into client history.
    """
    history_msgs = []
    for scan_id, scan_number in history_args:
        history_msgs.append(scan_history_factory(scan_id=scan_id, scan_number=scan_number))
    widget.client.history = ScanHistory(widget.client, False)
    for msg in history_msgs:
        widget.client.history._scan_data[msg.scan_id] = msg
        widget.client.history._scan_ids.append(msg.scan_id)
    widget.client.queue.scan_storage.current_scan = None
    return history_msgs
