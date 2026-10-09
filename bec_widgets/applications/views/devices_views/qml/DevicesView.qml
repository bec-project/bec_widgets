import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi
import "Tones.js" as Tones

// Devices for users: find any device, watch it live, move it and change its settings.
// A compact list on the left; the device fills the rest with a live panel next to its
// settings and readings. backend: DevicesBackend.
Rectangle {
    id: root
    required property QtObject backend
    readonly property var d: backend.detail
    readonly property bool hasDevice: backend.detailName !== ""
    readonly property string mono: "DejaVu Sans Mono"

    color: theme.bg

    component Panel: Rectangle {
        id: panel
        property string title: ""
        property string hint: ""
        default property alias content: body.data
        Layout.fillWidth: true
        implicitHeight: body.implicitHeight + 28
        radius: 8
        color: theme.card
        border.color: theme.border
        ColumnLayout {
            id: body
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; topMargin: 12 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                SectionTitle { text: panel.title; Layout.topMargin: 0 }
                Item { Layout.fillWidth: true }
                Text { text: panel.hint; color: theme.fgSubtle; font.pixelSize: 11 }
            }
        }
    }

    component SignalRow: ColumnLayout {
        id: sig
        required property string key
        required property bool settable
        required property string doc
        required property string valueText
        required property string statusText
        required property string statusTone
        Layout.fillWidth: true
        spacing: 2
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: sig.key
                color: theme.fg
                font.family: root.mono
                font.pixelSize: 12
                Layout.preferredWidth: 140
                elide: Text.ElideRight
                HoverHandler { id: keyHover }
                ToolTip.visible: keyHover.hovered && sig.doc !== ""
                ToolTip.text: sig.doc
            }
            Text {
                text: sig.valueText
                color: theme.fg
                font.family: root.mono
                font.pixelSize: 12
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            InputField {
                id: newValue
                visible: sig.settable
                Layout.preferredWidth: 120
                placeholderText: "New value"
                Accessible.name: "New value for " + sig.key
                onAccepted: root.backend.setSignal(sig.key, text)
            }
            TextButton {
                visible: sig.settable
                text: "Set"
                onClicked: root.backend.setSignal(sig.key, newValue.text)
            }
        }
        Text {
            visible: sig.statusText !== ""
            text: sig.statusText
            color: Tones.color(theme, sig.statusTone)
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            onTextChanged: if (sig.statusTone === "ok") newValue.clear()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- top bar ---------------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 46
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 10
                Icon { name: "memory"; size: 18; color: theme.fgMuted }
                Text { text: "Devices"; color: theme.fg; font.pixelSize: 13; font.weight: Font.Bold }
                Item { implicitWidth: 8 }
                Segmented {
                    model: root.backend.kinds
                    current: root.backend.kind
                    onPicked: (key) => root.backend.setKind(key)
                }
                Item { Layout.fillWidth: true }
                Chip {
                    text: "Device setup: staff only"
                    iconName: "lock"
                    HoverHandler { id: lockHover }
                    ToolTip.visible: lockHover.hovered
                    ToolTip.text: "Adding devices and changing the session is in Device Config"
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ---- device list -------------------------------------------------------------------
            Rectangle {
                Layout.preferredWidth: 360
                Layout.fillHeight: true
                color: theme.card
                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 10
                    spacing: 6
                    InputField {
                        id: search
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        placeholderText: "Search name, tag or description"
                        Accessible.name: "Search devices"
                        onTextChanged: debounce.restart()
                        Timer { id: debounce; interval: 120; onTriggered: root.backend.setQuery(search.text) }
                    }
                    Text {
                        text: root.backend.shownText
                        color: theme.fgSubtle
                        font.pixelSize: 11
                        Layout.leftMargin: 14
                    }
                    ListView {
                        id: list
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.backend.rows
                        boundsBehavior: Flickable.StopAtBounds
                        focus: true
                        keyNavigationEnabled: true
                        ScrollBar.vertical: ScrollBar {}
                        currentIndex: root.backend.selectedIndex
                        onCurrentIndexChanged: if (currentItem) root.backend.select(currentItem.rowName)
                        Connections {
                            target: root.backend
                            function onChanged() { if (root.backend.selectedIndex >= 0) list.positionViewAtIndex(root.backend.selectedIndex, ListView.Contain) }
                        }
                        delegate: Rectangle {
                            id: rowItem
                            required property int index
                            required property string name
                            required property string what
                            required property string valueText
                            required property bool selected
                            readonly property string rowName: name
                            width: ListView.view.width
                            height: 48
                            color: selected ? Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.18)
                                 : hover.hovered ? theme.hover : "transparent"
                            Rectangle { visible: rowItem.selected; width: 3; height: parent.height; color: theme.primary }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border; opacity: 0.6 }
                            HoverHandler { id: hover }
                            TapHandler { onTapped: { list.currentIndex = rowItem.index; root.backend.select(rowItem.name) } }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { text: rowItem.name; color: theme.fg; font.family: root.mono; font.pixelSize: 13; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: rowItem.what; color: theme.fgMuted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                }
                                Text { text: rowItem.valueText; color: theme.fg; font.family: root.mono; font.pixelSize: 12; Layout.maximumWidth: 150; elide: Text.ElideRight }
                            }
                        }
                    }
                }
            }
            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: theme.border }

            // ---- device ------------------------------------------------------------------------
            ScrollView {
                id: detailScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                Item {
                    width: detailScroll.availableWidth
                    implicitHeight: detail.implicitHeight + 36
                    ColumnLayout {
                        id: detail
                        x: 24
                        y: 18
                        width: parent.width - 48
                        spacing: 16

                        Text {
                            visible: !root.hasDevice
                            text: "Select a device to see it here."
                            color: theme.fgMuted
                            font.pixelSize: 12
                        }

                        // header: name, kind, description and the main action
                        RowLayout {
                            visible: root.hasDevice
                            Layout.fillWidth: true
                            spacing: 12
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                RowLayout {
                                    spacing: 10
                                    Text { text: root.d.name || ""; color: theme.fg; font.family: root.mono; font.pixelSize: 20; font.weight: Font.Bold }
                                    Chip { text: root.d.kindLabel || "" }
                                    Chip { visible: root.d.enabled === false; text: "Disabled in this session"; tone: "warn"; iconName: "block" }
                                }
                                Text { text: root.d.description || ""; color: theme.fgMuted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                            TextButton {
                                Layout.alignment: Qt.AlignTop
                                text: root.d.actionText || ""
                                iconName: root.d.kind === "detector" ? "image" : root.d.kind === "monitor" ? "show_chart" : "add"
                                variant: "primary"
                                onClicked: root.backend.openInWorkspace()
                            }
                        }

                        GridLayout {
                            visible: root.hasDevice
                            Layout.fillWidth: true
                            columns: detail.width < 860 ? 1 : 2
                            columnSpacing: 16
                            rowSpacing: 16

                            // left column: live panel (motor card or value and trend) and about
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                Layout.alignment: Qt.AlignTop
                                spacing: 16
                                Loader {
                                    id: motor
                                    active: root.d.kind === "positioner" && root.backend.motor !== null
                                    visible: active
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: item ? item.implicitHeight : 0
                                    onActiveChanged: if (active) setSource(root.backend.motorSource, { backend: root.backend.motor })
                                    Component.onCompleted: if (active) setSource(root.backend.motorSource, { backend: root.backend.motor })
                                }
                                Panel {
                                    visible: root.d.kind !== "positioner"
                                    title: "Live value"
                                    hint: root.d.numeric ? "last ~20 s" : ""
                                    Text {
                                        textFormat: Text.StyledText
                                        text: (root.d.valueText || "") + "<span style='font-size:15px'> " + (root.d.units || "") + "</span>"
                                        color: theme.fg
                                        font.family: root.mono
                                        font.pixelSize: 28
                                        font.weight: Font.DemiBold
                                    }
                                    Canvas {
                                        id: spark
                                        visible: root.d.numeric === true
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 120
                                        property var points: root.backend.spark
                                        onPointsChanged: requestPaint()
                                        onWidthChanged: requestPaint()
                                        onPaint: {
                                            const ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            ctx.strokeStyle = theme.border
                                            ctx.lineWidth = 1
                                            ctx.setLineDash([3, 3])
                                            for (const f of [0, 0.5, 1]) {
                                                const gy = Math.round(5 + f * (height - 10)) + 0.5
                                                ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke()
                                            }
                                            ctx.setLineDash([])
                                            if (!points || points.length < 2) return
                                            const lo = Math.min.apply(null, points), hi = Math.max.apply(null, points)
                                            const span = (hi - lo) || 1
                                            const px = i => i / 89 * width
                                            const py = v => height - 5 - (v - lo) / span * (height - 10)
                                            ctx.beginPath()
                                            for (let i = 0; i < points.length; i++) i ? ctx.lineTo(px(i), py(points[i])) : ctx.moveTo(px(i), py(points[i]))
                                            const last = points.length - 1
                                            ctx.lineTo(px(last), height); ctx.lineTo(0, height); ctx.closePath()
                                            ctx.fillStyle = Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.12)
                                            ctx.fill()
                                            ctx.beginPath()
                                            for (let i = 0; i < points.length; i++) i ? ctx.lineTo(px(i), py(points[i])) : ctx.moveTo(px(i), py(points[i]))
                                            ctx.strokeStyle = theme.primary
                                            ctx.lineWidth = 1.8
                                            ctx.stroke()
                                            ctx.fillStyle = theme.primary
                                            ctx.beginPath(); ctx.arc(px(last), py(points[last]), 3, 0, 2 * Math.PI); ctx.fill()
                                            ctx.fillStyle = theme.fgSubtle
                                            ctx.font = "10px sans-serif"
                                            ctx.textAlign = "right"
                                            ctx.fillText(Number(hi.toPrecision(6)).toString(), width - 4, 11)
                                            ctx.fillText(Number(lo.toPrecision(6)).toString(), width - 4, height - 3)
                                        }
                                    }
                                }
                                Panel {
                                    title: "About"
                                    GridLayout {
                                        columns: 2
                                        columnSpacing: 16
                                        rowSpacing: 4
                                        Layout.fillWidth: true
                                        Repeater {
                                            model: root.d.facts || []
                                            delegate: Text {
                                                required property var modelData
                                                required property int index
                                                text: modelData.label
                                                color: theme.fgMuted
                                                font.pixelSize: 12
                                                Layout.row: index
                                                Layout.column: 0
                                            }
                                        }
                                        Repeater {
                                            model: root.d.facts || []
                                            delegate: Text {
                                                required property var modelData
                                                required property int index
                                                text: modelData.value
                                                color: theme.fg
                                                font.pixelSize: 13
                                                Layout.row: index
                                                Layout.column: 1
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }
                            }

                            // right column: settings and readings
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                Layout.alignment: Qt.AlignTop
                                spacing: 16
                                Panel {
                                    visible: root.backend.settings.count > 0
                                    title: "Settings"
                                    hint: "Applied to the device at once"
                                    Repeater {
                                        model: root.backend.settings
                                        delegate: SignalRow {}
                                    }
                                }
                                Panel {
                                    visible: root.backend.readings.count > 0
                                    title: "Readings"
                                    hint: "live"
                                    Repeater {
                                        model: root.backend.readings
                                        delegate: SignalRow {}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
