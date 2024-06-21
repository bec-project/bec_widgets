# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from device_combobox import DeviceComboBox

from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

from bec_widgets.widgets.device_inputs.device_combobox.device_combobox_plugin import (
    DeviceComboBoxPlugin,
)

# Set PYSIDE_DESIGNER_PLUGINS to point to this directory and load the plugin


if __name__ == "__main__":  # pragma: no cover
    QPyDesignerCustomWidgetCollection.addCustomWidget(DeviceComboBoxPlugin())
