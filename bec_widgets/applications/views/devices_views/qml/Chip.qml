import QtQuick
import BecUi
import "Tones.js" as Tones

// State chip: icon and word on a soft tint, the same chip the QWidget view paints.
Rectangle {
    id: root
    property string text: ""
    property string tone: "neutral"
    property string iconName: ""
    readonly property color toneColor: Tones.color(theme, tone)

    implicitHeight: 20
    implicitWidth: label.implicitWidth + (iconName !== "" ? 30 : 16)
    radius: height / 2
    color: Tones.soft(theme, toneColor, tone === "neutral" ? 0.1 : 0.18)

    Icon {
        id: icon
        visible: root.iconName !== ""
        name: root.iconName
        size: 14
        color: root.toneColor
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        id: label
        text: root.text
        color: root.toneColor
        font.pixelSize: 11
        font.weight: Font.DemiBold
        anchors.left: root.iconName !== "" ? icon.right : parent.left
        anchors.leftMargin: root.iconName !== "" ? 3 : 8
        anchors.verticalCenter: parent.verticalCenter
    }
}
