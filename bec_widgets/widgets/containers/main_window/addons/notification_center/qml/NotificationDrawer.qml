import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Right-edge history drawer: filter chips, search, the list of notifications and the
// details of one entry with its full text, metadata and actions.
Rectangle {
    id: root
    required property var backend
    readonly property var st: backend.state
    readonly property var sel: st.selected || ({})
    readonly property bool hasSelection: sel.entryId !== undefined

    color: theme.bg

    // shadow towards the content and a hairline border
    Rectangle {
        anchors.right: parent.left
        width: 8; height: parent.height
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, theme.dark ? 0.3 : 0.08) }
        }
    }
    Rectangle { anchors.left: parent.left; width: 1; height: parent.height; color: theme.border }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 1
        spacing: 0

        // ---------------------------------------------------------------- header
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 16
            Layout.rightMargin: 12
            Layout.topMargin: 14
            Layout.bottomMargin: 8
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        Layout.fillWidth: true
                        text: "Notifications"
                        color: theme.fg
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: (root.st.total || 0) + " in history"
                            + ((root.st.openCriticals || 0) > 0 ? " · " + root.st.openCriticals + " critical open" : "")
                        color: theme.fgSubtle
                        font.pixelSize: 11
                    }
                }
                IconButton { iconName: "done_all"; tip: "Mark all as read"; onClicked: root.backend.markAllRead() }
                IconButton { iconName: "clear_all"; tip: "Clear history"; onClicked: root.backend.clearHistory() }
                IconButton { iconName: "close"; tip: "Close"; onClicked: root.backend.setDrawerOpen(false) }
            }

            Flow {
                Layout.fillWidth: true
                visible: !root.hasSelection
                spacing: 6
                Repeater {
                    model: root.st.filters || []
                    delegate: AbstractButton {
                        id: chip
                        required property var modelData
                        implicitHeight: 26
                        implicitWidth: chipLabel.implicitWidth + 22
                        hoverEnabled: true
                        onClicked: root.backend.setFilter(modelData.key)
                        background: Rectangle {
                            radius: 13
                            color: chip.modelData.active ? Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.18)
                                 : chip.hovered ? theme.hover : "transparent"
                            border.color: chip.modelData.active ? theme.primary : theme.border
                        }
                        contentItem: Text {
                            id: chipLabel
                            text: chip.modelData.label + "  " + chip.modelData.count
                            color: chip.modelData.active ? theme.fg : theme.fgMuted
                            font.pixelSize: 12
                            font.weight: chip.modelData.active ? Font.DemiBold : Font.Normal
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            InputField {
                id: search
                Layout.fillWidth: true
                visible: !root.hasSelection
                placeholderText: "Search notifications"
                text: root.st.search || ""
                onTextEdited: root.backend.setSearch(text)
            }
        }

        // ---------------------------------------------------------------- list
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.hasSelection && count > 0
            clip: true
            model: root.backend.rows
            spacing: 0
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Item {
                id: row
                required property string entryId
                required property string icon
                required property color color
                required property color tint
                required property string title
                required property string body
                required property string time
                required property string timeAbs
                required property string severityLabel
                required property string source
                required property string scan
                required property int count
                required property bool unread
                required property bool needsAck

                width: ListView.view.width
                height: 78

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 3
                    anchors.bottomMargin: 3
                    radius: 8
                    color: row.needsAck ? (rowMouse.containsMouse ? Qt.lighter(row.tint, 1.1) : row.tint)
                         : (rowMouse.containsMouse ? theme.hover : theme.card)
                    border.color: row.needsAck ? row.color : theme.border

                    Rectangle {
                        x: 10; y: 10
                        width: 28; height: 28; radius: 14
                        color: row.needsAck ? theme.card : row.tint
                        Icon { anchors.centerIn: parent; name: row.icon; color: row.color; filled: true; size: 17 }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 48
                        anchors.rightMargin: 10
                        anchors.topMargin: 6
                        anchors.bottomMargin: 6
                        spacing: 2

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                Layout.fillWidth: true
                                text: row.title
                                textFormat: Text.PlainText
                                color: theme.fg
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                visible: row.count > 1
                                implicitWidth: rowCount.implicitWidth + 12
                                implicitHeight: 16
                                radius: 8
                                color: row.tint
                                Text {
                                    id: rowCount
                                    anchors.centerIn: parent
                                    text: "×" + row.count
                                    color: row.color
                                    font.pixelSize: 11
                                }
                            }
                            Rectangle {
                                visible: row.unread
                                width: 7; height: 7; radius: 3.5
                                color: theme.primary
                            }
                            Text {
                                text: row.time
                                color: theme.fgSubtle
                                font.pixelSize: 11
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: row.body.replace(/\n/g, " ")
                            textFormat: Text.PlainText
                            color: theme.fgMuted
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: (row.needsAck ? "Needs acknowledgement · " : "")
                                + [row.severityLabel, row.source, row.scan].filter(function (p) { return p !== "" }).join(" · ")
                            color: row.needsAck ? row.color : theme.fgSubtle
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.backend.select(row.entryId)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 800
                        ToolTip.text: row.timeAbs
                    }
                }
            }
        }

        // ---------------------------------------------------------------- empty state
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.hasSelection && list.count === 0
            Column {
                anchors.centerIn: parent
                spacing: 8
                Icon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: (root.st.total || 0) > 0 ? "filter_alt_off" : "inbox"
                    color: theme.fgSubtle
                    size: 32
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: (root.st.total || 0) > 0 ? "Nothing matches this filter."
                        : "You're all caught up.\nNew messages and errors appear here."
                    color: theme.fgSubtle
                    font.pixelSize: 13
                }
            }
        }

        // ---------------------------------------------------------------- details
        Flickable {
            id: detailsView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.hasSelection
            clip: true
            contentHeight: details.implicitHeight + 16
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: details
                width: detailsView.width - 24
                x: 12
                spacing: 10

                TextButton {
                    text: "All notifications"
                    iconName: "arrow_back"
                    variant: "ghost"
                    onClicked: root.backend.select("")
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        width: 36; height: 36; radius: 18
                        color: root.sel.tint || theme.hover
                        Icon { anchors.centerIn: parent; name: root.sel.icon || ""; color: root.sel.color || theme.fg; filled: true; size: 21 }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Rectangle {
                            implicitHeight: 18
                            implicitWidth: pillText.implicitWidth + 16
                            radius: 9
                            color: root.sel.tint || "transparent"
                            Text {
                                id: pillText
                                anchors.centerIn: parent
                                text: (root.sel.severityLabel || "") + (root.sel.needsAck ? " · needs acknowledgement" : "")
                                color: root.sel.color || theme.fg
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                        }
                        TextEdit {
                            Layout.fillWidth: true
                            text: root.sel.title || ""
                            textFormat: TextEdit.PlainText
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            color: theme.fg
                            selectionColor: theme.primary
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                    }
                }
                TextEdit {
                    Layout.fillWidth: true
                    text: root.sel.body || "No message."
                    textFormat: TextEdit.PlainText
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                    color: theme.fg
                    selectionColor: theme.primary
                    font.pixelSize: 13
                }
                GridLayout {
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 4
                    Text { text: "When"; color: theme.fgSubtle; font.pixelSize: 12 }
                    Text { text: root.sel.timeAbs || ""; color: theme.fg; font.pixelSize: 12 }
                    Text { visible: (root.sel.count || 0) > 1; text: "Repeated"; color: theme.fgSubtle; font.pixelSize: 12 }
                    Text { visible: (root.sel.count || 0) > 1; text: (root.sel.count || 0) + " times since " + (root.sel.firstAbs || ""); color: theme.fg; font.pixelSize: 12 }
                    Text { visible: (root.sel.source || "") !== ""; text: "Source"; color: theme.fgSubtle; font.pixelSize: 12 }
                    Text { visible: (root.sel.source || "") !== ""; text: root.sel.source || ""; color: theme.fg; font.pixelSize: 12 }
                    Text { visible: (root.sel.scan || "") !== ""; text: "Scan"; color: theme.fgSubtle; font.pixelSize: 12 }
                    Text { visible: (root.sel.scan || "") !== ""; text: root.sel.scan || ""; color: theme.fg; font.pixelSize: 12 }
                }
                Text {
                    visible: root.sel.hasDetails || false
                    text: "DETAILS"
                    color: theme.fgSubtle
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(320, traceText.contentHeight + 16)
                    visible: root.sel.hasDetails || false
                    radius: 8
                    color: theme.field
                    border.color: theme.border
                    Flickable {
                        id: traceFlick
                        anchors.fill: parent
                        anchors.margins: 8
                        clip: true
                        contentWidth: traceText.contentWidth
                        contentHeight: traceText.contentHeight
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                        TextEdit {
                            id: traceText
                            text: root.sel.details || ""
                            textFormat: TextEdit.PlainText
                            readOnly: true
                            selectByMouse: true
                            color: theme.fg
                            selectionColor: theme.primary
                            font.family: "monospace"
                            font.pixelSize: 11
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    TextButton {
                        id: copyReport
                        property string copiedId: ""
                        text: copiedId !== "" && copiedId === root.sel.entryId ? "Copied" : "Copy report"
                        iconName: "content_copy"
                        onClicked: if (root.backend.copyDetails(root.sel.entryId)) copiedId = root.sel.entryId
                    }
                    TextButton {
                        visible: root.sel.needsAck || false
                        text: "Acknowledge"
                        iconName: "done"
                        variant: "danger"
                        onClicked: root.backend.acknowledge(root.sel.entryId)
                    }
                    Item { Layout.fillWidth: true }
                    TextButton {
                        text: "Remove"
                        iconName: "delete"
                        variant: "ghost"
                        onClicked: root.backend.remove(root.sel.entryId)
                    }
                }
            }
        }
    }
}
