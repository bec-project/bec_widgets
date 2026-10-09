import QtQuick
import QtQuick.Layouts

// A row of mutually exclusive options, e.g. a filter (All / Errors / Warnings) or a view
// switch. model: list of strings or of {text, iconName, count} objects.
// activated(index) fires on user clicks only; currentIndex is the state.
Rectangle {
    id: root
    property var model: []
    property int currentIndex: 0
    property bool compact: false
    signal activated(int index)

    implicitHeight: compact ? theme.controlHeightCompact : theme.controlHeight
    implicitWidth: row.implicitWidth + 6
    radius: theme.radiusSmall + 1
    color: theme.sunken
    border.color: theme.border
    Accessible.role: Accessible.PageTabList

    function _text(entry) { return typeof entry === "string" ? entry : (entry.text || "") }
    function _icon(entry) { return typeof entry === "string" ? "" : (entry.iconName || "") }
    function _count(entry) { return typeof entry === "string" || entry.count === undefined ? -1 : entry.count }

    Rectangle {
        // sliding selection marker
        id: marker
        readonly property Item target: repeater.count > root.currentIndex && root.currentIndex >= 0 ? repeater.itemAt(root.currentIndex) : null
        visible: target !== null
        x: target ? row.x + target.x : 0
        width: target ? target.width : 0
        y: 3
        height: root.height - 6
        radius: theme.radiusSmall - 1
        color: theme.card
        border.color: theme.dark ? theme.border : Qt.darker(theme.border, 1.05)
        Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    }
    RowLayout {
        id: row
        anchors.left: parent.left
        anchors.leftMargin: 3
        anchors.verticalCenter: parent.verticalCenter
        height: root.height - 6
        spacing: 0
        Repeater {
            id: repeater
            model: root.model
            delegate: Item {
                id: segment
                required property int index
                required property var modelData
                readonly property bool selected: root.currentIndex === index
                Layout.fillHeight: true
                implicitWidth: content.implicitWidth + (root.compact ? 16 : 22)
                Accessible.role: Accessible.PageTab
                Accessible.name: root._text(modelData)
                RowLayout {
                    id: content
                    anchors.centerIn: parent
                    spacing: 5
                    Icon {
                        visible: root._icon(segment.modelData) !== ""
                        name: root._icon(segment.modelData)
                        size: 15
                        color: segment.selected ? theme.fg : theme.fgMuted
                    }
                    Text {
                        text: root._text(segment.modelData)
                        color: segment.selected ? theme.fg : (hover.hovered ? theme.fg : theme.fgMuted)
                        font.pixelSize: root.compact ? theme.fontSmall : theme.fontBody
                        font.weight: segment.selected ? Font.DemiBold : Font.Medium
                    }
                    Badge {
                        visible: root._count(segment.modelData) >= 0
                        count: Math.max(0, root._count(segment.modelData))
                        tone: segment.selected ? "primary" : "neutral"
                        showZero: true
                    }
                }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                TapHandler {
                    onTapped: { root.currentIndex = segment.index; root.activated(segment.index) }
                }
            }
        }
    }
}
