import QtQuick
import QtQuick.Controls.Basic
import BecUi

// Command palette card. Twin of command_palette_qwidget.PaletteCardWidget; all state lives in
// the Python CommandPaletteController passed in as `backend`.
Item {
    id: root
    required property var backend
    required property var paletteModel
    property int margin: 24

    readonly property int rowHeight: 46
    readonly property int headerHeight: 28

    // called from Python every time the palette opens
    function opened() {
        field.forceActiveFocus()
        field.selectAll()
    }

    component KeyCap: Rectangle {
        property alias text: capLabel.text
        implicitWidth: capLabel.implicitWidth + 12
        implicitHeight: 20
        radius: 5
        color: theme.field
        border.color: theme.border
        Text {
            id: capLabel
            anchors.centerIn: parent
            color: theme.fgMuted
            font.pixelSize: 11
            font.weight: Font.DemiBold
        }
    }

    // clicks next to the card (on the shadow margin) close the palette like the dimmed window
    MouseArea {
        anchors.fill: parent
        onPressed: root.backend.request_dismiss()
    }

    // soft layered shadow; MultiEffect is unavailable on the software scene graph
    Repeater {
        model: 6
        Rectangle {
            required property int index
            x: root.margin - index * 3
            y: root.margin + 10 - index * 2
            width: card.width + index * 6
            height: card.height + index * 5
            radius: 12 + index * 3
            color: "black"
            opacity: (theme.dark ? 0.11 : 0.045) * (1 - index / 7)
        }
    }

    Rectangle {
        id: card
        x: root.margin
        y: root.margin
        width: root.width - 2 * root.margin
        height: root.height - 2 * root.margin
        radius: 12
        color: theme.card
        border.color: theme.border
        clip: true

        // swallow clicks so they do not reach the dismiss area
        MouseArea { anchors.fill: parent }

        Column {
            id: header
            width: parent.width

            Item {
                width: parent.width
                height: 54
                Icon {
                    id: searchIcon
                    name: "search"
                    size: 20
                    color: theme.fgMuted
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: 2
                }
                TextField {
                    id: field
                    anchors.left: searchIcon.right
                    anchors.leftMargin: 10
                    anchors.right: escCap.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: searchIcon.verticalCenter
                    background: null
                    padding: 0
                    color: theme.fg
                    placeholderText: "Search actions, widgets, devices and workspaces…"
                    placeholderTextColor: theme.fgSubtle
                    selectionColor: theme.primary
                    selectedTextColor: theme.onPrimary
                    font.pixelSize: 16
                    selectByMouse: true
                    onTextEdited: root.backend.query = text

                    Connections {
                        target: root.backend
                        function onQueryChanged() {
                            if (field.text !== root.backend.query)
                                field.text = root.backend.query
                        }
                    }

                    Keys.onPressed: (event) => {
                        const b = root.backend
                        switch (event.key) {
                        case Qt.Key_Down: b.move(1); break
                        case Qt.Key_Up: b.move(-1); break
                        case Qt.Key_PageDown: b.move_page(8); break
                        case Qt.Key_PageUp: b.move_page(-8); break
                        case Qt.Key_Return:
                        case Qt.Key_Enter: b.execute(-1); break
                        case Qt.Key_Tab: b.cycle_scope(1); break
                        case Qt.Key_Backtab: b.cycle_scope(-1); break
                        case Qt.Key_Escape: b.request_dismiss(); break
                        case Qt.Key_Backspace:
                            if (field.text !== "") return
                            b.clear_scope()
                            break
                        default: return
                        }
                        event.accepted = true
                    }
                }
                KeyCap {
                    id: escCap
                    text: "esc"
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: searchIcon.verticalCenter
                }
            }

            Row {
                leftPadding: 14
                bottomPadding: 10
                spacing: 6
                Repeater {
                    model: root.backend.scopes
                    Rectangle {
                        required property var modelData
                        readonly property bool active: root.backend.scope === modelData.id
                        height: 25
                        width: chipLabel.implicitWidth + 24
                        radius: 12.5
                        color: active ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.18))
                                      : chipMouse.containsMouse ? theme.hover : "transparent"
                        border.color: active ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.5))
                                             : theme.border
                        Text {
                            id: chipLabel
                            anchors.centerIn: parent
                            text: (modelData.label + "  " + modelData.prefix).trim()
                            color: parent.active ? theme.primary : theme.fgMuted
                            font.pixelSize: 12
                            font.weight: parent.active ? Font.DemiBold : Font.Normal
                        }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.backend.scope = modelData.id
                                field.forceActiveFocus()
                            }
                        }
                    }
                }
            }

            Rectangle { width: parent.width; height: 1; color: theme.border }
        }

        ListView {
            id: list
            anchors.top: header.bottom
            anchors.bottom: footer.top
            anchors.left: parent.left
            anchors.right: parent.right
            clip: true
            model: root.paletteModel
            currentIndex: root.backend.currentIndex
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0
            visible: count > 0
            onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
            onCountChanged: positionViewAtBeginning()

            ScrollBar.vertical: ScrollBar {
                width: 8
                visible: list.contentHeight > list.height
                contentItem: Rectangle { implicitWidth: 4; radius: 2; color: theme.track }
            }

            // rows carry an empty section while searching; changing section.property at
            // runtime instead crashes the ListView
            section.property: "section"
            section.delegate: Item {
                required property string section
                width: ListView.view.width
                height: section === "" ? 0 : root.headerHeight
                visible: section !== ""
                Text {
                    x: 18
                    y: 8
                    height: parent.height - 8
                    verticalAlignment: Text.AlignVCenter
                    text: parent.section.toUpperCase()
                    color: theme.fgSubtle
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
            }

            delegate: Item {
                id: row
                required property int index
                required property string titleRich
                required property string subtitle
                required property string icon
                required property string category
                required property string shortcut
                required property string hint
                readonly property bool current: ListView.isCurrentItem
                width: ListView.view.width
                height: root.rowHeight

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 1
                    anchors.bottomMargin: 1
                    radius: 8
                    color: row.current ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.16))
                                       : rowMouse.containsMouse ? theme.hover : "transparent"
                }
                Rectangle {
                    id: tile
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30
                    height: 30
                    radius: 7
                    color: row.current ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.24)) : theme.track
                    Icon {
                        anchors.centerIn: parent
                        name: row.icon
                        size: 18
                        color: row.current ? theme.primary : theme.fgMuted
                    }
                }
                Column {
                    anchors.left: tile.right
                    anchors.leftMargin: 12
                    anchors.right: trailing.left
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text {
                        width: parent.width
                        text: row.titleRich
                        textFormat: Text.StyledText
                        color: theme.fg
                        font.pixelSize: 13
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        visible: row.subtitle !== ""
                        text: row.subtitle
                        color: theme.fgSubtle
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }
                Row {
                    id: trailing
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Text {
                        visible: row.current
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.hint
                        color: theme.fgMuted
                        font.pixelSize: 12
                    }
                    KeyCap { visible: row.current; text: "↵" }
                    KeyCap { visible: !row.current && row.shortcut !== ""; text: row.shortcut }
                    Text {
                        visible: !row.current && row.shortcut === "" && !root.backend.sectioned
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.category
                        color: theme.fgSubtle
                        font.pixelSize: 11
                    }
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.backend.execute(row.index)
                }
            }
        }

        Column {
            anchors.centerIn: list
            anchors.verticalCenterOffset: -20
            visible: list.count === 0
            spacing: 8
            Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "search_off"; size: 32; color: theme.fgSubtle }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.backend.emptyText
                color: theme.fgMuted
                font.pixelSize: 14
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Type  >  for actions,  +  for widgets,  @  for devices,  #  for workspaces"
                color: theme.fgSubtle
                font.pixelSize: 12
            }
        }

        Rectangle {
            id: footer
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 1
            height: 31
            color: theme.field
            bottomLeftRadius: 11
            bottomRightRadius: 11
            Rectangle { width: parent.width; height: 1; color: theme.border }
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14
                Repeater {
                    model: [["↑↓", "navigate"], ["↵", "run"], ["tab", "scope"], ["esc", "close"]]
                    Text {
                        required property var modelData
                        textFormat: Text.StyledText
                        text: "<b><font color='" + theme.fgMuted + "'>" + modelData[0] + "</font></b> " + modelData[1]
                        color: theme.fgSubtle
                        font.pixelSize: 11
                    }
                }
            }
            Text {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                visible: root.backend.resultCount > 0
                text: root.backend.resultCount + (root.backend.resultCount === 1 ? " result" : " results")
                color: theme.fgSubtle
                font.pixelSize: 11
            }
        }
    }
}
