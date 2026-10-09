import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Staff sign-in in front of Device Config (BEC Atlas, like Admin View). backend: StaffBackend.
Rectangle {
    id: root
    required property QtObject backend
    color: theme.bg

    function submit() { root.backend.signIn(user.text, password.text) }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(420, parent.width - 32)
        implicitHeight: form.implicitHeight + 48
        radius: 10
        color: theme.card
        border.color: theme.border

        ColumnLayout {
            id: form
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 24 }
            spacing: 12

            Rectangle {
                implicitWidth: 44; implicitHeight: 44; radius: 22
                color: Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.14)
                Icon { anchors.centerIn: parent; name: "lock"; size: 22; color: theme.primary }
            }
            Text {
                text: "Device Config is for beamline staff"
                color: theme.fg
                font.pixelSize: 17
                font.weight: Font.Bold
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                text: "Sign in with your BEC Atlas account to add, remove and configure devices. Everyone can watch and operate devices in Devices."
                color: theme.fgMuted
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Layout.topMargin: 4
                Text { text: "User name"; color: theme.fg; font.pixelSize: 12; font.weight: Font.DemiBold }
                InputField {
                    id: user
                    Layout.fillWidth: true
                    enabled: !root.backend.busy
                    placeholderText: "e.g. e12345"
                    Accessible.name: "User name"
                    focus: true
                    onAccepted: password.forceActiveFocus()
                }
            }
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text { text: "Password"; color: theme.fg; font.pixelSize: 12; font.weight: Font.DemiBold }
                InputField {
                    id: password
                    Layout.fillWidth: true
                    enabled: !root.backend.busy
                    echoMode: TextInput.Password
                    Accessible.name: "Password"
                    onAccepted: root.submit()
                }
            }
            Text {
                visible: root.backend.error !== ""
                text: root.backend.error
                color: theme.danger
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                Text {
                    text: root.backend.deployment !== "" ? "Deployment " + root.backend.deployment : ""
                    color: theme.fgSubtle
                    font.pixelSize: 11
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                TextButton {
                    text: root.backend.busy ? "Signing in…" : "Sign in"
                    variant: "primary"
                    iconName: "login"
                    enabled: !root.backend.busy
                    onClicked: root.submit()
                }
            }
        }
    }
}
