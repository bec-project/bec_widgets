from __future__ import annotations

from typing import Callable, Literal

from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import SafeSlot


class SaveProfileDialog(QDialog):
    """Dialog for saving workspace profiles with quick select option."""

    def __init__(
        self,
        parent: QWidget | None = None,
        current_name: str = "",
        current_profile_name: str = "",
        *,
        name_exists: Callable[[str], bool] | None = None,
        profile_origin: (
            Callable[[str], Literal["module", "plugin", "settings", "unknown"]] | None
        ) = None,
        origin_label: Callable[[str], str | None] | None = None,
        quick_select_checked: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle("Save Workspace Profile")
        self.setModal(True)
        self.resize(400, 160)

        self._name_exists = name_exists or (lambda _: False)
        self._profile_origin = profile_origin or (lambda _: "unknown")
        self._origin_label = origin_label or (lambda _: None)
        self._current_profile_name = current_profile_name.strip()
        self._previous_name_before_overwrite = current_name
        self._block_name_signals = False
        self._block_checkbox_signals = False
        self.overwrite_existing = False

        layout = QVBoxLayout(self)

        # Name input
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Profile Name:"))
        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Enter profile name...")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Overwrite checkbox
        self.overwrite_checkbox = QCheckBox("Overwrite current profile")
        self.overwrite_checkbox.setEnabled(bool(self._current_profile_name))
        self.overwrite_checkbox.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self.overwrite_checkbox)

        # Quick-select checkbox
        self.quick_select_checkbox = QCheckBox("Include in quick selection.")
        self.quick_select_checkbox.setChecked(quick_select_checked)
        layout.addWidget(self.quick_select_checkbox)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Enable/disable save button based on name input
        self.name_edit.textChanged.connect(self._on_name_changed)
        self._update_save_button()

    @SafeSlot(bool)
    def _on_overwrite_toggled(self, checked: bool):
        if self._block_checkbox_signals:
            return
        if not self._current_profile_name:
            return

        self._block_name_signals = True
        if checked:
            self._previous_name_before_overwrite = self.name_edit.text()
            self.name_edit.setText(self._current_profile_name)
            self.name_edit.selectAll()
        else:
            if self.name_edit.text().strip() == self._current_profile_name:
                self.name_edit.setText(self._previous_name_before_overwrite or "")
        self._block_name_signals = False
        self._update_save_button()

    @SafeSlot(str)
    def _on_name_changed(self, _: str):
        if self._block_name_signals:
            return
        text = self.name_edit.text().strip()
        if self.overwrite_checkbox.isChecked() and text != self._current_profile_name:
            self._block_checkbox_signals = True
            self.overwrite_checkbox.setChecked(False)
            self._block_checkbox_signals = False
        self._update_save_button()

    def _update_save_button(self):
        """Enable save button only when name is not empty."""
        self.save_btn.setEnabled(bool(self.name_edit.text().strip()))

    def get_profile_name(self) -> str:
        """Return the entered profile name."""
        return self.name_edit.text().strip()

    def is_quick_select(self) -> bool:
        """Return whether the profile should appear in quick select."""
        return self.quick_select_checkbox.isChecked()

    def _generate_unique_name(self, base: str) -> str:
        candidate_base = base.strip() or "profile"
        suffix = "_custom"
        candidate = f"{candidate_base}{suffix}"
        counter = 1
        while self._name_exists(candidate) or self._profile_origin(candidate) != "unknown":
            candidate = f"{candidate_base}{suffix}_{counter}"
            counter += 1
        return candidate

    def accept(self):
        name = self.get_profile_name()
        if not name:
            return

        self.overwrite_existing = False
        origin = self._profile_origin(name)
        if origin in {"module", "plugin"}:
            source_label = self._origin_label(name)
            if origin == "module":
                provider = source_label or "BEC Widgets"
            else:
                provider = (
                    f"the {source_label} plugin repository"
                    if source_label
                    else "the plugin repository"
                )
            QMessageBox.information(
                self,
                "Read-only profile",
                (
                    f"'{name}' is a default profile provided by {provider} and cannot be overwritten.\n"
                    "Please choose a different name."
                ),
            )
            suggestion = self._generate_unique_name(name)
            self._block_name_signals = True
            self.name_edit.setText(suggestion)
            self.name_edit.selectAll()
            self._block_name_signals = False
            self._block_checkbox_signals = True
            self.overwrite_checkbox.setChecked(False)
            self._block_checkbox_signals = False
            return
        if origin == "settings":
            reply = QMessageBox.question(
                self,
                "Overwrite profile",
                (
                    f"A profile named '{name}' already exists.\n\n"
                    "Overwriting will update both the saved profile and its restore default.\n"
                    "Do you want to continue?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                suggestion = self._generate_unique_name(name)
                self._block_name_signals = True
                self.name_edit.setText(suggestion)
                self.name_edit.selectAll()
                self._block_name_signals = False
                self._block_checkbox_signals = True
                self.overwrite_checkbox.setChecked(False)
                self._block_checkbox_signals = False
                return
            self.overwrite_existing = True

        super().accept()


class PreviewPanel(QGroupBox):
    """Resizable preview pane that scales its pixmap with aspect ratio preserved."""

    def __init__(self, title: str, pixmap: QPixmap | None, parent: QWidget | None = None):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._original: QPixmap | None = pixmap if (pixmap and not pixmap.isNull()) else None

        layout = QVBoxLayout(self)
        # layout.setContentsMargins(0,0,0,0)  # leave room for group title and frame

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(360, 240)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label, 1)

        if self._original:
            self._update_scaled_pixmap()
        else:
            self.image_label.setText("No preview available")
            self.image_label.setStyleSheet(
                self.image_label.styleSheet() + "color: rgba(255,255,255,0.6); font-style: italic;"
            )

    def setPixmap(self, pixmap: QPixmap | None):
        self._original = pixmap if (pixmap and not pixmap.isNull()) else None
        if self._original:
            self.image_label.setText("")
            self._update_scaled_pixmap()
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No preview available")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original:
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if not self._original:
            return
        size = self.image_label.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self._original.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)


