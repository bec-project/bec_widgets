import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Root of the QML scan control: scan picker, scrolling form, sticky Start/Stop footer.
Pane {
    id: root

    readonly property var opts: sc.options
    readonly property bool wide: width > 620
    property string noticeText

    padding: 0
    font.pixelSize: 13
    background: Rectangle { color: theme.bg }
    palette.window: theme.bg
    palette.base: theme.field
    palette.button: theme.card
    palette.text: theme.fg
    palette.windowText: theme.fg
    palette.buttonText: theme.fg
    palette.highlight: theme.primary
    palette.highlightedText: theme.onPrimary
    palette.mid: theme.border
    palette.dark: theme.border
    palette.light: theme.card
    palette.toolTipBase: theme.card
    palette.toolTipText: theme.fg

    Connections {
        target: sc
        function onNotice(text) { root.noticeText = text; noticeTimer.restart() }
    }
    Timer { id: noticeTimer; interval: 4000; onTriggered: root.noticeText = "" }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- header
        Rectangle {
            Layout.fillWidth: true
            visible: !root.opts.hide_scan_selection_combobox
            implicitHeight: header.implicitHeight + 24
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }

            ColumnLayout {
                id: header
                anchors { fill: parent; margins: 12 }
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    ComboBox {
                        id: scanPicker
                        Layout.fillWidth: true
                        implicitHeight: 36
                        editable: true
                        model: sc.scans
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        Accessible.name: "Scan"
                        readonly property bool typedValid: sc.isValidScan(editText)
                        function sync() { currentIndex = find(sc.currentScan); editText = sc.currentScan }
                        function confirm() {
                            if (sc.isValidScan(editText)) sc.selectScan(editText)
                            sync()
                        }
                        Connections { target: sc; function onStructureChanged() { scanPicker.sync() } function onStatusChanged() { if (!scanPicker.contentItem.activeFocus) scanPicker.sync() } }
                        Component.onCompleted: sync()
                        onActivated: confirm()
                        onAccepted: confirm()
                        Connections { target: scanPicker.contentItem; function onActiveFocusChanged() { if (!scanPicker.contentItem.activeFocus) scanPicker.confirm() } }
                        background: FieldBackground {
                            focused: scanPicker.contentItem.activeFocus || scanPicker.popup.visible
                            invalid: !scanPicker.typedValid && scanPicker.editText.length > 0
                        }
                        contentItem: TextField {
                            leftPadding: 34
                            text: scanPicker.editText
                            placeholderText: "Search scans"
                            placeholderTextColor: theme.muted
                            color: theme.fg
                            font: scanPicker.font
                            selectionColor: theme.primary
                            selectedTextColor: theme.onPrimary
                            background: null
                            verticalAlignment: Text.AlignVCenter
                            Image {
                                x: 9
                                anchors.verticalCenter: parent.verticalCenter
                                source: "image://material/search?color=" + encodeURIComponent(theme.muted.toString())
                                sourceSize: Qt.size(18, 18)
                            }
                        }
                    }
                    IconButton {
                        iconName: "info"
                        tip: "Documentation of this scan"
                        enabled: sc.currentScan.length > 0
                        onClicked: sc.showInfo()
                    }
                    IconButton {
                        iconName: "filter_list"
                        tip: "Choose which scans are listed"
                        visible: !root.opts.hide_scan_selector_settings_button
                        onClicked: sc.showFilter()
                    }
                }
                Text {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: sc.summary
                    color: theme.muted
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }

        // ---------------------------------------------------------------- form
        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: scroll.availableWidth
                spacing: 10

                Item { implicitHeight: 2 }

                Text {
                    Layout.fillWidth: true
                    Layout.margins: 24
                    visible: sc.scans.length === 0
                    text: "No scans available. Check the scan filter or the BEC server."
                    color: theme.muted
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }

                // Positional argument rows
                Card {
                    id: argCard
                    Layout.leftMargin: 10
                    Layout.rightMargin: 10
                    visible: sc.argFields.length > 0 && !root.opts.hide_arg_box
                    title: sc.argTitle
                    subtitle: sc.rowCount > 1 ? sc.rowCount + " rows" : ""

                    // Column headings
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Item { implicitWidth: 22 }
                        Repeater {
                            model: sc.argFields
                            Text {
                                Layout.fillWidth: true
                                Layout.preferredWidth: modelData.kind === "device" ? 140 : 90
                                text: modelData.label
                                color: theme.muted
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                        }
                        Item { implicitWidth: 30; visible: !root.opts.hide_add_remove_buttons }
                    }

                    Repeater {
                        model: sc.rowCount
                        RowLayout {
                            id: argRow
                            required property int index
                            readonly property var row: sc.argRows[index] || ({ values: {}, units: {}, errors: {} })
                            Layout.fillWidth: true
                            spacing: 6

                            Text {
                                Layout.preferredWidth: 22
                                text: argRow.index + 1
                                color: theme.muted
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                            }
                            Repeater {
                                model: sc.argFields
                                FieldEditor {
                                    Layout.preferredWidth: modelData.kind === "device" ? 140 : 90
                                    spec: modelData
                                    value: argRow.row.values[modelData.name]
                                    units: argRow.row.units[modelData.name] || ""
                                    error: argRow.row.errors[modelData.name] || ""
                                    devices: sc.devices
                                    onEdited: (v) => sc.setArg(argRow.index, modelData.name, v)
                                }
                            }
                            IconButton {
                                visible: !root.opts.hide_add_remove_buttons
                                iconName: "close"
                                tip: "Remove row " + (argRow.index + 1)
                                tint: theme.muted
                                // Keep the column while rows cannot be removed, so the fields do not jump.
                                enabled: sc.canRemoveRow
                                opacity: enabled ? 1 : 0
                                onClicked: sc.removeRow(argRow.index)
                            }
                        }
                    }

                    ActionButton {
                        visible: !root.opts.hide_add_remove_buttons && sc.canAddRow
                        kind: "ghost"
                        iconName: "add"
                        text: "Add row"
                        onClicked: sc.addRow()
                    }
                }

                // Keyword argument groups
                Repeater {
                    model: root.opts.hide_kwarg_boxes ? [] : sc.groups
                    Card {
                        id: groupCard
                        required property var modelData
                        property bool showExpert: false
                        readonly property int expertCount: modelData.fields.filter(f => f.expert).length
                        Layout.leftMargin: 10
                        Layout.rightMargin: 10
                        title: modelData.name

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.wide ? 4 : 2
                            columnSpacing: 10
                            rowSpacing: 8

                            Repeater {
                                model: groupCard.modelData.fields.filter(f => !f.expert || groupCard.showExpert)
                                delegate: Item {
                                    // Wraps label + editor so both land in consecutive grid cells.
                                    required property var modelData
                                    Layout.columnSpan: 2
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    RowLayout {
                                        anchors.fill: parent
                                        spacing: 10
                                        Text {
                                            Layout.preferredWidth: 120
                                            Layout.maximumWidth: 140
                                            text: modelData.label
                                            color: theme.fg
                                            font.pixelSize: 13
                                            elide: Text.ElideRight
                                            ToolTip.text: modelData.tooltip || modelData.label
                                            ToolTip.visible: labelHover.hovered
                                            ToolTip.delay: 500
                                            HoverHandler { id: labelHover }
                                        }
                                        FieldEditor {
                                            spec: modelData
                                            value: sc.kwargs.values[modelData.name]
                                            units: sc.kwargs.units[modelData.name] || ""
                                            error: sc.kwargs.errors[modelData.name] || ""
                                            devices: sc.devices
                                            onEdited: (v) => sc.setKwarg(modelData.name, v)
                                        }
                                    }
                                }
                            }
                        }
                        ActionButton {
                            visible: groupCard.expertCount > 0
                            kind: "ghost"
                            iconName: groupCard.showExpert ? "expand_less" : "expand_more"
                            text: (groupCard.showExpert ? "Hide" : "Show") + " advanced (" + groupCard.expertCount + ")"
                            onClicked: groupCard.showExpert = !groupCard.showExpert
                        }
                    }
                }

                // Metadata
                Card {
                    id: metaCard
                    Layout.leftMargin: 10
                    Layout.rightMargin: 10
                    visible: !root.opts.hide_metadata && sc.currentScan.length > 0
                    collapsible: true
                    expanded: Object.keys(sc.metaErrors).length > 0
                    title: "Metadata"
                    subtitle: Object.keys(sc.metaErrors).length > 0 ? "" : (sc.metaSummary || "optional")
                    trailing: [
                        Rectangle {
                            visible: Object.keys(sc.metaErrors).length > 0
                            radius: 9
                            height: 18
                            width: badge.implicitWidth + 14
                            color: Qt.rgba(theme.danger.r, theme.danger.g, theme.danger.b, 0.18)
                            Text {
                                id: badge
                                anchors.centerIn: parent
                                text: Object.keys(sc.metaErrors).length + " to fix"
                                color: theme.danger
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                        }
                    ]

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 10
                        rowSpacing: 8
                        Repeater {
                            model: sc.metaFields
                            delegate: Item {
                                required property var modelData
                                Layout.columnSpan: 2
                                Layout.fillWidth: true
                                implicitHeight: 32
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: 10
                                    Text {
                                        Layout.preferredWidth: 120
                                        text: modelData.label + (modelData.required ? " *" : "")
                                        color: theme.fg
                                        font.pixelSize: 13
                                        elide: Text.ElideRight
                                        ToolTip.text: modelData.description || modelData.label
                                        ToolTip.visible: metaHover.hovered
                                        ToolTip.delay: 500
                                        HoverHandler { id: metaHover }
                                    }
                                    FieldEditor {
                                        spec: ({ kind: modelData.kind, label: modelData.label, tooltip: modelData.description, placeholder: modelData.placeholder,
                                                 minimum: -2147483647, maximum: 2147483647, decimals: 6 })
                                        value: sc.metaValues[modelData.name]
                                        error: sc.metaErrors[modelData.name] || ""
                                        onEdited: (v) => sc.setMeta(modelData.name, v)
                                    }
                                }
                            }
                        }
                    }

                    // Free key/value entries
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: !root.opts.hide_optional_metadata
                        spacing: 6
                        Text {
                            text: "Additional entries"
                            color: theme.muted
                            font.pixelSize: 12
                            Layout.topMargin: 4
                        }
                        Repeater {
                            id: extrasRepeater
                            model: sc.metaExtras
                            RowLayout {
                                required property int index
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 6
                                FieldEditor {
                                    spec: ({ kind: "str", label: "Key", placeholder: "Key" })
                                    value: modelData[0]
                                    onEdited: (v) => { var e = sc.metaExtras; e[index][0] = v; sc.setExtras(e) }
                                }
                                FieldEditor {
                                    spec: ({ kind: "str", label: "Value", placeholder: "Value" })
                                    value: modelData[1]
                                    onEdited: (v) => { var e = sc.metaExtras; e[index][1] = v; sc.setExtras(e) }
                                }
                                IconButton {
                                    iconName: "close"
                                    tint: theme.muted
                                    tip: "Remove entry"
                                    onClicked: { var e = sc.metaExtras; e.splice(index, 1); sc.setExtras(e) }
                                }
                            }
                        }
                        ActionButton {
                            kind: "ghost"
                            iconName: "add"
                            text: "Add entry"
                            onClicked: { var e = sc.metaExtras; e.push(["", ""]); sc.setExtras(e) }
                        }
                    }
                }

                Item { implicitHeight: 6 }
            }
        }

        // ---------------------------------------------------------------- footer
        Rectangle {
            Layout.fillWidth: true
            visible: !root.opts.hide_scan_control_buttons
            implicitHeight: footer.implicitHeight + 20
            color: theme.card
            Rectangle { width: parent.width; height: 1; color: theme.border }

            ColumnLayout {
                id: footer
                anchors { fill: parent; margins: 10 }
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    readonly property bool showProblem: root.noticeText.length === 0 && sc.problems.length > 0
                    visible: root.noticeText.length > 0 || sc.problems.length > 0
                    Image {
                        source: "image://material/" + (parent.showProblem ? "error" : "check_circle") + "?filled=1&color="
                                + encodeURIComponent((parent.showProblem ? theme.warning : theme.success).toString())
                        sourceSize: Qt.size(16, 16)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: parent.showProblem
                              ? sc.problems[0] + (sc.problems.length > 1 ? "  (+" + (sc.problems.length - 1) + " more)" : "")
                              : root.noticeText
                        color: theme.fg
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    ActionButton {
                        kind: "ghost"
                        iconName: "history"
                        text: sc.restoring ? "Restoring…" : "Restore last"
                        enabled: !sc.restoring && sc.currentScan.length > 0
                        ToolTip.text: "Fill in the parameters of the last run of this scan"
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        onClicked: sc.restoreLast()
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton {
                        kind: sc.stopArmed ? "danger" : "outlineDanger"
                        iconName: "stop"
                        text: sc.stopArmed ? "Halt now" : "Stop"
                        onClicked: sc.stop()
                    }
                    ActionButton {
                        kind: "primary"
                        iconName: "play_arrow"
                        text: "Start " + sc.currentScan
                        enabled: sc.problems.length === 0
                        Layout.maximumWidth: 220
                        onClicked: sc.start()
                    }
                }
            }
        }
    }
}
