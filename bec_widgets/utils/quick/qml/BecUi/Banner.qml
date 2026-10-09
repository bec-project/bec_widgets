import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Inline message inside a card or above a form: tinted background, tone icon, title, text,
// an optional action button and an optional close button.
// tone: "info", "success", "warning" or "danger" (aliases accepted).
Rectangle {
    id: root
    property string tone: "info"
    property string title: ""
    property string text: ""
    property string iconName: ""
    property string actionText: ""
    property bool closable: false
    signal actionTriggered()
    signal closed()

    readonly property string _tone: tone === "ok" ? "success" : tone === "warn" ? "warning"
        : tone === "err" || tone === "error" ? "danger" : tone === "busy" ? "info" : tone
    readonly property string _icon: iconName !== "" ? iconName
        : _tone === "success" ? "check_circle" : _tone === "warning" ? "warning"
        : _tone === "danger" ? "error" : "info"

    implicitHeight: layout.implicitHeight + 20
    implicitWidth: 320
    radius: theme.radiusSmall + 2
    color: (theme.name, theme.toneTint(_tone))
    border.color: Qt.alpha((theme.name, theme.tone(_tone)), 0.45)
    Accessible.role: Accessible.AlertMessage
    Accessible.name: title + " " + text

    Rectangle {
        // accent bar
        width: 3
        radius: 1.5
        color: (theme.name, theme.tone(root._tone))
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 6 }
    }
    RowLayout {
        id: layout
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 8
        anchors.topMargin: 10
        anchors.bottomMargin: 10
        spacing: 10
        Icon {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 1
            name: root._icon
            filled: true
            size: 18
            color: (theme.name, theme.toneText(root._tone))
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                visible: root.title !== ""
                Layout.fillWidth: true
                text: root.title
                color: theme.fg
                font.pixelSize: theme.fontBody
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                visible: root.text !== ""
                Layout.fillWidth: true
                text: root.text
                color: root.title !== "" ? theme.fgMuted : theme.fg
                font.pixelSize: root.title !== "" ? theme.fontSmall : theme.fontBody
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
            }
        }
        TextButton {
            visible: root.actionText !== ""
            Layout.alignment: Qt.AlignVCenter
            compact: true
            variant: "neutral"
            text: root.actionText
            onClicked: root.actionTriggered()
        }
        IconButton {
            visible: root.closable
            Layout.alignment: Qt.AlignTop
            compact: true
            iconName: "close"
            tip: "Dismiss"
            onClicked: root.closed()
        }
    }
}
