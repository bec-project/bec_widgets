import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Error dialog: summary first, then where it happened, then a navigable traceback.
// State comes from ErrorDialogController.view_state() through backend.state.
Rectangle {
    id: root
    required property QtObject backend
    readonly property var st: backend ? backend.state : ({ count: 0, index: -1, errors: [] })
    readonly property var cur: st.current
    readonly property bool hasCur: !!cur
    readonly property bool many: st.count > 1
    readonly property string mono: "monospace"
    property bool copied: false
    property bool locationCopied: false

    color: theme.bg

    Timer { id: copiedTimer; interval: 1500; onTriggered: { root.copied = false; root.locationCopied = false } }

    Shortcut { sequence: "Alt+Up"; onActivated: backend.step(-1) }
    Shortcut { sequence: "Alt+Down"; onActivated: backend.step(1) }
    Shortcut { sequence: "Ctrl+Shift+C"; onActivated: copyReport() }

    function copyReport() {
        if (backend.copyReport()) { root.copied = true; copiedTimer.restart() }
    }

    component Caption: Text {
        color: theme.fgSubtle
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.letterSpacing: 1
        font.capitalization: Font.AllUppercase
    }

    // Source lines with line numbers; the current line is tinted with the error colour.
    component CodeBlock: Rectangle {
        id: code
        property var lines: []
        implicitHeight: codeCol.implicitHeight + 12
        radius: 6
        color: theme.field
        border.color: theme.border
        clip: true
        Column {
            id: codeCol
            x: 4; y: 6
            width: parent.width - 8
            Repeater {
                model: code.lines
                Rectangle {
                    required property var modelData
                    width: codeCol.width
                    height: 18
                    color: modelData.current ? Qt.tint(theme.field, Qt.alpha(theme.danger, 0.2)) : "transparent"
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10
                        Text {
                            width: 34
                            horizontalAlignment: Text.AlignRight
                            text: modelData.no
                            font.family: root.mono
                            font.pixelSize: 12
                            color: modelData.current ? theme.danger : theme.fgSubtle
                        }
                        Text {
                            text: modelData.text
                            textFormat: Text.PlainText
                            font.family: root.mono
                            font.pixelSize: 12
                            color: modelData.current ? theme.fg : theme.fgMuted
                        }
                    }
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- error list
        Rectangle {
            visible: root.many
            Layout.fillHeight: true
            Layout.preferredWidth: 264
            color: theme.card
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: theme.border }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                anchors.topMargin: 14
                spacing: 8
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: "Errors (" + root.st.count + ")"
                        color: theme.fg
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    TextButton {
                        text: "Clear all"
                        variant: "ghost"
                        iconName: "delete_sweep"
                        tip: "Remove every error from the list"
                        onClicked: backend.clear()
                    }
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    model: root.st.errors
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        id: item
                        required property var modelData
                        readonly property bool selected: root.hasCur && modelData.id === root.cur.id
                        width: ListView.view.width
                        height: itemCol.implicitHeight + 16
                        radius: 8
                        color: selected ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.16))
                                        : itemMouse.containsMouse ? theme.hover : "transparent"
                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: backend.select(item.modelData.id)
                        }
                        ColumnLayout {
                            id: itemCol
                            x: 10; y: 8
                            width: parent.width - 20
                            spacing: 2
                            RowLayout {
                                spacing: 6
                                Rectangle {
                                    visible: !item.modelData.seen
                                    width: 7; height: 7; radius: 3.5
                                    color: theme.primary
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: item.modelData.type
                                    color: theme.fg
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    visible: item.modelData.count > 1
                                    text: item.modelData.count + "×"
                                    color: theme.warning
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                                Text { text: item.modelData.time; color: theme.fgSubtle; font.pixelSize: 12 }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: item.modelData.message
                                color: theme.fgMuted
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
        }

        // ---------------------------------------------------------------- details
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Layout.topMargin: 18
            Layout.bottomMargin: 16
            spacing: 14

            // summary
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    width: 40; height: 40; radius: 20
                    color: Qt.tint(theme.card, Qt.alpha(theme.danger, 0.18))
                    Icon { anchors.centerIn: parent; name: "error"; filled: true; size: 24; color: theme.danger }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    TextEdit {
                        Layout.fillWidth: true
                        readOnly: true
                        selectByMouse: true
                        text: root.cur ? root.cur.type : "No errors"
                        color: theme.fg
                        font.pixelSize: 19
                        font.weight: Font.Bold
                        HoverHandler { id: typeHover }
                        ToolTip.visible: typeHover.hovered && root.hasCur
                        ToolTip.delay: 500
                        ToolTip.text: root.cur ? root.cur.qualified_type : ""
                    }
                    TextEdit {
                        Layout.fillWidth: true
                        visible: root.hasCur
                        readOnly: true
                        selectByMouse: true
                        wrapMode: Text.Wrap
                        text: root.cur ? (root.cur.headline || "(no message)") : ""
                        color: theme.fg
                        font.pixelSize: 14
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        visible: root.hasCur && !!root.cur.message_more
                        Layout.preferredHeight: Math.min(132, moreText.implicitHeight + 8)
                        radius: 6
                        color: theme.field
                        border.color: theme.border
                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 4
                            clip: true
                            TextArea {
                                id: moreText
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                text: root.cur ? root.cur.message_more : ""
                                color: theme.fgMuted
                                font.family: root.mono
                                font.pixelSize: 12
                                padding: 2
                                background: null
                            }
                        }
                    }
                    Text {
                        visible: root.hasCur
                        textFormat: Text.StyledText
                        color: theme.fgMuted
                        font.pixelSize: 12
                        text: {
                            if (!root.cur) return ""
                            const sep = "&nbsp;&nbsp;·&nbsp;&nbsp;"
                            let parts = ["<font color='" + theme.danger + "'><b>" + root.cur.title + "</b></font>"]
                            if (root.cur.source)
                                parts.push("in <font color='" + theme.fg + "'><b>" + root.cur.source + "</b></font>")
                            parts.push(root.cur.time.substring(11))
                            if (root.cur.count > 1)
                                parts.push("<font color='" + theme.warning + "'><b>" + root.cur.count
                                           + "× since " + root.cur.first_time.substring(11) + "</b></font>")
                            return parts.join(sep)
                        }
                    }
                }
                RowLayout {
                    visible: root.many
                    Layout.alignment: Qt.AlignTop
                    spacing: 2
                    IconButton {
                        iconName: "chevron_left"
                        tip: "Newer error (Alt+Up)"
                        enabled: root.st.index > 0
                        onClicked: backend.step(-1)
                    }
                    Text { text: (root.st.index + 1) + " of " + root.st.count; color: theme.fgMuted; font.pixelSize: 12 }
                    IconButton {
                        iconName: "chevron_right"
                        tip: "Older error (Alt+Down)"
                        enabled: root.st.index >= 0 && root.st.index < root.st.count - 1
                        onClicked: backend.step(1)
                    }
                }
            }

            // where it happened
            Rectangle {
                Layout.fillWidth: true
                visible: root.hasCur && !!root.cur.location
                implicitHeight: locCol.implicitHeight + 22
                radius: 10
                color: theme.card
                border.color: theme.border
                ColumnLayout {
                    id: locCol
                    x: 14; y: 10
                    width: parent.width - 24
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Caption { text: "Where it happened" }
                        Text {
                            text: root.cur && root.cur.location ? root.cur.location.func : ""
                            color: theme.fg
                            font.family: root.mono
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.cur && root.cur.location ? root.cur.location.file_short + ":" + root.cur.location.line : ""
                            color: theme.fgMuted
                            font.pixelSize: 12
                            elide: Text.ElideMiddle
                        }
                        IconButton {
                            iconName: root.locationCopied ? "check" : "content_copy"
                            iconSize: 16
                            tip: "Copy file path and line"
                            onClicked: if (backend.copyLocation()) { root.locationCopied = true; copiedTimer.restart() }
                        }
                    }
                    CodeBlock {
                        Layout.fillWidth: true
                        visible: lines.length > 0
                        lines: root.cur && root.cur.location ? root.cur.location.context : []
                    }
                }
            }

            // traceback header
            RowLayout {
                Layout.fillWidth: true
                visible: root.hasCur
                spacing: 10
                Text { text: "Traceback"; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    color: theme.fgMuted
                    font.pixelSize: 12
                    text: {
                        if (!root.cur) return ""
                        let hint = root.cur.frame_count + " frames, newest first"
                        if (!root.st.show_library && root.cur.library_frame_count > 0)
                            hint += " · " + root.cur.library_frame_count + " folded"
                        return hint
                    }
                }
                Text { text: "Library frames"; color: theme.fgMuted; font.pixelSize: 12 }
                SwitchField {
                    checked: !!root.st.show_library
                    onToggled: backend.setShowLibrary(checked)
                }
                Rectangle {
                    implicitWidth: segRow.implicitWidth + 4
                    implicitHeight: 32
                    radius: 7
                    color: theme.field
                    border.color: theme.border
                    Row {
                        id: segRow
                        anchors.centerIn: parent
                        spacing: 2
                        TextButton {
                            text: "Frames"
                            implicitHeight: 26
                            variant: root.st.mode === "frames" ? "primary" : "ghost"
                            onClicked: backend.setMode("frames")
                        }
                        TextButton {
                            text: "Raw text"
                            implicitHeight: 26
                            variant: root.st.mode === "raw" ? "primary" : "ghost"
                            onClicked: backend.setMode("raw")
                        }
                    }
                }
            }

            // traceback body
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.hasCur
                radius: 10
                color: theme.card
                border.color: theme.border
                clip: true

                ScrollView {
                    id: framesView
                    visible: root.st.mode === "frames"
                    anchors.fill: parent
                    anchors.margins: 6
                    contentWidth: availableWidth
                    clip: true
                    Column {
                        width: framesView.availableWidth
                        spacing: 2
                        Repeater {
                            model: root.cur ? root.cur.rows : []
                            delegate: Loader {
                                required property var modelData
                                width: parent.width
                                sourceComponent: modelData.kind === "section" ? sectionRow
                                               : modelData.kind === "group" ? groupRow : frameRow
                                property var row: modelData
                            }
                        }
                    }
                }

                ScrollView {
                    visible: root.st.mode === "raw"
                    anchors.fill: parent
                    anchors.margins: 4
                    clip: true
                    TextArea {
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.NoWrap
                        text: root.cur ? root.cur.raw : ""
                        color: theme.fg
                        selectionColor: theme.primary
                        font.family: root.mono
                        font.pixelSize: 12
                        background: null
                    }
                }
            }

            Item { Layout.fillHeight: true; visible: root.cur === null }

            // actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextButton {
                    text: root.copied ? "Copied" : "Copy report"
                    iconName: root.copied ? "check" : "content_copy"
                    tip: "Copy error, location, versions and traceback (Ctrl+Shift+C)"
                    enabled: root.hasCur
                    onClicked: root.copyReport()
                }
                TextButton {
                    text: "Report issue"
                    iconName: "bug_report"
                    tip: "Open a pre-filled issue in the browser"
                    enabled: root.hasCur
                    onClicked: backend.reportIssue()
                }
                Item { Layout.fillWidth: true }
                TextButton {
                    visible: root.many
                    text: "Dismiss"
                    variant: "ghost"
                    tip: "Remove this error from the list"
                    onClicked: backend.dismiss()
                }
                TextButton {
                    text: "Close"
                    variant: "primary"
                    onClicked: backend.close()
                }
            }
        }
    }

    // ---------------------------------------------------------------- traceback rows

    Component {
        id: sectionRow
        Item {
            readonly property var r: parent ? parent.row : null
            implicitHeight: secCol.implicitHeight + (r && r.first ? 10 : 18)
            ColumnLayout {
                id: secCol
                x: 8
                y: r && r.first ? 6 : 14
                width: parent.width - 16
                spacing: 2
                Caption {
                    text: r ? r.label : ""
                    color: r && r.first ? theme.danger : theme.fgSubtle
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    textFormat: Text.StyledText
                    font.pixelSize: 13
                    color: theme.fg
                    text: {
                        if (!r) return ""
                        const first = r.message ? r.message.split("\n")[0] : ""
                        return "<b>" + r.type + "</b>" + (first ? "<font color='" + theme.fgMuted + "'>: "
                               + first.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</font>" : "")
                    }
                }
            }
        }
    }

    Component {
        id: groupRow
        Rectangle {
            readonly property var r: parent ? parent.row : null
            implicitHeight: 26
            radius: 6
            color: groupMouse.containsMouse ? theme.hover : "transparent"
            border.color: theme.border
            // dashed look: a solid hairline reads the same at this size
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 6
                Icon { name: r && r.open ? "expand_less" : "unfold_more"; size: 16; color: theme.fgSubtle }
                Text { Layout.fillWidth: true; text: r ? r.label : ""; color: theme.fgSubtle; font.pixelSize: 12; elide: Text.ElideRight }
            }
            MouseArea {
                id: groupMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: backend.toggleGroup(r.key)
                ToolTip.visible: containsMouse
                ToolTip.delay: 500
                ToolTip.text: r && r.open ? "Hide these frames" : "Show these frames"
            }
        }
    }

    Component {
        id: frameRow
        Rectangle {
            readonly property var r: parent ? parent.row : null
            implicitHeight: frameCol.implicitHeight
            color: r && r.focus ? Qt.alpha(theme.danger, 0.06) : "transparent"
            Rectangle {
                visible: r && r.focus
                width: 3; height: parent.height
                color: theme.danger
            }
            Column {
                id: frameCol
                x: 3
                width: parent.width - 3
                Rectangle {
                    width: parent.width
                    height: headCol.implicitHeight + 10
                    radius: 6
                    color: headMouse.containsMouse ? theme.hover : "transparent"
                    MouseArea {
                        id: headMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: backend.toggleFrame(r.key)
                    }
                    Icon {
                        x: 4; y: 6
                        name: r && r.expanded ? "expand_more" : "chevron_right"
                        size: 16
                        color: theme.fgSubtle
                    }
                    ColumnLayout {
                        id: headCol
                        x: 26; y: 5
                        width: parent.width - 34
                        spacing: 1
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: r ? r.func : ""
                                font.family: root.mono
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: r && r.bec ? theme.fg : theme.fgMuted
                            }
                            Rectangle {
                                visible: r && r.focus
                                implicitWidth: pillText.implicitWidth + 14
                                implicitHeight: 18
                                radius: 9
                                color: Qt.alpha(theme.danger, 0.14)
                                Text {
                                    id: pillText
                                    anchors.centerIn: parent
                                    text: "raised here"
                                    color: theme.danger
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignRight
                                text: r ? r.file_short + ":" + r.line : ""
                                color: theme.fgSubtle
                                font.pixelSize: 12
                                elide: Text.ElideMiddle
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: r && r.code !== "" && !r.expanded
                            text: r ? r.code : ""
                            textFormat: Text.PlainText
                            font.family: root.mono
                            font.pixelSize: 12
                            color: theme.fgMuted
                            elide: Text.ElideRight
                        }
                    }
                }
                Item {
                    visible: r && r.expanded && r.context.length > 0
                    width: parent.width
                    height: visible ? ctx.implicitHeight + 6 : 0
                    CodeBlock {
                        id: ctx
                        x: 25
                        width: parent.width - 33
                        lines: r ? r.context : []
                    }
                }
            }
        }
    }
}
