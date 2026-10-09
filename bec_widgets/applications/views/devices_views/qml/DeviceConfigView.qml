import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi
import "Tones.js" as Tones

// Config for staff: edit a copy of the session config, see what differs, review, then apply.
// backend: ConfigBackend.
Rectangle {
    id: root
    required property QtObject backend
    readonly property var bar: backend.bar
    readonly property var d: backend.detail
    readonly property string mono: "JetBrains Mono, Menlo, DejaVu Sans Mono"

    readonly property bool reviewOpen: reviewSheet.opened
    function openReview() { addSheet.close(); clearSheet.close(); reviewSheet.applyMode = false; reviewSheet.open() }
    function openAdd() { addSheet.open() }
    function openClear() { clearSheet.open() }
    function closeSheets() { reviewSheet.close(); addSheet.close(); clearSheet.close() }

    color: theme.bg
    focus: true
    Keys.onPressed: (event) => {
        if (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_Z) { backend.undo(); event.accepted = true }
        else if (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_S) { backend.saveFile(); event.accepted = true }
    }

    component Upper: Text {
        color: theme.fgSubtle
        font.pixelSize: 11
        font.weight: Font.Bold
        font.letterSpacing: 0.5
        font.capitalization: Font.AllUppercase
    }
    component VRule: Rectangle { implicitWidth: 1; implicitHeight: 18; color: theme.border }
    component Was: Text {
        visible: text !== ""
        color: theme.warning
        font.pixelSize: 11
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    component FieldLabel: Text { color: theme.fg; font.pixelSize: 12; font.weight: Font.DemiBold }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- session bar ---------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: barCol.implicitHeight + 16
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            ColumnLayout {
                id: barCol
                anchors.fill: parent
                anchors.margins: 8
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8
                RowLayout {
                    spacing: 8
                    Rectangle { implicitWidth: 9; implicitHeight: 9; radius: 4.5; color: theme.success }
                    Text { text: "Running session"; color: theme.fg; font.pixelSize: 13; font.weight: Font.Bold }
                    Text { text: root.bar.sessionCount + " devices · connected"; color: theme.fgMuted; font.pixelSize: 12 }
                    Item { implicitWidth: 10 }
                    VRule {}
                    Item { implicitWidth: 10 }
                    Icon { name: "description"; size: 16; color: theme.fgMuted }
                    Text { text: "Editing a copy from"; color: theme.fgMuted; font.pixelSize: 12 }
                    Text { text: root.bar.source; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.Bold }
                    Chip {
                        text: root.bar.changeText
                        tone: root.bar.changeCount > 0 ? "warn" : "ok"
                        iconName: root.bar.changeCount > 0 ? "" : "check"
                    }
                    Item { Layout.fillWidth: true }
                    TextButton {
                        text: root.bar.reviewText
                        variant: "primary"
                        iconName: "difference"
                        enabled: root.bar.changeCount > 0
                        tip: root.bar.scanRunning ? "You can review now; applying waits until the scan finishes"
                                                  : "See exactly what will change in the running session, then apply"
                        onClicked: root.openReview()
                    }
                }
                Banner {
                    visible: root.bar.scanRunning
                    Layout.fillWidth: true
                    tone: "warn"
                    iconName: "lock"
                    title: root.bar.scanText
                    text: "You can keep editing and reviewing. Applying to the session is locked until the scan ends."
                }
            }
        }

        // ---- toolbar -------------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 38
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 2
                GhostButton {
                    id: openBtn
                    text: "Open…"
                    iconName: "folder_open"
                    onClicked: openMenu.popup(openBtn, 0, openBtn.height + 2)
                    Menu {
                        id: openMenu
                        MenuItem { text: "Open YAML file…"; onTriggered: root.backend.openFile() }
                        MenuSeparator {}
                        MenuItem { text: "Start from the running session"; onTriggered: root.backend.loadSession() }
                    }
                }
                GhostButton { text: "Save"; iconName: "save"; tip: "Save the edited copy as YAML (Ctrl+S)"; onClicked: root.backend.saveFile() }
                Item { implicitWidth: 6 }
                VRule {}
                Item { implicitWidth: 6 }
                GhostButton { text: "Add device"; iconName: "add"; onClicked: root.openAdd() }
                GhostButton { text: "Remove"; iconName: "delete"; enabled: root.bar.hasSelection; onClicked: root.backend.remove() }
                GhostButton { text: "Test connection"; iconName: "power"; enabled: root.bar.hasSelection; tip: "Tests the selected device; to test everything use ⋯"; onClicked: root.backend.test() }
                Item { implicitWidth: 6 }
                VRule {}
                Item { implicitWidth: 6 }
                GhostButton { iconName: "undo"; tip: "Undo (Ctrl+Z)"; enabled: root.bar.canUndo; onClicked: root.backend.undo() }
                Item { Layout.fillWidth: true }
                GhostButton {
                    id: moreBtn
                    iconName: "more_horiz"
                    tip: "More"
                    onClicked: moreMenu.popup(moreBtn, moreBtn.width - moreMenu.width, moreBtn.height + 2)
                    Menu {
                        id: moreMenu
                        MenuItem { text: "Test all " + root.backend.workCount + " devices"; onTriggered: root.backend.testAll() }
                        MenuItem { text: "Reload from running session"; onTriggered: root.backend.loadSession() }
                        MenuSeparator {}
                        MenuItem { text: "Danger zone"; enabled: false }
                        MenuItem {
                            text: "Clear the running session…"
                            onTriggered: root.openClear()
                            contentItem: Text { text: parent.text; color: theme.danger; font.pixelSize: 13; leftPadding: 4 }
                        }
                    }
                }
            }
        }

        // ---- body ----------------------------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // filters
            ScrollView {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                background: Rectangle { color: theme.bg }
                ColumnLayout {
                    width: 200
                    x: 10
                    spacing: 4
                    Item { implicitHeight: 6 }
                    Upper { text: "Search" }
                    InputField {
                        id: search
                        Layout.fillWidth: true
                        placeholderText: "Name, class, tag or PV prefix"
                        Accessible.name: "Search devices"
                        onTextChanged: searchDebounce.restart()
                        Timer { id: searchDebounce; interval: 120; onTriggered: root.backend.setQuery(search.text) }
                        Connections {
                            target: root.backend
                            function onChanged() { if (!root.backend.filtersActive && search.text !== "") search.text = "" }
                        }
                    }
                    Repeater {
                        model: root.backend.facets
                        delegate: ColumnLayout {
                            id: section
                            required property var modelData
                            visible: modelData.items.length > 0
                            spacing: 3
                            Layout.fillWidth: true
                            Upper { text: section.modelData.title; Layout.topMargin: 10; Layout.bottomMargin: 2 }
                            Repeater {
                                model: section.modelData.items
                                delegate: RowLayout {
                                    id: facet
                                    required property var modelData
                                    Layout.fillWidth: true
                                    TickBox {
                                        text: facet.modelData.label
                                        checked: facet.modelData.checked
                                        Layout.fillWidth: true
                                        onToggled: root.backend.toggleFacet(section.modelData.key, facet.modelData.value, checked)
                                    }
                                    Text { text: facet.modelData.count; color: theme.fgSubtle; font.family: root.mono; font.pixelSize: 11 }
                                }
                            }
                        }
                    }
                    Item { implicitHeight: 10 }
                }
            }
            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: theme.border }

            // table + problems
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: theme.card
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0
                        RowLayout {
                            Layout.margins: 10
                            Layout.topMargin: 6
                            Layout.bottomMargin: 6
                            Text { text: root.backend.showingText; color: theme.fgMuted; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Text {
                                visible: root.backend.filtersActive
                                text: "Clear filters"
                                color: theme.primary
                                font.pixelSize: 12
                                TapHandler { onTapped: root.backend.clearFilters() }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 26
                            color: theme.card
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                spacing: 0
                                Repeater {
                                    model: [["Δ", 30], ["Status", 150], ["Name", 130], ["Class", 130], ["Readout", 150], ["On", 40], ["Tags", -1]]
                                    delegate: Text {
                                        required property var modelData
                                        text: modelData[0]
                                        color: theme.fgMuted
                                        font.pixelSize: 11
                                        font.weight: Font.Bold
                                        Layout.preferredWidth: modelData[1] > 0 ? modelData[1] : -1
                                        Layout.fillWidth: modelData[1] < 0
                                    }
                                }
                            }
                        }
                        ListView {
                            id: table
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: root.backend.rows
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar {}
                            activeFocusOnTab: true
                            Connections {
                                target: root.backend
                                function onChanged() { if (root.backend.selectedIndex >= 0) table.positionViewAtIndex(root.backend.selectedIndex, ListView.Contain) }
                            }
                            Component.onCompleted: if (root.backend.selectedIndex >= 0) positionViewAtIndex(root.backend.selectedIndex, ListView.Contain)
                            Keys.onUpPressed: root.backend.selectRelative(-1)
                            Keys.onDownPressed: root.backend.selectRelative(1)
                            Keys.onDeletePressed: root.backend.remove()
                            Keys.onSpacePressed: if (root.d.name) root.backend.setField(root.d.name, "enabled", !root.d.enabled)
                            delegate: Rectangle {
                                id: row
                                required property int index
                                required property string name
                                required property string deviceClass
                                required property string readout
                                required property string readoutWas
                                required property bool on
                                required property string tags
                                required property string change
                                required property string changeLabel
                                required property string statusText
                                required property string statusTone
                                required property string statusIcon
                                required property bool selected
                                width: ListView.view.width
                                height: 32
                                color: selected ? Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.18)
                                     : rowHover.hovered ? theme.hover : "transparent"
                                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border; opacity: 0.6 }
                                HoverHandler { id: rowHover }
                                TapHandler { onTapped: { table.forceActiveFocus(); root.backend.select(row.name) } }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    spacing: 0
                                    Text {
                                        text: row.change
                                        color: Tones.color(theme, row.change === "A" ? "ok" : row.change === "D" ? "err" : "warn")
                                        font.family: root.mono
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        Layout.preferredWidth: 30
                                        ToolTip.visible: row.changeLabel !== "" && changeHover.hovered
                                        ToolTip.text: row.changeLabel
                                        HoverHandler { id: changeHover }
                                    }
                                    Item {
                                        Layout.preferredWidth: 150
                                        implicitHeight: 20
                                        Chip { text: row.statusText; tone: row.statusTone; iconName: row.statusIcon; anchors.verticalCenter: parent.verticalCenter }
                                    }
                                    Text { text: row.name; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.preferredWidth: 130 }
                                    Text { text: row.deviceClass; color: theme.fg; font.pixelSize: 12; elide: Text.ElideRight; Layout.preferredWidth: 130; rightPadding: 6 }
                                    Text {
                                        textFormat: Text.StyledText
                                        text: row.readout + (row.readoutWas !== "" ? " <font color='" + theme.fgSubtle + "' size='2'>" + row.readoutWas + "</font>" : "")
                                        color: theme.fg
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                        Layout.preferredWidth: 150
                                    }
                                    Item {
                                        Layout.preferredWidth: 40
                                        implicitHeight: 20
                                        TickBox {
                                            anchors.verticalCenter: parent.verticalCenter
                                            checked: row.on
                                            Accessible.name: "Enable " + row.name
                                            onToggled: root.backend.setField(row.name, "enabled", checked)
                                        }
                                    }
                                    Text { text: row.tags; color: theme.fg; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true; rightPadding: 8 }
                                }
                            }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                // problems
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: probCol.implicitHeight + 14
                    color: theme.bg
                    ColumnLayout {
                        id: probCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        anchors.topMargin: 6
                        spacing: 2
                        RowLayout {
                            spacing: 6
                            Text { text: "Problems"; color: theme.fg; font.pixelSize: 12; font.weight: Font.Bold }
                            Chip { text: String(root.backend.problemCount); tone: root.backend.problemCount > 0 ? "err" : "neutral" }
                            Text { text: "· " + root.backend.uncheckedCount + " not checked"; color: theme.fgMuted; font.pixelSize: 12 }
                        }
                        Repeater {
                            model: root.backend.problems.slice(0, 4)
                            delegate: Rectangle {
                                id: prob
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: 24
                                radius: 4
                                color: probHover.hovered ? theme.hover : "transparent"
                                HoverHandler { id: probHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: root.backend.select(prob.modelData.name) }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 4
                                    anchors.rightMargin: 4
                                    spacing: 8
                                    Icon {
                                        name: prob.modelData.state === "unchecked" ? "help" : "warning"
                                        size: 14
                                        color: prob.modelData.state === "unchecked" ? theme.fgSubtle : theme.danger
                                    }
                                    Text { text: prob.modelData.name; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.Bold }
                                    Text { text: prob.modelData.message; color: theme.fgMuted; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: "Select"; color: theme.primary; font.pixelSize: 12 }
                                }
                            }
                        }
                        Text {
                            visible: root.backend.problems.length > 4
                            text: "and " + (root.backend.problems.length - 4) + " more"
                            color: theme.fgSubtle
                            font.pixelSize: 11
                        }
                    }
                }
            }
            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: theme.border }

            // inspector
            Rectangle {
                Layout.preferredWidth: 340
                Layout.fillHeight: true
                color: theme.bg
                Text {
                    visible: !root.d.name
                    anchors.fill: parent
                    anchors.margins: 20
                    text: "Select a device to see and edit its configuration."
                    color: theme.fgMuted
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
                ColumnLayout {
                    visible: !!root.d.name
                    anchors.fill: parent
                    spacing: 0
                    ColumnLayout {
                        Layout.margins: 12
                        Layout.topMargin: 10
                        Layout.bottomMargin: 8
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: root.d.name || ""; color: theme.fg; font.family: root.mono; font.pixelSize: 14; font.weight: Font.Bold }
                            Text { text: root.d.shortClass || ""; color: theme.fgMuted; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            TextButton { visible: !!root.d.isModified; text: "Revert"; iconName: "undo"; implicitHeight: 26; onClicked: root.backend.revert() }
                        }
                        RowLayout {
                            spacing: 6
                            Chip { text: root.d.statusText || ""; tone: root.d.statusTone || "neutral"; iconName: root.d.statusIcon || "" }
                            Chip { visible: !!root.d.isNew; text: "New — not in session"; tone: "ok"; iconName: "add" }
                        }
                        Text {
                            visible: !!root.d.statusMessage
                            text: root.d.statusMessage || ""
                            color: theme.danger
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                    Segmented {
                        Layout.leftMargin: 12
                        model: [{ key: "form", label: "Form" }, { key: "yaml", label: "YAML" }, { key: "docs", label: "Docs" }]
                        current: root.backend.tab
                        onPicked: (key) => root.backend.setTab(key)
                    }
                    Rectangle { Layout.fillWidth: true; Layout.topMargin: 6; implicitHeight: 1; color: theme.border }

                    StackLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: root.backend.tab === "yaml" ? 1 : root.backend.tab === "docs" ? 2 : 0

                        // ---- form
                        ScrollView {
                            id: formScroll
                            contentWidth: availableWidth
                            clip: true
                            ColumnLayout {
                                width: formScroll.availableWidth - 24
                                x: 12
                                spacing: 6
                                Item { implicitHeight: 6 }
                                FieldLabel { text: "Readout priority" }
                                SelectField {
                                    Layout.fillWidth: true
                                    model: root.backend.readoutLabels
                                    currentIndex: root.backend.readoutKeys.indexOf(root.d.readout || "")
                                    onActivated: (i) => root.backend.setField(root.d.name, "readoutPriority", root.backend.readoutKeys[i])
                                }
                                Text { text: root.backend.readoutHint; color: theme.fgSubtle; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Was { text: root.d.readoutWas ? "↳ " + root.d.readoutWas : "" }
                                Item { implicitHeight: 4 }
                                RowLayout {
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        spacing: 0
                                        Layout.fillWidth: true
                                        FieldLabel { text: "Enabled" }
                                        Text { text: "Disabled devices stay in the file but are not loaded"; color: theme.fgSubtle; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    }
                                    SwitchField {
                                        checked: !!root.d.enabled
                                        onToggled: root.backend.setField(root.d.name, "enabled", checked)
                                    }
                                }
                                Was { text: root.d.enabledWas ? "↳ " + root.d.enabledWas : "" }
                                Item { implicitHeight: 4 }
                                FieldLabel { text: "If reading fails" }
                                SelectField {
                                    Layout.fillWidth: true
                                    model: root.backend.failureLabels
                                    currentIndex: Math.max(0, root.backend.failureKeys.indexOf(root.d.onFailure || "retry"))
                                    onActivated: (i) => root.backend.setField(root.d.name, "onFailure", root.backend.failureKeys[i])
                                }
                                Was { text: root.d.onFailureWas ? "↳ " + root.d.onFailureWas : "" }
                                Item { implicitHeight: 4 }
                                FieldLabel { text: "Description" }
                                InputField {
                                    id: desc
                                    Layout.fillWidth: true
                                    text: root.d.description || ""
                                    placeholderText: "What this device is, for colleagues"
                                    onEditingFinished: root.backend.setField(root.d.name, "description", text)
                                }
                                Was { text: root.d.descriptionWas ? "↳ " + root.d.descriptionWas : "" }
                                Upper { text: "Tags"; Layout.topMargin: 6 }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Repeater {
                                        model: root.d.tags || []
                                        delegate: GhostButton {
                                            required property string modelData
                                            text: modelData + "  ✕"
                                            tip: "Remove the tag " + modelData
                                            onClicked: root.backend.removeTag(root.d.name, modelData)
                                        }
                                    }
                                    InputField {
                                        width: 90
                                        placeholderText: "Add tag"
                                        onAccepted: { root.backend.addTag(root.d.name, text); text = "" }
                                    }
                                }
                                Was { text: root.d.tagsWas ? "↳ " + root.d.tagsWas : "" }
                                Upper { text: "Device config"; Layout.topMargin: 6 }
                                Text { visible: (root.d.deviceConfig || []).length === 0; text: "No deviceConfig keys"; color: theme.fgSubtle; font.pixelSize: 11 }
                                Repeater {
                                    model: root.d.deviceConfig || []
                                    delegate: ColumnLayout {
                                        id: cfgRow
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 2
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text { text: cfgRow.modelData.key; color: theme.fgMuted; font.family: root.mono; font.pixelSize: 12; Layout.preferredWidth: 110; elide: Text.ElideRight }
                                            InputField {
                                                Layout.fillWidth: true
                                                implicitHeight: 28
                                                font.family: root.mono
                                                font.pixelSize: 12
                                                text: cfgRow.modelData.value
                                                onEditingFinished: root.backend.setConfigValue(root.d.name, cfgRow.modelData.key, text)
                                            }
                                        }
                                        Was { text: cfgRow.modelData.was ? "↳ " + cfgRow.modelData.was : ""; leftPadding: 114 }
                                    }
                                }
                                Upper { visible: (root.d.extra || []).length > 0; text: "Other keys · kept as they are"; Layout.topMargin: 6 }
                                Repeater {
                                    model: root.d.extra || []
                                    delegate: Text {
                                        required property var modelData
                                        text: modelData.key + ": " + modelData.value
                                        color: theme.fg
                                        font.family: root.mono
                                        font.pixelSize: 12
                                        wrapMode: Text.WrapAnywhere
                                        Layout.fillWidth: true
                                    }
                                }
                                RowLayout {
                                    Layout.topMargin: 6
                                    Layout.fillWidth: true
                                    TextButton { text: "Test connection"; iconName: "power"; onClicked: root.backend.test() }
                                    Text { text: "Result appears here, no dialog"; color: theme.fgSubtle; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }
                                Item { implicitHeight: 12 }
                            }
                        }
                        // ---- yaml
                        ColumnLayout {
                            spacing: 6
                            ScrollView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.margins: 12
                                Layout.bottomMargin: 0
                                background: Rectangle { color: theme.field; radius: 6; border.color: theme.border }
                                TextArea {
                                    readOnly: true
                                    text: root.d.yaml || ""
                                    color: theme.fg
                                    font.family: root.mono
                                    font.pixelSize: 12
                                    selectByMouse: true
                                    background: null
                                }
                            }
                            Text {
                                text: "Saved as plain YAML; only keys that differ from defaults are listed."
                                color: theme.fgSubtle
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                Layout.margins: 12
                                Layout.topMargin: 0
                            }
                        }
                        // ---- docs
                        ScrollView {
                            id: docsScroll
                            contentWidth: availableWidth
                            clip: true
                            ColumnLayout {
                                width: docsScroll.availableWidth - 24
                                x: 12
                                y: 12
                                spacing: 4
                                Text { text: root.d.shortClass || ""; color: theme.fg; font.pixelSize: 13; font.weight: Font.Bold }
                                Text {
                                    text: root.backend.tab === "docs" && root.d.deviceClass ? root.backend.docs(root.d.deviceClass) : ""
                                    color: theme.fgMuted
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- toasts -------------------------------------------------------------------------------
    ListModel { id: toastModel }
    Connections {
        target: root.backend
        function onToast(message, tone, undo) {
            toastModel.append({ message: message, tone: tone, undo: undo, stamp: Date.now() })
            while (toastModel.count > 3) toastModel.remove(0)
        }
    }
    Timer {
        interval: 250
        running: toastModel.count > 0
        repeat: true
        onTriggered: {
            for (let i = toastModel.count - 1; i >= 0; i--)
                if (Date.now() - toastModel.get(i).stamp > 5000) toastModel.remove(i)
        }
    }
    Column {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 16
        spacing: 6
        Repeater {
            model: toastModel
            delegate: Rectangle {
                id: toast
                required property string message
                required property bool undo
                required property int index
                width: Math.min(440, toastRow.implicitWidth + 24)
                height: toastRow.implicitHeight + 16
                radius: 8
                color: theme.fg
                RowLayout {
                    id: toastRow
                    anchors.fill: parent
                    anchors.margins: 8
                    anchors.leftMargin: 12
                    Text { text: toast.message; color: theme.bg; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.maximumWidth: 380 }
                    Text {
                        visible: toast.undo
                        text: "Undo"
                        color: Qt.lighter(theme.primary, theme.dark ? 1.4 : 1.6)
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        TapHandler { onTapped: { root.backend.undo(); toastModel.remove(toast.index) } }
                    }
                }
            }
        }
    }

    // ---- sheets -------------------------------------------------------------------------------
    Sheet {
        id: reviewSheet
        property bool applyMode: false
        readonly property var review: root.backend.review
        parent: Overlay.overlay
        wide: true
        title: "Apply changes to the running session"
        sub: applyMode ? "" : "These are the only differences between your edited copy and what BEC runs now. Other devices are left exactly as they are."

        // review
        Repeater {
            model: reviewSheet.applyMode ? [] : reviewSheet.review.groups
            delegate: ColumnLayout {
                id: group
                required property var modelData
                Layout.fillWidth: true
                spacing: 6
                Upper { text: group.modelData.title }
                Repeater {
                    model: group.modelData.items
                    delegate: Rectangle {
                        id: card
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: cardCol.implicitHeight + 14
                        radius: 7
                        color: theme.card
                        border.color: theme.border
                        ColumnLayout {
                            id: cardCol
                            anchors.fill: parent
                            anchors.margins: 7
                            anchors.leftMargin: 9
                            anchors.rightMargin: 9
                            spacing: 3
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: card.modelData.name; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.Bold }
                                Text { text: card.modelData.deviceClass; color: theme.fgMuted; font.pixelSize: 12 }
                                Item { Layout.fillWidth: true }
                                Chip { visible: card.modelData.statusText !== ""; text: card.modelData.statusText; tone: card.modelData.statusTone; iconName: card.modelData.statusIcon }
                            }
                            Repeater {
                                model: card.modelData.fields
                                delegate: Text {
                                    required property var modelData
                                    textFormat: Text.StyledText
                                    text: "<font color='" + theme.fgMuted + "'>" + modelData.field + ": </font><font color='" + theme.danger + "'><s>" + modelData.old + "</s></font> → <font color='" + theme.success + "'>" + modelData.new + "</font>"
                                    font.family: root.mono
                                    font.pixelSize: 12
                                    color: theme.fg
                                    wrapMode: Text.WrapAnywhere
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }
        Banner {
            visible: !reviewSheet.applyMode && reviewSheet.review.uncheckedText !== ""
            Layout.fillWidth: true
            tone: "warn"
            iconName: "warning"
            title: reviewSheet.review.uncheckedText
            text: "Each is loaded on its own; if one cannot connect it is reported and the others are not affected."
        }
        Banner {
            visible: !reviewSheet.applyMode && reviewSheet.review.scanRunning
            Layout.fillWidth: true
            tone: "err"
            iconName: "lock"
            title: root.bar.scanText
            text: "Applying waits until it finishes."
        }
        // apply progress
        Banner {
            readonly property bool failed: root.backend.applyRows.some((r) => r.state === "failed")
            visible: reviewSheet.applyMode && !root.backend.applying && root.backend.applySummary !== ""
            Layout.fillWidth: true
            tone: failed ? "warn" : "ok"
            iconName: failed ? "warning" : "check_circle"
            title: root.backend.applySummary
            text: failed ? "The devices marked Failed were not changed; see the Problems panel. Everything else is live."
                         : "The running session now matches your copy."
        }
        Repeater {
            model: reviewSheet.applyMode ? root.backend.applyRows : []
            delegate: RowLayout {
                id: applyRow
                required property var modelData
                readonly property var st: ({
                    waiting: ["Waiting", "neutral", "schedule"], running: ["Initialising…", "busy", "sync"],
                    done: ["Done", "ok", "check"], failed: ["Failed", "err", "warning"]
                })[modelData.state]
                Layout.fillWidth: true
                Text { text: applyRow.modelData.name; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.Bold; Layout.preferredWidth: 140 }
                Text { text: applyRow.modelData.action; color: theme.fgMuted; font.pixelSize: 12; Layout.fillWidth: true }
                Text { visible: applyRow.modelData.message !== ""; text: applyRow.modelData.message; color: theme.danger; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Chip { text: applyRow.st[0]; tone: applyRow.st[1]; iconName: applyRow.st[2] }
            }
        }

        footer: [
            Text {
                visible: !reviewSheet.applyMode
                text: reviewSheet.review.footText
                color: theme.fgMuted
                font.pixelSize: 12
                Layout.fillWidth: true
            },
            Item { visible: reviewSheet.applyMode; Layout.fillWidth: true },
            TextButton { visible: !reviewSheet.applyMode; text: "Cancel"; onClicked: reviewSheet.close() },
            TextButton {
                visible: !reviewSheet.applyMode
                text: reviewSheet.review.applyText
                variant: "primary"
                enabled: root.backend.canApply
                onClicked: if (root.backend.apply()) reviewSheet.applyMode = true
            },
            TextButton {
                visible: reviewSheet.applyMode
                text: "Done"
                variant: "primary"
                enabled: !root.backend.applying
                onClicked: reviewSheet.close()
            }
        ]
    }

    Sheet {
        id: addSheet
        parent: Overlay.overlay
        title: "Add device"
        sub: "Added to the edited copy. Test it, then review and apply."
        onOpened: { newName.text = ""; newPrefix.text = ""; addError.text = root.backend.nameRule; addError.color = theme.fgSubtle; newName.forceActiveFocus() }
        function submit() {
            const message = root.backend.addDevice(newName.text, newClass.editText, newPrefix.text)
            if (message !== "") { addError.text = message; addError.color = theme.danger; newName.invalid = true; return }
            addSheet.close()
        }
        FieldLabel { text: "Name" }
        InputField { id: newName; Layout.fillWidth: true; placeholderText: "e.g. pinz2"; onTextEdited: invalid = false; onAccepted: addSheet.submit() }
        Text { id: addError; color: theme.fgSubtle; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        FieldLabel { text: "Class" }
        SelectField { id: newClass; Layout.fillWidth: true; editable: true; model: root.backend.deviceClasses }
        FieldLabel { text: "PV prefix" }
        InputField { id: newPrefix; Layout.fillWidth: true; placeholderText: "X05LA-ES-PH:Z2"; onAccepted: addSheet.submit() }
        footer: [
            Item { Layout.fillWidth: true },
            TextButton { text: "Cancel"; onClicked: addSheet.close() },
            TextButton { text: "Add device"; variant: "primary"; onClicked: addSheet.submit() }
        ]
    }

    Sheet {
        id: clearSheet
        parent: Overlay.overlay
        title: "Clear the running session?"
        sub: "Removes <b>all " + root.backend.sessionCount + " devices</b> from BEC for everybody using this beamline. Plots, scans and motors stop working until a config is loaded again."
        onOpened: { confirmField.text = ""; confirmField.forceActiveFocus() }
        Banner {
            visible: root.bar.scanRunning
            Layout.fillWidth: true
            tone: "err"
            iconName: "lock"
            title: "A scan is running"
            text: "Clearing is not possible during a scan."
        }
        FieldLabel { text: "Type CLEAR to confirm" }
        InputField { id: confirmField; Layout.fillWidth: true; placeholderText: "Type CLEAR" }
        footer: [
            Item { Layout.fillWidth: true },
            TextButton { text: "Cancel"; onClicked: clearSheet.close() },
            TextButton {
                text: "Remove all " + root.backend.sessionCount + " devices"
                variant: "danger"
                enabled: confirmField.text.trim() === "CLEAR" && !root.bar.scanRunning
                onClicked: if (root.backend.clearSession(confirmField.text) === "") clearSheet.close()
            }
        ]
    }
}
