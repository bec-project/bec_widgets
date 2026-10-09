import QtQuick
import QtQuick.Layouts

// Rounded surface with an optional title row. Children go into the content column.
Rectangle {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias content: column.data
    property alias headerExtras: extras.data
    property int padding: 12
    property alias spacing: column.spacing

    color: theme.card
    radius: 10
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
            visible: root.title !== "" || extras.children.length > 0
            Layout.fillWidth: true
            spacing: 8
            Text {
                text: root.title
                color: theme.fg
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Text {
                text: root.subtitle
                visible: text !== ""
                color: theme.fgSubtle
                font.pixelSize: 12
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Item { Layout.fillWidth: root.subtitle === "" }
            Row { id: extras; spacing: 4 }
        }
        ColumnLayout {
            id: column
            Layout.fillWidth: true
            spacing: 8
        }
    }
}
