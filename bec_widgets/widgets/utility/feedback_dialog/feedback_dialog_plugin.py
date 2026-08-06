# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.utility.feedback_dialog.feedback_dialog import FeedbackDialog

DOM_XML = """
<ui language='c++'>
    <widget class='FeedbackDialog' name='feedback_dialog'>
    </widget>
</ui>
"""


class FeedbackDialogPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = FeedbackDialog(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(FeedbackDialog.ICON_NAME)

    def includeFile(self):
        return "feedback_dialog"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "FeedbackDialog"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
