import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// What an empty dock area shows: Add widget, three starter layouts and a docking hint.
Rectangle {
    id: root
    required property QtObject backend
    signal addRequested()

    color: theme.bg

    readonly property var schematics: ({
        "Scanning": [[0, 0, 0.36, 1], [0.38, 0, 0.62, 0.58], [0.38, 0.62, 0.62, 0.38]],
        "Alignment": [[0, 0, 0.58, 1], [0.6, 0, 0.4, 0.48], [0.6, 0.52, 0.4, 0.48]],
        "Monitoring": [[0, 0, 0.4, 0.48], [0, 0.52, 0.4, 0.48], [0.42, 0, 0.58, 1]]
    })

    ColumnLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -parent.height * 0.04
        width: Math.min(680, parent.width - 32)
        spacing: 8

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 56; height: 56; radius: 28
            color: Qt.tint(theme.bg, Qt.alpha(theme.primary, 0.16))
            Icon { anchors.centerIn: parent; name: "dashboard_customize"; color: theme.primary; size: 30 }
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "This workspace is empty"
            color: theme.fg
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Add the widgets you need, or start from a layout and change it afterwards."
            color: theme.fgMuted
            font.pixelSize: 13
        }
        TextButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 8
            Layout.minimumWidth: 150
            text: "Add widget"
            iconName: "add"
            variant: "primary"
            tip: "Open the widget gallery (Ctrl+Shift+A)"
            onClicked: root.addRequested()
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 18
            text: "Or start from a layout"
            color: theme.fgMuted
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 12
            Repeater {
                model: root.backend.layoutModel
                delegate: AbstractButton {
                    id: card
                    required property string name
                    required property string description
                    implicitWidth: 196
                    implicitHeight: content.implicitHeight + 24
                    padding: 12
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    Accessible.name: "Start from the " + name + " layout"
                    onClicked: root.backend.activate_layout(name)
                    background: Rectangle {
                        radius: 10
                        color: theme.card
                        border.color: card.hovered || card.visualFocus ? theme.primary : theme.border
                        Behavior on border.color { ColorAnimation { duration: 90 } }
                    }
                    contentItem: ColumnLayout {
                        id: content
                        spacing: 4
                        Item {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 64
                            Repeater {
                                model: root.schematics[card.name] || []
                                delegate: Rectangle {
                                    required property var modelData
                                    x: modelData[0] * parent.width
                                    y: modelData[1] * parent.height
                                    width: modelData[2] * parent.width
                                    height: modelData[3] * parent.height
                                    radius: 4
                                    color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.14))
                                    border.color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.45))
                                    Rectangle {
                                        x: 5; y: 5; height: 4; radius: 2
                                        width: Math.min(26, parent.width - 10)
                                        color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.55))
                                    }
                                }
                            }
                        }
                        Text {
                            Layout.topMargin: 6
                            text: card.name; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: card.description; color: theme.fgMuted; font.pixelSize: 12
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }
        Text {
            Layout.fillWidth: true
            Layout.topMargin: 14
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Tip: drag a tab onto the edge of another widget to split the view, or onto its centre to stack them as tabs."
            color: theme.fgSubtle
            font.pixelSize: 12
        }
    }
}
