import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Beamline state manager: status counts as filters, search, scan-interlock switch and a
// list of states grouped by scan-interlock membership.
// backend: BeamlineStatesBackend (state map, rows model, actions).
Rectangle {
    id: root
    required property QtObject backend
    readonly property var s: backend.state

    function toneColor(tone) {
        return tone === "primary" ? theme.primary : tone === "success" ? theme.success
             : tone === "warning" ? theme.warning : tone === "danger" ? theme.danger : theme.fgMuted
    }
    function soft(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    color: theme.bg
    implicitWidth: 420
    implicitHeight: 480

    Card {
        id: card
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8
        fillContent: true
        title: "Beamline states"
        subtitle: root.s.total > 0 ? root.s.total + (root.s.total === 1 ? " state" : " states") : ""

        // ---- scan interlock --------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: interlockRow.implicitHeight + 12
            radius: 8
            color: root.s.interlockEnabled ? root.soft(root.toneColor(root.s.interlockTone), 0.10) : theme.field
            border.color: root.s.interlockEnabled ? root.soft(root.toneColor(root.s.interlockTone), 0.45) : theme.border
            Behavior on color { ColorAnimation { duration: 160 } }
            RowLayout {
                id: interlockRow
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 6
                spacing: 8
                Icon {
                    name: root.s.interlockEnabled ? "lock" : "no_encryption"
                    filled: true
                    color: root.toneColor(root.s.interlockTone)
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    Text {
                        text: "Scan interlock"
                        color: theme.fg
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: root.s.interlockCount === 0 ? "No states watched"
                            : root.s.interlockCount + (root.s.interlockCount === 1 ? " state watched" : " states watched")
                        color: theme.fgMuted
                        font.pixelSize: 11
                    }
                }
                StatusPill {
                    text: root.s.interlockText || ""
                    tone: root.toneColor(root.s.interlockTone)
                    pulse: root.s.banner !== ""
                }
                SwitchField {
                    checked: root.s.interlockEnabled === true
                    onToggled: root.backend.setInterlockEnabled(checked)
                    Accessible.name: "Arm scan interlock"
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: checked ? "Disarm the scan interlock" : "Arm the scan interlock"
                }
            }
        }

        // ---- tripped banner ----------------------------------------------------------------
        Rectangle {
            visible: root.s.banner !== ""
            Layout.fillWidth: true
            implicitHeight: bannerText.implicitHeight + 14
            radius: 8
            color: root.soft(theme.danger, 0.14)
            border.color: root.soft(theme.danger, 0.5)
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8
                Icon { name: "block"; color: theme.danger; size: 16 }
                Text {
                    id: bannerText
                    Layout.fillWidth: true
                    text: root.s.banner || ""
                    color: theme.fg
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
        }

        // ---- search, filters and add -------------------------------------------------------
        RowLayout {
            visible: root.s.empty !== true
            Layout.fillWidth: true
            spacing: 6
            InputField {
                id: search
                Layout.fillWidth: true
                leftPadding: 30
                placeholderText: "Filter by name or device"
                onTextEdited: root.backend.setFilterText(text)
                Accessible.name: "Filter states"
                Icon {
                    name: "search"
                    size: 16
                    color: theme.fgSubtle
                    anchors.left: parent.left
                    anchors.leftMargin: 9
                    anchors.verticalCenter: parent.verticalCenter
                }
                Connections {
                    target: root.backend
                    function onChanged() {
                        if (!search.activeFocus && search.text !== root.s.filterText)
                            search.text = root.s.filterText || ""
                    }
                }
            }
            IconButton {
                visible: root.s.filtersActive === true
                iconName: "filter_alt_off"
                tip: "Clear filters"
                onClicked: root.backend.clearFilters()
            }
            TextButton {
                text: "Add"
                iconName: "add"
                variant: "primary"
                onClicked: root.backend.addState()
            }
        }

        // ---- status chips (quick filters) -------------------------------------------------
        Flow {
            visible: root.s.empty !== true
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: root.s.chips || []
                delegate: AbstractButton {
                    id: chip
                    required property var modelData
                    readonly property color tone: root.toneColor(modelData.tone)
                    hoverEnabled: true
                    implicitHeight: 24
                    implicitWidth: chipLabel.implicitWidth + 28
                    Accessible.name: "Show only " + modelData.status + " states"
                    background: Rectangle {
                        radius: height / 2
                        color: chip.modelData.active ? root.soft(chip.tone, 0.28)
                             : chip.hovered ? root.soft(chip.tone, 0.16) : "transparent"
                        border.color: chip.modelData.active ? chip.tone : root.soft(chip.tone, 0.45)
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }
                    contentItem: Item {
                        Rectangle {
                            width: 7; height: 7; radius: 3.5
                            color: chip.tone
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            id: chipLabel
                            x: 22
                            anchors.verticalCenter: parent.verticalCenter
                            text: chip.modelData.text
                            color: chip.modelData.active ? theme.fg : theme.fgMuted
                            font.pixelSize: 12
                            font.weight: chip.modelData.active ? Font.DemiBold : Font.Normal
                        }
                    }
                    onClicked: root.backend.toggleStatus(modelData.status)
                    ToolTip.visible: hovered
                    ToolTip.delay: 600
                    ToolTip.text: modelData.active ? "Click to stop filtering by this status"
                                                   : "Click to show only this status"
                }
            }
        }

        // ---- list of states ----------------------------------------------------------------
        ListView {
            id: list
            visible: root.s.empty !== true && root.s.noMatches !== true
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            boundsBehavior: Flickable.StopAtBounds
            model: root.backend.rows
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Item {
                id: row
                required property var model
                readonly property bool isHeader: model.kind === "header"
                readonly property color tone: root.toneColor(model.tone)
                width: ListView.view.width - 2
                height: isHeader ? 26 : stateCard.height

                // section header
                RowLayout {
                    visible: row.isHeader
                    anchors.fill: parent
                    anchors.leftMargin: 4
                    spacing: 6
                    Icon {
                        name: row.model.name === "interlock" ? "lock" : "lock_open_right"
                        filled: row.model.armed === true
                        size: 14
                        color: row.model.armed === true ? theme.fg : theme.fgMuted
                    }
                    Text {
                        text: (row.model.title || "") + "  ·  " + row.model.count
                        color: row.model.armed === true ? theme.fg : theme.fgMuted
                        font.pixelSize: 11
                        font.weight: Font.Bold
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }
                }

                // state card
                Rectangle {
                    id: stateCard
                    visible: !row.isHeader
                    width: parent.width
                    height: column.implicitHeight
                    radius: 8
                    property real flash: 0
                    color: row.model.tripped === true ? root.soft(theme.danger, 0.08 + 0.10 * flash)
                         : row.model.expanded === true ? theme.field
                         : headerArea.containsMouse ? theme.hover : "transparent"
                    border.width: row.model.tripped === true ? 2 : 1
                    border.color: row.model.tripped === true ? root.soft(theme.danger, 0.5 + 0.5 * flash)
                                : row.model.expanded === true ? theme.border : "transparent"
                    Behavior on color { enabled: row.model.tripped !== true; ColorAnimation { duration: 120 } }
                    SequentialAnimation on flash {
                        running: row.model.tripped === true
                        loops: Animation.Infinite
                        NumberAnimation { from: 0; to: 1; duration: 700; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 1; to: 0; duration: 700; easing.type: Easing.InOutSine }
                    }

                    ColumnLayout {
                        id: column
                        width: parent.width
                        spacing: 0

                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 52
                            MouseArea {
                                id: headerArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.backend.toggleExpanded(row.model.name)
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 4
                                spacing: 10
                                Rectangle {
                                    width: 30; height: 30; radius: 15
                                    color: root.soft(row.tone, 0.18)
                                    Icon {
                                        anchors.centerIn: parent
                                        name: row.model.icon || "help"
                                        filled: true
                                        color: row.tone
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        Layout.fillWidth: true
                                        text: row.model.name || ""
                                        color: theme.fg
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: row.model.label || ""
                                        color: theme.fgMuted
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }
                                StatusPill {
                                    text: row.model.statusText || ""
                                    tone: row.tone
                                }
                                IconButton {
                                    iconName: row.model.watched === true ? "lock" : "lock_open_right"
                                    iconColor: row.model.tripped === true ? theme.danger
                                             : row.model.watched === true ? theme.fg : theme.fgSubtle
                                    tip: row.model.watched === true
                                         ? "Watched by the scan interlock (accepts " + row.model.acceptedText + "). Click to stop watching."
                                         : "Not watched by the scan interlock. Click to watch this state."
                                    onClicked: root.backend.toggleInterlockFor(row.model.name)
                                }
                                Icon {
                                    name: row.model.expanded === true ? "expand_less" : "expand_more"
                                    color: theme.fgMuted
                                }
                            }
                        }

                        // details
                        ColumnLayout {
                            visible: row.model.expanded === true
                            Layout.fillWidth: true
                            Layout.leftMargin: 50
                            Layout.rightMargin: 12
                            Layout.bottomMargin: 12
                            spacing: 8
                            GridLayout {
                                columns: 2
                                columnSpacing: 14
                                rowSpacing: 3
                                Text { text: "type"; color: theme.fgSubtle; font.pixelSize: 12 }
                                Text { text: row.model.stateType || ""; color: theme.fg; font.pixelSize: 12 }
                                Repeater {
                                    model: row.model.params || []
                                    delegate: Text {
                                        required property var modelData
                                        required property int index
                                        text: modelData.key
                                        color: theme.fgSubtle
                                        font.pixelSize: 12
                                        Layout.row: index + 1
                                        Layout.column: 0
                                    }
                                }
                                Repeater {
                                    model: row.model.params || []
                                    delegate: Text {
                                        required property var modelData
                                        required property int index
                                        text: modelData.value
                                        color: theme.fg
                                        font.pixelSize: 12
                                        font.family: "monospace"
                                        Layout.row: index + 1
                                        Layout.column: 1
                                    }
                                }
                            }
                            SwitchField {
                                text: "WARNING trips the scan interlock"
                                checked: row.model.tripOnWarning === true
                                onToggled: root.backend.setTripOnWarning(row.model.name, checked)
                            }
                            RowLayout {
                                spacing: 6
                                TextButton {
                                    text: "Edit…"
                                    iconName: "edit"
                                    onClicked: root.backend.editState(row.model.name)
                                }
                                TextButton {
                                    text: "Remove"
                                    iconName: "delete"
                                    variant: "ghost"
                                    onClicked: root.backend.removeState(row.model.name)
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- no matches -------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.noMatches === true
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            Item { Layout.fillHeight: true }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "No states match the filters."
                color: theme.fgMuted
                font.pixelSize: 13
            }
            TextButton {
                Layout.alignment: Qt.AlignHCenter
                text: "Clear filters"
                iconName: "filter_alt_off"
                onClicked: root.backend.clearFilters()
            }
            Item { Layout.fillHeight: true }
        }

        // ---- hidden by filters ----------------------------------------------------------------
        AbstractButton {
            id: hiddenToggle
            visible: root.s.hiddenCount > 0 && root.s.noMatches !== true
            Layout.fillWidth: true
            implicitHeight: 28
            hoverEnabled: true
            background: Rectangle {
                radius: 6
                color: hiddenToggle.hovered ? theme.hover : "transparent"
            }
            contentItem: RowLayout {
                spacing: 6
                Icon {
                    name: root.s.showHidden ? "visibility_off" : "visibility"
                    size: 16
                    color: theme.fgMuted
                    Layout.leftMargin: 6
                }
                Text {
                    Layout.fillWidth: true
                    text: (root.s.hiddenText || "") + (root.s.showHidden ? "  ·  Hide them" : "  ·  Show them")
                    color: theme.fgMuted
                    font.pixelSize: 12
                }
            }
            onClicked: root.backend.setShowHidden(!root.s.showHidden)
        }

        // ---- empty state ----------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.empty === true
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            Item { Layout.fillHeight: true }
            Icon {
                Layout.alignment: Qt.AlignHCenter
                name: "rule"
                size: 36
                color: theme.fgSubtle
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "No beamline states yet"
                color: theme.fg
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "A state watches a device, for example whether a motor is within limits, and can block scans through the scan interlock."
                color: theme.fgMuted
                font.pixelSize: 12
            }
            TextButton {
                Layout.alignment: Qt.AlignHCenter
                text: "Add state"
                iconName: "add"
                variant: "primary"
                onClicked: root.backend.addState()
            }
            Item { Layout.fillHeight: true }
        }
    }
}
