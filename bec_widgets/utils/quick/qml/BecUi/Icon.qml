import QtQuick

// Material icon served by the "material" image provider, tinted with the given colour.
Item {
    id: root
    property string name: ""
    property color color: theme.fg
    property bool filled: false
    property int size: 18

    implicitWidth: size
    implicitHeight: size

    Image {
        anchors.centerIn: parent
        width: root.size
        height: root.size
        sourceSize.width: root.size * 2
        sourceSize.height: root.size * 2
        smooth: true
        fillMode: Image.PreserveAspectFit
        source: root.name === "" ? "" : "image://material/" + root.name + "?color="
            + encodeURIComponent(root.color.toString()) + (root.filled ? "&filled=1" : "")
    }
}
