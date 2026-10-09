import QtQuick

// Thin progress bar. value: 0..1; indeterminate: a sliding segment for unknown duration.
// tone: "primary" (default), "success", "warning", "danger" ... ; the fill animates.
Item {
    id: root
    property real value: 0
    property bool indeterminate: false
    property string tone: "primary"
    property int thickness: 6

    readonly property color toneColor: (theme.name, tone === "primary" ? theme.primary : theme.tone(tone))

    implicitHeight: thickness
    implicitWidth: 160
    Accessible.role: Accessible.ProgressBar
    Accessible.name: indeterminate ? "busy" : Math.round(value * 100) + "%"

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: theme.track
        clip: true
        Rectangle {
            id: fill
            visible: !root.indeterminate
            height: parent.height
            radius: height / 2
            width: Math.max(root.value > 0 ? height : 0, parent.width * Math.max(0, Math.min(1, root.value)))
            color: root.toneColor
            Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 150 } }
        }
        Rectangle {
            id: runner
            visible: root.indeterminate
            height: parent.height
            radius: height / 2
            width: parent.width * 0.3
            color: root.toneColor
            NumberAnimation on x {
                running: root.indeterminate && root.visible
                from: -runner.width
                to: track.width
                duration: 1300
                loops: Animation.Infinite
                easing.type: Easing.InOutQuad
            }
        }
    }
}
