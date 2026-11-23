import QtQuick
import QtQuick.Controls.Basic

// Flat, square icon button with hover and pressed feedback and a tooltip.
AbstractButton {
    id: root
    property string iconName: ""
    property color iconColor: theme.fgMuted
    property string tip: ""
    property int iconSize: 18

    implicitWidth: 30
    implicitHeight: 30
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    opacity: enabled ? 1.0 : 0.4
    Accessible.name: tip

    background: Rectangle {
        radius: 6
        color: root.down ? theme.pressed : (root.hovered || root.checked ? theme.hover : "transparent")
        border.width: root.visualFocus ? 1 : 0
        border.color: theme.primary
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: root.iconName
            size: root.iconSize
            color: root.checked ? theme.primary : root.iconColor
        }
    }
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500
    ToolTip.text: tip
}
