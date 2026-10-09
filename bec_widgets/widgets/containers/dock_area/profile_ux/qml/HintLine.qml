import QtQuick
import QtQuick.Layouts
import BecUi

// Icon and text in the colour of a tone: neutral, info, success, warning or error.
RowLayout {
    id: root
    property string tone: "neutral"
    property string text: ""
    readonly property color toneColor: tone === "error" ? theme.danger
        : tone === "warning" ? theme.warning
        : tone === "success" ? theme.success
        : tone === "info" ? theme.primary
        : theme.fgMuted
    readonly property color textColor: tone === "neutral" ? theme.fgMuted
        : tone === "warning" && !theme.dark ? Qt.darker(theme.warning, 1.6)
        : toneColor
    spacing: 6
    Icon {
        Layout.alignment: Qt.AlignTop
        Layout.topMargin: 1
        visible: root.tone !== "neutral"
        size: 16
        color: root.toneColor
        name: root.tone === "error" ? "error" : root.tone === "warning" ? "warning"
            : root.tone === "success" ? "check_circle" : "info"
    }
    Text {
        Layout.fillWidth: true
        text: root.text
        color: root.textColor
        font.pixelSize: 12
        wrapMode: Text.WordWrap
    }
}
