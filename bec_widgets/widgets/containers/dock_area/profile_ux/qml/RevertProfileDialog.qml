import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Confirm reverting a profile to its saved layout; current and saved layout side by side.
Rectangle {
    id: root
    required property var backend
    color: theme.card
    Keys.onEscapePressed: backend.cancel()

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 18
        anchors.bottomMargin: 16
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Revert '" + root.backend.name + "' to its saved layout?"
            color: theme.fg
            font.pixelSize: 16
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: root.backend.text
            color: theme.fgMuted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12
            Repeater {
                model: [
                    { caption: "NOW", url: root.backend.nowUrl, sub: "Current layout" },
                    { caption: "AFTER REVERT", url: root.backend.savedUrl, sub: root.backend.savedCaption }
                ]
                delegate: RowLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    spacing: 12
                    Icon {
                        visible: index === 1
                        name: "arrow_forward"
                        size: 20
                        color: theme.fgSubtle
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.fillHeight: true
                        spacing: 6
                        Text {
                            text: modelData.caption
                            color: theme.fgSubtle
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.5
                        }
                        PreviewFrame {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 150
                            source: modelData.url
                            placeholder: "No screenshot"
                        }
                        Text { text: modelData.sub; color: theme.fgMuted; font.pixelSize: 12 }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            TextButton {
                text: "Keep current layout"
                variant: "neutral"
                focus: true
                onClicked: root.backend.cancel()
                Keys.onReturnPressed: root.backend.cancel()
            }
            TextButton {
                text: "Revert"
                variant: "danger"
                iconName: "history"
                onClicked: root.backend.confirm()
            }
        }
    }
}
