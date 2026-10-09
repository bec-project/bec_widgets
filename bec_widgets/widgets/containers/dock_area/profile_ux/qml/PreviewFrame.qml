import QtQuick
import BecUi

// Screenshot preview that keeps the aspect ratio, with a placeholder text.
Item {
    id: root
    property string source: ""
    property string placeholder: "No preview yet"
    readonly property bool hasImage: source !== "" && image.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        visible: !root.hasImage
        radius: 8
        color: Qt.rgba(theme.fg.r, theme.fg.g, theme.fg.b, 0.04)
        border.color: theme.border
        Column {
            anchors.centerIn: parent
            spacing: 6
            Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "dashboard"; size: 32; color: theme.fgSubtle }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: root.width - 16
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: root.placeholder
                color: theme.fgSubtle
                font.pixelSize: 12
            }
        }
    }
    Image {
        id: image
        anchors.fill: parent
        source: root.source
        cache: false
        smooth: true
        mipmap: true
        fillMode: Image.PreserveAspectFit
    }
    Rectangle {
        visible: root.hasImage
        anchors.centerIn: parent
        width: image.paintedWidth + 1
        height: image.paintedHeight + 1
        radius: 4
        color: "transparent"
        border.color: theme.border
    }
}
