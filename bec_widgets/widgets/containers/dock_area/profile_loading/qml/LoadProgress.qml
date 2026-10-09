import QtQuick

// Floating card that reports profile loading progress.
Item {
    id: root

    property string profile: ""
    property string subtitle: ""
    property real fraction: 0
    property var colors: ({})

    signal cancelRequested()

    Rectangle {
        id: card
        anchors.fill: parent
        anchors.margins: 1
        radius: 10
        color: root.colors.card
        border.color: root.colors.border
        clip: true

        Column {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.right: cancel.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -2
            spacing: 2
            Text {
                width: parent.width
                text: "Loading workspace “" + root.profile + "”"
                color: root.colors.text
                font.bold: true
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: root.subtitle
                color: root.colors.muted
                elide: Text.ElideRight
            }
        }

        Rectangle {
            id: cancel
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -2
            width: cancelText.implicitWidth + 20
            height: 28
            radius: 6
            color: cancelArea.containsMouse ? root.colors.block : "transparent"
            Text {
                id: cancelText
                anchors.centerIn: parent
                text: "Cancel"
                color: root.colors.accent
                font.bold: true
            }
            MouseArea {
                id: cancelArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.cancelRequested()
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 3
            color: root.colors.block
            Rectangle {
                height: parent.height
                width: parent.width * root.fraction
                color: root.colors.accent
                Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            }
        }
    }
}
