import QtQuick
import QtQuick.Controls.Basic

// Flat, square icon button with hover and pressed feedback and a tooltip.
// Every icon-only button needs a tip: it is also the accessible name.
// checkable + checked tints the icon with the primary colour; danger tints it red.
AbstractButton {
    id: root
    property string iconName: ""
    property color iconColor: theme.fgMuted
    property string tip: ""
    property int iconSize: compact ? 16 : 18
    property bool danger: false
    property bool compact: false
    property bool filled: false

    implicitWidth: compact ? theme.controlHeightCompact : 30
    implicitHeight: compact ? theme.controlHeightCompact : 30
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    opacity: enabled ? 1.0 : 0.4
    Accessible.name: tip
    Accessible.role: Accessible.Button

    background: Rectangle {
        radius: theme.radiusSmall
        color: root.down ? theme.pressed
            : root.danger && root.hovered ? theme.dangerTint
            : (root.hovered || root.checked ? theme.hover : "transparent")
        border.width: root.visualFocus ? 2 : 0
        border.color: theme.primary
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: root.iconName
            size: root.iconSize
            filled: root.filled || root.checked
            color: root.checked ? theme.primary : root.danger ? theme.dangerText : root.iconColor
        }
    }
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500
    ToolTip.text: tip
}
