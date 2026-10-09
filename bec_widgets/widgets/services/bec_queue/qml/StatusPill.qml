import QtQuick
import QtQuick.Layouts

// Status shown as glyph + word; colour only for states that need attention.
// tone: neutral | busy | ok | warn | err | stale
Rectangle {
    id: root
    property string label
    property string iconName
    property string tone: "neutral"

    readonly property color textColor: tone === "busy" ? theme.busyText
        : tone === "ok" ? theme.okText
        : tone === "warn" ? theme.warnText
        : tone === "err" ? theme.errText
        : tone === "stale" ? theme.faint : theme.muted
    readonly property color fillColor: tone === "busy" ? theme.busyTint
        : tone === "warn" ? theme.warnTint
        : tone === "err" ? theme.errTint : "transparent"

    implicitHeight: 22
    implicitWidth: row.implicitWidth + 14
    radius: height / 2
    color: fillColor
    border.width: tone === "neutral" || tone === "stale" || tone === "ok" ? 1 : 0
    border.color: theme.separator
    Behavior on color { ColorAnimation { duration: 150 } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 4
        Icon {
            name: root.iconName
            size: 14
            color: root.textColor
        }
        Text {
            text: root.label
            color: root.textColor
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
    }
}
