import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Save, rename and duplicate a profile. The name is checked while typing; conflicts are
// explained under the field instead of in follow-up message boxes.
Rectangle {
    id: root
    required property var backend
    readonly property var check: backend.check
    color: theme.card

    Keys.onEscapePressed: backend.cancel()

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 18
        anchors.bottomMargin: 16
        spacing: 14

        Text {
            text: root.backend.heading
            color: theme.fg
            font.pixelSize: 16
            font.weight: Font.DemiBold
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            PreviewFrame {
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 220
                Layout.preferredHeight: 140
                source: root.backend.previewUrl
                placeholder: "Nothing to preview"
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 6

                Text { text: "Name"; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                InputField {
                    id: nameField
                    Layout.fillWidth: true
                    text: root.backend.initialName
                    placeholderText: "e.g. alignment, overview, tomo_scan"
                    invalid: root.check.tone === "error"
                    focus: true
                    onTextChanged: root.backend.setName(text)
                    onAccepted: root.backend.confirm()
                    Component.onCompleted: { selectAll(); forceActiveFocus() }
                }
                HintLine {
                    Layout.fillWidth: true
                    visible: root.check.message !== ""
                    tone: root.check.tone
                    text: root.check.message
                }
                TextButton {
                    visible: root.check.suggestion !== ""
                    variant: "ghost"
                    iconName: "auto_fix_high"
                    implicitHeight: 26
                    text: "Use '" + root.check.suggestion + "'"
                    onClicked: { nameField.text = root.check.suggestion; nameField.forceActiveFocus() }
                }

                ColumnLayout {
                    visible: root.backend.mode === "save"
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 6
                    Text { text: "Description"; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                    InputField {
                        Layout.fillWidth: true
                        text: root.backend.initialNotes
                        placeholderText: "Optional, shown in the profile library"
                        onTextChanged: root.backend.setNotes(text)
                        onAccepted: root.backend.confirm()
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text { text: "Show in toolbar list"; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                            Text { text: "Quick access from the profile drop-down."; color: theme.fgMuted; font.pixelSize: 12 }
                        }
                        SwitchField {
                            checked: root.backend.initialPinned
                            text: checked ? "On" : "Off"
                            onToggled: root.backend.setPinned(checked)
                        }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            TextButton { text: "Cancel"; variant: "neutral"; onClicked: root.backend.cancel() }
            TextButton {
                text: root.check.action
                variant: root.check.replaces ? "danger" : "primary"
                enabled: root.check.ok
                onClicked: root.backend.confirm()
            }
        }
    }
}
