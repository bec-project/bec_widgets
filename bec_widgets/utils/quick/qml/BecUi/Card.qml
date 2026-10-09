import QtQuick
import QtQuick.Layouts

// Rounded surface with an optional title row. Children go into the content column.
// titleStyle: "title" (13 px semibold) or "caption" (11 px uppercase, for form sections).
// collapsible: the title row toggles the content; expanded holds the state.
// headerExtras / trailing: items placed at the right end of the title row.
// fillContent: the content column takes the remaining height, e.g. for a list.
Rectangle {
    id: root
    property string title: ""
    property string subtitle: ""
    property string iconName: ""
    property string titleStyle: "title"
    property bool collapsible: false
    property bool expanded: true
    default property alias content: column.data
    property alias headerExtras: extras.data
    property alias trailing: extras.data
    property int padding: theme.padding
    property alias spacing: column.spacing
    property bool fillContent: false

    color: theme.card
    radius: theme.radiusLarge
    border.color: theme.border
    border.width: 1
    implicitHeight: outer.implicitHeight + 2 * padding
    implicitWidth: outer.implicitWidth + 2 * padding

    ColumnLayout {
        id: outer
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: 10
        RowLayout {
            id: header
            visible: root.title !== "" || extras.children.length > 0
            Layout.fillWidth: true
            spacing: 6
            Icon {
                visible: root.collapsible
                name: root.expanded ? "expand_more" : "chevron_right"
                size: 18
                color: theme.fgMuted
            }
            Icon {
                visible: root.iconName !== ""
                name: root.iconName
                size: 16
                color: theme.fgMuted
            }
            Text {
                text: root.titleStyle === "caption" ? root.title.toUpperCase() : root.title
                color: root.titleStyle === "caption" ? theme.fgMuted : theme.fg
                font.pixelSize: root.titleStyle === "caption" ? theme.fontCaption : theme.fontBody
                font.weight: root.titleStyle === "caption" ? Font.Bold : Font.DemiBold
                font.letterSpacing: root.titleStyle === "caption" ? 0.8 : 0
            }
            Text {
                text: root.subtitle
                visible: text !== ""
                color: theme.fgSubtle
                font.pixelSize: theme.fontSmall
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Item { Layout.fillWidth: root.subtitle === "" }
            Row { id: extras; spacing: 4 }
        }
        ColumnLayout {
            id: column
            visible: root.expanded
            Layout.fillWidth: true
            Layout.fillHeight: root.fillContent
            spacing: 8
        }
    }
    TapHandler {
        enabled: root.collapsible
        // only the title row toggles
        onTapped: (point) => {
            if (point.position.y <= root.padding + header.height + 4)
                root.expanded = !root.expanded
        }
    }
}
