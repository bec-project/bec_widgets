import QtQuick

// Small rounded status chip with a coloured dot. Set pulse for live states such as "Moving".
Rectangle {
    id: root
    property string text: ""
    property color tone: theme.fgMuted
    property bool pulse: false

    implicitHeight: 22
    implicitWidth: label.implicitWidth + 26
    radius: height / 2
    color: Qt.rgba(tone.r, tone.g, tone.b, 0.16)

    Rectangle {
        id: dot
        width: 7; height: 7; radius: 3.5
        color: root.tone
        anchors.left: parent.left
        anchors.leftMargin: 9
        anchors.verticalCenter: parent.verticalCenter
        SequentialAnimation on opacity {
            running: root.pulse
            loops: Animation.Infinite
            alwaysRunToEnd: true
            NumberAnimation { to: 0.25; duration: 550; easing.type: Easing.InOutQuad }
            NumberAnimation { to: 1.0; duration: 550; easing.type: Easing.InOutQuad }
        }
    }
    Text {
        id: label
        anchors.left: dot.right
        anchors.leftMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.tone
        font.pixelSize: 12
        font.weight: Font.DemiBold
    }
}
