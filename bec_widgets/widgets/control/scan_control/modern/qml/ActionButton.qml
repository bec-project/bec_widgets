import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Text button in one of four looks: "primary", "danger", "outlineDanger" or "ghost".
Button {
    id: control

    property string kind: "primary"
    property string iconName

    readonly property bool filled: kind === "primary" || kind === "danger"
    readonly property color base: kind === "primary" ? theme.primary
                                 : (kind === "danger" || kind === "outlineDanger") ? theme.danger
                                 : theme.fg
    readonly property color ink: filled ? theme.onPrimary : base

    implicitHeight: 34
    leftPadding: 12
    rightPadding: 14
    hoverEnabled: true
    Accessible.name: text

    background: Rectangle {
        radius: 7
        opacity: control.enabled ? 1 : 0.4
        color: control.filled
               ? (control.down ? Qt.darker(control.base, 1.25) : control.hovered ? Qt.lighter(control.base, 1.1) : control.base)
               : (control.down ? theme.border : control.hovered ? theme.hover : "transparent")
        border.width: control.kind === "outlineDanger" || control.visualFocus ? 1 : 0
        border.color: control.visualFocus ? theme.primary : control.base
    }
    contentItem: RowLayout {
        spacing: 6
        opacity: control.enabled ? 1 : 0.6
        Image {
            visible: control.iconName.length > 0
            source: visible ? "image://material/" + control.iconName + "?filled=1&color=" + encodeURIComponent(control.ink.toString()) : ""
            sourceSize: Qt.size(18, 18)
            Layout.alignment: Qt.AlignVCenter
        }
        Text {
            text: control.text
            color: control.ink
            font.pixelSize: 13
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.maximumWidth: implicitWidth
            verticalAlignment: Text.AlignVCenter
        }
    }
}
