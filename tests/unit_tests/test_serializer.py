import pytest
from bec_lib.serialization import msgpack
from qtpy.QtCore import QPointF

from bec_widgets.utils import serialization


@pytest.mark.parametrize("data, expected", [(QPointF(20, 10), [20, 10])])
def test_serialize(data, expected):
    """
    Test serialization of various data types. Note that the auto-use fixture of
    the bec-dispatcher already registers the serializer extension, so we don't need to
    register it again here.
    """

    serialized_data = msgpack.loads(msgpack.dumps(data))
    assert serialized_data == expected


def test_multiple_extension_registration():
    """
    Test that multiple extension registrations do not cause issues.
    """
    assert msgpack.is_registered(QPointF)
    serialization.register_serializer_extension()
    assert msgpack.is_registered(QPointF)
