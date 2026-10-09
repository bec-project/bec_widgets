import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// One queue entry. Model roles arrive as required properties.
Rectangle {
    id: row
    required property int index
    required property string section
    required property string requestId
    required property string scanId
    required property string scanNumber
    required property string title
    required property string subtitle
    required property string sample
    required property string stateLabel
    required property string tone
    required property string icon
    required property string details
    required property bool canMoveUp
    required property bool canMoveDown
    required property real progress
    required property string progressText
    required property bool removing

    signal abortClicked(Item anchor)

    property bool confirmingRemove: false

    implicitHeight: 54
    color: hover.hovered ? theme.hover : "transparent"
    opacity: removing ? 0.45 : section === "Recent" ? 0.82 : 1
    Behavior on opacity { NumberAnimation { duration: 150 } }

    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered && details !== "" && !confirmingRemove
    ToolTip.delay: 700
    ToolTip.text: details

    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 12; rightMargin: 12 }
        height: 1
        color: theme.separator
    }

    Timer {
        id: confirmTimer
        interval: 4000
        onTriggered: row.confirmingRemove = false
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 12; rightMargin: 8 }
        spacing: 10

        Text {
            Layout.preferredWidth: 44
            text: row.scanNumber !== "" ? row.scanNumber : "—"
            color: row.scanNumber !== "" ? theme.fg : theme.faint
            font.pixelSize: 13
            font.weight: Font.DemiBold
            font.family: "monospace"
            horizontalAlignment: Text.AlignRight
            Accessible.name: row.scanNumber !== "" ? "Scan " + row.scanNumber : "No scan number yet"
        }

        Item {
            Layout.preferredWidth: 136
            Layout.fillHeight: true
            StatusPill {
                anchors.verticalCenter: parent.verticalCenter
                label: row.removing ? "Removing…" : row.stateLabel
                iconName: row.removing ? "hourglass_empty" : row.icon
                tone: row.removing ? "stale" : row.tone
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 80
            spacing: 2
            RowLayout {
                spacing: 6
                Layout.fillWidth: true
                Text {
                    text: row.title
                    color: theme.fg
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: row.sample === ""
                }
                Rectangle {
                    visible: row.sample !== ""
                    implicitHeight: 18
                    implicitWidth: sampleText.implicitWidth + 12
                    radius: 4
                    color: theme.field
                    border.width: 1
                    border.color: theme.separator
                    Layout.maximumWidth: 180
                    Text {
                        id: sampleText
                        anchors.centerIn: parent
                        width: Math.min(implicitWidth, 168)
                        elide: Text.ElideRight
                        text: row.sample
                        color: theme.muted
                        font.pixelSize: 11
                    }
                }
                Item { Layout.fillWidth: row.sample !== "" }
            }
            Text {
                visible: text !== ""
                text: row.subtitle
                color: theme.muted
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // Progress of the running scan
        ColumnLayout {
            visible: row.section === "Now"
            Layout.preferredWidth: 190
            spacing: 4
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 5
                radius: 2.5
                color: theme.separator
                clip: true
                Rectangle {
                    visible: row.progress >= 0
                    height: parent.height
                    radius: 2.5
                    width: parent.width * Math.max(0, row.progress)
                    color: row.tone === "warn" ? theme.warning : theme.busy
                    Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                }
                Rectangle {   // indeterminate: no progress reported yet
                    id: sweep
                    visible: row.progress < 0 && row.tone === "busy"
                    height: parent.height
                    width: parent.width * 0.3
                    radius: 2.5
                    color: theme.busy
                    opacity: 0.7
                    NumberAnimation on x {
                        running: sweep.visible
                        loops: Animation.Infinite
                        from: -sweep.width
                        to: sweep.parent.width
                        duration: 1400
                        easing.type: Easing.InOutSine
                    }
                }
            }
            Text {
                text: row.progressText !== "" ? row.progressText : row.tone === "busy" ? "Waiting for progress…" : ""
                color: theme.muted
                font.pixelSize: 11
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // Actions
        Item {
            Layout.preferredWidth: 96
            Layout.fillHeight: true

            RowLayout {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0
                visible: !row.confirmingRemove

                IconButton {
                    visible: row.section === "Waiting"
                    iconName: "arrow_upward"
                    tip: "Move up"
                    enabled: row.canMoveUp && !row.removing
                    onClicked: queue.moveUp(row.scanId)
                }
                IconButton {
                    visible: row.section === "Waiting"
                    iconName: "arrow_downward"
                    tip: "Move down"
                    enabled: row.canMoveDown && !row.removing
                    onClicked: queue.moveDown(row.scanId)
                }
                IconButton {
                    visible: row.section === "Waiting"
                    iconName: "delete"
                    tip: "Remove this waiting scan from the queue"
                    danger: true
                    enabled: !row.removing && row.requestId !== ""
                    onClicked: { row.confirmingRemove = true; confirmTimer.restart(); keepButton.forceActiveFocus() }
                }
                IconButton {
                    id: abortButton
                    visible: row.section === "Now"
                    iconName: "stop_circle"
                    tip: "Abort " + (row.scanNumber !== "" ? "scan " + row.scanNumber : row.title) + "…"
                    danger: true
                    enabled: !row.removing && row.tone !== "ok"
                    onClicked: row.abortClicked(abortButton)
                }
            }

            // Inline two-step remove: no dialog, nothing removed on a single click
            RowLayout {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: row.confirmingRemove
                spacing: 4
                TextButton {
                    id: keepButton
                    text: "Keep"
                    implicitHeight: 24
                    onClicked: row.confirmingRemove = false
                }
                TextButton {
                    text: "Remove"
                    kind: "dangerSolid"
                    implicitHeight: 24
                    onClicked: { row.confirmingRemove = false; queue.remove(row.requestId) }
                }
            }
        }
    }
}
