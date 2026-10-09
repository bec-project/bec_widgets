import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import BecUi

// Tour guide overlay: dimming with a spotlight, "What's this?" outlines and one card per mode.
// Draws backend.state (see TourGuide.state) and reports clicks with backend.trigger(action, arg).
Item {
    id: root
    required property QtObject backend

    readonly property var st: backend.state
    readonly property string mode: st.mode || "hidden"
    readonly property bool hasSpot: !!st.spot && (mode === "step" || mode === "whatsthis")
    readonly property var anchorRect: (mode === "welcome" || mode === "hint") ? (st.anchor || null) : null
    readonly property real dim: mode === "step" ? 0.55 : mode === "hub" || mode === "done" ? 0.5
        : mode === "whatsthis" ? 0.28 : 0

    // Spotlight geometry, animated between steps.
    property real sx: st.spot ? st.spot.x : 0
    property real sy: st.spot ? st.spot.y : 0
    property real sw: st.spot ? st.spot.w : 0
    property real sh: st.spot ? st.spot.h : 0
    Behavior on sx { enabled: root.mode === "step"; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on sy { enabled: root.mode === "step"; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on sw { enabled: root.mode === "step"; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on sh { enabled: root.mode === "step"; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    function statusTone(status) {
        return status === "done" ? "success" : status === "in_progress" ? "warning" : "info"
    }

    // ---------------------------------------------------------------- input behind the card
    MouseArea {
        anchors.fill: parent
        enabled: root.mode !== "hidden"
        onClicked: {
            if (root.mode === "whatsthis")
                root.backend.trigger("anchor", "-1")
            else if (root.mode === "hub" || root.mode === "done")
                root.backend.trigger("close", "")
        }
    }

    // ---------------------------------------------------------------- dimming with a hole
    Shape {
        anchors.fill: parent
        visible: root.dim > 0
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: Qt.rgba(0, 0, 0, root.dim)
            strokeWidth: -1
            fillRule: ShapePath.OddEvenFill
            PathRectangle { x: 0; y: 0; width: root.width; height: root.height }
            PathRectangle {
                x: root.hasSpot ? root.sx : -10
                y: root.hasSpot ? root.sy : -10
                width: root.hasSpot ? root.sw : 1
                height: root.hasSpot ? root.sh : 1
                radius: 10
            }
        }
    }

    // ---------------------------------------------------------------- "What's this?" outlines
    Repeater {
        model: root.mode === "whatsthis" ? (root.st.anchors || []) : []
        delegate: Item {
            id: anchorItem
            required property var modelData
            required property int index
            x: modelData.rect.x
            y: modelData.rect.y
            width: modelData.rect.w
            height: modelData.rect.h
            visible: index !== root.st.selected
            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeColor: theme.primary
                    strokeWidth: 1.5
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [4, 3]
                    fillColor: "transparent"
                    PathRectangle { x: 1; y: 1; width: anchorItem.width - 2; height: anchorItem.height - 2; radius: 6 }
                }
            }
            Rectangle {
                width: 14; height: 14; radius: 7
                x: parent.width - 9; y: -5
                color: theme.primary
                Text {
                    anchors.centerIn: parent
                    text: "?"
                    color: theme.onPrimary
                    font.pixelSize: 10
                    font.bold: true
                }
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.WhatsThisCursor
                onClicked: root.backend.trigger("anchor", String(index))
            }
        }
    }

    // ---------------------------------------------------------------- rings
    component Ring: Item {
        id: ring
        property real rx
        property real ry
        property real rw
        property real rh
        x: rx; y: ry; width: rw; height: rh
        Rectangle { anchors.fill: parent; anchors.margins: -5; radius: 15; color: "transparent"; border.width: 10; border.color: Qt.alpha(theme.primary, 0.16) }
        Rectangle { anchors.fill: parent; anchors.margins: -3; radius: 13; color: "transparent"; border.width: 6; border.color: Qt.alpha(theme.primary, 0.28) }
        Rectangle { anchors.fill: parent; radius: 10; color: "transparent"; border.width: 2; border.color: theme.primary }
    }
    Ring {
        visible: root.hasSpot
        rx: root.sx; ry: root.sy; rw: root.sw; rh: root.sh
    }
    Ring {
        visible: root.anchorRect !== null
        rx: root.anchorRect ? root.anchorRect.x - 4 : 0
        ry: root.anchorRect ? root.anchorRect.y - 4 : 0
        rw: root.anchorRect ? root.anchorRect.w + 8 : 0
        rh: root.anchorRect ? root.anchorRect.h + 8 : 0
        MouseArea { anchors.fill: parent; onClicked: root.backend.trigger("hub", "") }
    }

    // ---------------------------------------------------------------- card
    readonly property var cardWidths: ({ step: 340, welcome: 380, hint: 330, hub: 560, done: 380, whatsthis: 320 })
    property var placement: ({ x: 0, y: 0, side: "center", pointer: 0 })

    function relayout() {
        if (mode === "hidden" || !loader.item)
            return
        placement = backend.place(mode, card.width, card.height)
        backend.setCardRect(placement.x, placement.y, card.width, card.height)
    }
    onStChanged: Qt.callLater(relayout)
    onWidthChanged: Qt.callLater(relayout)
    onHeightChanged: Qt.callLater(relayout)

    // pointer towards the spotlight or the help button
    Rectangle {
        visible: card.visible && ["right", "left", "below", "above"].indexOf(root.placement.side) >= 0
        width: 14; height: 14
        rotation: 45
        color: theme.card
        border.color: theme.border
        x: root.placement.side === "right" ? card.x - 7
            : root.placement.side === "left" ? card.x + card.width - 7
            : card.x + root.placement.pointer - 7
        y: root.placement.side === "below" ? card.y - 7
            : root.placement.side === "above" ? card.y + card.height - 7
            : card.y + root.placement.pointer - 7
    }

    Rectangle {
        id: card
        visible: root.mode !== "hidden"
        x: root.placement.x
        y: root.placement.y
        width: root.cardWidths[root.mode] || 340
        height: (loader.item ? loader.item.implicitHeight : 0) + 32
        radius: theme.radiusLarge + 2
        color: theme.card
        border.color: theme.border
        onHeightChanged: Qt.callLater(root.relayout)
        MouseArea { anchors.fill: parent }  // swallow clicks on the card background

        Loader {
            id: loader
            x: 18; y: 16
            width: parent.width - 36
            sourceComponent: root.mode === "step" ? stepCard
                : root.mode === "welcome" ? welcomeCard
                : root.mode === "hint" ? hintCard
                : root.mode === "hub" ? hubCard
                : root.mode === "done" ? doneCard
                : root.mode === "whatsthis" ? whatsCard : null
            onLoaded: Qt.callLater(root.relayout)
        }
    }

    // ---------------------------------------------------------------- building blocks
    component Caption: Text {
        color: theme.primary
        font.pixelSize: 11
        font.bold: true
        font.capitalization: Font.AllUppercase
        elide: Text.ElideRight
    }
    component Body: Text {
        color: theme.fg
        font.pixelSize: 13
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    component Muted: Text {
        color: theme.fgMuted
        font.pixelSize: 12
        wrapMode: Text.WordWrap
    }
    component Title: Text {
        color: theme.fg
        font.pixelSize: 16
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    component IconTile: Rectangle {
        property string iconName: "explore"
        property string tone: "primary"
        property int size: 36
        implicitWidth: size
        implicitHeight: size
        radius: size / 4
        color: (theme.name, theme.toneTint(tone))
        Icon { anchors.centerIn: parent; name: parent.iconName; size: parent.size - 14; color: (theme.name, theme.toneText(parent.tone)) }
    }
    component Header: RowLayout {
        property string caption: ""
        property string closeTip: "Close"
        spacing: 6
        Caption { text: parent.caption; Layout.fillWidth: true }
        IconButton { iconName: "close"; tip: parent.closeTip; compact: true; onClicked: root.backend.trigger("close", "") }
    }
    component TourRow: Rectangle {
        id: row
        required property var tour
        property bool detailed: false
        Layout.fillWidth: true
        implicitHeight: rowLayout.implicitHeight + 18
        radius: theme.radiusSmall + 2
        color: theme.sunken
        RowLayout {
            id: rowLayout
            anchors.fill: parent
            anchors.margins: 9
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 12
            IconTile {
                Layout.alignment: Qt.AlignTop
                iconName: row.tour.icon
                size: 34
                tone: row.tour.status === "done" ? "success" : "primary"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: row.tour.title; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                Muted { visible: row.detailed; text: row.tour.summary; Layout.fillWidth: true }
                RowLayout {
                    spacing: 8
                    Muted { text: row.tour.steps + " steps · " + row.tour.minutes + " min"; font.pixelSize: 11 }
                    StatusPill { visible: row.detailed; text: row.tour.label; tone: root.statusTone(row.tour.status); outlined: true }
                }
                LinearProgress {
                    visible: row.detailed && row.tour.status === "in_progress"
                    Layout.fillWidth: true
                    value: row.tour.progress
                    tone: "warning"
                    thickness: 4
                }
            }
            TextButton {
                compact: true
                text: row.tour.status === "new" ? "Start" : row.tour.status === "in_progress" ? "Resume" : "Replay"
                variant: row.tour.status === "in_progress" ? "primary" : "neutral"
                onClicked: root.backend.trigger(row.tour.status === "done" ? "start" : "resume", row.tour.id)
            }
        }
    }

    // ---------------------------------------------------------------- cards per mode
    Component {
        id: stepCard
        ColumnLayout {
            spacing: 10
            Header { caption: root.st.tourTitle || ""; closeTip: "Close tour (resume later)"; Layout.fillWidth: true }
            Title { text: root.st.title || "" }
            Body { text: root.st.text || "" }
            Rectangle {
                visible: !!root.st.hint
                Layout.fillWidth: true
                implicitHeight: hintRow.implicitHeight + 16
                radius: theme.radiusSmall
                color: (theme.name, theme.toneTint("primary"))
                RowLayout {
                    id: hintRow
                    anchors.fill: parent
                    anchors.margins: 8
                    anchors.leftMargin: 10
                    spacing: 8
                    Icon { name: "touch_app"; color: theme.primary; size: 18; Layout.alignment: Qt.AlignTop }
                    Text { text: "Try it: " + (root.st.hint || ""); color: theme.fg; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
            Row {
                Layout.fillWidth: true
                Layout.topMargin: 2
                spacing: 4
                Repeater {
                    model: root.st.count || 0
                    Rectangle {
                        required property int index
                        width: (parent.width - 4 * ((root.st.count || 1) - 1)) / (root.st.count || 1)
                        height: 6
                        radius: 3
                        color: index <= root.st.index ? theme.primary : theme.track
                        Behavior on color { ColorAnimation { duration: 160 } }
                    }
                }
            }
            RowLayout {
                spacing: 8
                Muted { text: ((root.st.index || 0) + 1) + " of " + (root.st.count || 1) }
                Item { Layout.fillWidth: true }
                TextButton { text: "Back"; variant: "ghost"; compact: true; enabled: (root.st.index || 0) > 0; onClicked: root.backend.trigger("back", "") }
                TextButton {
                    text: (root.st.index || 0) >= (root.st.count || 1) - 1 ? "Finish" : "Next"
                    variant: "primary"
                    compact: true
                    onClicked: root.backend.trigger("next", "")
                }
            }
        }
    }

    Component {
        id: welcomeCard
        ColumnLayout {
            spacing: 10
            Header { caption: "Welcome to BEC"; closeTip: "Close (show again next time)"; Layout.fillWidth: true }
            Title { text: "New here? Let us show you around." }
            Muted { text: "Short tours of a minute or two, one task each. Pick one now, or find them later under Help (F1)."; Layout.fillWidth: true }
            Repeater {
                model: (root.st.tours || []).slice(0, 4)
                TourRow { required property var modelData; tour: modelData }
            }
            RowLayout {
                spacing: 8
                TextButton { text: "Don't show again"; variant: "ghost"; compact: true; onClicked: root.backend.trigger("never", "") }
                Item { Layout.fillWidth: true }
                TextButton { text: "Later"; compact: true; onClicked: root.backend.trigger("close", "") }
                TextButton {
                    readonly property var first: (root.st.tours || []).filter(t => t.status !== "done")[0]
                    visible: !!first
                    text: "Show me around"
                    variant: "primary"
                    compact: true
                    onClicked: root.backend.trigger("resume", first.id)
                }
            }
        }
    }

    Component {
        id: hintCard
        ColumnLayout {
            id: hintRoot
            readonly property var tour: root.st.tour || ({})
            spacing: 10
            RowLayout {
                spacing: 12
                IconTile { iconName: hintRoot.tour.icon || "explore"; Layout.alignment: Qt.AlignTop }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: "New here? " + (hintRoot.tour.title || ""); color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Muted { text: "A " + (hintRoot.tour.steps || 0) + "-step tour of this view, about " + (hintRoot.tour.minutes || 1) + " min."; Layout.fillWidth: true }
                }
                IconButton { iconName: "close"; tip: "Not now"; compact: true; Layout.alignment: Qt.AlignTop; onClicked: root.backend.trigger("close", "") }
            }
            RowLayout {
                spacing: 8
                Item { Layout.fillWidth: true }
                TextButton { text: "Not now"; variant: "ghost"; compact: true; onClicked: root.backend.trigger("close", "") }
                TextButton { text: "Start tour"; variant: "primary"; compact: true; onClicked: root.backend.trigger("start", (root.st.tour || {}).id || "") }
            }
        }
    }

    Component {
        id: hubCard
        ColumnLayout {
            spacing: 10
            RowLayout {
                spacing: 12
                IconTile { iconName: "school"; size: 40; Layout.alignment: Qt.AlignTop }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: "Tours"; color: theme.fg; font.pixelSize: 20; font.weight: Font.DemiBold }
                    Muted { text: "Short guided tours, one task each. Your progress is saved."; Layout.fillWidth: true }
                }
                IconButton { iconName: "close"; tip: "Close"; compact: true; Layout.alignment: Qt.AlignTop; onClicked: root.backend.trigger("close", "") }
            }
            RowLayout {
                spacing: 10
                LinearProgress { Layout.fillWidth: true; tone: "success"; value: (root.st.done || 0) / Math.max(1, root.st.total || 1) }
                Muted { text: (root.st.done || 0) + " of " + (root.st.total || 0) + " done" }
            }
            Repeater {
                model: root.st.tours || []
                TourRow { required property var modelData; tour: modelData; detailed: true }
            }
            Divider {}
            RowLayout {
                spacing: 8
                TextButton { text: "What's this?  Shift+F1"; iconName: "help_center"; compact: true; onClicked: root.backend.trigger("whatsthis", "") }
                Item { Layout.fillWidth: true }
                TextButton { text: "Reset progress"; variant: "ghost"; compact: true; onClicked: root.backend.trigger("reset", "") }
            }
        }
    }

    Component {
        id: doneCard
        ColumnLayout {
            spacing: 10
            RowLayout {
                spacing: 12
                IconTile { iconName: "check_circle"; tone: "success"; size: 40; Layout.alignment: Qt.AlignTop }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Title { text: "Tour complete" }
                    Muted { text: "You finished “" + (root.st.finished || "") + "”."; Layout.fillWidth: true }
                }
            }
            Divider { visible: !!root.st.next }
            Muted { visible: !!root.st.next; text: "UP NEXT"; font.pixelSize: 11 }
            Text {
                visible: !!root.st.next
                text: root.st.next ? root.st.next.title + " · " + root.st.next.steps + " steps" : ""
                color: theme.fg; font.pixelSize: 13; font.weight: Font.Medium
            }
            RowLayout {
                spacing: 8
                TextButton { text: "All tours"; variant: "ghost"; compact: true; onClicked: root.backend.trigger("hub", "") }
                Item { Layout.fillWidth: true }
                TextButton { text: "Close"; compact: true; onClicked: root.backend.trigger("close", "") }
                TextButton {
                    visible: !!root.st.next
                    text: "Start next"; variant: "primary"; compact: true
                    onClicked: root.backend.trigger("resume", root.st.next.id)
                }
            }
        }
    }

    Component {
        id: whatsCard
        ColumnLayout {
            id: whatsRoot
            readonly property var anchors_: root.st.anchors || []
            readonly property int selected: root.st.selected === undefined ? -1 : root.st.selected
            readonly property var current: selected >= 0 && selected < anchors_.length ? anchors_[selected] : null
            spacing: 10
            RowLayout {
                visible: !whatsRoot.current
                spacing: 10
                Icon { name: "help_center"; color: theme.primary; size: 20 }
                Body { text: "What's this? Click any outlined control (" + whatsRoot.anchors_.length + " on screen)." }
                TextButton { text: "Done"; compact: true; onClicked: root.backend.trigger("close", "") }
            }
            Header { visible: !!whatsRoot.current; caption: "What's this?"; closeTip: "Leave What's this"; Layout.fillWidth: true }
            Text {
                visible: !!whatsRoot.current
                text: whatsRoot.current ? whatsRoot.current.title : ""
                color: theme.fg; font.pixelSize: 15; font.weight: Font.DemiBold
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            Body { visible: !!whatsRoot.current; text: whatsRoot.current ? whatsRoot.current.text : "" }
            RowLayout {
                visible: !!whatsRoot.current && !!whatsRoot.current.tour_id
                spacing: 8
                Muted { text: whatsRoot.current ? "Part of “" + whatsRoot.current.tour_title + "”" : ""; Layout.fillWidth: true }
                TextButton { text: "Take the tour"; variant: "primary"; compact: true; onClicked: root.backend.trigger("resume", whatsRoot.current.tour_id) }
            }
        }
    }
}
