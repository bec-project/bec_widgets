import QtQuick
import QtQuick.Controls.Basic

// Search input: magnifier icon, placeholder, a clear button once text is typed and an
// optional shortcut hint (e.g. "Ctrl K"). Escape clears the text.
InputField {
    id: root
    property string shortcutHint: ""
    signal cleared()

    iconName: "search"
    placeholderText: "Search"
    rightPadding: clear.visible ? 34 : hint.visible ? hint.implicitWidth + 18 : 9
    Keys.onEscapePressed: (event) => {
        if (root.text !== "") { root.clear(); root.cleared(); event.accepted = true }
        else event.accepted = false
    }

    IconButton {
        id: clear
        visible: root.text !== ""
        compact: true
        implicitWidth: 24
        implicitHeight: 24
        iconSize: 15
        iconName: "close"
        tip: "Clear"
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        onClicked: { root.clear(); root.cleared(); root.forceActiveFocus() }
    }
    Rectangle {
        id: hint
        visible: root.shortcutHint !== "" && root.text === "" && !root.activeFocus
        implicitWidth: hintText.implicitWidth + 10
        implicitHeight: 18
        radius: 4
        color: "transparent"
        border.color: theme.border
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        Text {
            id: hintText
            anchors.centerIn: parent
            text: root.shortcutHint
            color: theme.fgSubtle
            font.pixelSize: theme.fontCaption
        }
    }
}
