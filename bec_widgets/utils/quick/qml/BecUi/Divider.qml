import QtQuick
import QtQuick.Layouts

// Hairline separator. vertical: true for a vertical rule inside a row.
Rectangle {
    property bool vertical: false
    color: theme.separator
    implicitWidth: vertical ? 1 : 10
    implicitHeight: vertical ? 10 : 1
    Layout.fillWidth: !vertical
    Layout.fillHeight: vertical
}
