from __future__ import annotations

import enum
from dataclasses import dataclass, field
from uuid import uuid4
from weakref import WeakValueDictionary

import shiboken6
from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt, Signal
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


@dataclass
class _TerminalOwnerInfo:
    """Should be managed only by the BecConsoleRegistry. Consoles should ask the registry for
    necessary ownership info."""

    owner_console_id: str | None = None
    registered_console_ids: set[str] = field(default_factory=set)
    instance: BecTerminal | None = None
    terminal_id: str = ""
    initialized: bool = False
    persist_session: bool = False
    zoom_level: int = 0
    fallback_holder: QWidget | None = None


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

    @staticmethod
    def _is_valid_qobject(obj: object | None) -> bool:
        return obj is not None and shiboken6.isValid(obj)

    def _connect_app_cleanup(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.aboutToQuit.connect(self.clear, Qt.ConnectionType.UniqueConnection)

    @staticmethod
    def _apply_zoom_step(term: BecTerminal, direction: int) -> bool:
        method_name = "zoom_in" if direction > 0 else "zoom_out"
        method = getattr(term, method_name, None)
        if not callable(method):
            return False
        method()
        return True

    @staticmethod
    def _apply_zoom_level(term: BecTerminal, zoom_level: int) -> None:
        if zoom_level > 0:
            for _ in range(zoom_level):
                if not BecConsoleRegistry._apply_zoom_step(term, 1):
                    break
        elif zoom_level < 0:
            for _ in range(-zoom_level):
                if not BecConsoleRegistry._apply_zoom_step(term, -1):
                    break

    @staticmethod
    def _new_terminal_info(console: BecConsole) -> _TerminalOwnerInfo:
        term = _BecTermClass()
        BecConsoleRegistry._apply_zoom_level(term, console.default_zoom_level)
        return _TerminalOwnerInfo(
            registered_console_ids={console.console_id},
            owner_console_id=console.console_id,
            instance=term,
            terminal_id=console.terminal_id,
            persist_session=console.persist_terminal_session,
            zoom_level=console.default_zoom_level,
        )

    @staticmethod
    def _replace_terminal(info: _TerminalOwnerInfo, console: BecConsole) -> None:
        info.instance = _BecTermClass()
        BecConsoleRegistry._apply_zoom_level(info.instance, info.zoom_level)
        info.initialized = False
        info.owner_console_id = console.console_id
        info.registered_console_ids.add(console.console_id)
        info.persist_session = info.persist_session or console.persist_terminal_session

    def _delete_terminal_info(self, info: _TerminalOwnerInfo) -> None:
        if self._is_valid_qobject(info.instance):
            info.instance.deleteLater()  # type: ignore[union-attr]
        info.instance = None
        if self._is_valid_qobject(info.fallback_holder):
            info.fallback_holder.deleteLater()
        info.fallback_holder = None

    def _parking_parent(
        self,
        info: _TerminalOwnerInfo,
        console: BecConsole | None = None,
        *,
        avoid_console: bool = False,
    ) -> QWidget | None:
        for console_id in info.registered_console_ids:
            candidate = self._consoles.get(console_id)
            if candidate is None or candidate is console:
                continue
            if self._is_valid_qobject(candidate):
                return candidate._term_holder

        if console is None or not self._is_valid_qobject(console):
            return None

        window = console.window()
        if (
            window is not None
            and window is not console
            and self._is_valid_qobject(window)
            and not getattr(window, "_destroyed", False)
        ):
            return window

        if not avoid_console:
            return console._term_holder
        return None

    def _fallback_holder(
        self,
        info: _TerminalOwnerInfo,
        console: BecConsole | None = None,
        *,
        avoid_console: bool = False,
    ) -> QWidget:
        if not self._is_valid_qobject(info.fallback_holder):
            info.fallback_holder = QWidget(
                parent=self._parking_parent(info, console, avoid_console=avoid_console)
            )
            info.fallback_holder.setObjectName(f"_bec_console_terminal_holder_{info.terminal_id}")
            info.fallback_holder.hide()
        return info.fallback_holder

    def _park_terminal(
        self,
        info: _TerminalOwnerInfo,
        console: BecConsole | None = None,
        *,
        avoid_console: bool = False,
    ) -> None:
        if not self._is_valid_qobject(info.instance):
            return

        parent = self._parking_parent(info, console, avoid_console=avoid_console)
        if parent is None and info.persist_session:
            parent = self._fallback_holder(info, console, avoid_console=avoid_console)

        info.instance.hide()  # type: ignore[union-attr]
        info.instance.setParent(parent)  # type: ignore[union-attr]

    def clear(self) -> None:
        """Delete every tracked terminal and holder."""
        for info in list(self._terminal_registry.values()):
            self._delete_terminal_info(info)
        self._terminal_registry.clear()
        self._consoles.clear()

    def register(self, console: BecConsole):
        """
        Register an instance of BecConsole. If there is already a terminal with the associated
        terminal_id, this does not automatically grant ownership.

        Args:
            console (BecConsole): The instance to register.
        """
        self._connect_app_cleanup()
        self._consoles[console.console_id] = console
        console_id, terminal_id = console.console_id, console.terminal_id
        term_info = self._terminal_registry.get(terminal_id)
        if term_info is None:
            self._terminal_registry[terminal_id] = self._new_terminal_info(console)
            return

        term_info.persist_session = term_info.persist_session or console.persist_terminal_session
        had_registered_consoles = bool(term_info.registered_console_ids)
        term_info.registered_console_ids.add(console_id)
        if not self._is_valid_qobject(term_info.instance):
            self._replace_terminal(term_info, console)
            return
        if (
            term_info.owner_console_id is not None
            and term_info.owner_console_id not in self._consoles
        ):
            term_info.owner_console_id = None
        if term_info.owner_console_id is None and not had_registered_consoles:
            term_info.owner_console_id = console_id
        logger.info(f"Registered new console {console_id} for terminal {terminal_id}")

    def unregister(self, console: BecConsole):
        """
        Unregister an instance of BecConsole.

        Args:
            console (BecConsole): The instance to unregister.
        """
        console_id, terminal_id = console.console_id, console.terminal_id
        if console_id in self._consoles:
            del self._consoles[console_id]
        if (term_info := self._terminal_registry.get(terminal_id)) is None:
            return
        detached = console._detach_terminal_widget(term_info.instance)
        if console_id in term_info.registered_console_ids:
            term_info.registered_console_ids.remove(console_id)
        if term_info.owner_console_id == console_id:
            term_info.owner_console_id = None
        if not term_info.registered_console_ids:
            if term_info.persist_session and self._is_valid_qobject(term_info.instance):
                self._park_terminal(term_info, console, avoid_console=True)
                logger.info(f"Unregistered console {console_id} for terminal {terminal_id}")
                return

            self._delete_terminal_info(term_info)
            del self._terminal_registry[terminal_id]
        elif detached:
            self._park_terminal(term_info, console, avoid_console=True)

        logger.info(f"Unregistered console {console_id} for terminal {terminal_id}")

    def is_owner(self, console: BecConsole):
        """Returns true if the given console is the owner of its terminal"""
        if console not in self._consoles.values():
            return False
        if (info := self._terminal_registry.get(console.terminal_id)) is None:
            logger.warning(f"Console {console.console_id} references an unknown terminal!")
            return False
        if not self._is_valid_qobject(info.instance):
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
            self.register(console)

        instance_info = self._terminal_registry[terminal_id]
        if not self._is_valid_qobject(instance_info.instance):
            self._replace_terminal(instance_info, console)
        if (old_owner_console_ide := instance_info.owner_console_id) is not None:
            if (
                old_owner_console_ide != console_id
                and (old_owner := self._consoles.get(old_owner_console_ide)) is not None
            ):
                old_owner.yield_ownership()  # call this on the old owner to make sure it is updated
        instance_info.owner_console_id = console_id
        instance_info.registered_console_ids.add(console_id)
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
        if not self._is_valid_qobject(instance_info.instance):
            if instance_info.owner_console_id == console_id:
                self._replace_terminal(instance_info, console)
            else:
                return None
        if instance_info.owner_console_id == console_id:
            return instance_info.instance

    def yield_ownership(self, console: BecConsole):
        """
        Yield ownership of an instance without destroying it. The instance remains in the
        registry with no owner, available for another widget to claim.

        Args:
            console (BecConsole): The console which wishes to yield ownership of its associated terminal.
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
        console._detach_terminal_widget(term_info.instance)
        self._park_terminal(term_info, console)

    def should_initialize(self, console: BecConsole) -> bool:
        """Return true if the console should send its startup command to the terminal."""
        info = self._terminal_registry.get(console.terminal_id)
        if info is None:
            return False
        return (
            info.owner_console_id == console.console_id
            and not info.initialized
            and self._is_valid_qobject(info.instance)
        )

    def mark_initialized(self, console: BecConsole) -> None:
        info = self._terminal_registry.get(console.terminal_id)
        if info is not None and info.owner_console_id == console.console_id:
            info.initialized = True

    def get_terminal(self, term_id: str) -> BecTerminal | None:
        """Return a tracked terminal instance even if another console currently owns it."""
        info = self._terminal_registry.get(term_id)
        if info is None or not self._is_valid_qobject(info.instance):
            return None
        return info.instance

    def change_zoom(self, term_id: str, delta: int) -> int | None:
        """Apply a relative zoom change to the tracked terminal and return the resulting level."""
        info = self._terminal_registry.get(term_id)
        if info is None or not self._is_valid_qobject(info.instance) or delta == 0:
            return None

        if delta > 0:
            for _ in range(delta):
                if not self._apply_zoom_step(info.instance, 1):
                    return info.zoom_level
        else:
            for _ in range(-delta):
                if not self._apply_zoom_step(info.instance, -1):
                    return info.zoom_level
        info.zoom_level += delta
        return info.zoom_level

    def zoom_level(self, term_id: str) -> int:
        info = self._terminal_registry.get(term_id)
        if info is None:
            return 0
        return info.zoom_level

    def owner_is_visible(self, term_id: str) -> bool:
        """
        Check if the owner of an instance is currently visible.

        Args:
            term_id (str): The terminal ID to check.
        Returns:
            bool: True if the owner is visible, False otherwise.
        """
        instance_info = self._terminal_registry.get(term_id)
        if (
            instance_info is None
            or instance_info.owner_console_id is None
            or not self._is_valid_qobject(instance_info.instance)
        ):
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

    _js_callback = Signal(bool)
    initialized = Signal()

    PLUGIN = True
    ICON_NAME = "terminal"
    persist_terminal_session = False
    default_zoom_level = 1

    def __init__(
        self,
        parent=None,
        config=None,
        client=None,
        gui_id=None,
        startup_cmd: str | None = None,
        terminal_id: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self._mode = ConsoleMode.INACTIVE
        self._startup_cmd = startup_cmd
        self._is_initialized = False
        self.terminal_id = terminal_id or str(uuid4())
        self.console_id = self.gui_id
        self.term: BecTerminal | None = None  # Will be set in _set_up_instance

        self._set_up_instance()

    def _set_up_instance(self):
        """
        Set up the console instance.
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
        self._ensure_startup_started()

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
        Set the mode of the console.

        Args:
            mode (ConsoleMode): The mode to set.
        """

        match mode:
            case ConsoleMode.ACTIVE:
                if self.term:
                    if self._term_layout.indexOf(self.term) == -1:  # type: ignore[arg-type]
                        self._term_layout.addWidget(self.term)  # type: ignore # BecTerminal is QWidget
                    self.term.show()  # type: ignore[attr-defined]
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
        """
        self._startup_cmd = cmd

    def write(self, data: str, send_return: bool = True, regardless_of_ownership: bool = False):
        """
        Send data to the console

        Args:
            data (str): The data to send.
            send_return (bool): Whether to send a return after the data.
            regardless_of_ownership (bool): Whether to send to the shared terminal session even
                when this console does not currently own the visible terminal widget.
        """
        term = self.term
        if term is None and regardless_of_ownership:
            term = _bec_console_registry.get_terminal(self.terminal_id)
        if term:
            term.write(data, send_return)

    def send_ctrl_c(self, regardless_of_ownership: bool = False):
        """
        Send Ctrl+C to the console

        Args:
            regardless_of_ownership (bool): Whether to send to the shared terminal session even
                when this console does not currently own the visible terminal widget.
        """
        term = self.term
        if term is None and regardless_of_ownership:
            term = _bec_console_registry.get_terminal(self.terminal_id)
        if term:
            term.send_ctrl_c()

    @property
    def zoom_level(self) -> int:
        return _bec_console_registry.zoom_level(self.terminal_id)

    def zoom_in(self) -> int | None:
        """Increase the tracked zoom level for the shared terminal session."""
        return _bec_console_registry.change_zoom(self.terminal_id, 1)

    def zoom_out(self) -> int | None:
        """Decrease the tracked zoom level for the shared terminal session."""
        return _bec_console_registry.change_zoom(self.terminal_id, -1)

    def _ensure_startup_started(self):
        if not self.startup_cmd or not _bec_console_registry.should_initialize(self):
            return
        self.write(self.startup_cmd, True)
        _bec_console_registry.mark_initialized(self)

    def _detach_terminal_widget(self, term: BecTerminal | None) -> bool:
        if term is None or not BecConsoleRegistry._is_valid_qobject(term):
            if self.term is term:
                self.term = None
            return False

        is_child = self.isAncestorOf(term)  # type: ignore[arg-type]
        if self._term_layout.indexOf(term) != -1:  # type: ignore[arg-type]
            self._term_layout.removeWidget(term)  # type: ignore[arg-type]
            is_child = True
        if is_child:
            term.hide()  # type: ignore[attr-defined]
            term.setParent(None)  # type: ignore[attr-defined]
        if self.term is term:
            self.term = None
        return is_child

    def take_terminal_ownership(self):
        """
        Take ownership of a console instance from the registry. This will transfer the instance
        from its current owner (if any) to this widget.
        """
        # Get the instance from registry
        self.term = _bec_console_registry.take_ownership(self)
        self._infer_mode()
        self._ensure_startup_started()
        if self._mode == ConsoleMode.ACTIVE:
            logger.debug(f"Widget {self.gui_id} took ownership of instance {self.terminal_id}")

    def yield_ownership(self):
        """
        Yield ownership of the console instance. The instance remains in the registry with no owner,
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
    persist_terminal_session = True

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(
            parent=parent,
            config=config,
            client=client,
            gui_id=gui_id,
            terminal_id="bec_shell",
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
