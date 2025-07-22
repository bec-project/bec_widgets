# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from qtpy.QtCore import QSize
from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

DOM_XML = """
<ui language='c++'>
    <widget class='BECMainWindow' name='bec_main_window'>
    </widget>
</ui>
"""


class BECMainWindowPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        # We want to initialize BECMainWindow upon starting designer
        t = BECMainWindow(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return "BEC Containers"

    def icon(self):
        return designer_material_icon(BECMainWindow.ICON_NAME)

    def includeFile(self):
        return "bec_main_window"

    def initialize(self, form_editor):
        import os

        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QApplication

        import bec_widgets

        MODULE_PATH = os.path.dirname(bec_widgets.__file__)
        QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, True)
        app = QApplication.instance()
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "BEC-General-App.png"),
            size=QSize(48, 48),
        )
        app.setWindowIcon(icon)
        self._form_editor = form_editor

    def isContainer(self):
        return True

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "BECMainWindow"

    def toolTip(self):
        return "BECMainWindow"

    def whatsThis(self):
        return self.toolTip()
