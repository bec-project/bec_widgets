# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QDesignerCustomWidgetInterface
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_designer import designer_material_icon
from bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer import HDF5Viewer

DOM_XML = """
<ui language='c++'>
    <widget class='HDF5Viewer' name='hdf5_viewer'>
    </widget>
</ui>
"""


class HDF5ViewerPlugin(QDesignerCustomWidgetInterface):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self._form_editor = None

    def createWidget(self, parent):
        if parent is None:
            return QWidget()
        t = HDF5Viewer(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ""

    def icon(self):
        return designer_material_icon(HDF5Viewer.ICON_NAME)

    def includeFile(self):
        return "hdf5_viewer"

    def initialize(self, form_editor):
        self._form_editor = form_editor

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._form_editor is not None

    def name(self):
        return "HDF5Viewer"

    def toolTip(self):
        return ""

    def whatsThis(self):
        return self.toolTip()
