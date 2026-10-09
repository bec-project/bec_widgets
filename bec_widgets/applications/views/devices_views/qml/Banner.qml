import QtQuick
import QtQuick.Layouts
import BecUi
import "Tones.js" as Tones

// Inline banner with icon, bold title and body text.
Rectangle {
    id: root
    property string tone: "warn"
    property string iconName: "lock"
    property string title: ""
    property string text: ""
    readonly property color toneColor: Tones.color(theme, tone)

    implicitHeight: col.implicitHeight + 16
    radius: 8
    color: Tones.soft(theme, toneColor, tone === "err" ? 0.14 : 0.16)
    border.color: Qt.rgba(toneColor.r, toneColor.g, toneColor.b, 0.5)

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        anchors.leftMargin: 10
        spacing: 10
        Icon { name: root.iconName; size: 18; color: root.toneColor; Layout.alignment: Qt.AlignTop }
        ColumnLayout {
            id: col
            spacing: 2
            Layout.fillWidth: true
            Text { text: root.title; color: theme.fg; font.pixelSize: 13; font.weight: Font.Bold }
            Text {
                visible: root.text !== ""
                text: root.text
                color: theme.fgMuted
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
}
