from bec_lib.serialization import msgpack
from qtpy.QtCore import QPointF


def register_serializer_extension():
    """
    Register the serializer extension for the BECConnector.
    """
    if not module_is_registered("bec_widgets.utils.serialization"):
        msgpack.register_object_hook(encode_qpointf, decode_qpointf)


def module_is_registered(module_name: str) -> bool:
    """
    Check if the module is registered in the encoder.

    Args:
        module_name (str): The name of the module to check.

    Returns:
        bool: True if the module is registered, False otherwise.
    """
    # pylint: disable=protected-access
    for enc in msgpack._encoder:
        if enc[0].__module__ == module_name:
            return True
    return False


def encode_qpointf(obj):
    """
    Encode a QPointF object to a list of floats. As this is mostly used for sending
    data to the client, it is not necessary to convert it back to a QPointF object.
    """
    if isinstance(obj, QPointF):
        return [obj.x(), obj.y()]
    return obj


def decode_qpointf(obj):
    """
    no-op function since QPointF is encoded as a list of floats.
    """
    return obj
