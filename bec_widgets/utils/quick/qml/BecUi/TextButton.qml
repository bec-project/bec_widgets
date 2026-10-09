import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Labelled button. variant: "primary", "danger", "success", "neutral" or "ghost".
AbstractButton {
    id: root
    property string variant: "neutral"
    property string iconName: ""
    property string tip: ""
    property bool busy: false

    readonly property color baseColor: variant === "primary" ? theme.primary
        : variant === "danger" ? theme.danger
        : variant === "success" ? theme.success
        : "transparent"
    readonly property bool solid: variant === "primary" || variant === "danger" || variant === "success"
    readonly property color labelColor: solid ? "white" : theme.fg

    implicitHeight: 32
    implicitWidth: Math.max(64, row.implicitWidth + 24)
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.45
    Accessible.name: text

    background: Rectangle {
        radius: 6
        color: root.solid ? (root.down ? Qt.darker(root.baseColor, 1.25) : root.hovered ? Qt.lighter(root.baseColor, 1.1) : root.baseColor)
                          : (root.down ? theme.pressed : root.hovered ? theme.hover : "transparent")
        border.width: root.variant === "neutral" || root.visualFocus ? 1 : 0
        border.color: root.visualFocus ? theme.primary : theme.border
        Behavior on color { ColorAnimation { duration: 90 } }
    }
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 6
            BusyIndicator {
                visible: root.busy
                running: root.busy
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
            }
            Icon {
                visible: root.iconName !== "" && !root.busy
                name: root.iconName
                color: root.labelColor
                size: 16
            }
            Text {
                text: root.text
                color: root.labelColor
                font.pixelSize: 13
                font.weight: root.solid ? Font.DemiBold : Font.Medium
                elide: Text.ElideRight
            }
        }
    }
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500
    ToolTip.text: tip
}
