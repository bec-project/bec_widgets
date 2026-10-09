import QtQuick
import BecUi

// Navigation panel of the main app. The rows keep their geometry in the rail (56 px) and in the
// drawer (256 px); the surface only widens over the views and the labels fade.
Item {
    id: root
    required property var backend

    readonly property real p: backend.progress
    readonly property int railW: backend.railWidth
    readonly property int drawerW: backend.drawerWidth

    clip: true

    function lerp(a, b, t) { return a + (b - a) * t }
    function labelAlpha() { return Math.max(0, (root.p - 0.35) / 0.65) }
    function miniAlpha() { return Math.max(0, 1 - root.p * 2) }

    function focusRow(id) {
        const reps = [topRepeater, bottomRepeater]
        for (let r = 0; r < reps.length; ++r) {
            for (let i = 0; i < reps[r].count; ++i) {
                const item = reps[r].itemAt(i)
                if (item && item.entry.id === id) {
                    item.forceActiveFocus(Qt.TabFocusReason)
                    if (r === 0) flick.ensureVisible(item)
                    return
                }
            }
        }
    }

    Connections {
        target: root.backend
        function onFocusRequested(id) { root.focusRow(id) }
    }

    Rectangle { anchors.fill: parent; color: theme.card }
    Rectangle {
        width: 1; height: parent.height; anchors.right: parent.right
        color: theme.border
    }

    // ------------------------------------------------------------ header
    component HeaderButton: Item {
        id: hb
        property string icon: ""
        property int iconSize: 22
        property bool checked: false
        property bool filled: false
        property bool muted: false
        property string tip: ""
        signal clicked()
        activeFocusOnTab: true
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                    || event.key === Qt.Key_Space) { hb.clicked(); event.accepted = true }
            else if (event.key === Qt.Key_Escape) { root.backend.escape(); event.accepted = true }
            else if (event.key === Qt.Key_Down) {
                root.focusRow(root.backend.moveFocus("", 1)); event.accepted = true
            }
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: 1; radius: 8
            color: hbMouse.pressed || hb.checked ? theme.pressed
                 : hbMouse.containsMouse ? theme.hover : "transparent"
            border.width: hb.activeFocus && root.backend.keyboardFocus ? 2 : 0
            border.color: theme.primary
        }
        Icon {
            anchors.centerIn: parent
            name: hb.icon; size: hb.iconSize; filled: hb.filled
            color: hb.muted ? theme.fgMuted : theme.fg
        }
        MouseArea {
            id: hbMouse
            anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: hb.clicked()
            onEntered: hbTip.restart()
            onExited: { hbTip.stop(); root.backend.hideTooltip() }
        }
        Timer {
            id: hbTip; interval: 700
            onTriggered: {
                const pt = hb.mapToItem(root, hb.width, hb.height / 2)
                root.backend.showText(hb.tip, pt.x, pt.y)
            }
        }
    }

    Item {
        id: header
        width: parent.width; height: root.backend.headerHeight

        HeaderButton {
            objectName: "NavMenuButton"
            x: 8; y: (header.height - 40) / 2; width: 40; height: 40
            icon: root.p > 0.5 ? "menu_open" : "menu"
            tip: root.backend.toggleTooltip
            onClicked: root.backend.toggleExpanded()
        }
        Text {
            x: 60; width: 120; height: header.height
            verticalAlignment: Text.AlignVCenter
            text: root.backend.title
            color: theme.fg
            opacity: root.labelAlpha()
            visible: opacity > 0
            font.pixelSize: 14; font.weight: Font.DemiBold
        }
        HeaderButton {
            objectName: "NavPinButton"
            x: root.drawerW - 8 - 32; y: (header.height - 32) / 2; width: 32; height: 32
            visible: root.p > 0 && root.backend.pinAvailable
            activeFocusOnTab: root.p > 0.5 && root.backend.pinAvailable
            icon: "keep"; iconSize: 18
            filled: root.backend.pinned; checked: root.backend.pinned
            muted: !root.backend.pinned
            tip: root.backend.pinned ? "Unpin: close the panel after choosing a view"
                                     : "Pin: keep the panel open next to the views"
            onClicked: root.backend.setPinned(!root.backend.pinned)
        }
    }

    // ------------------------------------------------------------ rows
    component NavRow: Item {
        id: row
        required property var modelData
        readonly property var entry: modelData
        readonly property bool active: root.backend.activeIds.indexOf(entry.id) >= 0
        readonly property bool hovered: mouse.containsMouse
        readonly property bool focusVisible: activeFocus && root.backend.keyboardFocus
        readonly property bool isItem: entry.kind === "item" || entry.kind === "action"
        readonly property color textColor: active ? theme.onPrimary : theme.fg
        readonly property color subColor: active ? Qt.rgba(theme.onPrimary.r, theme.onPrimary.g,
                                                           theme.onPrimary.b, 0.78)
                                                 : theme.fgMuted
        readonly property bool showShortcut: entry.shortcut !== "" && (hovered || focusVisible)

        width: parent ? parent.width : root.width
        height: entry.height
        activeFocusOnTab: entry.focusable
        Accessible.role: Accessible.Button
        Accessible.name: entry.title + (active ? " (current view)" : "")
        Accessible.description: entry.subtitle

        Keys.onPressed: (event) => {
            const steps = { [Qt.Key_Up]: -1, [Qt.Key_Down]: 1,
                            [Qt.Key_Home]: -1000000, [Qt.Key_End]: 1000000 }
            if (event.key in steps) {
                root.focusRow(root.backend.moveFocus(entry.id, steps[event.key]))
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                       || event.key === Qt.Key_Space) {
                root.backend.activate(entry.id)
            } else if (event.key === Qt.Key_Escape) {
                root.backend.escape()
            } else if (event.key === Qt.Key_Right && !root.backend.opened) {
                root.backend.expand()
            } else if (event.key === Qt.Key_Left && root.backend.opened) {
                root.backend.collapse()
            } else {
                return
            }
            event.accepted = true
        }

        // separator
        Rectangle {
            visible: row.entry.kind === "separator"
            x: 10; width: row.width - 20; height: 1; y: Math.floor(row.height / 2)
            color: theme.border
        }

        // section: a short divider in the rail, a heading in the drawer
        Rectangle {
            visible: row.entry.kind === "section"
            x: 14; width: root.railW - 28; height: 1; y: Math.floor(row.height / 2)
            color: theme.border; opacity: 1 - root.p
        }
        Text {
            visible: row.entry.kind === "section" && opacity > 0
            x: 16; width: root.drawerW - 32; height: row.height
            verticalAlignment: Text.AlignVCenter
            text: row.entry.title.toUpperCase()
            color: theme.fgSubtle; opacity: root.labelAlpha()
            font.pixelSize: 11; font.weight: Font.DemiBold
        }

        // item highlight: a pill behind the icon in the rail, the whole row in the drawer
        Rectangle {
            visible: row.isItem
            x: 8
            y: root.lerp(5, 2, root.p)
            width: root.lerp(root.railW - 16, row.width - 16, root.p)
            height: root.lerp(28, row.height - 4, root.p)
            radius: root.lerp(14, 8, root.p)
            color: row.active && row.entry.kind === "item" ? theme.primary
                 : mouse.pressed ? theme.pressed
                 : row.hovered ? theme.hover : "transparent"
            border.width: row.focusVisible ? 2 : 0
            border.color: row.active ? theme.onPrimary : theme.primary
        }
        Icon {
            visible: row.isItem
            x: (root.railW - 22) / 2
            y: root.lerp(8, (row.height - 22) / 2, root.p)
            size: 22
            name: row.entry.icon
            filled: row.active
            color: row.active ? theme.onPrimary : theme.fg
        }
        Text {
            visible: row.isItem && opacity > 0
            x: 2; y: 35; width: root.railW - 4; height: 16
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            text: row.entry.miniText
            color: row.active ? theme.fg : theme.fgMuted
            opacity: root.miniAlpha()
            font.pixelSize: 10; font.weight: row.active ? Font.DemiBold : Font.Normal
        }
        Text {
            id: shortcutText
            visible: row.isItem && row.showShortcut && opacity > 0
            x: root.drawerW - 16 - implicitWidth; height: row.height
            verticalAlignment: Text.AlignVCenter
            text: row.entry.shortcut
            color: row.subColor; opacity: root.labelAlpha()
            font.pixelSize: 11
        }
        Item {
            visible: row.isItem && root.labelAlpha() > 0
            opacity: root.labelAlpha()
            x: root.railW
            width: root.drawerW - 16 - root.railW
                   - (row.showShortcut ? shortcutText.implicitWidth + 8 : 0)
            height: row.height
            Text {
                y: row.entry.subtitle !== "" ? 9 : 0
                width: parent.width; height: row.entry.subtitle !== "" ? 20 : row.height
                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                text: row.entry.title; color: row.textColor
                font.pixelSize: 13
                font.weight: row.active ? Font.DemiBold : Font.Medium
            }
            Text {
                visible: row.entry.subtitle !== ""
                y: 28; width: parent.width; height: 18
                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                text: row.entry.subtitle; color: row.subColor
                font.pixelSize: 11
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            enabled: row.isItem
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.backend.activateFromMouse(row.entry.id)
            onEntered: tipTimer.restart()
            onExited: { tipTimer.stop(); root.backend.hideTooltip() }
        }
        Timer {
            id: tipTimer; interval: 700
            onTriggered: {
                const pt = row.mapToItem(root, root.railW, row.height / 2)
                root.backend.showTooltip(row.entry.id, pt.x, pt.y)
            }
        }
    }

    Flickable {
        id: flick
        y: header.height
        width: parent.width - 1
        height: bottomBox.y - y
        contentHeight: topColumn.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        function ensureVisible(item) {
            if (item.y < contentY) contentY = item.y
            else if (item.y + item.height > contentY + height)
                contentY = item.y + item.height - height
        }

        Column {
            id: topColumn
            width: flick.width
            Repeater {
                id: topRepeater
                model: root.backend.topEntries
                delegate: NavRow {}
            }
        }
    }

    Item {
        id: bottomBox
        visible: bottomRepeater.count > 0
        width: parent.width - 1
        height: visible ? bottomColumn.height + 6 : 0
        y: root.height - 6 - height

        Rectangle {
            x: 10; width: parent.width - 20; height: 1
            color: theme.border
        }
        Column {
            id: bottomColumn
            y: 6
            width: parent.width
            Repeater {
                id: bottomRepeater
                model: root.backend.bottomEntries
                delegate: NavRow {}
            }
        }
    }
}
