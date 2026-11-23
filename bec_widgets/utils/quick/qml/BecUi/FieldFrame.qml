import QtQuick

// Background used by all input controls: field colour, border, focus and error states.
Rectangle {
    property bool focused: false
    property bool invalid: false
    property bool hovered: false
    radius: 6
    color: theme.field
    border.width: focused || invalid ? 2 : 1
    border.color: invalid ? theme.danger : focused ? theme.primary : hovered ? theme.fgSubtle : theme.border
}