class RestoreProfileDialog(QDialog):
    """
    Confirmation dialog that previews the current profile screenshot against the default baseline.
    """

    def __init__(
        self, parent: QWidget | None, current_pixmap: QPixmap | None, default_pixmap: QPixmap | None
    ):
        super().__init__(parent)
        self.setWindowTitle("Restore Profile to Default")
        self.setModal(True)
        self.resize(880, 480)

        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Restoring will discard your custom layout and replace it with the default profile."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        preview_row = QHBoxLayout()
        layout.addLayout(preview_row)

        current_preview = PreviewPanel("Current", current_pixmap, self)
        default_preview = PreviewPanel("Default", default_pixmap, self)

        # Equal expansion left/right
        preview_row.addWidget(current_preview, 1)

        arrow_label = QLabel("\u2192")
        arrow_label.setAlignment(Qt.AlignCenter)
        arrow_label.setStyleSheet("font-size: 32px; padding: 0 16px;")
        arrow_label.setMinimumWidth(40)
        arrow_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        preview_row.addWidget(arrow_label)

        preview_row.addWidget(default_preview, 1)

        # Enforce equal stretch for both previews
        preview_row.setStretch(0, 1)
        preview_row.setStretch(1, 0)
        preview_row.setStretch(2, 1)

        warn_label = QLabel(
            "This action cannot be undone. Do you want to restore the default layout now?"
        )
        warn_label.setWordWrap(True)
        layout.addWidget(warn_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        restore_btn = QPushButton("Restore")
        restore_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        restore_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(restore_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Make the previews take most of the vertical space on resize
        layout.setStretch(0, 0)  # info label
        layout.setStretch(1, 1)  # preview row
        layout.setStretch(2, 0)  # warning label
        layout.setStretch(3, 0)  # buttons

    @staticmethod
    def confirm(
        parent: QWidget | None, current_pixmap: QPixmap | None, default_pixmap: QPixmap | None
    ) -> bool:
        dialog = RestoreProfileDialog(parent, current_pixmap, default_pixmap)
        return dialog.exec() == QDialog.Accepted
