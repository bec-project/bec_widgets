import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Toolbar button: icon and optional text, no frame until hovered.
AbstractButton {
    id: root
    property string iconName: ""
    property string tip: ""
    property bool showMenuArrow: false

    implicitHeight: 28
    implicitWidth: row.implicitWidth + 16
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    opacity: enabled ? 1.0 : 0.45
    Accessible.name: text !== "" ? text : tip

    background: Rectangle {
        radius: 6
        color: root.down ? theme.pressed : root.hovered ? theme.hover : "transparent"
        border.width: root.visualFocus ? 1 : 0
        border.color: theme.primary
    }
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 5
            Icon { name: root.iconName; size: 16; color: theme.fgMuted; visible: root.iconName !== "" }
            Text {
                visible: root.text !== ""
                text: root.text
                color: theme.fg
                font.pixelSize: 12
            }
        }
    }
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500
    ToolTip.text: tip
}
