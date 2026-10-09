import QtQuick
import QtQuick.Layouts

// Label above a control, with a required mark, a helper line and an error line.
// The error replaces the helper and turns red; put the control as the child.
ColumnLayout {
    id: root
    property string label: ""
    property bool required: false
    property string helper: ""
    property string error: ""
    property string unit: ""
    default property alias control: slot.data

    spacing: 4
    RowLayout {
        visible: root.label !== ""
        spacing: 4
        Text {
            text: root.label
            color: theme.fgMuted
            font.pixelSize: theme.fontSmall
            font.weight: Font.Medium
        }
        Text {
            visible: root.required
            text: "*"
            color: theme.dangerText
            font.pixelSize: theme.fontSmall
            Accessible.name: "required"
        }
        Text {
            visible: root.unit !== ""
            text: "(" + root.unit + ")"
            color: theme.fgSubtle
            font.pixelSize: theme.fontSmall
        }
    }
    ColumnLayout {
        id: slot
        Layout.fillWidth: true
        spacing: 0
        // the control stretches to the width of the field
        onChildrenChanged: {
            for (let i = 0; i < children.length; ++i)
                children[i].Layout.fillWidth = true
        }
    }
    RowLayout {
        visible: root.error !== "" || root.helper !== ""
        spacing: 4
        Icon {
            visible: root.error !== ""
            name: "error"
            filled: true
            size: 13
            color: theme.dangerText
        }
        Text {
            Layout.fillWidth: true
            text: root.error !== "" ? root.error : root.helper
            color: root.error !== "" ? theme.dangerText : theme.fgSubtle
            font.pixelSize: theme.fontSmall
            wrapMode: Text.WordWrap
        }
    }
}
