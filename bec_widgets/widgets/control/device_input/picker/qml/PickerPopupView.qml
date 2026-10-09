import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Searchable, grouped device/signal list with a live-value footer.
// All state lives in the Python PickerController; `backend` forwards it.
Rectangle {
    id: root
    required property var backend

    color: theme.card
    radius: 10
    border.color: theme.border
    border.width: 1

    function badgeTone(badge) {
        switch (badge) {
        case "monitored":
        case "hinted": return theme.primary
        case "async": return theme.highlight
        case "on_request": return theme.warning
        case "continuous":
        case "normal": return theme.success
        default: return theme.fgMuted
        }
    }

    Connections {
        target: root.backend
        function onFocusRequested() { search.forceActiveFocus(); search.cursorPosition = search.text.length }
        function onHighlightChanged() {
            const row = root.backend.highlight
            if (row < 0) return
            // keep the section header of the highlighted row in view as well
            if (row > 0) list.positionViewAtIndex(row - 1, ListView.Contain)
            list.positionViewAtIndex(row, ListView.Contain)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        // ---- search -------------------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.topMargin: 7
            Layout.bottomMargin: 7
            spacing: 8
            Icon { name: "search"; size: 18; color: theme.fgMuted }
            TextField {
                id: search
                Layout.fillWidth: true
                text: root.backend.query
                placeholderText: root.backend.placeholder
                placeholderTextColor: theme.fgSubtle
                color: theme.fg
                selectionColor: theme.primary
                selectedTextColor: theme.onPrimary
                font.pixelSize: 14
                leftPadding: 0
                implicitHeight: 32
                verticalAlignment: TextInput.AlignVCenter
                background: null
                selectByMouse: true
                onTextEdited: root.backend.setQuery(text)
                Keys.onPressed: (event) => {
                    switch (event.key) {
                    case Qt.Key_Down:
                    case Qt.Key_Tab: root.backend.move(1); break
                    case Qt.Key_Up:
                    case Qt.Key_Backtab: root.backend.move(-1); break
                    case Qt.Key_PageDown: root.backend.page(1); break
                    case Qt.Key_PageUp: root.backend.page(-1); break
                    case Qt.Key_Return:
                    case Qt.Key_Enter: root.backend.accept(-1); break
                    case Qt.Key_Escape: root.backend.dismiss(); break
                    default: return
                    }
                    event.accepted = true
                }
            }
            Text {
                text: root.backend.summary
                color: theme.fgSubtle
                font.pixelSize: 12
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }

        // ---- rows -----------------------------------------------------------------------
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.backend.rows
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 8 }

            delegate: Item {
                id: row
                required property int index
                required property string rowType
                required property string titleRich
                required property string title
                required property string subtitle
                required property string badge
                required property string icon
                required property bool isCurrent
                required property int count
                readonly property bool highlighted: index === root.backend.highlight

                width: ListView.view.width
                height: rowType === "header" ? 28 : rowType === "empty" ? 96 : 34

                // header
                RowLayout {
                    visible: row.rowType === "header"
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 4
                    spacing: 6
                    Icon { visible: row.icon !== ""; name: row.icon; size: 14; color: theme.fgSubtle }
                    Text {
                        text: row.title.toUpperCase()
                        color: theme.fgSubtle
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.6
                    }
                    Text {
                        visible: row.count > 0
                        text: row.count
                        color: theme.fgSubtle
                        font.pixelSize: 11
                        font.letterSpacing: 0.6
                    }
                    Item { Layout.fillWidth: true }
                }

                // empty state
                Column {
                    visible: row.rowType === "empty"
                    anchors.centerIn: parent
                    spacing: 8
                    Icon { anchors.horizontalCenter: parent.horizontalCenter; name: row.icon; size: 24; color: theme.fgSubtle }
                    Text { text: row.title; color: theme.fgMuted; font.pixelSize: 13 }
                }

                // item
                Rectangle {
                    visible: row.rowType === "item"
                    anchors.fill: parent
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    anchors.topMargin: 1
                    anchors.bottomMargin: 1
                    radius: 6
                    color: row.highlighted ? theme.hover : "transparent"

                    Rectangle {
                        visible: row.isCurrent
                        width: 3; radius: 1.5
                        height: parent.height - 14
                        anchors.verticalCenter: parent.verticalCenter
                        color: theme.primary
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 8
                        Icon {
                            name: row.icon
                            size: 16
                            color: row.isCurrent ? theme.primary : theme.fgMuted
                        }
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Text {
                                id: titleText
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, parent.width)
                                text: row.titleRich
                                textFormat: Text.StyledText
                                color: theme.fg
                                font.pixelSize: 13
                                font.weight: row.isCurrent ? Font.Medium : Font.Normal
                                elide: Text.ElideRight
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                x: titleText.width + 8
                                width: Math.max(0, parent.width - x)
                                visible: width > 24
                                text: row.subtitle
                                color: theme.fgSubtle
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle {
                            visible: row.badge !== ""
                            implicitWidth: badgeLabel.implicitWidth + 14
                            implicitHeight: 18
                            radius: 9
                            readonly property color tone: root.badgeTone(row.badge)
                            color: Qt.rgba(tone.r, tone.g, tone.b, 0.18)
                            Text {
                                id: badgeLabel
                                anchors.centerIn: parent
                                text: row.badge
                                color: parent.tone
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.backend.hover(row.index)
                        onClicked: root.backend.accept(row.index)
                    }
                }
            }
        }

        // ---- footer ---------------------------------------------------------------------
        Rectangle { Layout.fillWidth: true; height: 1; color: theme.border; visible: footer.visible }
        ColumnLayout {
            id: footer
            readonly property var detail: root.backend.detail
            visible: detail.title !== undefined
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            spacing: 2
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Icon { name: footer.detail.icon || "sensors"; size: 16; color: theme.fgMuted }
                Text {
                    Layout.fillWidth: true
                    text: footer.detail.title || ""
                    color: theme.fg
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    readonly property bool live: footer.detail.valueState === "live" && footer.detail.value !== ""
                    text: live ? footer.detail.value + (footer.detail.valueTime ? "  ·  " + footer.detail.valueTime : "")
                               : footer.detail.valueState === "loading" ? "reading…" : "no value yet"
                    color: live ? theme.success : theme.fgSubtle
                    font.pixelSize: 12
                    font.family: "monospace"
                }
            }
            Text {
                readonly property string line: [footer.detail.subtitle, footer.detail.details].filter(p => p).join(" · ")
                visible: line !== ""
                Layout.fillWidth: true
                text: line
                color: theme.fgMuted
                font.pixelSize: 12
                elide: Text.ElideRight
            }
            Text {
                Layout.topMargin: 4
                text: "↑↓ move   ↵ select   esc close"
                color: theme.fgSubtle
                font.pixelSize: 11
            }
        }
    }
}
