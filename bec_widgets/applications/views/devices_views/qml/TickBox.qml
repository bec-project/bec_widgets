import QtQuick
import QtQuick.Controls.Basic
import BecUi

// Small checkbox matching the field style.
CheckBox {
    id: root
    padding: 0
    spacing: 6
    font.pixelSize: 12
    indicator: Rectangle {
        implicitWidth: 15
        implicitHeight: 15
        x: root.leftPadding
        y: (root.height - height) / 2
        radius: 4
        color: root.checked ? theme.primary : theme.field
        border.color: root.checked ? theme.primary : root.visualFocus ? theme.primary : theme.border
        Icon { anchors.centerIn: parent; name: "check"; size: 12; color: theme.onPrimary; visible: root.checked }
    }
    contentItem: Text {
        leftPadding: root.text !== "" ? root.indicator.width + root.spacing : 0
        text: root.text
        color: theme.fg
        font: root.font
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }
}
