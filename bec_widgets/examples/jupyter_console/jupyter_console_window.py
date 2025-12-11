from __future__ import annotations

import ast
import importlib
import os
from typing import Any, Dict

import numpy as np
import pyqtgraph as pg
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.cli.rpc.rpc_widget_handler import widget_handler
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.widget_io import WidgetHierarchy as wh
from bec_widgets.widgets.editors.jupyter_console.jupyter_console import BECJupyterConsole


class JupyterConsoleWindow(QWidget):  # pragma: no cover:
    """A widget that contains a Jupyter console linked to BEC Widgets with full API access.

    Features:
    - Add widgets dynamically from the UI (top-right panel) or from the console via `jc.add_widget(...)`.
    - Add BEC widgets by registered type via a combo box or `jc.add_widget_by_type(...)`.
    - Each added widget appears as a new tab in the left tab widget and is exposed in the console under the chosen shortcut.
    - Hardcoded example tabs removed; two examples are added programmatically at startup in the __main__ block.
    """

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self._widgets_by_name: Dict[str, QWidget] = {}
        self._init_ui()

        # expose helper API and basics in the inprocess console
        if self.console.inprocess is True:
            # A thin API wrapper so users have a stable, minimal surface in the console
            class _ConsoleAPI:
                def __init__(self, win: "JupyterConsoleWindow"):
                    self._win = win

                def add_widget(self, widget: QWidget, shortcut: str, title: str | None = None):
                    """Add an existing QWidget as a new tab and expose it in the console under `shortcut`."""
                    return self._win.add_widget(widget, shortcut, title=title)

                def add_widget_by_class_path(
                    self,
                    class_path: str,
                    shortcut: str,
                    kwargs: dict | None = None,
                    title: str | None = None,
                ):
                    """Import a QWidget class from `class_path`, instantiate it, and add it."""
                    return self._win.add_widget_by_class_path(
                        class_path, shortcut, kwargs=kwargs, title=title
                    )

                def add_widget_by_type(
                    self,
                    widget_type: str,
                    shortcut: str,
                    kwargs: dict | None = None,
                    title: str | None = None,
                ):
                    """Instantiate a registered BEC widget by type string and add it."""
                    return self._win.add_widget_by_type(
                        widget_type, shortcut, kwargs=kwargs, title=title
                    )

                def list_widgets(self):
                    return list(self._win._widgets_by_name.keys())

                def get_widget(self, shortcut: str) -> QWidget | None:
                    return self._win._widgets_by_name.get(shortcut)

                def available_widgets(self):
                    return list(widget_handler.widget_classes.keys())

            self.jc = _ConsoleAPI(self)
            self._push_to_console({"jc": self.jc, "np": np, "pg": pg, "wh": wh})

    def _init_ui(self):
        self.layout = QHBoxLayout(self)

        # Horizontal splitter: left = widgets tabs, right = console + add-widget panel
        splitter = QSplitter(self)
        self.layout.addWidget(splitter)

        # Left: tabs that will host dynamically added widgets
        self.tab_widget = QTabWidget(splitter)

        # Right: console area with an add-widget mini panel on top
        right_panel = QGroupBox("Jupyter Console", splitter)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 12, 6, 6)

        # Add-widget mini panel
        add_panel = QFrame(right_panel)
        shape = QFrame.Shape.StyledPanel  # PySide6 style enums
        add_panel.setFrameShape(shape)
        add_grid = QGridLayout(add_panel)
        add_grid.setContentsMargins(8, 8, 8, 8)
        add_grid.setHorizontalSpacing(8)
        add_grid.setVerticalSpacing(6)

        instr = QLabel(
            "Add a widget by class path or choose a registered BEC widget type,"
            " and expose it in the console under a shortcut.\n"
            "Example class path: bec_widgets.widgets.plots.waveform.waveform.Waveform"
        )
        instr.setWordWrap(True)
        add_grid.addWidget(instr, 0, 0, 1, 2)

        # Registered widget selector
        reg_label = QLabel("Registered")
        reg_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.registry_combo = QComboBox(add_panel)
        self.registry_combo.setEditable(False)
        self.refresh_btn = QPushButton("Refresh")
        reg_row = QHBoxLayout()
        reg_row.addWidget(self.registry_combo)
        reg_row.addWidget(self.refresh_btn)
        add_grid.addWidget(reg_label, 1, 0)
        add_grid.addLayout(reg_row, 1, 1)

        # Class path entry
        class_label = QLabel("Class")
        class_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.class_path_edit = QLineEdit(add_panel)
        self.class_path_edit.setPlaceholderText("Fully-qualified class path (e.g. pkg.mod.Class)")
        add_grid.addWidget(class_label, 2, 0)
        add_grid.addWidget(self.class_path_edit, 2, 1)

        # Shortcut
        shortcut_label = QLabel("Shortcut")
        shortcut_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.shortcut_edit = QLineEdit(add_panel)
        self.shortcut_edit.setPlaceholderText("Shortcut in console (variable name)")
        add_grid.addWidget(shortcut_label, 3, 0)
        add_grid.addWidget(self.shortcut_edit, 3, 1)

        # Kwargs
        kwargs_label = QLabel("Kwargs")
        kwargs_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.kwargs_edit = QLineEdit(add_panel)
        self.kwargs_edit.setPlaceholderText(
            'Optional kwargs as dict literal, e.g. {"popups": True}'
        )
        add_grid.addWidget(kwargs_label, 4, 0)
        add_grid.addWidget(self.kwargs_edit, 4, 1)

        # Title
        title_label = QLabel("Title")
        title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.title_edit = QLineEdit(add_panel)
        self.title_edit.setPlaceholderText("Optional tab title (defaults to Shortcut or Class)")
        add_grid.addWidget(title_label, 5, 0)
        add_grid.addWidget(self.title_edit, 5, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add by class path")
        self.add_btn.clicked.connect(self._on_add_widget_clicked)
        self.add_reg_btn = QPushButton("Add registered")
        self.add_reg_btn.clicked.connect(self._on_add_registered_clicked)
        btn_row.addStretch(1)
        btn_row.addWidget(self.add_reg_btn)
        btn_row.addWidget(self.add_btn)
        add_grid.addLayout(btn_row, 6, 0, 1, 2)

        # Make the second column expand
        add_grid.setColumnStretch(0, 0)
        add_grid.setColumnStretch(1, 1)

        # Console widget
        self.console = BECJupyterConsole(inprocess=True)

        # Vertical splitter between add panel and console
        right_splitter = QSplitter(Qt.Vertical, right_panel)
        right_splitter.addWidget(add_panel)
        right_splitter.addWidget(self.console)
        right_splitter.setStretchFactor(0, 0)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([300, 600])

        # Put splitter into the right group box
        right_layout.addWidget(right_splitter)

        # Populate registry on startup
        self._populate_registry_widgets()

    def _populate_registry_widgets(self):
        try:
            widget_handler.update_available_widgets()
            items = sorted(widget_handler.widget_classes.keys())
        except Exception as exc:
            print(f"Failed to load registered widgets: {exc}")
            items = []
        self.registry_combo.clear()
        self.registry_combo.addItems(items)

    def _on_add_widget_clicked(self):
        class_path = self.class_path_edit.text().strip()
        shortcut = self.shortcut_edit.text().strip()
        kwargs_text = self.kwargs_edit.text().strip()
        title = self.title_edit.text().strip() or None

        if not class_path or not shortcut:
            print("Please provide both class path and shortcut.")
            return

        kwargs: dict | None = None
        if kwargs_text:
            try:
                parsed = ast.literal_eval(kwargs_text)
                if isinstance(parsed, dict):
                    kwargs = parsed
                else:
                    print("Kwargs must be a Python dict literal, ignoring input.")
            except Exception as exc:
                print(f"Failed to parse kwargs: {exc}")

        try:
            widget = self._instantiate_from_class_path(class_path, kwargs=kwargs)
        except Exception as exc:
            print(f"Failed to instantiate {class_path}: {exc}")
            return

        try:
            self.add_widget(widget, shortcut, title=title)
        except Exception as exc:
            print(f"Failed to add widget: {exc}")
            return

        # focus the newly added tab
        idx = self.tab_widget.count() - 1
        if idx >= 0:
            self.tab_widget.setCurrentIndex(idx)

    def _on_add_registered_clicked(self):
        widget_type = self.registry_combo.currentText().strip()
        shortcut = self.shortcut_edit.text().strip()
        kwargs_text = self.kwargs_edit.text().strip()
        title = self.title_edit.text().strip() or None

        if not widget_type or not shortcut:
            print("Please select a registered widget and provide a shortcut.")
            return

        kwargs: dict | None = None
        if kwargs_text:
            try:
                parsed = ast.literal_eval(kwargs_text)
                if isinstance(parsed, dict):
                    kwargs = parsed
                else:
                    print("Kwargs must be a Python dict literal, ignoring input.")
            except Exception as exc:
                print(f"Failed to parse kwargs: {exc}")

        try:
            self.add_widget_by_type(widget_type, shortcut, kwargs=kwargs, title=title)
        except Exception as exc:
            print(f"Failed to add registered widget: {exc}")
            return

        # focus the newly added tab
        idx = self.tab_widget.count() - 1
        if idx >= 0:
            self.tab_widget.setCurrentIndex(idx)

    def _instantiate_from_class_path(self, class_path: str, kwargs: dict | None = None) -> QWidget:
        module_path, _, class_name = class_path.rpartition(".")
        if not module_path or not class_name:
            raise ValueError("class_path must be of the form 'package.module.Class'")
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        if kwargs is None:
            obj = cls()
        else:
            obj = cls(**kwargs)
        if not isinstance(obj, QWidget):
            raise TypeError(f"Instantiated object from {class_path} is not a QWidget: {type(obj)}")
        return obj

    def add_widget(self, widget: QWidget, shortcut: str, title: str | None = None) -> QWidget:
        """Add a QWidget as a new tab and expose it in the Jupyter console.

        - widget: a QWidget instance to host in a new tab
        - shortcut: variable name used in the console to access it
        - title: optional tab title (defaults to shortcut or class name)
        """
        if not isinstance(widget, QWidget):
            raise TypeError("widget must be a QWidget instance")
        if not shortcut or not shortcut.isidentifier():
            raise ValueError("shortcut must be a valid Python identifier")
        if shortcut in self._widgets_by_name:
            raise ValueError(f"A widget with shortcut '{shortcut}' already exists")
        if self.console.inprocess is not True:
            raise RuntimeError("Adding widgets and exposing them requires inprocess console")

        tab_title = title or shortcut or widget.__class__.__name__
        self.tab_widget.addTab(widget, tab_title)
        self._widgets_by_name[shortcut] = widget

        # Expose in console under the given shortcut
        self._push_to_console({shortcut: widget})
        return widget

    def add_widget_by_class_path(
        self, class_path: str, shortcut: str, kwargs: dict | None = None, title: str | None = None
    ) -> QWidget:
        widget = self._instantiate_from_class_path(class_path, kwargs=kwargs)
        return self.add_widget(widget, shortcut, title=title)

    def add_widget_by_type(
        self, widget_type: str, shortcut: str, kwargs: dict | None = None, title: str | None = None
    ) -> QWidget:
        """Instantiate a registered BEC widget by its type string and add it as a tab.

        If kwargs does not contain `object_name`, it will default to the provided shortcut.
        """
        # Ensure registry is loaded
        widget_handler.update_available_widgets()
        cls = widget_handler.widget_classes.get(widget_type)
        if cls is None:
            raise ValueError(f"Unknown registered widget type: {widget_type}")

        if kwargs is None:
            kwargs = {"object_name": shortcut}
        else:
            kwargs = dict(kwargs)
            kwargs.setdefault("object_name", shortcut)

        # Instantiate and add
        widget = cls(**kwargs)
        if not isinstance(widget, QWidget):
            raise TypeError(
                f"Instantiated object for type '{widget_type}' is not a QWidget: {type(widget)}"
            )
        return self.add_widget(widget, shortcut, title=title)

    def _push_to_console(self, mapping: Dict[str, Any]):
        """Push Python objects into the inprocess kernel user namespace."""
        if self.console.inprocess is True:
            self.console.kernel_manager.kernel.shell.push(mapping)
        else:
            raise RuntimeError("Can only push variables when using inprocess kernel")

    def closeEvent(self, event):
        """Override to handle things when main window is closed."""

        # Ensure the embedded kernel and BEC client are shut down before window teardown
        self.console.shutdown_kernel()
        self.console.close()

        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    import bec_widgets

    module_path = os.path.dirname(bec_widgets.__file__)

    app = QApplication(sys.argv)
    apply_theme("dark")
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    icon = material_icon("terminal", color=(255, 255, 255, 255), filled=True)
    app.setWindowIcon(icon)

    win = JupyterConsoleWindow()

    # Examples: add two widgets programmatically to demonstrate usage
    try:
        win.add_widget_by_type("Waveform", shortcut="wf")
    except Exception as exc:
        print(f"Example add failed (Waveform by type): {exc}")

    try:
        win.add_widget_by_type("Image", shortcut="im", kwargs={"popups": True})
    except Exception as exc:
        print(f"Example add failed (Image by type): {exc}")

    win.show()
    win.resize(1500, 800)

    sys.exit(app.exec_())
