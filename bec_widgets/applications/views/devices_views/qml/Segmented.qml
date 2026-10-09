import QtQuick
import QtQuick.Controls.Basic

// Segmented control. model: [{key, label}], current: key.
Rectangle {
    id: root
    property var model: []
    property string current: ""
    signal picked(string key)

    implicitHeight: 30
    implicitWidth: row.implicitWidth + 6
    radius: 7
    color: theme.track
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: root.model
            delegate: AbstractButton {
                id: seg
                required property var modelData
                readonly property bool on: modelData.key === root.current
                implicitHeight: 24
                implicitWidth: lbl.implicitWidth + 20
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                Accessible.name: modelData.label
                onClicked: root.picked(modelData.key)
                background: Rectangle {
                    radius: 5
                    color: seg.on ? theme.card : seg.hovered ? theme.hover : "transparent"
                    border.width: seg.visualFocus ? 1 : 0
                    border.color: theme.primary
                }
                contentItem: Text {
                    id: lbl
                    text: seg.modelData.label
                    color: seg.on ? theme.fg : theme.fgMuted
                    font.pixelSize: 12
                    font.weight: seg.on ? Font.DemiBold : Font.Normal
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
