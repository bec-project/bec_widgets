from __future__ import annotations

import enum
from uuid import uuid4
from weakref import WeakValueDictionary

import shiboken6
from bec_lib.logger import bec_logger
from pydantic import BaseModel
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QStackedLayout,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.utility.bec_term.protocol import BecTerminal
from bec_widgets.widgets.utility.bec_term.util import get_current_bec_term_class

logger = bec_logger.logger

_BecTermClass = get_current_bec_term_class()

# Note on definitions:
# Terminal: an instance of a terminal widget with a system shell
# Console: one of possibly several widgets which may share ownership of one single terminal
# Shell: a Console set to start the BEC IPython client in its terminal


class ConsoleMode(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    HIDDEN = "hidden"


class _TerminalOwnerInfo(BaseModel):
    """Should be managed only by the BecConsoleRegistry. Consoles should ask the registry for
    necessary ownership info."""

    owner_console_id: str | None = None
    registered_console_ids: set[str] = set()
    instance: BecTerminal
    terminal_id: str
    initialized: bool = False
    keep_if_last_console_closed: bool = False

    model_config = {"arbitrary_types_allowed": True}


class BecConsoleRegistry:
    """
    A registry for the BecConsole class to manage its instances.
    """

    def __init__(self):
        """
        Initialize the registry.
        """
        self._consoles: WeakValueDictionary[str, BecConsole] = WeakValueDictionary()
        self._terminal_registry: dict[str, _TerminalOwnerInfo] = {}

    def register(self, console: BecConsole):
        """
        Register an instance of BecConsole. If there is already a terminal with the associated
        terminal_id, this does not automatically grant ownership.

        Args:
            console (BecConsole): The instance to register.
        """
        # create this on first registration of anything, so we know QApp exists
        if not getattr(self, "_persevered_terminals", None):
            self._preserved_terminals = QWidget()

        self._consoles[console.console_id] = console
        console_id, terminal_id = console.console_id, console.terminal_id
        if (term_info := self._terminal_registry.get(terminal_id)) is None or not shiboken6.isValid(
            term_info.instance
        ):
            term = _BecTermClass()
            self._terminal_registry[terminal_id] = _TerminalOwnerInfo(
                registered_console_ids={console_id},
                owner_console_id=console_id,
                instance=term,
                terminal_id=terminal_id,
                keep_if_last_console_closed=console.persevere_terminal,
            )
            if console.persevere_terminal:
                term.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            return

        logger.info(f"Registered new console {console_id} for terminal {terminal_id}")
        term_info.registered_console_ids.add(console_id)

    def unregister(self, console: BecConsole):
        """
        Unregister an instance of BecConsole.

        Args:
            instance (BecConsole): The instance to unregister.
        """
        console_id, terminal_id = console.console_id, console.terminal_id
        if console_id in self._consoles:
            del self._consoles[console_id]
        if (term_info := self._terminal_registry.get(terminal_id)) is None:
            return
        if console_id in term_info.registered_console_ids:
            term_info.registered_console_ids.remove(console_id)
        if term_info.owner_console_id == console_id:
            term_info.owner_console_id = None
        if not term_info.registered_console_ids:
            if not term_info.keep_if_last_console_closed:
                term_info.instance.deleteLater()
                del self._terminal_registry[terminal_id]
            else:
                term_info.instance.setParent(self._preserved_terminals)

        logger.info(f"Unregistered console {console_id} for terminal {terminal_id}")

    def is_owner(self, console: BecConsole):
        """Returns true if the given console is the owner of its terminal"""
        if console not in self._consoles.values():
            return False
        if (info := self._terminal_registry.get(console.terminal_id)) is None:
            logger.warning(f"Console {console.console_id} references an unknown terminal!")
            return False
        return info.owner_console_id == console.console_id

    def take_ownership(self, console: BecConsole) -> BecTerminal | None:
        """
        Transfer ownership of a terminal to the given console.

        Args:
            console: the console which wishes to take ownership of its associated terminal.
        Returns:
            BecTerminal | None: The instance if ownership transfer was successful, None otherwise.
        """
        console_id, terminal_id = console.console_id, console.terminal_id

        if terminal_id not in self._terminal_registry:
            logger.warning(f"Terminal {terminal_id} not found in registry")
            return None

        instance_info = self._terminal_registry[terminal_id]
        if (old_owner_console_id := instance_info.owner_console_id) is not None:
            if (old_owner := self._consoles.get(old_owner_console_id)) is not None:
                old_owner.yield_ownership()  # call this on the old owner to make sure it is updated
        instance_info.owner_console_id = console_id
        logger.info(f"Transferred ownership of terminal {terminal_id} to {console_id}")
        return instance_info.instance

    def try_get_term(self, console: BecConsole) -> BecTerminal | None:
        """
        Return the terminal instance if the requesting console is the owner

        Args:
            console: the requesting console.
        Returns:
            BecTerminal | None: The instance if the console is the owner, None otherwise.
        """
        console_id, terminal_id = console.console_id, console.terminal_id
        logger.debug(f"checking term for {console_id}")
        if terminal_id not in self._terminal_registry:
            logger.warning(f"Terminal {terminal_id} not found in registry")
            return None

        instance_info = self._terminal_registry[terminal_id]
        if instance_info.owner_console_id == console_id:
            return instance_info.instance

    def yield_ownership(self, console: BecConsole):
        """
        Yield ownership of a instance without destroying it. The instance remains in the
        registry with no owner, available for another widget to claim.

        Args:
            gui_id (str): The GUI ID of the widget yielding ownership.

        """
        console_id, terminal_id = console.console_id, console.terminal_id
        logger.debug(f"Console {console_id} attempted to yield ownership")
        if console_id not in self._consoles or terminal_id not in self._terminal_registry:
            return

        term_info = self._terminal_registry[terminal_id]
        if term_info.owner_console_id != console_id:
            logger.debug(f"But it was not the owner, which was {term_info.owner_console_id}!")
            return
        term_info.owner_console_id = None
        term_info.instance.setParent(None)

    def owner_is_visible(self, term_id: str) -> bool:
        """
        Check if the owner of a instance is currently visible.

        Args:
            unique_id (str): The unique identifier for the instance.
        Returns:
            bool: True if the owner is visible, False otherwise.
        """
        instance_info = self._terminal_registry.get(term_id)
        if instance_info is None or instance_info.owner_console_id is None:
            return False

        if (owner := self._consoles.get(instance_info.owner_console_id)) is None:
            return False
        return owner.isVisible()


_bec_console_registry = BecConsoleRegistry()


class _Overlay(QWidget):
    def __init__(self, console: BecConsole):
        super().__init__(parent=console)
        self._console = console

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._console.take_terminal_ownership()
            event.accept()
            return
        return super().mousePressEvent(event)


class BecConsole(BECWidget, QWidget):
    """A console widget with access to a shared registry of terminals, such that instances can be moved around."""

    PLUGIN = True
    ICON_NAME = "terminal"

    def __init__(
        self,
        parent=None,
        config=None,
        client=None,
        gui_id=None,
        startup_cmd: str | None = None,
        terminal_id: str | None = None,
        persevere_terminal: bool = False,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self._mode = ConsoleMode.INACTIVE
        self._startup_cmd = startup_cmd
        self._is_initialized = False
        self.terminal_id = terminal_id or str(uuid4())
        self.console_id = self.gui_id
        self.term: BecTerminal | None = None  # Will be set in _set_up_instance
        self.persevere_terminal = persevere_terminal

        self._set_up_instance()

    def _set_up_instance(self):
        """
        Set up the web instance and UI elements.
        """
        self._stacked_layout = QStackedLayout()
        # self._stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self._term_holder = QWidget()
        self._term_layout = QVBoxLayout()
        self._term_layout.setContentsMargins(0, 0, 0, 0)
        self._term_holder.setLayout(self._term_layout)

        self.setLayout(self._stacked_layout)

        # prepare overlay
        self._overlay = _Overlay(self)
        layout = QVBoxLayout(self._overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("Click to activate terminal", self._overlay)
        layout.addWidget(label)

        self._stacked_layout.addWidget(self._term_holder)
        self._stacked_layout.addWidget(self._overlay)

        # will create a new terminal instance if there isn't already one for this ID
        _bec_console_registry.register(self)
        self._infer_mode()
        if self.startup_cmd:
            self.write(self.startup_cmd, True)  # will have no effect if not the owner

    def _infer_mode(self):
        self.term = _bec_console_registry.try_get_term(self)
        if self.term:
            self._set_mode(ConsoleMode.ACTIVE)
        elif self.isHidden():
            self._set_mode(ConsoleMode.HIDDEN)
        else:
            self._set_mode(ConsoleMode.INACTIVE)

    def _set_mode(self, mode: ConsoleMode):
        """
        Set the mode of the web console.

        Args:
            mode (ConsoleMode): The mode to set.
        """

        match mode:
            case ConsoleMode.ACTIVE:
                if self.term:
                    if self.term not in (self._term_layout.children()):
                        self._term_layout.addWidget(self.term)  # type: ignore # BecTerminal is QWidget
                    self._stacked_layout.setCurrentIndex(0)
                    self._mode = mode
                else:
                    self._stacked_layout.setCurrentIndex(1)
                    self._mode = ConsoleMode.INACTIVE
            case ConsoleMode.INACTIVE:
                self._stacked_layout.setCurrentIndex(1)
                self._mode = mode
            case ConsoleMode.HIDDEN:
                self._stacked_layout.setCurrentIndex(1)
                self._mode = mode

    @property
    def startup_cmd(self):
        """
        Get the startup command for the web console.
        """
        return self._startup_cmd

    @startup_cmd.setter
    def startup_cmd(self, cmd: str | None):
        """
        Set the startup command for the console.
        logger.info(f"{self._console_id} inferred mode active through ownerp)
        """
        self._startup_cmd = cmd

    def write(self, data: str, send_return: bool = True):
        """
        Send data to the console

        Args:
            data (str): The data to send.
            send_return (bool): Whether to send a return after the data.
        """
        if self.term:
            self.term.write(data, send_return)

    def take_terminal_ownership(self):
        """
        Take ownership of a web instance from the registry. This will transfer the instance
        from its current owner (if any) to this widget.
        """
        # Get the instance from registry
        self.term = _bec_console_registry.take_ownership(self)
        self._infer_mode()
        if self._mode == ConsoleMode.ACTIVE:
            logger.debug(f"Widget {self.gui_id} took ownership of instance {self.terminal_id}")

    def yield_ownership(self):
        """
        Yield ownership of the instance. The instance remains in the registry with no owner,
        available for another widget to claim. This is automatically called when the
        widget becomes hidden.
        """
        _bec_console_registry.yield_ownership(self)
        self._infer_mode()
        if self._mode != ConsoleMode.ACTIVE:
            logger.debug(f"Widget {self.gui_id} yielded ownership of instance {self.terminal_id}")

    def hideEvent(self, event):
        """Called when the widget is hidden. Automatically yields ownership."""
        self.yield_ownership()
        super().hideEvent(event)

    def showEvent(self, event):
        """Called when the widget is shown. Updates UI state based on ownership."""
        super().showEvent(event)
        if not _bec_console_registry.is_owner(self):
            if not _bec_console_registry.owner_is_visible(self.terminal_id):
                self.take_terminal_ownership()

    def cleanup(self):
        """Unregister this console on destruction."""
        _bec_console_registry.unregister(self)
        super().cleanup()


class BECShell(BecConsole):
    """
    A BecConsole pre-configured to run the BEC shell.
    We cannot simply expose the web console properties to Qt as we need to have a deterministic
    startup behavior for sharing the same shell instance across multiple widgets.
    """

    ICON_NAME = "hub"

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(
            parent=parent,
            config=config,
            client=client,
            gui_id=gui_id,
            terminal_id="bec_shell",
            persevere_terminal=True,
            **kwargs,
        )

    @property
    def startup_cmd(self):
        """
        Get the startup command for the BEC shell.
        """
        if self.bec_dispatcher.cli_server is None:
            return "bec --nogui"
        return f"bec --gui-id {self.bec_dispatcher.cli_server.gui_id}"

    @startup_cmd.setter
    def startup_cmd(self, cmd: str | None): ...


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    widget = QTabWidget()

    # Create two consoles with different unique_ids
    bec_console_1a = BecConsole(startup_cmd="htop", gui_id="console_1_a", terminal_id="terminal_1")
    bec_console_1b = BecConsole(startup_cmd="htop", gui_id="console_1_b", terminal_id="terminal_1")
    bec_console_1 = QWidget()
    bec_console_1_layout = QHBoxLayout(bec_console_1)
    bec_console_1_layout.addWidget(bec_console_1a)
    bec_console_1_layout.addWidget(bec_console_1b)
    bec_console2 = BECShell()
    bec_console3 = BecConsole(gui_id="console_3", terminal_id="terminal_1")
    widget.addTab(bec_console_1, "Console 1")
    widget.addTab(bec_console2, "Console 2 - BEC Shell")
    widget.addTab(bec_console3, "Console 3 -- mirror of Console 1")
    widget.show()

    widget.resize(800, 600)

    sys.exit(app.exec_())
