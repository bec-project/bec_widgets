"""Main-app view that hosts the five sequencer GUI concepts side by side.

A switcher at the top picks the concept; each concept keeps its own sequence while you
switch, so they can be compared on the same example. Run one concept directly with::

    python -m bec_widgets.applications.views.sequencer_view.sequencer_view --concept table
"""

from __future__ import annotations

import argparse
import os
import sys

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.sequencer_view.concepts import CONCEPTS
from bec_widgets.applications.views.view import ViewBase
from bec_widgets.utils.colors import rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.sequencer.style import heading, hint, theme


class SequencerView(ViewBase):
    """Sequencer view with a concept switcher.

    Editors are created when first shown, so the main app starts as fast as before.

    Args:
        parent (QWidget | None): Parent widget.
        concept (str | None): Concept to show right away. Without it, the view waits until it
            is opened and then shows ``BEC_SEQUENCER_CONCEPT`` or the first concept.
        keep_drafts (bool): Keep each concept's work in a draft file, so it is still there
            after the application was closed.
    """

    RPC = False

    def __init__(
        self, parent=None, *, concept: str | None = None, keep_drafts: bool = False, **kwargs
    ):
        super().__init__(parent=parent, view_id="sequencer", title="Sequencer", **kwargs)
        self.keep_drafts = keep_drafts
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top = QWidget(content)
        self.top.setObjectName("SequencerTop")
        self.top.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        top_row = QHBoxLayout(self.top)
        top_row.setContentsMargins(16, 10, 16, 10)
        top_row.setSpacing(14)
        top_row.addWidget(heading("Sequencer", self.top, 16))
        self.switcher = QButtonGroup(self.top)
        self.switcher.setExclusive(True)
        segments = QHBoxLayout()
        segments.setSpacing(0)
        for number, (cid, cls) in enumerate(CONCEPTS.items(), 1):
            button = QPushButton(f"{number}  {cls.CONCEPT_TITLE}", self.top)
            button.setCheckable(True)
            button.setProperty("concept", cid)
            button.setToolTip(cls.CONCEPT_TAGLINE)
            self.switcher.addButton(button)
            segments.addWidget(button)
        top_row.addLayout(segments)
        self.tagline = hint("", self.top)
        top_row.addWidget(self.tagline, 1)
        self.prototype_note = QLabel(f"{len(CONCEPTS)} layouts to compare", self.top)
        top_row.addWidget(self.prototype_note)
        layout.addWidget(self.top)
        self._style_top()

        self.stack = QStackedWidget(content)
        layout.addWidget(self.stack, 1)
        self.editors: dict[str, QWidget] = {}
        self.switcher.buttonClicked.connect(self._on_switch)
        self.set_content(content)

        start = concept or os.environ.get("BEC_SEQUENCER_CONCEPT") or next(iter(CONCEPTS))
        self._start_concept = start if start in CONCEPTS else next(iter(CONCEPTS))
        if concept is not None:
            self.show_concept(self._start_concept)

    def _style_top(self) -> None:
        self.top.setStyleSheet(
            f"#SequencerTop {{ background: {theme('CARD_BG', '#ffffff').name()};"
            f" border-bottom: 1px solid {theme('BORDER', '#d0d0d0').name()}; }}"
        )
        primary = theme("PRIMARY", "#2f6fdf")
        border = theme("BORDER", "#d0d0d0").name()
        buttons = self.switcher.buttons()
        for number, button in enumerate(buttons, 1):
            first, last = number == 1, number == len(buttons)
            radius = (
                f"border-top-left-radius: {8 if first else 0}px;"
                f" border-bottom-left-radius: {8 if first else 0}px;"
                f" border-top-right-radius: {8 if last else 0}px;"
                f" border-bottom-right-radius: {8 if last else 0}px;"
            )
            button.setStyleSheet(
                f"QPushButton {{ padding: 6px 14px; border: 1px solid {border}; {radius}"
                " margin-left: -1px; }"
                f"QPushButton:checked {{ background: {rgba(primary, 45)};"
                f" border: 1px solid {primary.name()}; color: {primary.name()}; font-weight: 600; }}"
            )
        self.tagline.setStyleSheet(f"color: {rgba(theme('FG', '#333333'), 150)};")
        self.prototype_note.setStyleSheet(f"color: {rgba(theme('FG', '#333333'), 150)};")

    def apply_theme(self, theme_name: str) -> None:
        """Restyle the view and rebuild the editors in the new colors, keeping their work."""
        super().apply_theme(theme_name)
        self._style_top()
        current = next(
            (cid for cid, editor in self.editors.items() if editor is self.stack.currentWidget()),
            None,
        )
        for cid, old in list(self.editors.items()):
            state = old.save_state()
            del self.editors[cid]
            editor = self._create(cid)
            editor.restore_state(state)
            self.stack.removeWidget(old)
            old.close()
            old.deleteLater()
        if current is not None:
            self.show_concept(current)

    def _create(self, concept: str) -> QWidget:
        editor = CONCEPTS[concept](self.stack, draft_name=concept if self.keep_drafts else None)
        editor.open_in_recipe.connect(self._open_in_recipe)
        self.editors[concept] = editor
        self.stack.addWidget(editor)
        return editor

    @SafeSlot()
    def on_enter(self) -> None:
        """Create the first concept when the view is opened for the first time."""
        if not self.editors:
            self.show_concept(self._start_concept)

    def show_concept(self, concept: str) -> QWidget:
        """Show a concept, creating its editor on first use.

        Args:
            concept (str): Concept id, e.g. ``recipe`` or ``table``.

        Returns:
            QWidget: The concept's editor.
        """
        editor = self.editors.get(concept)
        if editor is None:
            editor = self._create(concept)
        self.stack.setCurrentWidget(editor)
        self.tagline.setText(CONCEPTS[concept].CONCEPT_TAGLINE)
        for button in self.switcher.buttons():
            button.setChecked(button.property("concept") == concept)
        return editor

    @SafeSlot()
    def _on_switch(self, button) -> None:
        self.show_concept(button.property("concept"))

    @SafeSlot(dict)
    def _open_in_recipe(self, doc: dict) -> None:
        recipe = self.show_concept("recipe")
        recipe.document.set_document(doc)


def main():  # pragma: no cover - manual entry point
    """Open the sequencer view in its own window."""
    # pylint: disable=import-outside-toplevel
    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

    parser = argparse.ArgumentParser(description="Try the sequencer GUI concepts")
    parser.add_argument("--concept", choices=list(CONCEPTS), default=None)
    parser.add_argument("--theme", choices=["light", "dark"], default="dark")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    apply_theme(args.theme)
    window = BECMainWindow()
    window.setWindowTitle("BEC Sequencer (prototype)")
    view = SequencerView(window, concept=args.concept or next(iter(CONCEPTS)), keep_drafts=True)
    window.setCentralWidget(view)
    window.resize(1400, 860)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
