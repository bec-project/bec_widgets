import QtQuick
import QtQuick.Controls.Basic
import BecUi

// Status-bar bell. The badge counts unread notifications and takes the colour of the most
// serious one; a critical error that is not acknowledged keeps the bell coloured.
AbstractButton {
    id: root
    required property var backend
    readonly property var st: backend.state
    readonly property int unread: st.unread || 0
    readonly property bool alert: unread > 0 || (st.openCriticals || 0) > 0

    implicitWidth: 36
    implicitHeight: 24
    hoverEnabled: true
    checked: st.drawerOpen || false
    Accessible.name: "Notifications"
    onClicked: backend.toggleDrawer()

    background: Rectangle {
        radius: 6
        color: root.down ? theme.pressed : (root.hovered || root.checked ? theme.hover : "transparent")
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: root.st.bellIcon || "notifications"
            color: root.alert ? (root.st.bellColor || theme.fgMuted) : theme.fgMuted
            size: 18
        }
    }
    Rectangle {
        visible: root.unread > 0
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 1
        height: 14
        width: Math.max(14, badgeText.implicitWidth + 8)
        radius: 7
        color: root.st.bellColor || theme.primary
        Text {
            id: badgeText
            anchors.centerIn: parent
            text: root.unread > 99 ? "99+" : root.unread
            color: "white"
            font.pixelSize: 9
            font.weight: Font.Bold
        }
    }
    ToolTip.visible: hovered
    ToolTip.delay: 400
    ToolTip.text: st.bellTip || "Notifications"
}
