import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Profile library: searchable list with sections on the left, the selected profile's
// preview, description, facts and actions on the right.
Rectangle {
    id: root
    required property var backend
    readonly property var st: backend.state
    readonly property var sel: st.selected || ({})
    readonly property bool hasSelection: sel.key !== undefined
    readonly property bool isTrash: sel.kind === "trash"
    readonly property var banner: st.banner || ({})

    color: theme.bg

    function toneColor(tone) {
        return tone === "error" ? theme.danger : tone === "warning" ? theme.warning
            : tone === "success" ? theme.success : tone === "info" ? theme.primary : theme.fgMuted
    }
    function soft(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    Shortcut { sequence: "Ctrl+F"; onActivated: search.forceActiveFocus() }
    Shortcut { sequence: "F2"; onActivated: root.backend.requestName("rename") }
    Shortcut { sequence: "Ctrl+D"; onActivated: root.backend.requestName("duplicate") }
    Shortcut { sequence: "Ctrl+S"; onActivated: root.backend.requestName("save") }
    Shortcut { sequence: "Delete"; enabled: !notes.activeFocus && !search.activeFocus; onActivated: root.backend.requestDelete() }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.topMargin: 14
        anchors.bottomMargin: 14
        spacing: 10

        // ---------------------------------------------------------------- header
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ColumnLayout {
                spacing: 0
                Text { text: "Profiles"; color: theme.fg; font.pixelSize: 16; font.weight: Font.DemiBold }
                Text {
                    text: root.st.total + (root.st.total === 1 ? " profile" : " profiles")
                    color: theme.fgMuted
                    font.pixelSize: 12
                }
            }
            Item { Layout.fillWidth: true }
            InputField {
                id: search
                Layout.preferredWidth: 260
                placeholderText: "Search profiles  (Ctrl+F)"
                leftPadding: 30
                text: root.st.query
                onTextEdited: root.backend.setQuery(text)
                Keys.onDownPressed: root.backend.moveSelection(1)
                Keys.onUpPressed: root.backend.moveSelection(-1)
                Keys.onReturnPressed: root.backend.openSelected(true)
                Icon {
                    anchors.left: parent.left
                    anchors.leftMargin: 9
                    anchors.verticalCenter: parent.verticalCenter
                    name: "search"
                    size: 16
                    color: theme.fgSubtle
                }
            }
            TextButton {
                text: "Save current layout…"
                variant: "primary"
                iconName: "save"
                onClicked: root.backend.requestName("save")
            }
        }

        // ---------------------------------------------------------------- banner
        Rectangle {
            Layout.fillWidth: true
            visible: root.banner.text !== undefined
            implicitHeight: bannerRow.implicitHeight + 12
            radius: 8
            color: root.soft(root.toneColor(root.banner.tone), 0.14)
            border.color: root.soft(root.toneColor(root.banner.tone), 0.45)
            RowLayout {
                id: bannerRow
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                spacing: 6
                HintLine {
                    Layout.fillWidth: true
                    tone: root.banner.tone || "neutral"
                    text: root.banner.text || ""
                }
                TextButton {
                    visible: (root.banner.action || "") !== ""
                    text: root.banner.action || ""
                    variant: "ghost"
                    implicitHeight: 28
                    onClicked: root.backend.bannerAction()
                }
                IconButton { iconName: "close"; tip: "Dismiss"; iconSize: 16; onClicked: root.backend.dismissBanner() }
            }
        }

        // ---------------------------------------------------------------- body
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            Rectangle {
                Layout.preferredWidth: 330
                Layout.fillHeight: true
                radius: 10
                color: theme.card
                border.color: theme.border

                ListView {
                    id: list
                    anchors.fill: parent
                    anchors.margins: 6
                    clip: true
                    model: root.backend.rows
                    spacing: 1
                    boundsBehavior: Flickable.StopAtBounds
                    currentIndex: -1
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    section.property: "section"
                    section.delegate: Text {
                        required property string section
                        width: ListView.view.width
                        topPadding: 10
                        bottomPadding: 4
                        leftPadding: 8
                        text: section.toUpperCase()
                        color: theme.fgSubtle
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.5
                    }
                    delegate: Rectangle {
                        id: row
                        required property var model
                        width: ListView.view.width
                        height: 48
                        radius: 8
                        color: model.selected ? root.soft(theme.primary, 0.14)
                             : rowMouse.containsMouse ? theme.hover : "transparent"
                        border.color: model.selected ? theme.primary : "transparent"
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: root.backend.select(row.model.key)
                            onDoubleClicked: if (row.model.kind !== "trash") root.backend.openSelected(true)
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 6
                            spacing: 8
                            Icon {
                                name: row.model.kind === "trash" ? "delete" : row.model.kind === "bundled" ? "lock" : "dashboard"
                                size: 18
                                color: row.model.isCurrent ? theme.primary : theme.fgSubtle
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    Layout.fillWidth: true
                                    text: row.model.name
                                    color: row.model.kind === "trash" ? theme.fgMuted : theme.fg
                                    font.pixelSize: 13
                                    font.weight: row.model.isCurrent ? Font.DemiBold : Font.Medium
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: row.model.subtitle
                                    color: theme.fgSubtle
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }
                            StatusPill {
                                visible: row.model.isCurrent || row.model.isOpen
                                text: row.model.isCurrent ? "This tab" : "Open"
                                tone: row.model.isCurrent ? theme.primary : theme.success
                            }
                            TextButton {
                                visible: row.model.kind === "trash"
                                text: "Restore"
                                variant: "ghost"
                                iconName: "restore_from_trash"
                                implicitHeight: 28
                                onClicked: root.backend.restore(row.model.token)
                            }
                            AbstractButton {
                                id: pin
                                visible: row.model.kind !== "trash"
                                implicitWidth: 30
                                implicitHeight: 30
                                hoverEnabled: true
                                onClicked: root.backend.togglePin(row.model.key)
                                background: Rectangle { radius: 6; color: pin.hovered ? theme.hover : "transparent" }
                                contentItem: Item {
                                    Icon {
                                        anchors.centerIn: parent
                                        name: "star"
                                        size: 16
                                        filled: row.model.pinned
                                        color: row.model.pinned ? theme.warning : theme.fgSubtle
                                    }
                                }
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: row.model.pinned ? "Shown in the toolbar list. Click to hide."
                                                               : "Not in the toolbar list. Click to show."
                            }
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 32
                    visible: list.count === 0
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.st.emptyText
                    color: theme.fgMuted
                    font.pixelSize: 12
                }
            }

            // ------------------------------------------------------------ details
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.hasSelection
                clip: true
                radius: 10
                color: theme.card
                border.color: theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    anchors.topMargin: 16
                    anchors.bottomMargin: 14
                    spacing: 10

                    PreviewFrame {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 220
                        source: root.isTrash ? "" : root.backend.previewUrl
                        placeholder: root.isTrash ? "Deleted profile. Restore it to open it." : "No preview yet"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: root.sel.name || ""
                            color: theme.fg
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                        }
                        StatusPill {
                            visible: !root.isTrash && (root.sel.status || "") !== ""
                            text: root.sel.status || ""
                            tone: root.sel.isCurrent ? theme.primary : theme.success
                        }
                        Item { Layout.fillWidth: true }
                        TextButton {
                            visible: !root.isTrash
                            enabled: root.sel.canDelete === true
                            variant: "ghost"
                            iconName: "delete"
                            text: "Delete…"
                            tip: root.sel.deleteReason || "Move to Recently deleted"
                            onClicked: root.backend.requestDelete()
                        }
                    }
                    InputField {
                        id: notes
                        Layout.fillWidth: true
                        visible: !root.isTrash && !root.sel.readOnly
                        placeholderText: "Add a description…"
                        text: root.sel.notes || ""
                        onEditingFinished: root.backend.saveNotes(text)
                    }
                    HintLine {
                        Layout.fillWidth: true
                        visible: root.isTrash || root.sel.readOnly === true
                        tone: root.isTrash ? "neutral" : "info"
                        text: root.isTrash ? (root.sel.status || "")
                            : "Read-only profile from " + (root.sel.source || "BEC") + ". Your changes are kept as you work; "
                              + "Revert brings back the original. Duplicate it to keep your own version."
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 18
                        rowSpacing: 4
                        Repeater {
                            model: root.sel.facts || []
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                spacing: 12
                                Text { text: modelData.label; color: theme.fgMuted; font.pixelSize: 12; Layout.preferredWidth: 56 }
                                Text { text: modelData.value; color: theme.fg; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        TextButton {
                            visible: !root.isTrash && !root.sel.isCurrent
                            variant: "primary"
                            iconName: "tab"
                            text: root.st.hasTabs ? (root.sel.isOpen ? "Go to tab" : "Open in new tab") : "Open"
                            onClicked: root.backend.openSelected(true)
                        }
                        TextButton {
                            visible: !root.isTrash && root.st.hasTabs && !root.sel.isOpen
                            iconName: "open_in_browser"
                            text: "Open here"
                            onClicked: root.backend.openSelected(false)
                        }
                        TextButton {
                            visible: root.isTrash
                            variant: "primary"
                            iconName: "restore_from_trash"
                            text: "Restore"
                            onClicked: root.backend.restore("")
                        }
                        TextButton {
                            visible: !root.isTrash
                            iconName: "content_copy"
                            text: "Duplicate…"
                            onClicked: root.backend.requestName("duplicate")
                        }
                        TextButton {
                            visible: !root.isTrash && !root.sel.readOnly
                            iconName: "edit"
                            text: "Rename…"
                            onClicked: root.backend.requestName("rename")
                        }
                        TextButton {
                            visible: !root.isTrash
                            enabled: root.sel.canRevert === true
                            iconName: "history"
                            text: "Revert…"
                            tip: enabled ? "Go back to the saved layout" : "Nothing saved to go back to"
                            onClicked: root.backend.requestRevert()
                        }
                        Item { Layout.fillWidth: true }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        visible: root.st.pendingDelete !== ""
                        implicitHeight: confirmRow.implicitHeight + 16
                        radius: 8
                        color: root.soft(theme.danger, 0.12)
                        border.color: root.soft(theme.danger, 0.5)
                        RowLayout {
                            id: confirmRow
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 8
                            spacing: 8
                            HintLine {
                                Layout.fillWidth: true
                                tone: "warning"
                                text: "Move '" + root.st.pendingDelete + "' to Recently deleted? You can restore it any time."
                            }
                            TextButton { text: "Cancel"; onClicked: root.backend.cancelDelete() }
                            TextButton {
                                text: "Delete"
                                variant: "danger"
                                iconName: "delete"
                                onClicked: root.backend.confirmDelete()
                            }
                        }
                    }
                }
            }
        }
    }
}
