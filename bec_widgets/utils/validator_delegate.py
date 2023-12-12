# from qtpy.QtGui import QDoubleValidator
# from qtpy.QtWidgets import QStyledItemDelegate, QLineEdit

from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QStyledItemDelegate, QLineEdit


class DoubleValidationDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        validator = QDoubleValidator()
        editor.setValidator(validator)
        return editor
