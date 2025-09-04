from __future__ import annotations

from qtpy.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
from qtpy.QtWidgets import QGraphicsOpacityEffect, QWidget

ANIMATION_DURATION = 500  # ms


class RevealAnimator:
    """Animate reveal/hide for a single widget using opacity + max W/H.

    This keeps the widget always visible to avoid jitter from setVisible().
    Collapsed state: opacity=0, maxW=0, maxH=0.
    Expanded state: opacity=1, maxW=sizeHint.width(), maxH=sizeHint.height().
    """

    def __init__(
        self,
        widget: QWidget,
        duration: int = ANIMATION_DURATION,
        easing: QEasingCurve.Type = QEasingCurve.InOutCubic,
        initially_revealed: bool = False,
        *,
        animate_opacity: bool = True,
        animate_width: bool = True,
        animate_height: bool = True,
    ):
        self.widget = widget
        self.animate_opacity = animate_opacity
        self.animate_width = animate_width
        self.animate_height = animate_height
        # Opacity effect
        self.fx = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(self.fx)
        # Animations
        self.opacity_anim = (
            QPropertyAnimation(self.fx, b"opacity") if self.animate_opacity else None
        )
        self.width_anim = (
            QPropertyAnimation(widget, b"maximumWidth") if self.animate_width else None
        )
        self.height_anim = (
            QPropertyAnimation(widget, b"maximumHeight") if self.animate_height else None
        )
        for anim in (self.opacity_anim, self.width_anim, self.height_anim):
            if anim is not None:
                anim.setDuration(duration)
                anim.setEasingCurve(easing)
        # Initialize to requested state
        self.set_immediate(initially_revealed)

    def _natural_sizes(self) -> tuple[int, int]:
        sh = self.widget.sizeHint()
        w = max(sh.width(), 1)
        h = max(sh.height(), 1)
        return w, h

    def set_immediate(self, revealed: bool):
        """
        Immediately set the widget to the target revealed/collapsed state.

        Args:
            revealed(bool): True to reveal, False to collapse.
        """
        w, h = self._natural_sizes()
        if self.animate_opacity:
            self.fx.setOpacity(1.0 if revealed else 0.0)
        if self.animate_width:
            self.widget.setMaximumWidth(w if revealed else 0)
        if self.animate_height:
            self.widget.setMaximumHeight(h if revealed else 0)

    def setup(self, reveal: bool):
        """
        Prepare animations to transition to the target revealed/collapsed state.

        Args:
            reveal(bool): True to reveal, False to collapse.
        """
        # Prepare animations from current state to target
        target_w, target_h = self._natural_sizes()
        if self.opacity_anim is not None:
            self.opacity_anim.setStartValue(self.fx.opacity())
            self.opacity_anim.setEndValue(1.0 if reveal else 0.0)
        if self.width_anim is not None:
            self.width_anim.setStartValue(self.widget.maximumWidth())
            self.width_anim.setEndValue(target_w if reveal else 0)
        if self.height_anim is not None:
            self.height_anim.setStartValue(self.widget.maximumHeight())
            self.height_anim.setEndValue(target_h if reveal else 0)

    def add_to_group(self, group: QParallelAnimationGroup):
        """
        Add the prepared animations to the given animation group.

        Args:
            group(QParallelAnimationGroup): The animation group to add to.
        """
        if self.opacity_anim is not None:
            group.addAnimation(self.opacity_anim)
        if self.width_anim is not None:
            group.addAnimation(self.width_anim)
        if self.height_anim is not None:
            group.addAnimation(self.height_anim)

    def animations(self):
        """
        Get a list of all animations (non-None) for adding to a group.
        """
        return [
            anim
            for anim in (self.opacity_anim, self.height_anim, self.width_anim)
            if anim is not None
        ]
