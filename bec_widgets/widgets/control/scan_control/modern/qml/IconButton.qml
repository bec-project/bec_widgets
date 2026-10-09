import QtQuick
import QtQuick.Controls.Basic

// Flat, round-cornered icon button with a tooltip.
AbstractButton {
    id: control

    property string iconName
    property color tint: theme.fg
    property string tip

    implicitWidth: 30
    implicitHeight: 30
    padding: 6
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    Accessible.name: tip
    ToolTip.visible: hovered && tip.length > 0
    ToolTip.text: tip
    ToolTip.delay: 500

    background: Rectangle {
        radius: 6
        color: control.down ? theme.border : control.hovered ? theme.hover : "transparent"
        border.width: control.visualFocus ? 1 : 0
        border.color: theme.primary
    }
    contentItem: Image {
        source: "image://material/" + control.iconName + "?color=" + encodeURIComponent(control.tint.toString())
        sourceSize: Qt.size(18, 18)
        fillMode: Image.PreserveAspectFit
        opacity: control.enabled ? 1 : 0.35
    }
}
