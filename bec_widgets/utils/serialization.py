from bec_lib.codecs import BECCodec
from bec_lib.serialization import msgpack
from qtpy.QtCore import QPointF


class QPointFEncoder(BECCodec):
    obj_type = QPointF

    @staticmethod
    def encode(obj: QPointF) -> list[float]:
        """Encode a QPointF object to a list of floats."""
        return [obj.x(), obj.y()]

    @staticmethod
    def decode(type_name: str, data: list[float]) -> list[float]:
        """No-op function since QPointF is encoded as a list of floats."""
        return data


def register_serializer_extension():
    """
    Register the serializer extension for the BECConnector.
    """
    if not msgpack.is_registered(QPointF):
        msgpack.register(QPointF, QPointFEncoder.encode, QPointFEncoder.decode)
