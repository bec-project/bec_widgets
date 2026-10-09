import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Labelled button. kind: "default", "danger" (red outline) or "dangerSolid".
Button {
    id: root
    property string iconName
    property string kind: "default"
    property string tip

    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    implicitHeight: 28
    leftPadding: iconName ? 8 : 12
    rightPadding: 12
    font.pixelSize: 12
    font.weight: Font.Medium

    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 450
    ToolTip.text: tip

    readonly property color fgColor: !enabled ? theme.faint
        : kind === "dangerSolid" ? "white"
        : kind === "danger" ? theme.dangerText : theme.fg

    background: Rectangle {
        radius: 6
        color: root.kind === "dangerSolid"
               ? (root.down ? Qt.darker(theme.danger, 1.2) : root.hovered ? Qt.lighter(theme.danger, 1.1) : theme.danger)
               : root.down ? theme.pressed : root.hovered ? theme.hover : "transparent"
        border.width: root.visualFocus ? 2 : 1
        border.color: root.visualFocus ? theme.primary
                      : root.kind === "danger" && root.enabled ? Qt.alpha(theme.danger, 0.55)
                      : root.kind === "dangerSolid" ? "transparent" : theme.border
        Behavior on color { ColorAnimation { duration: 90 } }
    }
    contentItem: RowLayout {
        spacing: 5
        Icon {
            visible: root.iconName !== ""
            name: root.iconName
            size: 16
            color: root.fgColor
        }
        Text {
            text: root.text
            font: root.font
            color: root.fgColor
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}
