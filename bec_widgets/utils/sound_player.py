from pathlib import Path

from qtpy.QtCore import QUrl
from qtpy.QtMultimedia import QAudioOutput, QMediaPlayer
from qtpy.QtWidgets import QApplication, QComboBox, QPushButton, QVBoxLayout, QWidget


class SoundPlayerWidget(QWidget):
    """Simple widget to preview bundled sound assets."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("Sound Player")

        self._sounds_dir = Path(__file__).resolve().parent.parent / "assets" / "sounds"
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self.sound_combo_box = QComboBox(self)
        self.play_button = QPushButton("Play", self)

        self._populate_sounds()
        self.play_button.clicked.connect(self.play_selected_sound)

        layout = QVBoxLayout(self)
        layout.addWidget(self.sound_combo_box)
        layout.addWidget(self.play_button)

        self.resize(420, 100)

    def _populate_sounds(self) -> None:
        """Load bundled sound assets into the combo box."""
        sound_files = sorted(self._sounds_dir.glob("*.mp3"))
        for sound_file in sound_files:
            self.sound_combo_box.addItem(sound_file.stem, str(sound_file))

        self.play_button.setEnabled(bool(sound_files))
        if not sound_files:
            self.sound_combo_box.addItem("No sounds found")

    def play_selected_sound(self) -> None:
        """Play the currently selected sound asset."""
        sound_path = self.sound_combo_box.currentData()
        if not sound_path:
            return

        self._player.setSource(QUrl.fromLocalFile(sound_path))
        self._player.stop()
        self._player.play()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme

    app = QApplication(sys.argv)
    apply_theme("light")

    widget = SoundPlayerWidget()
    widget.show()
    sys.exit(app.exec_())
