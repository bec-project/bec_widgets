from enum import IntFlag

try:

    from enum import KEEP

    class IFBase(IntFlag, boundary=KEEP): ...

except ImportError:

    IFBase = IntFlag


class Kind(IFBase):
    """
    This is used in the .kind attribute of all OphydObj (Signals, Devices).

    A Device examines its components' .kind atttribute to decide whether to
    traverse it in read(), read_configuration(), or neither. Additionally, if
    decides whether to include its name in `hints['fields']`.
    """

    omitted = 0b000
    normal = 0b001
    config = 0b010
    hinted = 0b101  # Notice that bool(hinted & normal) is True.
