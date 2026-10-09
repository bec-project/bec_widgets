import QtQuick
import QtQuick.Layouts
import BecUi

// A field that shows a device or signal and opens the searchable picker popup when clicked
// (or on Enter / Space). The popup itself is the shared QML picker, opened by Python.
FocusScope {
    id: root
    property string text: ""
    property string placeholder: ""
    property string iconName: "memory"
    property bool invalid: false
    signal requested()

    implicitHeight: theme.controlHeight
    implicitWidth: 160
    activeFocusOnTab: true
    Accessible.role: Accessible.ComboBox
    Accessible.name: root.text !== "" ? root.text : root.placeholder
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space || event.key === Qt.Key_Down) {
            root.requested()
            event.accepted = true
        }
    }

    FieldFrame {
        anchors.fill: parent
        focused: root.activeFocus
        invalid: root.invalid
        hovered: mouse.containsMouse
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 9
        anchors.rightMargin: 6
        spacing: 6
        Icon { name: root.iconName; size: 15; color: theme.fgMuted }
        Text {
            Layout.fillWidth: true
            text: root.text !== "" ? root.text : root.placeholder
            color: root.text !== "" ? theme.fg : theme.fgSubtle
            font.pixelSize: theme.fontBody
            elide: Text.ElideRight
        }
        Icon { name: "expand_more"; size: 18; color: theme.fgMuted }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.forceActiveFocus(); root.requested() }
    }
}
