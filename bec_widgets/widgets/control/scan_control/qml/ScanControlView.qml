import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Scan submission form: scan picker, argument rows, parameter groups and a sticky footer.
// backend: ScanControlBackend (state, groups, devices and actions).
Rectangle {
    id: root
    required property QtObject backend
    readonly property var s: backend.state
    readonly property var errors: s.errors || ({})

    color: theme.bg
    implicitWidth: 420
    implicitHeight: 520

    // One labelled editor for a form field; the editor depends on the field kind.
    component FieldEditor: ColumnLayout {
        id: fieldRoot
        required property var field
        readonly property string error: root.errors[field.key] || ""
        spacing: 3

        RowLayout {
            spacing: 4
            Layout.fillWidth: true
            Text {
                text: fieldRoot.field.label
                color: theme.fgMuted
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Icon {
                visible: fieldRoot.field.tooltip !== ""
                name: "info"
                size: 13
                color: theme.fgSubtle
                HoverHandler { id: tipHover }
                ToolTip.visible: tipHover.hovered
                ToolTip.text: fieldRoot.field.tooltip
            }
        }
        Loader {
            Layout.fillWidth: true
            sourceComponent: fieldRoot.field.kind === "bool" ? switchEditor
                : fieldRoot.field.kind === "literal" ? literalEditor
                : fieldRoot.field.kind === "device" ? deviceEditor
                : textEditor
        }
        Text {
            visible: fieldRoot.error !== ""
            text: fieldRoot.error
            color: theme.danger
            font.pixelSize: 11
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Component {
            id: textEditor
            InputField {
                text: fieldRoot.field.value === undefined || fieldRoot.field.value === null ? "" : String(fieldRoot.field.value)
                placeholderText: fieldRoot.field.placeholder
                suffix: fieldRoot.field.units
                invalid: fieldRoot.error !== ""
                horizontalAlignment: fieldRoot.field.kind === "str" ? Text.AlignLeft : Text.AlignRight
                inputMethodHints: fieldRoot.field.kind === "str" ? Qt.ImhNone : Qt.ImhFormattedNumbersOnly
                onTextEdited: root.backend.setField(fieldRoot.field.key, text)
                onAccepted: root.backend.run()
                Accessible.name: fieldRoot.field.label
            }
        }
        Component {
            id: switchEditor
            SwitchField {
                checked: fieldRoot.field.value === true
                text: checked ? "On" : "Off"
                onToggled: root.backend.setField(fieldRoot.field.key, checked)
                Accessible.name: fieldRoot.field.label
            }
        }
        Component {
            id: literalEditor
            SelectField {
                model: fieldRoot.field.options
                currentIndex: Math.max(0, fieldRoot.field.options.indexOf(String(fieldRoot.field.value)))
                displayText: currentText === "" ? "None" : currentText
                onActivated: (index) => root.backend.setField(fieldRoot.field.key, textAt(index))
                Accessible.name: fieldRoot.field.label
            }
        }
        Component {
            id: deviceEditor
            SelectField {
                editable: true
                model: root.backend.devices
                placeholder: "Device"
                invalid: fieldRoot.error !== ""
                Component.onCompleted: editText = fieldRoot.field.value || ""
                onEditTextChanged: if (activeFocus || popup.visible) root.backend.setField(fieldRoot.field.key, editText)
                onActivated: (index) => root.backend.setField(fieldRoot.field.key, textAt(index))
                Accessible.name: fieldRoot.field.label
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        // ---- scan picker -------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.showSelector === true
            Layout.fillWidth: true
            spacing: 4
            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                SelectField {
                    id: scanPicker
                    Layout.fillWidth: true
                    editable: true
                    model: root.s.scans || []
                    placeholder: "Search scans"
                    invalid: editText !== "" && model.indexOf(editText) < 0 && find(editText, Qt.MatchFixedString) < 0
                    onActivated: (index) => root.backend.selectScan(textAt(index))
                    onAccepted: {
                        root.backend.selectScan(editText)
                        editText = root.s.current || ""
                    }
                    onActiveFocusChanged: if (!activeFocus) editText = root.s.current || ""
                    Connections {
                        target: root.backend
                        function onChanged() {
                            if (!scanPicker.activeFocus && scanPicker.editText !== (root.s.current || ""))
                                scanPicker.editText = root.s.current || ""
                        }
                    }
                    Accessible.name: "Scan"
                }
                IconButton {
                    iconName: "info"
                    tip: "Scan documentation"
                    enabled: (root.s.current || "") !== ""
                    onClicked: root.backend.openInfo()
                }
                IconButton {
                    visible: root.s.showFilter === true
                    iconName: "filter_list"
                    tip: "Choose scans shown in the list"
                    onClicked: root.backend.openFilter()
                }
                IconButton {
                    iconName: "history"
                    tip: "Restore the parameters of the last run of this scan"
                    enabled: (root.s.current || "") !== "" && root.s.restoreBusy !== true
                    onClicked: root.backend.restoreLast()
                }
            }
            Text {
                visible: text !== ""
                text: root.s.summary || ""
                color: theme.fgMuted
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // ---- parameter groups ------------------------------------------------------------------
        ScrollView {
            id: scroller
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: scroller.availableWidth
                spacing: 8

                Repeater {
                    model: root.backend.groups
                    delegate: Card {
                        id: groupCard
                        required property var modelData
                        readonly property bool isArgs: modelData.kind === "args"
                        visible: isArgs ? root.s.showArgs === true : root.s.showKwargs === true
                        Layout.fillWidth: true
                        title: modelData.title
                        subtitle: isArgs ? modelData.rows.length + (modelData.rows.length === 1 ? " row" : " rows") : ""

                        headerExtras: [
                            TextButton {
                                visible: groupCard.isArgs && root.s.showRowButtons === true
                                enabled: groupCard.modelData.canAdd
                                text: "Add row"
                                iconName: "add"
                                variant: "ghost"
                                implicitHeight: 28
                                onClicked: root.backend.addRow()
                            }
                        ]

                        // argument rows
                        Repeater {
                            model: groupCard.isArgs ? groupCard.modelData.rows : []
                            delegate: RowLayout {
                                id: argRow
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 8
                                Rectangle {
                                    Layout.alignment: Qt.AlignTop
                                    Layout.topMargin: 22
                                    width: 22; height: 22; radius: 11
                                    color: theme.track
                                    Text {
                                        anchors.centerIn: parent
                                        text: argRow.index + 1
                                        color: theme.fgMuted
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                    }
                                }
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: Math.max(1, Math.min(argRow.modelData.length, Math.floor((scroller.availableWidth - 80) / 75)))
                                    columnSpacing: 8
                                    rowSpacing: 6
                                    Repeater {
                                        model: argRow.modelData
                                        delegate: FieldEditor {
                                            required property var modelData
                                            field: modelData
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignTop
                                        }
                                    }
                                }
                                IconButton {
                                    Layout.alignment: Qt.AlignTop
                                    Layout.topMargin: 18
                                    visible: root.s.showRowButtons === true
                                    enabled: groupCard.modelData.canRemove
                                    iconName: "close"
                                    tip: "Remove row " + (argRow.index + 1)
                                    onClicked: root.backend.removeRow(argRow.index)
                                }
                            }
                        }

                        // keyword fields
                        GridLayout {
                            visible: !groupCard.isArgs
                            Layout.fillWidth: true
                            columns: Math.max(1, Math.floor((scroller.availableWidth - 30) / 170))
                            columnSpacing: 10
                            rowSpacing: 8
                            Repeater {
                                model: groupCard.isArgs ? [] : groupCard.modelData.fields
                                delegate: FieldEditor {
                                    required property var modelData
                                    field: modelData
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignTop
                                }
                            }
                        }
                    }
                }

                Text {
                    visible: (root.s.current || "") === ""
                    Layout.fillWidth: true
                    Layout.topMargin: 24
                    horizontalAlignment: Text.AlignHCenter
                    text: (root.s.scans || []).length === 0 ? "No scans are available. Check the scan filter or the BEC server." : "Choose a scan to set its parameters."
                    wrapMode: Text.WordWrap
                    color: theme.fgMuted
                    font.pixelSize: 13
                }
                Item { Layout.preferredHeight: 4 }
            }
        }

        // ---- footer ------------------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: footer.implicitHeight + 16
            radius: 10
            color: theme.card
            border.color: theme.border
            visible: root.s.showButtons === true || root.s.showMetadata === true

            ColumnLayout {
                id: footer
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                Text {
                    visible: text !== ""
                    text: root.s.hint || ""
                    color: root.s.metadataValid === true ? theme.danger : theme.warning
                    font.pixelSize: 12
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    TextButton {
                        visible: root.s.showMetadata === true
                        text: "Metadata"
                        iconName: root.s.metadataValid === true ? "check_circle" : "error"
                        variant: "neutral"
                        tip: root.s.metadataValid === true ? "Metadata is complete" : "Metadata needs attention"
                        onClicked: root.backend.openMetadata()
                    }
                    Item { Layout.fillWidth: true; visible: root.s.showButtons !== true }
                    TextButton {
                        visible: root.s.showButtons === true
                        Layout.fillWidth: true
                        text: root.s.startLabel || "Start"
                        iconName: "play_arrow"
                        variant: "success"
                        enabled: root.s.canStart === true
                        onClicked: root.backend.run()
                    }
                    TextButton {
                        visible: root.s.showButtons === true
                        text: root.s.stopLabel || "Stop"
                        iconName: "stop"
                        variant: "danger"
                        onClicked: root.backend.stop()
                    }
                }
            }
        }
    }
}
