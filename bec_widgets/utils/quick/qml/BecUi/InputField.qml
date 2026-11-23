import QtQuick
import QtQuick.Controls.Basic

// Single-line text input with optional unit suffix and error state.
TextField {
    id: root
    property bool invalid: false
    property string suffix: ""

    implicitHeight: 32
    implicitWidth: 120
    color: theme.fg
    placeholderTextColor: theme.fgSubtle
    selectionColor: theme.primary
    selectedTextColor: theme.onPrimary
    font.pixelSize: 13
    leftPadding: 9
    rightPadding: suffixLabel.visible ? suffixLabel.implicitWidth + 14 : 9
    selectByMouse: true
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.5

    background: FieldFrame {
        focused: root.activeFocus
        invalid: root.invalid
        hovered: root.hovered
    }
    Text {
        id: suffixLabel
        visible: root.suffix !== ""
        text: root.suffix
        color: theme.fgSubtle
        font.pixelSize: 12
        anchors.right: parent.right
        anchors.rightMargin: 9
        anchors.verticalCenter: parent.verticalCenter
    }
}
