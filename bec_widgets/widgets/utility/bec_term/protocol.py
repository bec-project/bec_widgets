from typing import Protocol, runtime_checkable


@runtime_checkable
class BecTerminal(Protocol):
    """Implementors of this protocol must also be subclasses of QWidget"""

    def write(self, text: str, add_newline: bool = True): ...

    def zoom_in(self): ...

    def zoom_out(self): ...

    def send_ctrl_c(self): ...
