import QtQuick
import QtQuick.Controls.Basic

// Single-line text input with optional unit suffix, leading icon and error state.
TextField {
    id: root
    property bool invalid: false
    property string suffix: ""
    property string iconName: ""
    property bool monospace: false

    implicitHeight: theme.controlHeight
    implicitWidth: 120
    color: theme.fg
    placeholderTextColor: theme.fgSubtle
    selectionColor: theme.primary
    selectedTextColor: theme.onPrimary
    font.pixelSize: theme.fontBody
    font.family: monospace ? theme.monoFamily : Qt.application.font.family
    leftPadding: iconName !== "" ? 30 : 9
    rightPadding: suffixLabel.visible ? suffixLabel.implicitWidth + 14 : 9
    selectByMouse: true
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.5
    Accessible.name: placeholderText

    background: FieldFrame {
        focused: root.activeFocus
        invalid: root.invalid
        hovered: root.hovered
    }
    Icon {
        visible: root.iconName !== ""
        name: root.iconName
        size: 16
        color: root.activeFocus ? theme.primary : theme.fgSubtle
        anchors.left: parent.left
        anchors.leftMargin: 9
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        id: suffixLabel
        visible: root.suffix !== ""
        text: root.suffix
        color: theme.fgSubtle
        font.pixelSize: theme.fontSmall
        anchors.right: parent.right
        anchors.rightMargin: 9
        anchors.verticalCenter: parent.verticalCenter
    }
}
