from typing import Type

from bec_lib.codecs import BECCodec
from bec_lib.serialization import msgpack
from qtpy.QtCore import QPointF


def register_serializer_extension():
    """
    Register the serializer extension for the BECConnector.
    """
    if not msgpack.is_registered(QPointF):
        msgpack.register_codec(QPointFEncoder)


class QPointFEncoder(BECCodec):
    obj_type: Type = QPointF

    @staticmethod
    def encode(obj: QPointF) -> str:
        """
        Encode a QPointF object to a list of floats. As this is mostly used for sending
        data to the client, it is not necessary to convert it back to a QPointF object.
        """
        if isinstance(obj, QPointF):
            return [obj.x(), obj.y()]
        return obj

    @staticmethod
    def decode(type_name: str, data: list[float]) -> list[float]:
        """
        no-op function since QPointF is encoded as a list of floats.
        """
        return data
