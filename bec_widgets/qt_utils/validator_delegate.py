from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import QStyledItemDelegate, QLineEdit


class DoubleValidationDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        validator = QDoubleValidator()
        editor.setValidator(validator)
        return editor
