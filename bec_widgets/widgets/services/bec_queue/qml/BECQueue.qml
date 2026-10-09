import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// BEC scan queue. Context properties: `queue` (QueueController), `theme` (QmlTheme).
Rectangle {
    id: root
    color: theme.card

    readonly property bool hasCurrent: queue.runningCount > 0
    readonly property bool paused: queue.state === "paused"
    readonly property bool locked: queue.state === "locked"

    function stateTone() {
        return locked ? "err" : paused ? "warn" : queue.state === "running" ? "busy" : "neutral"
    }
    function stateLabel() {
        return locked ? "Locked" : paused ? "Paused" : queue.state === "running" ? "Running" : "Ready"
    }
    function stateIcon() {
        return locked ? "lock" : paused ? "pause" : queue.state === "running" ? "play_arrow" : "check"
    }
    function countsText() {
        var parts = []
        if (queue.runningCount > 0) parts.push(queue.runningCount + " running")
        parts.push(queue.waitingCount + " waiting")
        return parts.join(" · ")
    }

    // ------------------------------------------------------------------ confirmation popover
    Popup {
        id: confirm
        property string title
        property string body
        property string confirmText
        property var action: null

        property Item anchorItem: null

        function ask(anchor, t, b, c, fn) {
            title = t; body = b; confirmText = c; action = fn; anchorItem = anchor
            place()
            open()
            cancelButton.forceActiveFocus()
        }
        // Below the button that asked, kept inside the view.
        function place() {
            if (!anchorItem) return
            var p = anchorItem.mapToItem(root, 0, anchorItem.height + 6)
            x = Math.max(8, Math.min(p.x + anchorItem.width - width, root.width - width - 8))
            y = Math.max(8, Math.min(p.y, root.height - height - 8))
        }
        onHeightChanged: place()

        width: 320
        padding: 14
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            color: theme.card
            radius: 9
            border.color: theme.border
        }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110 } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 90 } }

        contentItem: ColumnLayout {
            spacing: 8
            Text {
                text: confirm.title
                color: theme.fg
                font.pixelSize: 14
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Text {
                text: confirm.body
                color: theme.muted
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.topMargin: 4
                Layout.alignment: Qt.AlignRight
                spacing: 6
                TextButton { id: cancelButton; text: "Cancel"; onClicked: confirm.close() }
                TextButton {
                    text: confirm.confirmText
                    kind: "dangerSolid"
                    onClicked: { confirm.close(); if (confirm.action) confirm.action() }
                }
            }
        }
    }

    function askAbort(anchor) {
        var scan = queue.currentLabel
        var waiting = queue.waitingCount
        confirm.ask(anchor, "Abort " + scan + "?",
                    "Data recorded so far is kept and the cleanup runs. The queue pauses afterwards"
                    + (waiting > 0 ? "; the " + waiting + " waiting scan" + (waiting > 1 ? "s stay" : " stays") + " queued." : "."),
                    "Abort scan", function () { queue.abortCurrent() })
    }

    // ------------------------------------------------------------------ layout
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header: state, counts and queue controls
        RowLayout {
            visible: queue.toolbarVisible
            Layout.fillWidth: true
            Layout.margins: 10
            Layout.bottomMargin: 8
            spacing: 8

            StatusPill {
                label: root.stateLabel()
                iconName: root.stateIcon()
                tone: root.stateTone()
                Accessible.name: "Queue " + root.stateLabel()
            }
            Text {
                text: root.countsText()
                color: theme.muted
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            TextButton {
                text: root.paused || root.locked ? "Resume" : "Pause"
                iconName: root.paused || root.locked ? "play_arrow" : "pause"
                enabled: !root.locked
                tip: root.locked ? "The queue is locked: " + queue.lockReason
                     : root.paused ? "Let the next scan start"
                     : "Pause the queue: the running scan holds at its next checkpoint, nothing new starts"
                onClicked: root.paused ? queue.resume() : queue.pause()
            }
            TextButton {
                id: abortHeader
                text: "Abort scan"
                iconName: "stop"
                kind: "danger"
                enabled: root.hasCurrent
                tip: root.hasCurrent ? "Abort " + queue.currentLabel + " (asks first)" : "No scan is running"
                onClicked: root.askAbort(abortHeader)
            }
            IconButton {
                id: moreButton
                iconName: "more_horiz"
                tip: "More queue actions"
                onClicked: moreMenu.popup(moreButton, 0, moreButton.height + 4)
            }
        }

        Menu {
            id: moreMenu
            background: Rectangle { implicitWidth: 260; color: theme.card; radius: 8; border.color: theme.border }
            delegate: MenuItem {
                id: mi
                implicitHeight: 30
                contentItem: Text {
                    leftPadding: mi.checkable ? 22 : 4
                    text: mi.text
                    color: !mi.enabled ? theme.faint : mi.text.indexOf("Halt") === 0 || mi.text.indexOf("Clear") === 0 ? theme.dangerText : theme.fg
                    font.pixelSize: 13
                    verticalAlignment: Text.AlignVCenter
                }
                indicator: Icon {
                    visible: mi.checkable && mi.checked
                    x: 8; anchors.verticalCenter: parent.verticalCenter
                    name: "check"; size: 15; color: theme.fg
                }
                background: Rectangle { color: mi.highlighted ? theme.hover : "transparent"; radius: 5 }
            }
            MenuItem {
                text: "Show recent scans"
                checkable: true
                checked: queue.showRecent
                onTriggered: queue.showRecent = !queue.showRecent
            }
            MenuSeparator {
                contentItem: Rectangle { implicitHeight: 1; color: theme.separator }
            }
            MenuItem {
                text: "Halt scan without cleanup…"
                enabled: root.hasCurrent
                onTriggered: confirm.ask(moreButton, "Halt " + queue.currentLabel + " without cleanup?",
                    "Stops immediately and skips the scan's cleanup routines, so motors may stay where they are. Use Abort unless cleanup itself is the problem.",
                    "Halt scan", function () { queue.halt() })
            }
            MenuItem {
                text: "Clear queue…"
                enabled: root.hasCurrent || queue.waitingCount > 0
                onTriggered: confirm.ask(moreButton, "Clear the queue?",
                    (root.hasCurrent ? "Stops " + queue.currentLabel + " and removes " : "Removes ")
                    + queue.waitingCount + " waiting scan" + (queue.waitingCount === 1 ? "" : "s") + ". This cannot be undone, and the queue is paused afterwards.",
                    "Clear queue", function () { queue.clear() })
            }
        }

        // Banners: say why nothing is moving
        Rectangle {
            visible: root.locked || root.paused
            Layout.fillWidth: true
            Layout.leftMargin: 10
            Layout.rightMargin: 10
            Layout.bottomMargin: 8
            implicitHeight: bannerRow.implicitHeight + 16
            radius: 7
            color: root.locked ? theme.dangerTint : theme.warningTint
            RowLayout {
                id: bannerRow
                anchors { fill: parent; margins: 8; leftMargin: 10 }
                spacing: 10
                Icon {
                    name: root.locked ? "lock" : "pause_circle"
                    size: 20
                    color: root.locked ? theme.dangerText : theme.warningText
                    Layout.alignment: Qt.AlignTop
                }
                ColumnLayout {
                    spacing: 1
                    Layout.fillWidth: true
                    Text {
                        text: root.locked ? "Queue locked" : "Queue paused"
                        color: theme.fg
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: theme.muted
                        font.pixelSize: 12
                        text: root.locked
                              ? (queue.lockReason !== "" ? queue.lockReason + ". " : "") + "Scans start again when the lock is released."
                              : root.hasCurrent ? "The running scan holds at its next checkpoint; nothing new starts until you resume."
                              : "Nothing new starts until you resume."
                    }
                }
                TextButton {
                    visible: root.paused
                    text: "Resume"
                    iconName: "play_arrow"
                    onClicked: queue.resume()
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.separator; visible: queue.toolbarVisible }

        // Rows
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: queue.model
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            keyNavigationEnabled: true

            section.property: "section"
            section.delegate: Rectangle {
                required property string section
                width: ListView.view.width
                implicitHeight: 26
                color: theme.bg
                Text {
                    anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                    text: (section === "Recent" ? "Recently finished" : section).toUpperCase()
                          + (section === "Waiting" ? "  ·  " + queue.waitingCount : "")
                    color: theme.faint
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                }
            }

            delegate: QueueRow {
                width: ListView.view.width
                onAbortClicked: (anchor) => root.askAbort(anchor)
            }

            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180 }
                NumberAnimation { property: "x"; from: -12; to: 0; duration: 180; easing.type: Easing.OutCubic }
            }
            remove: Transition {
                NumberAnimation { property: "opacity"; to: 0; duration: 150 }
            }
            displaced: Transition {
                NumberAnimation { properties: "y"; duration: 200; easing.type: Easing.OutCubic }
            }
            move: Transition {
                NumberAnimation { properties: "y"; duration: 200; easing.type: Easing.OutCubic }
            }
        }
    }

    // Empty state: teaches instead of showing a blank table
    ColumnLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: queue.toolbarVisible ? 22 : 0
        visible: !root.hasCurrent && queue.waitingCount === 0 && queue.recentCount === 0
        spacing: 6
        Icon {
            Layout.alignment: Qt.AlignHCenter
            name: "playlist_add"
            size: 30
            color: theme.faint
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Queue is empty"
            color: theme.fg
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: queue.lastFinished !== "" ? "Last: " + queue.lastFinished
                  : "Scans you submit from Scan Control or the command line appear here."
            color: theme.muted
            font.pixelSize: 12
        }
    }
}
