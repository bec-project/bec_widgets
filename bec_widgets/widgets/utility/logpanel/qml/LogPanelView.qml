import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Reworked BEC log panel. Same UX as log_panel_qwidget.py; all state comes from
// LogPanelBackend (backend.stateMap) and the rows from its LogFeedModel (backend.feed).
Rectangle {
    id: root
    required property var backend
    property string monoFamily: "monospace"
    readonly property var st: backend.stateMap
    property int currentRow: -1

    // geometry shared with log_panel_qwidget.py
    readonly property int rowH: 26
    readonly property int lineH: 18
    readonly property int xTime: 12
    readonly property int xBadge: 112
    readonly property int xService: 166
    readonly property int xChevron: 294
    readonly property int xMessage: 312
    readonly property int serviceW: 120
    readonly property color markColor: Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, theme.dark ? 0.45 : 0.55)

    color: theme.bg
    focus: true

    FontMetrics { id: mono; font.family: root.monoFamily; font.pixelSize: 12 }
    FontMetrics { id: monoBold; font.family: root.monoFamily; font.pixelSize: 12; font.bold: true }

    function followTail() {
        if (root.backend.isFollowing()) list.positionViewAtEnd()
    }

    function setCurrent(row) {
        root.currentRow = row
        root.backend.setCurrent(row)
    }

    Connections {
        target: root.backend
        function onScroll_to_end() { Qt.callLater(root.followTail) }
        function onReveal_row(row) {
            root.currentRow = row
            list.positionViewAtIndex(row, ListView.Center)
        }
        function onToast(text) {
            toast.text = text
            toast.opacity = 1
            toastTimer.restart()
        }
        function onFocus_search() {
            search.forceActiveFocus()
            search.selectAll()
        }
    }

    // text with search highlights painted behind the matches (monospace metrics)
    component MarkedText: Item {
        id: marked
        property string text: ""
        property var spans: []
        property color color: theme.fg
        property bool bold: false
        readonly property var metrics: bold ? monoBold : mono
        clip: true
        implicitHeight: label.implicitHeight
        Repeater {
            model: marked.spans
            delegate: Rectangle {
                required property var modelData
                x: marked.metrics.advanceWidth(marked.text.substring(0, modelData[0])) - 1
                width: marked.metrics.advanceWidth(marked.text.substring(modelData[0], modelData[0] + modelData[1])) + 2
                height: 17
                anchors.verticalCenter: parent.verticalCenter
                radius: 3
                color: root.markColor
            }
        }
        Text {
            id: label
            anchors.fill: parent
            text: marked.text
            textFormat: Text.PlainText
            color: marked.color
            font.family: root.monoFamily
            font.pixelSize: 12
            font.bold: marked.bold
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
    }

    // pill-shaped field button that opens a popup, like the QWidget SelectButton
    component SelectPill: AbstractButton {
        id: pill
        property string iconName: ""
        property bool highlighted: false
        implicitHeight: 26
        implicitWidth: pillRow.implicitWidth + 20
        hoverEnabled: true
        background: Rectangle {
            radius: 13
            color: theme.field
            border.color: pill.highlighted ? theme.primary : pill.hovered ? theme.fgSubtle : theme.border
        }
        contentItem: Item {
            RowLayout {
                id: pillRow
                anchors.centerIn: parent
                spacing: 5
                Icon { name: pill.iconName; size: 15; color: pill.highlighted ? theme.primary : theme.fgMuted }
                Text { text: pill.text; color: theme.fg; font.pixelSize: 12 }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- toolbar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: bar.implicitHeight + 16
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }

            ColumnLayout {
                id: bar
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    InputField {
                        id: search
                        Layout.fillWidth: true
                        Layout.maximumWidth: 440
                        Layout.minimumWidth: 160
                        leftPadding: 32
                        placeholderText: "Search logs  (Ctrl+F)"
                        invalid: (root.st.regexError || "") !== ""
                        onTextEdited: root.backend.setSearch(text)
                        Keys.onReturnPressed: (event) => {
                            if (root.st.searchMode === "highlight") {
                                if (event.modifiers & Qt.ShiftModifier) root.backend.prevMatch()
                                else root.backend.nextMatch()
                            }
                        }
                        Keys.onEscapePressed: { text = ""; root.backend.setSearch(""); list.forceActiveFocus() }
                        Icon { x: 9; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 17; color: theme.fgSubtle }
                        ToolTip.visible: invalid && hovered
                        ToolTip.text: root.st.regexError || ""
                    }

                    // Filter | Highlight segmented control
                    Rectangle {
                        implicitWidth: modes.implicitWidth + 4
                        implicitHeight: 30
                        radius: 7
                        color: theme.field
                        border.color: theme.border
                        RowLayout {
                            id: modes
                            anchors.centerIn: parent
                            spacing: 0
                            Repeater {
                                model: [
                                    { key: "filter", label: "Filter", tip: "Show only matching entries" },
                                    { key: "highlight", label: "Highlight", tip: "Show everything and mark the matches" }
                                ]
                                delegate: AbstractButton {
                                    id: mode
                                    required property var modelData
                                    readonly property bool active: root.st.searchMode === modelData.key
                                    implicitHeight: 26
                                    implicitWidth: modeLabel.implicitWidth + 20
                                    hoverEnabled: true
                                    onClicked: root.backend.setSearchMode(modelData.key)
                                    background: Rectangle { radius: 5; color: mode.active ? theme.hover : "transparent" }
                                    contentItem: Text {
                                        id: modeLabel
                                        text: mode.modelData.label
                                        color: mode.active || mode.hovered ? theme.fg : theme.fgMuted
                                        font.pixelSize: 12
                                        font.weight: mode.active ? Font.DemiBold : Font.Normal
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    ToolTip.visible: hovered
                                    ToolTip.delay: 500
                                    ToolTip.text: modelData.tip
                                }
                            }
                        }
                    }

                    IconButton {
                        iconName: "regular_expression"
                        tip: "Regular expression"
                        checked: root.st.regex || false
                        onClicked: root.backend.setRegex(!root.st.regex)
                    }

                    readonly property bool highlighting: root.st.searchMode === "highlight" && (root.st.search || "") !== ""
                    Text {
                        visible: parent.highlighting
                        text: root.st.matchPos > 0 ? root.st.matchPos + " of " + root.st.matchCount : root.st.matchCount + " matches"
                        color: theme.fgSubtle
                        font.pixelSize: 12
                    }
                    IconButton { visible: parent.highlighting; iconName: "keyboard_arrow_up"; tip: "Previous match (Shift+Enter)"; onClicked: root.backend.prevMatch() }
                    IconButton { visible: parent.highlighting; iconName: "keyboard_arrow_down"; tip: "Next match (Enter)"; onClicked: root.backend.nextMatch() }

                    Item { Layout.fillWidth: true }

                    StatusPill {
                        text: root.st.paused ? (root.st.pending > 0 ? "Paused · " + root.st.pending.toLocaleString(Qt.locale("en_US"), "f", 0) + " new" : "Paused") : "Live"
                        tone: root.st.paused ? theme.warning : theme.success
                        pulse: !root.st.paused
                        MouseArea {
                            id: liveMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.backend.togglePause()
                        }
                        ToolTip.visible: liveMouse.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: root.st.paused ? "Updates are paused. Click to resume." : "Receiving logs. Click to pause."
                    }
                    IconButton {
                        iconName: root.st.timeMode === "relative" ? "history" : "schedule"
                        tip: root.st.timeMode === "relative" ? "Show clock times" : "Show relative times"
                        onClicked: root.backend.toggleTimeMode()
                    }
                    IconButton { iconName: "content_copy"; tip: "Copy visible entries"; onClicked: root.backend.copyVisible() }
                    IconButton { iconName: "download"; tip: "Export visible entries to a file"; onClicked: root.backend.exportVisible() }
                    IconButton { iconName: "delete_sweep"; tip: "Clear the panel"; onClicked: root.backend.clear() }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: root.st.groups || []
                        delegate: AbstractButton {
                            id: chip
                            required property var modelData
                            implicitHeight: 26
                            implicitWidth: chipMetrics.advanceWidth(modelData.label + "  " + modelData.count.toLocaleString(Qt.locale("en_US"), "f", 0)) + 34
                            hoverEnabled: true
                            onClicked: root.backend.toggleGroup(modelData.key)
                            onDoubleClicked: root.backend.soloGroup(modelData.key)
                            FontMetrics { id: chipMetrics; font.pixelSize: 12; font.weight: Font.DemiBold }
                            background: Rectangle {
                                radius: 13
                                color: chip.modelData.active ? Qt.rgba(chip.modelData.color.r, chip.modelData.color.g, chip.modelData.color.b, 0.16)
                                     : chip.hovered ? theme.hover : "transparent"
                                border.color: chip.modelData.active ? chip.modelData.color : theme.border
                            }
                            contentItem: Item {
                                Rectangle {
                                    x: 10; width: 8; height: 8; radius: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: chip.modelData.active ? chip.modelData.color : theme.fgSubtle
                                }
                                Text {
                                    x: 24
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: chip.modelData.label
                                    color: chip.modelData.active ? theme.fg : theme.fgSubtle
                                    font.pixelSize: 12
                                    font.weight: chip.modelData.active ? Font.DemiBold : Font.Normal
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: chip.modelData.count.toLocaleString(Qt.locale("en_US"), "f", 0)
                                    color: chip.modelData.active ? theme.fgMuted : theme.fgSubtle
                                    font.pixelSize: 12
                                    font.weight: chip.modelData.active ? Font.DemiBold : Font.Normal
                                }
                            }
                            ToolTip.visible: hovered
                            ToolTip.delay: 500
                            ToolTip.text: "Show or hide " + modelData.label.toLowerCase() + " (double-click to show only " + modelData.label.toLowerCase() + ")"
                        }
                    }
                    Item { implicitWidth: 6 }

                    SelectPill {
                        id: serviceButton
                        iconName: "dns"
                        text: root.st.servicesLabel || "All services"
                        highlighted: root.st.servicesFiltered || false
                        onClicked: servicePopup.opened ? servicePopup.close() : servicePopup.open()
                        Popup {
                            id: servicePopup
                            y: parent.height + 4
                            width: 260
                            padding: 4
                            implicitHeight: Math.min(serviceColumn.implicitHeight + 8, 360)
                            background: Rectangle { color: theme.card; border.color: theme.border; radius: 8 }
                            contentItem: Flickable {
                                clip: true
                                contentHeight: serviceColumn.implicitHeight
                                implicitHeight: serviceColumn.implicitHeight
                                Column {
                                    id: serviceColumn
                                    width: parent.width
                                    ItemDelegate {
                                        width: parent.width
                                        height: 30
                                        onClicked: root.backend.allServices()
                                        contentItem: Text { text: "Show all services"; color: theme.primary; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                                        background: Rectangle { color: parent.hovered ? theme.hover : "transparent"; radius: 5 }
                                    }
                                    Rectangle { width: parent.width; height: 1; color: theme.border }
                                    Text {
                                        visible: (root.st.services || []).length === 0
                                        text: "No services yet"
                                        color: theme.fgSubtle
                                        font.pixelSize: 12
                                        padding: 8
                                    }
                                    Repeater {
                                        model: root.st.services || []
                                        delegate: ItemDelegate {
                                            id: svc
                                            required property var modelData
                                            width: serviceColumn.width
                                            height: 30
                                            onClicked: root.backend.toggleService(modelData.name)
                                            background: Rectangle { color: svc.hovered ? theme.hover : "transparent"; radius: 5 }
                                            contentItem: RowLayout {
                                                spacing: 8
                                                Rectangle {
                                                    width: 16; height: 16; radius: 4
                                                    color: svc.modelData.active ? theme.primary : "transparent"
                                                    border.color: svc.modelData.active ? theme.primary : theme.fgSubtle
                                                    Icon { anchors.centerIn: parent; visible: svc.modelData.active; name: "check"; size: 13; color: theme.onPrimary }
                                                }
                                                Rectangle { width: 8; height: 8; radius: 4; color: svc.modelData.color }
                                                Text { Layout.fillWidth: true; text: svc.modelData.name; color: theme.fg; font.pixelSize: 12; elide: Text.ElideRight }
                                                Text { text: svc.modelData.count.toLocaleString(Qt.locale("en_US"), "f", 0); color: theme.fgSubtle; font.pixelSize: 12 }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    SelectPill {
                        iconName: "schedule"
                        text: root.st.sinceLabel || "All time"
                        highlighted: (root.st.since || "all") !== "all"
                        onClicked: sincePopup.opened ? sincePopup.close() : sincePopup.open()
                        Popup {
                            id: sincePopup
                            y: parent.height + 4
                            width: 160
                            padding: 4
                            background: Rectangle { color: theme.card; border.color: theme.border; radius: 8 }
                            contentItem: Column {
                                Repeater {
                                    model: root.st.sinceOptions || []
                                    delegate: ItemDelegate {
                                        id: opt
                                        required property var modelData
                                        width: 152
                                        height: 30
                                        onClicked: { root.backend.setSince(modelData.key); sincePopup.close() }
                                        background: Rectangle {
                                            color: opt.hovered ? theme.hover : "transparent"; radius: 5
                                            Rectangle {
                                                width: 3; height: parent.height - 10; radius: 1.5
                                                anchors.verticalCenter: parent.verticalCenter
                                                color: theme.primary
                                                visible: root.st.since === opt.modelData.key
                                            }
                                        }
                                        contentItem: Text { text: opt.modelData.label; color: theme.fg; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }
                    Text { text: root.st.summary || ""; color: theme.fgSubtle; font.pixelSize: 12 }
                    Text {
                        visible: root.st.filtered || false
                        text: "Reset filters"
                        color: theme.primary
                        font.pixelSize: 12
                        leftPadding: 4
                        rightPadding: 4
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { search.text = ""; root.backend.resetFilters() }
                        }
                    }
                }
            }
        }

        // ---------------------------------------------------------------- rows
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.backend.feed
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            cacheBuffer: 400
            focus: true
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                onPressedChanged: if (!pressed) root.backend.setFollow(list.atYEnd)
            }
            onMovementEnded: root.backend.setFollow(atYEnd)
            onAtYEndChanged: if (atYEnd && !root.st.follow) root.backend.setFollow(true)

            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                    const next = Math.max(0, Math.min(count - 1, root.currentRow + (event.key === Qt.Key_Down ? 1 : -1)))
                    root.setCurrent(next)
                    positionViewAtIndex(next, ListView.Contain)
                    root.backend.setFollow(next === count - 1)
                    event.accepted = true
                } else if ((event.key === Qt.Key_Space || event.key === Qt.Key_Right || event.key === Qt.Key_Left) && root.currentRow >= 0) {
                    root.backend.toggleExpanded(root.currentRow)
                    event.accepted = true
                }
            }

            delegate: Item {
                id: row
                required property int index
                required property string level
                required property string group
                required property string badge
                required property color levelColor
                required property color levelInk
                required property color rowTint
                required property string time
                required property string timeFull
                required property string service
                required property color serviceColor
                required property string summary
                required property var summarySpans
                required property int lineCount
                required property bool expanded
                required property var bodyLines
                required property int count
                required property bool current
                readonly property bool debug: level === "DEBUG" || level === "TRACE"

                width: ListView.view.width
                height: expanded ? root.rowH + bodyLines.length * root.lineH + 20 : root.rowH

                HoverHandler { id: hover }

                Rectangle { anchors.fill: parent; color: row.rowTint }
                Rectangle {
                    anchors.fill: parent
                    color: row.current ? Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.12)
                         : hover.hovered ? theme.hover : "transparent"
                }
                Rectangle { x: 0; y: 3; width: 3; height: parent.height - 6; color: row.levelColor }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (mouse) => {
                        root.setCurrent(row.index)
                        list.forceActiveFocus()
                        if (mouse.button === Qt.RightButton) {
                            rowMenu.row = row.index
                            rowMenu.service = row.service
                            rowMenu.group = row.group
                            rowMenu.multiLine = row.lineCount > 1
                            rowMenu.expanded = row.expanded
                            rowMenu.popup()
                        }
                    }
                    onDoubleClicked: root.backend.toggleExpanded(row.index)
                }

                Item {
                    id: header
                    width: parent.width
                    height: root.rowH

                    Text {
                        x: root.xTime
                        width: root.xBadge - root.xTime - 6
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        text: row.time
                        color: theme.fgSubtle
                        font.family: root.monoFamily
                        font.pixelSize: 12
                        ToolTip.visible: timeHover.hovered
                        ToolTip.delay: 400
                        ToolTip.text: row.timeFull
                        HoverHandler { id: timeHover }
                    }
                    Rectangle {
                        x: root.xBadge; y: 4
                        width: 46; height: root.rowH - 8
                        radius: 4
                        color: Qt.rgba(row.levelColor.r, row.levelColor.g, row.levelColor.b, 0.18)
                        Text {
                            anchors.centerIn: parent
                            text: row.badge
                            color: row.levelInk
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                    Rectangle {
                        x: root.xService + 0.5; width: 7; height: 7; radius: 3.5
                        anchors.verticalCenter: parent.verticalCenter
                        color: row.serviceColor
                    }
                    Text {
                        x: root.xService + 13
                        width: root.serviceW - 13
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        text: row.service
                        color: theme.fgMuted
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    Icon {
                        visible: row.lineCount > 1
                        x: root.xChevron; y: 5
                        name: row.expanded ? "expand_more" : "chevron_right"
                        size: 16
                        color: theme.fgMuted
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -4
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.backend.toggleExpanded(row.index)
                        }
                    }
                    MarkedText {
                        x: root.xMessage
                        width: Math.max(0, extras.x - root.xMessage - 6)
                        height: parent.height
                        text: row.summary
                        spans: row.summarySpans
                        color: row.debug ? theme.fgMuted : theme.fg
                    }
                    Row {
                        id: extras
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        height: parent.height
                        spacing: 6
                        Rectangle {
                            visible: row.lineCount > 1 && !row.expanded
                            anchors.verticalCenter: parent.verticalCenter
                            height: root.rowH - 10
                            width: linesLabel.implicitWidth + 12
                            radius: height / 2
                            color: theme.track
                            Text { id: linesLabel; anchors.centerIn: parent; text: "+" + (row.lineCount - 1) + " lines"; color: theme.fgMuted; font.pixelSize: 11; font.weight: Font.DemiBold }
                        }
                        Rectangle {
                            visible: row.count > 1
                            anchors.verticalCenter: parent.verticalCenter
                            height: root.rowH - 10
                            width: countLabel.implicitWidth + 12
                            radius: height / 2
                            color: Qt.rgba(row.levelColor.r, row.levelColor.g, row.levelColor.b, 0.18)
                            Text { id: countLabel; anchors.centerIn: parent; text: "×" + row.count; color: row.levelInk; font.pixelSize: 11; font.weight: Font.DemiBold }
                        }
                        IconButton {
                            visible: hover.hovered
                            anchors.verticalCenter: parent.verticalCenter
                            implicitWidth: 24; implicitHeight: 22
                            iconSize: 16
                            iconName: "content_copy"
                            tip: "Copy entry"
                            onClicked: root.backend.copyRow(row.index)
                        }
                    }
                }

                // expanded body: full message, tracebacks styled per line
                Rectangle {
                    visible: row.expanded
                    x: root.xChevron
                    y: root.rowH
                    width: parent.width - root.xChevron - 12
                    height: parent.height - root.rowH - 6
                    radius: 6
                    color: theme.field
                    border.color: theme.border
                    Column {
                        x: 10; y: 7
                        width: parent.width - 20
                        Repeater {
                            model: row.expanded ? row.bodyLines : []
                            delegate: MarkedText {
                                required property var modelData
                                width: parent.width
                                height: root.lineH
                                text: modelData.text
                                spans: modelData.spans
                                bold: modelData.kind === "exception"
                                color: modelData.kind === "exception" ? root.st.exceptionInk
                                     : (modelData.kind === "file" || modelData.kind === "head") ? theme.fgSubtle : theme.fg
                            }
                        }
                    }
                }
            }

            // empty states
            Column {
                anchors.centerIn: parent
                visible: list.count === 0
                spacing: 6
                Icon { anchors.horizontalCenter: parent.horizontalCenter; name: root.st.empty ? "hourglass_empty" : "filter_alt_off"; size: 40; color: theme.fgSubtle }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.st.empty ? "Waiting for logs" : "No entries match"; color: theme.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.st.empty ? "New BEC log messages appear here." : (root.st.total || 0).toLocaleString(Qt.locale("en_US"), "f", 0) + " entries are hidden by the filters."
                    color: theme.fgSubtle
                    font.pixelSize: 12
                }
                TextButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !root.st.empty
                    text: "Reset filters"
                    onClicked: { search.text = ""; root.backend.resetFilters() }
                }
            }

            // jump to latest
            AbstractButton {
                id: jump
                visible: !root.st.follow && list.count > 0
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 12
                implicitHeight: 30
                implicitWidth: jumpRow.implicitWidth + 28
                hoverEnabled: true
                onClicked: root.backend.jumpToLatest()
                background: Rectangle { radius: 15; color: jump.hovered ? Qt.lighter(theme.primary, 1.1) : theme.primary }
                contentItem: Item {
                    RowLayout {
                        id: jumpRow
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { name: "arrow_downward"; size: 16; color: theme.onPrimary }
                        Text {
                            text: root.st.newBelow > 0 ? root.st.newBelow.toLocaleString(Qt.locale("en_US"), "f", 0) + " new" : "Jump to latest"
                            color: theme.onPrimary
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }

            // short feedback such as "Copied 1 entry"
            Rectangle {
                id: toastBox
                x: 12
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 12
                visible: toast.opacity > 0
                opacity: toast.opacity
                width: toast.implicitWidth + 24
                height: 30
                radius: 8
                color: theme.card
                border.color: theme.border
                Text {
                    id: toast
                    anchors.centerIn: parent
                    opacity: 0
                    color: theme.fg
                    font.pixelSize: 12
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                }
                Timer { id: toastTimer; interval: 1600; onTriggered: toast.opacity = 0 }
            }
        }
    }

    Menu {
        id: rowMenu
        property int row: -1
        property string service: ""
        property string group: ""
        property bool multiLine: false
        property bool expanded: false
        MenuItem { text: "Copy entry"; onTriggered: root.backend.copyRow(rowMenu.row) }
        MenuItem { text: "Copy message only"; onTriggered: root.backend.copyMessage(rowMenu.row) }
        MenuItem {
            visible: rowMenu.multiLine
            height: visible ? implicitHeight : 0
            text: rowMenu.expanded ? "Collapse" : "Expand"
            onTriggered: root.backend.toggleExpanded(rowMenu.row)
        }
        MenuSeparator {}
        MenuItem { text: "Only " + rowMenu.service; onTriggered: root.backend.soloService(rowMenu.service) }
        MenuItem { text: "Hide " + rowMenu.service; onTriggered: root.backend.hideService(rowMenu.service) }
        MenuItem { text: "Only " + rowMenu.group + " level"; onTriggered: root.backend.soloGroup(rowMenu.group) }
        MenuSeparator {}
        MenuItem { text: "Copy visible entries"; onTriggered: root.backend.copyVisible() }
        MenuItem { text: "Jump to latest"; onTriggered: root.backend.jumpToLatest() }
    }
}
