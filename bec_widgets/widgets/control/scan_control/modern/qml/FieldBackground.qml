import QtQuick

// Shared look of every input: filled box, accent border on focus, red border on error.
Rectangle {
    property bool focused: false
    property bool invalid: false
    radius: 6
    color: theme.field
    border.width: focused || invalid ? 1.5 : 1
    border.color: invalid ? theme.danger : focused ? theme.primary : theme.border
}
