import QtQuick

// Small rounded status chip: a coloured dot (or an icon) and a short label.
// tone: a tone name ("neutral", "info", "success", "warning", "danger", "subtle" and the
// aliases busy/ok/warn/err/stale) or any colour, e.g. theme.success.
// pulse: the dot breathes, for live states such as "Moving" or "Running".
// outlined: transparent fill with a hairline border, for quiet states that need no attention.
Rectangle {
    id: root
    property string text: ""
    property var tone: "neutral"
    property string iconName: ""
    property bool pulse: false
    property bool outlined: false

    readonly property bool namedTone: typeof tone === "string"
    // "theme.name," makes the binding re-evaluate when the theme changes
    readonly property color toneColor: namedTone ? (theme.name, theme.toneText(tone)) : tone

    implicitHeight: 22
    implicitWidth: label.implicitWidth + (iconName !== "" ? 30 : 26)
    radius: height / 2
    color: outlined ? "transparent" : Qt.rgba(toneColor.r, toneColor.g, toneColor.b, theme.dark ? 0.18 : 0.13)
    border.width: outlined ? 1 : 0
    border.color: theme.separator
    Accessible.name: text
    Behavior on color { ColorAnimation { duration: 150 } }

    Rectangle {
        id: dot
        visible: root.iconName === ""
        width: 7; height: 7; radius: 3.5
        color: root.toneColor
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
    Icon {
        id: glyph
        visible: root.iconName !== ""
        name: root.iconName
        size: 14
        color: root.toneColor
        anchors.left: parent.left
        anchors.leftMargin: 7
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        id: label
        anchors.left: root.iconName !== "" ? glyph.right : dot.right
        anchors.leftMargin: root.iconName !== "" ? 4 : 6
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.toneColor
        font.pixelSize: theme.fontSmall
        font.weight: Font.DemiBold
    }
}
