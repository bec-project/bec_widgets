import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Titled section. With collapsible: true the header toggles the content.
Rectangle {
    id: card

    property string title
    property string subtitle
    property bool collapsible: false
    property bool expanded: true
    property alias trailing: trailingSlot.data
    default property alias content: body.data

    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + 24
    radius: 10
    color: theme.card
    border.color: theme.border

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Image {
                visible: card.collapsible
                source: "image://material/" + (card.expanded ? "expand_more" : "chevron_right") + "?color=" + encodeURIComponent(theme.muted.toString())
                sourceSize: Qt.size(18, 18)
            }
            Text {
                text: card.title.toUpperCase()
                color: theme.muted
                font.pixelSize: 11
                font.weight: Font.Bold
                font.letterSpacing: 0.8
            }
            Text {
                text: card.subtitle
                color: theme.muted
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Row { id: trailingSlot; spacing: 4 }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 8
            visible: card.expanded
        }
    }

    MouseArea {
        visible: card.collapsible
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 40
        cursorShape: Qt.PointingHandCursor
        onClicked: card.expanded = !card.expanded
        z: -1
    }
}
