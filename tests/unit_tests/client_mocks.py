# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
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
