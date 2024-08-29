# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.lmfit_dialog.lmfit_dialog import LMFitDialog

DOM_XML = """
<ui language='c++'>
    <widget class='LMFitDialog' name='lm_fit_dialog'>
    </widget>
</ui>
"""


class LMFitDialogPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        t = LMFitDialog(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(LMFitDialog.ICON_NAME)

    def includeFile(self):
        return "lm_fit_dialog"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "LMFitDialog"

    def toolTip(self):
        return "LMFitDialog"

    def whatsThis(self):
        return self.toolTip()
