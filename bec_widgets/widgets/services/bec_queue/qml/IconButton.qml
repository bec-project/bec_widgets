import QtQuick
import QtQuick.Controls.Basic

// Square icon-only button. Always carries a tooltip: no unlabelled icons.
AbstractButton {
    id: root
    property string iconName
    property string tip
    property bool danger: false
    property int iconSize: 18

    implicitWidth: 28
    implicitHeight: 28
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: tip
    Accessible.role: Accessible.Button

    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 450
    ToolTip.text: tip

    background: Rectangle {
        radius: 6
        color: root.down ? theme.pressed : root.hovered ? theme.hover : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: theme.primary
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: root.iconName
            size: root.iconSize
            color: !root.enabled ? theme.faint : root.danger ? theme.errText : theme.muted
        }
    }
}
