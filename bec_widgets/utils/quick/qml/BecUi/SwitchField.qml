import QtQuick
import QtQuick.Controls.Basic

// Toggle switch for boolean parameters.
Switch {
    id: root
    implicitHeight: 32
    hoverEnabled: true
    padding: 0
    indicator: Rectangle {
        implicitWidth: 38
        implicitHeight: 22
        x: root.leftPadding
        y: (root.height - height) / 2
        radius: 11
        color: root.checked ? theme.primary : theme.track
        border.color: root.visualFocus ? theme.primary : (root.checked ? theme.primary : theme.border)
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            x: root.checked ? parent.width - width - 3 : 3
            y: 3
            width: 16; height: 16; radius: 8
            color: root.checked ? theme.onPrimary : theme.fgMuted
            Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Text {
        leftPadding: root.indicator.width + 8
        text: root.text
        color: theme.fg
        font.pixelSize: 13
        verticalAlignment: Text.AlignVCenter
    }
}
