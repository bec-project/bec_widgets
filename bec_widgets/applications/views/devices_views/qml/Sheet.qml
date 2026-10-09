import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Window-modal sheet: title, sub line, scrolling body and a footer row.
Popup {
    id: root
    property string title: ""
    property string sub: ""
    property bool wide: false
    default property alias content: body.data
    property alias footer: foot.data

    modal: true
    dim: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 40 : 640, wide ? 680 : 440)
    height: Math.min(parent ? parent.height - 40 : 600, layout.implicitHeight + 36)
    padding: 18
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle { color: theme.card; radius: 12; border.color: theme.border }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.45) }

    contentItem: ColumnLayout {
        id: layout
        spacing: 12
        Text { text: root.title; color: theme.fg; font.pixelSize: 16; font.weight: Font.Bold }
        Text {
            visible: root.sub !== ""
            text: root.sub
            textFormat: Text.StyledText
            color: theme.fgMuted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: Math.min(body.implicitHeight, 460)
            clip: true
            contentWidth: availableWidth
            ColumnLayout { id: body; width: parent.width; spacing: 8 }
        }
        RowLayout { id: foot; Layout.fillWidth: true; spacing: 8 }
    }
}
