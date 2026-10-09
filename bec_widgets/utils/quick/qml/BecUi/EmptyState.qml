import QtQuick
import QtQuick.Layouts

// Placeholder for an empty list or view: a large icon, a title, an explanation and an
// optional action. Centre it in the area that would otherwise be blank.
ColumnLayout {
    id: root
    property string iconName: "inbox"
    property string title: ""
    property string text: ""
    property string actionText: ""
    property string actionIcon: ""
    property bool compact: false
    signal actionTriggered()

    spacing: compact ? 4 : 8
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: root.compact ? 36 : 52
        implicitHeight: implicitWidth
        radius: implicitWidth / 2
        color: theme.hover
        Icon {
            anchors.centerIn: parent
            name: root.iconName
            size: root.compact ? 20 : 28
            color: theme.fgSubtle
        }
    }
    Text {
        visible: root.title !== ""
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: root.compact ? 2 : 4
        text: root.title
        color: theme.fg
        font.pixelSize: root.compact ? theme.fontBody : theme.fontTitle
        font.weight: Font.DemiBold
    }
    Text {
        visible: root.text !== ""
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: 320
        text: root.text
        color: theme.fgMuted
        font.pixelSize: root.compact ? theme.fontSmall : theme.fontBody
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
    TextButton {
        visible: root.actionText !== ""
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 6
        variant: "neutral"
        compact: root.compact
        iconName: root.actionIcon
        text: root.actionText
        onClicked: root.actionTriggered()
    }
}
