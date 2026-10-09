import QtQuick

// A bec_qthemes Material icon, tinted with any theme colour.
Item {
    id: root
    property string name: "help"
    property color color: theme.fg
    property bool filled: true
    property int size: 18

    implicitWidth: size
    implicitHeight: size

    Image {
        anchors.fill: parent
        sourceSize.width: root.size * 2
        sourceSize.height: root.size * 2
        fillMode: Image.PreserveAspectFit
        smooth: true
        source: root.name ? "image://material/" + root.name + "?color="
                            + root.color.toString().substring(1, 7) + "&filled=" + (root.filled ? 1 : 0)
                          : ""
    }
}
