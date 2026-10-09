import QtQuick
import QtQuick.Controls.Basic

// Combo box styled like the input fields. With editable: true it filters while typing.
ComboBox {
    id: root
    property bool invalid: false

    implicitHeight: 32
    implicitWidth: 140
    font.pixelSize: 13
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.5

    background: FieldFrame {
        focused: root.activeFocus || root.popup.visible
        invalid: root.invalid
        hovered: root.hovered
    }
    contentItem: TextField {
        leftPadding: 9
        rightPadding: 4
        text: root.editable ? root.editText : root.displayText
        readOnly: !root.editable
        enabled: root.enabled
        color: theme.fg
        selectionColor: theme.primary
        selectedTextColor: theme.onPrimary
        font: root.font
        verticalAlignment: Text.AlignVCenter
        background: null
        selectByMouse: true
        // forward clicks to the combo when it is not editable
        TapHandler { enabled: !root.editable; onTapped: root.popup.visible ? root.popup.close() : root.popup.open() }
    }
    indicator: Icon {
        x: root.width - width - 6
        y: (root.height - height) / 2
        name: "expand_more"
        size: 18
        color: theme.fgMuted
    }
    delegate: ItemDelegate {
        id: option
        required property int index
        required property var modelData
        width: ListView.view ? ListView.view.width : root.width
        height: 30
        highlighted: root.highlightedIndex === index
        contentItem: Text {
            text: option.modelData === "" ? "None" : option.modelData
            color: option.modelData === "" ? theme.fgSubtle : theme.fg
            font.pixelSize: 13
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: option.highlighted ? theme.hover : "transparent"
            Rectangle {
                width: 3; height: parent.height - 10; radius: 1.5
                anchors.verticalCenter: parent.verticalCenter
                color: theme.primary
                visible: root.currentIndex === option.index
            }
        }
    }
    popup: Popup {
        y: root.height + 2
        width: root.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 280)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle {
            color: theme.card
            border.color: theme.border
            radius: 8
        }
    }
}
