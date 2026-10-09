import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Beamline states view. Context properties: theme (QmlTheme), controller
// (BeamlineStatesController) and statesModel (BeamlineStatesModel).
Rectangle {
    id: root
    color: theme.background
    focus: true

    property var expanded: ({})
    readonly property var statusOrder: ["invalid", "warning", "unknown", "valid"]
    readonly property var statusTitles: ({ invalid: "Invalid", warning: "Warning", unknown: "Unknown", valid: "Valid" })
    readonly property var statusIcons: ({ invalid: "cancel", warning: "warning", unknown: "help", valid: "check_circle" })

    function statusColor(status) {
        if (status === "invalid") return theme.danger
        if (status === "warning") return theme.warning
        if (status === "valid") return theme.success
        return theme.muted
    }
    function tint(c, alpha) { return Qt.rgba(c.r, c.g, c.b, alpha) }
    function icon(name, c, filled) {
        return "image://material/" + name + "?color=" + encodeURIComponent(c.toString()) + "&filled=" + (filled ? 1 : 0)
    }
    function isExpanded(name) { return expanded[name] === true }
    function toggleExpanded(name) {
        var copy = Object.assign({}, expanded)
        copy[name] = !copy[name]
        expanded = copy
    }
    function collapseAll() { expanded = ({}) }

    // ---------------------------------------------------------------- shared controls

    component Icon: Image {
        property string name
        property color tintColor: theme.foreground
        property bool filled: true
        property int size: 18
        source: name ? root.icon(name, tintColor, filled) : ""
        sourceSize: Qt.size(size, size)
        width: size
        height: size
        smooth: true
    }

    component IconButton: Rectangle {
        id: iconButton
        property string iconName
        property color iconColor: theme.foreground
        property bool filled: true
        property string tip
        signal clicked()
        implicitWidth: 28
        implicitHeight: 28
        radius: 6
        color: mouse.containsMouse ? root.tint(theme.foreground, 0.10) : "transparent"
        Icon { anchors.centerIn: parent; name: iconButton.iconName; tintColor: iconButton.iconColor; filled: iconButton.filled }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: iconButton.clicked()
        }
        ToolTip.visible: tip.length > 0 && mouse.containsMouse
        ToolTip.delay: 500
        ToolTip.text: tip
    }

    component TextButton: Rectangle {
        id: textButton
        property string text
        property string iconName
        property color accent: theme.primary
        property bool solid: false
        signal clicked()
        implicitHeight: 28
        implicitWidth: label.implicitWidth + (iconName ? 40 : 24)
        radius: 6
        color: solid ? (mouse.containsMouse ? Qt.darker(accent, 1.12) : accent)
                     : (mouse.containsMouse ? root.tint(accent, 0.14) : "transparent")
        border.width: solid ? 0 : 1
        border.color: root.tint(accent, 0.6)
        Row {
            anchors.centerIn: parent
            spacing: 6
            Icon {
                visible: textButton.iconName.length > 0
                name: textButton.iconName
                size: 16
                anchors.verticalCenter: parent.verticalCenter
                tintColor: textButton.solid ? theme.onPrimary : textButton.accent
            }
            Text {
                id: label
                text: textButton.text
                color: textButton.solid ? theme.onPrimary : textButton.accent
                font.pixelSize: 12
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: textButton.clicked()
        }
    }

    // Pulsing red outline marking something that blocks scans.
    component Pulse: Rectangle {
        id: pulse
        property bool running
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: 2
        border.color: theme.danger
        SequentialAnimation on opacity {
            running: pulse.running
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.25; duration: 700; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.25; to: 1.0; duration: 700; easing.type: Easing.InOutSine }
        }
    }

    component Toggle: Rectangle {
        id: toggle
        property bool checked
        property color accent: theme.success
        signal toggled(bool value)
        implicitWidth: 38
        implicitHeight: 22
        radius: height / 2
        color: checked ? accent : root.tint(theme.foreground, 0.22)
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            width: 16; height: 16; radius: 8
            y: 3
            x: toggle.checked ? toggle.width - width - 3 : 3
            color: "white"
            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: toggle.toggled(!toggle.checked)
        }
    }

    // ---------------------------------------------------------------- layout

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Summary chips (status filters), search and add.
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: root.statusOrder
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    readonly property int count: controller.counts[modelData] || 0
                    readonly property bool active: controller.statusFilter.indexOf(modelData) >= 0
                    readonly property color accent: root.statusColor(modelData)
                    implicitHeight: 28
                    implicitWidth: chipRow.implicitWidth + 20
                    radius: 14
                    opacity: count === 0 && !active ? 0.45 : 1.0
                    color: active ? root.tint(accent, 0.22) : (chipMouse.containsMouse ? root.tint(theme.foreground, 0.08) : "transparent")
                    border.width: 1
                    border.color: active ? accent : theme.border
                    Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle { width: 8; height: 8; radius: 4; color: chip.accent; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: chip.count + " " + root.statusTitles[chip.modelData]
                            color: theme.foreground
                            font.pixelSize: 12
                            font.weight: chip.active ? Font.DemiBold : Font.Normal
                        }
                    }
                    MouseArea {
                        id: chipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: controller.toggleStatusFilter(chip.modelData)
                    }
                    ToolTip.visible: chipMouse.containsMouse
                    ToolTip.delay: 600
                    ToolTip.text: chip.active ? "Stop filtering by " + root.statusTitles[chip.modelData] : "Show only " + root.statusTitles[chip.modelData] + " states"
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 150
                implicitHeight: 28
                radius: 6
                color: theme.field
                border.width: 1
                border.color: search.activeFocus ? theme.primary : theme.border
                Icon { id: searchIcon; name: "search"; size: 16; tintColor: theme.muted; anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter }
                TextInput {
                    id: search
                    anchors.left: searchIcon.right
                    anchors.right: clearSearch.left
                    anchors.margins: 6
                    anchors.verticalCenter: parent.verticalCenter
                    color: theme.foreground
                    font.pixelSize: 12
                    clip: true
                    selectByMouse: true
                    text: controller.searchText
                    onTextEdited: controller.setSearchText(text)
                    Keys.onEscapePressed: { text = ""; controller.setSearchText("") }
                    Text {
                        visible: !search.text && !search.activeFocus
                        text: "Search name or device"
                        color: theme.muted
                        font: search.font
                    }
                }
                IconButton {
                    id: clearSearch
                    visible: search.text.length > 0
                    width: visible ? 24 : 0; height: 24
                    anchors.right: parent.right; anchors.rightMargin: 2
                    anchors.verticalCenter: parent.verticalCenter
                    iconName: "close"; iconColor: theme.muted
                    onClicked: controller.setSearchText("")
                }
            }

            TextButton { text: "Add state"; iconName: "add"; solid: true; onClicked: controller.requestAdd() }
        }

        // Scan interlock banner.
        Rectangle {
            id: banner
            Layout.fillWidth: true
            readonly property bool armed: controller.interlockArmed
            readonly property var blocking: controller.blockingStates
            readonly property bool tripped: armed && blocking.length > 0
            readonly property color accent: tripped ? theme.danger : (armed ? theme.success : theme.muted)
            implicitHeight: 52
            radius: 8
            color: root.tint(accent, armed ? 0.16 : 0.08)
            border.width: 1
            border.color: root.tint(accent, tripped ? 0.9 : 0.45)

            Pulse { visible: banner.tripped; running: banner.tripped }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10
                Rectangle {
                    width: 30; height: 30; radius: 15
                    color: root.tint(banner.accent, 0.22)
                    Icon {
                        anchors.centerIn: parent
                        name: banner.tripped ? "block" : (banner.armed ? "lock" : "lock_open_right")
                        tintColor: banner.accent
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        Layout.fillWidth: true
                        text: banner.tripped ? "Scans are blocked by the scan interlock"
                              : banner.armed ? "Scan interlock armed, scans can run"
                              : "Scan interlock is off"
                        color: theme.foreground
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: banner.tripped ? "Blocking: " + banner.blocking.join(", ")
                              : controller.watchedCount === 0 ? "No states are watched. Use the lock on a state to watch it."
                              : controller.watchedCount + (controller.watchedCount === 1 ? " state is" : " states are") + " watched"
                                + (banner.armed ? "." : ". Arm the interlock to block scans when they fail.")
                        color: banner.tripped ? theme.danger : theme.muted
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }
                Text { text: banner.armed ? "Armed" : "Off"; color: theme.muted; font.pixelSize: 12 }
                Toggle {
                    checked: banner.armed
                    accent: banner.tripped ? theme.danger : theme.success
                    onToggled: function(value) { controller.setInterlockArmed(value) }
                }
            }
        }

        // State list.
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: list
                anchors.fill: parent
                clip: true
                spacing: 6
                model: statesModel
                boundsBehavior: Flickable.StopAtBounds
                reuseItems: false
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                section.property: "section"
                section.delegate: Item {
                    required property string section
                    width: list.width
                    height: 28
                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 2
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 4
                        spacing: 6
                        Icon {
                            name: section === "interlock" ? "lock" : "lock_open_right"
                            size: 14
                            tintColor: theme.muted
                        }
                        Text {
                            text: section === "interlock" ? "WATCHED BY SCAN INTERLOCK" : "NOT WATCHED"
                            color: theme.muted
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            font.letterSpacing: 0.6
                        }
                    }
                }

                move: Transition { NumberAnimation { properties: "y"; duration: 180; easing.type: Easing.OutCubic } }
                displaced: Transition { NumberAnimation { properties: "y"; duration: 180; easing.type: Easing.OutCubic } }
                add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 } }

                delegate: Rectangle {
                    id: card
                    required property string name
                    required property string status
                    required property string statusText
                    required property string label
                    required property string device
                    required property string stateType
                    required property var details
                    required property bool watched
                    required property string accepted
                    required property bool triggerOnWarning
                    required property bool triggered
                    required property bool filteredOut

                    readonly property bool open: root.isExpanded(name)
                    readonly property color accent: root.statusColor(status)
                    property bool confirmRemove: false

                    width: list.width - (list.ScrollBar.vertical.visible ? 10 : 0)
                    height: header.height + (open ? body.implicitHeight : 0)
                    Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    clip: true
                    radius: 8
                    opacity: filteredOut ? 0.5 : 1.0
                    color: headerMouse.containsMouse || open ? Qt.lighter(theme.card, theme.dark ? 1.08 : 0.98) : theme.card
                    border.width: 1
                    border.color: triggered ? theme.danger : (open ? root.tint(accent, 0.6) : theme.border)

                    Pulse { visible: card.triggered; running: card.triggered; z: 2 }

                    // Status stripe.
                    Rectangle {
                        x: 0; y: 0
                        width: 4; height: header.height
                        radius: 2
                        color: card.accent
                    }

                    Item {
                        id: header
                        width: parent.width
                        height: 52
                        MouseArea {
                            id: headerMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toggleExpanded(card.name)
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 8
                            spacing: 10
                            Rectangle {
                                width: 30; height: 30; radius: 15
                                color: root.tint(card.accent, 0.18)
                                Icon { anchors.centerIn: parent; name: root.statusIcons[card.status]; tintColor: card.accent }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Row {
                                    id: titleRow
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Text {
                                        width: Math.min(implicitWidth, titleRow.width - (deviceChip.visible ? deviceChip.width + 6 : 0))
                                        text: card.name
                                        color: theme.foreground
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Rectangle {
                                        id: deviceChip
                                        visible: card.device.length > 0
                                        anchors.verticalCenter: parent.verticalCenter
                                        implicitHeight: 18
                                        implicitWidth: deviceText.implicitWidth + 12
                                        radius: 4
                                        color: root.tint(theme.foreground, 0.08)
                                        Text { id: deviceText; anchors.centerIn: parent; text: card.device; color: theme.muted; font.pixelSize: 10; font.family: "monospace" }
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: card.label
                                    color: theme.muted
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }
                            Rectangle {
                                implicitHeight: 22
                                implicitWidth: statusLabel.implicitWidth + 14
                                radius: 11
                                color: root.tint(card.accent, 0.18)
                                Text { id: statusLabel; anchors.centerIn: parent; text: card.statusText; color: card.accent; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 0.5 }
                            }
                            IconButton {
                                iconName: card.watched ? "lock" : "lock_open_right"
                                filled: card.watched
                                iconColor: card.triggered ? theme.danger : (card.watched ? theme.foreground : theme.muted)
                                tip: card.watched ? "Watched by the scan interlock (accepts " + card.accepted + "). Click to stop watching."
                                                  : "Not watched by the scan interlock. Click to watch this state."
                                onClicked: controller.toggleWatched(card.name)
                            }
                            Icon { name: card.open ? "expand_less" : "expand_more"; tintColor: theme.muted }
                        }
                    }

                    ColumnLayout {
                        id: body
                        y: header.height
                        x: 14
                        width: parent.width - 28
                        spacing: 8
                        visible: card.open || card.height > header.height

                        Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }

                        GridLayout {
                            columns: 2
                            columnSpacing: 14
                            rowSpacing: 4
                            Layout.fillWidth: true
                            Text { text: "Type"; color: theme.muted; font.pixelSize: 11 }
                            Text { text: card.stateType; color: theme.foreground; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            Repeater {
                                model: card.details
                                delegate: Text {
                                    required property var modelData
                                    required property int index
                                    text: modelData.key
                                    color: theme.muted
                                    font.pixelSize: 11
                                    Layout.row: index + 1
                                    Layout.column: 0
                                }
                            }
                            Repeater {
                                model: card.details
                                delegate: Text {
                                    required property var modelData
                                    required property int index
                                    text: modelData.value
                                    color: theme.foreground
                                    font.pixelSize: 11
                                    font.family: "monospace"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    Layout.row: index + 1
                                    Layout.column: 1
                                }
                            }
                        }

                        RowLayout {
                            spacing: 8
                            Toggle {
                                checked: card.triggerOnWarning
                                accent: theme.warning
                                onToggled: function(value) { controller.setTriggerOnWarning(card.name, value) }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "Block scans on WARNING too" + (card.watched ? "" : " (applies once watched)")
                                color: theme.foreground
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }

                        RowLayout {
                            spacing: 8
                            Layout.bottomMargin: 10
                            TextButton { text: "Edit parameters"; iconName: "edit"; onClicked: controller.requestEdit(card.name) }
                            Item { Layout.fillWidth: true }
                            TextButton {
                                text: card.confirmRemove ? "Click again to remove" : "Remove"
                                iconName: "delete"
                                accent: theme.danger
                                solid: card.confirmRemove
                                onClicked: {
                                    if (card.confirmRemove) {
                                        card.confirmRemove = false
                                        controller.removeState(card.name)
                                    } else {
                                        card.confirmRemove = true
                                        confirmTimer.restart()
                                    }
                                }
                            }
                            Timer { id: confirmTimer; interval: 3000; onTriggered: card.confirmRemove = false }
                        }
                    }
                }

                footer: Item {
                    width: list.width
                    height: visible ? 40 : 0
                    visible: controller.hiddenCount > 0 && list.count > 0
                    Row {
                        anchors.centerIn: parent
                        spacing: 10
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: controller.hiddenCount + (controller.hiddenCount === 1 ? " state hidden" : " states hidden") + " by filters"
                            color: theme.muted
                            font.pixelSize: 11
                        }
                        TextButton {
                            text: controller.showFiltered ? "Hide them" : "Show them"
                            accent: theme.foreground
                            onClicked: controller.setShowFiltered(!controller.showFiltered)
                        }
                        TextButton { text: "Clear filters"; accent: theme.primary; onClicked: controller.clearFilters() }
                    }
                }
            }

            // Empty states.
            Column {
                anchors.centerIn: parent
                spacing: 10
                visible: list.count === 0
                Icon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: controller.totalCount === 0 ? "playlist_add" : "filter_alt_off"
                    size: 36
                    tintColor: theme.muted
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: controller.totalCount === 0 ? "No beamline states yet" : "No states match the filters"
                    color: theme.foreground
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: controller.totalCount === 0 ? "States check conditions such as a motor within limits." : controller.hiddenCount + " states are hidden."
                    color: theme.muted
                    font.pixelSize: 11
                }
                TextButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: controller.totalCount === 0 ? "Add state" : "Clear filters"
                    iconName: controller.totalCount === 0 ? "add" : ""
                    solid: controller.totalCount === 0
                    onClicked: controller.totalCount === 0 ? controller.requestAdd() : controller.clearFilters()
                }
            }
        }
    }
}
