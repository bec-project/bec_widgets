import QtQuick

// Count bubble, e.g. unread notifications or items in a filter. Hidden at zero unless
// showZero. tone: "primary", "danger", "warning", "neutral" ... ; solid paints a filled bubble.
Rectangle {
    id: root
    property int count: 0
    property int maximum: 99
    property string tone: "danger"
    property bool solid: tone !== "neutral" && tone !== "primary"
    property bool showZero: false

    readonly property color toneColor: (theme.name, tone === "primary" ? theme.primary : theme.tone(tone))
    readonly property string label: count > maximum ? maximum + "+" : String(count)

    visible: count > 0 || showZero
    implicitHeight: 16
    implicitWidth: Math.max(implicitHeight, labelText.implicitWidth + 9)
    radius: implicitHeight / 2
    color: solid ? toneColor : Qt.rgba(toneColor.r, toneColor.g, toneColor.b, theme.dark ? 0.22 : 0.14)
    Accessible.name: label

    Text {
        id: labelText
        anchors.centerIn: parent
        text: root.label
        color: root.solid ? (0.299 * root.toneColor.r + 0.587 * root.toneColor.g + 0.114 * root.toneColor.b > 0.6 ? "#1a1a1a" : "white")
                          : (theme.name, theme.toneText(root.tone))
        font.pixelSize: 10
        font.weight: Font.Bold
    }
}
