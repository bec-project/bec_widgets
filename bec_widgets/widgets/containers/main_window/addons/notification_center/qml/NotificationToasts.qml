import QtQuick
import QtQuick.Layouts
import BecUi

// Bottom-right toast stack. Newest toast at the bottom, nearest to the status bar.
// Hovering the stack pauses every countdown. Critical errors stay until acknowledged.
Item {
    id: root
    required property var backend
    readonly property var st: backend.state

    implicitWidth: 396
    implicitHeight: stack.implicitHeight + 16

    HoverHandler {
        onHoveredChanged: root.backend.setHovered(hovered)
    }

    Column {
        id: stack
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 8
        spacing: 10

        move: Transition { NumberAnimation { properties: "y"; duration: 140; easing.type: Easing.OutCubic } }
        add: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 }
            NumberAnimation { property: "x"; from: 40; to: 0; duration: 180; easing.type: Easing.OutCubic }
        }

        Item {
            width: stack.width
            height: moreButton.visible ? moreButton.implicitHeight : 0
            visible: (root.st.overflow || 0) > 0
            TextButton {
                id: moreButton
                anchors.right: parent.right
                visible: parent.visible
                text: (root.st.overflow || 0) + " more in notifications"
                iconName: "expand_less"
                background: Rectangle {
                    radius: 6
                    color: moreButton.hovered ? theme.hover : theme.card
                    border.color: theme.border
                }
                onClicked: root.backend.setDrawerOpen(true)
            }
        }

        Repeater {
            model: root.backend.toasts
            delegate: Item {
                id: toast
                required property string entryId
                required property string icon
                required property color color
                required property color tint
                required property string title
                required property string body
                required property string meta
                required property string severity
                required property int count
                required property bool needsAck
                required property bool hasDetails

                width: stack.width
                height: card.height

                // soft shadow
                Rectangle {
                    x: 0; y: 3
                    width: card.width; height: card.height
                    radius: 11
                    color: Qt.rgba(0, 0, 0, theme.dark ? 0.35 : 0.07)
                }

                Rectangle {
                    id: card
                    width: parent.width
                    height: content.implicitHeight + 22
                    radius: 10
                    color: theme.card
                    border.width: toast.needsAck ? 1.5 : 1
                    border.color: toast.needsAck ? toast.color : theme.border

                    Rectangle {
                        x: 0; y: card.radius
                        width: 4; height: parent.height - 2 * card.radius
                        radius: 2
                        color: toast.color
                    }

                    RowLayout {
                        id: content
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.leftMargin: 14
                        anchors.rightMargin: 10
                        anchors.topMargin: 12
                        spacing: 12

                        Rectangle {
                            Layout.alignment: Qt.AlignTop
                            width: 32; height: 32; radius: 16
                            color: toast.tint
                            Icon { anchors.centerIn: parent; name: toast.icon; color: toast.color; filled: true; size: 19 }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text {
                                    Layout.fillWidth: true
                                    text: toast.title
                                    textFormat: Text.PlainText
                                    color: theme.fg
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    visible: toast.count > 1
                                    implicitWidth: countLabel.implicitWidth + 12
                                    implicitHeight: 16
                                    radius: 8
                                    color: toast.tint
                                    Text {
                                        id: countLabel
                                        anchors.centerIn: parent
                                        text: "×" + toast.count
                                        color: toast.color
                                        font.pixelSize: 11
                                        font.weight: Font.Bold
                                    }
                                }
                                IconButton {
                                    visible: !toast.needsAck
                                    implicitWidth: 24; implicitHeight: 24
                                    iconName: "close"; iconSize: 16
                                    tip: "Dismiss"
                                    onClicked: root.backend.dismissToast(toast.entryId)
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: toast.body !== ""
                                text: toast.body
                                textFormat: Text.PlainText
                                color: theme.fgMuted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                maximumLineCount: 4
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: toast.meta
                                color: theme.fgSubtle
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                visible: copyButton.visible || detailsButton.visible || ackButton.visible
                                Item { Layout.fillWidth: true }
                                IconButton {
                                    id: copyButton
                                    visible: toast.severity === "error" || toast.severity === "critical"
                                    implicitWidth: 28; implicitHeight: 28
                                    iconName: "content_copy"; iconSize: 16
                                    tip: "Copy report"
                                    onClicked: root.backend.copyDetails(toast.entryId)
                                }
                                TextButton {
                                    id: detailsButton
                                    visible: toast.hasDetails || toast.needsAck
                                    implicitHeight: 28
                                    text: "Details"; iconName: "open_in_new"; variant: "ghost"
                                    onClicked: root.backend.openDetails(toast.entryId)
                                }
                                TextButton {
                                    id: ackButton
                                    visible: toast.needsAck
                                    implicitHeight: 28
                                    text: "Acknowledge"; iconName: "done"; variant: "danger"
                                    onClicked: root.backend.acknowledge(toast.entryId)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
