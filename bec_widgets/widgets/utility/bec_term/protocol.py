from typing import Protocol, runtime_checkable


@runtime_checkable
class BecTerminal(Protocol):
    """Implementors of this protocol must also be subclasses of QWidget"""

    def write(self, text: str, add_newline: bool = True): ...
