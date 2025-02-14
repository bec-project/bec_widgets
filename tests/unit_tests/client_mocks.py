# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from math import inf
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from bec_lib.bec_service import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.redis_connector import RedisConnector

from bec_widgets.tests.utils import DEVICES, DMMock, FakePositioner, Positioner


def fake_redis_server(host, port):
    redis = fakeredis.FakeRedis()
    return redis


@pytest.fixture(scope="function")
def mocked_client(bec_dispatcher):
    connector = RedisConnector("localhost:1", redis_cls=fake_redis_server)
    # Create a MagicMock object
    client = MagicMock()  # TODO change to real BECClient

    # Shutdown the original client
    bec_dispatcher.client.shutdown()
    # Mock the connector attribute
    bec_dispatcher.client = client

    # Mock the device_manager.devices attribute
    client.connector = connector
    client.device_manager = DMMock()
    client.device_manager.add_devives(DEVICES)

    def mock_mv(*args, relative=False):
        # Extracting motor and value pairs
        for i in range(0, len(args), 2):
            motor = args[i]
            value = args[i + 1]
            motor.move(value, relative=relative)
        return MagicMock(wait=MagicMock())

    client.scans = MagicMock(mv=mock_mv)

    # Ensure isinstance check for Positioner passes
    original_isinstance = isinstance

    def isinstance_mock(obj, class_info):
        if class_info == Positioner and isinstance(obj, FakePositioner):
            return True
        return original_isinstance(obj, class_info)

    with patch("builtins.isinstance", new=isinstance_mock):
        yield client
    connector.shutdown()  # TODO change to real BECClient


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
    client = mocked_client
    client.service_status = dap_services
    client.connector.set(
        topic=MessageEndpoints.dap_available_plugins("dap"), msg=dap_plugin_message
    )

    # Patch the client's DAP attribute so that the available models include "GaussianModel"
    patched_models = {"GaussianModel": {}, "LorentzModel": {}, "SineModel": {}}
    client.dap._available_dap_plugins = patched_models

    yield client
