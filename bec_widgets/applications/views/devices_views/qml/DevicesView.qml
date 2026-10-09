import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Devices for everyone: find a device by kind and text, see it live, move motors.
// backend: DevicesBackend.
Rectangle {
    id: root
    required property QtObject backend
    readonly property var d: backend.detail
    readonly property string mono: "JetBrains Mono, Menlo, DejaVu Sans Mono"

    color: theme.bg

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- toolbar -------------------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 46
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10
                Icon { name: "memory"; size: 18; color: theme.fgMuted }
                Text { text: "Devices"; color: theme.fg; font.pixelSize: 13; font.weight: Font.Bold }
                InputField {
                    id: search
                    Layout.preferredWidth: 300
                    placeholderText: "Search devices by name, tag or description"
                    Accessible.name: "Search devices"
                    onTextChanged: debounce.restart()
                    Timer { id: debounce; interval: 120; onTriggered: root.backend.setQuery(search.text) }
                }
                Segmented {
                    model: root.backend.kinds
                    current: root.backend.kind
                    onPicked: (key) => root.backend.setKind(key)
                }
                Item { Layout.fillWidth: true }
                Chip {
                    text: "Read-only configuration"
                    iconName: "lock"
                    HoverHandler { id: lockHover }
                    ToolTip.visible: lockHover.hovered
                    ToolTip.text: "Editing the device session is in Config (staff)"
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ---- device list -------------------------------------------------------------------
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: theme.card
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    Text {
                        text: root.backend.shownText
                        color: theme.fgMuted
                        font.pixelSize: 12
                        Layout.margins: 10
                        Layout.topMargin: 6
                        Layout.bottomMargin: 6
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 26
                        color: theme.card
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 16
                            spacing: 0
                            Text { text: "Name"; color: theme.fgMuted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 150 }
                            Text { text: "What it is"; color: theme.fgMuted; font.pixelSize: 11; font.weight: Font.Bold; Layout.fillWidth: true }
                            Text { text: "Value"; color: theme.fgMuted; font.pixelSize: 11; font.weight: Font.Bold; Layout.preferredWidth: 140; horizontalAlignment: Text.AlignRight }
                        }
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
                            height: 32
                            color: selected ? Qt.rgba(theme.primary.r, theme.primary.g, theme.primary.b, 0.18)
                                 : hover.hovered ? theme.hover : "transparent"
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border; opacity: 0.6 }
                            HoverHandler { id: hover }
                            TapHandler { onTapped: { list.currentIndex = rowItem.index; root.backend.select(rowItem.name) } }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 16
                                spacing: 0
                                Text { text: rowItem.name; color: theme.fg; font.family: root.mono; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.preferredWidth: 150; elide: Text.ElideRight }
                                Text { text: rowItem.what; color: theme.fgMuted; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                                Text { text: rowItem.valueText; color: theme.fg; font.family: root.mono; font.pixelSize: 12; Layout.preferredWidth: 140; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                }
            }
            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: theme.border }

            // ---- detail ------------------------------------------------------------------------
            ScrollView {
                id: detailScroll
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                Item {
                    width: detailScroll.availableWidth
                    implicitHeight: detail.implicitHeight + 24
                    ColumnLayout {
                        id: detail
                        width: Math.min(440, parent.width - 32)
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 12
                        spacing: 8

                        Text {
                            visible: root.backend.detailName === ""
                            text: "Select a device to see it here."
                            color: theme.fgMuted
                            font.pixelSize: 12
                        }
                        ColumnLayout {
                            visible: root.backend.detailName !== ""
                            spacing: 4
                            Layout.fillWidth: true
                            Text { visible: root.d.kind !== "positioner"; text: root.d.name || ""; color: theme.fg; font.family: root.mono; font.pixelSize: 15; font.weight: Font.Bold }
                            Text { text: root.d.description || ""; color: theme.fgMuted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text {
                                visible: root.d.kind === "monitor"
                                textFormat: Text.StyledText
                                text: (root.d.valueText || "") + "<span style='font-size:14px'> " + (root.d.units || "") + "</span>"
                                color: theme.fg
                                font.family: root.mono
                                font.pixelSize: 28
                                font.weight: Font.DemiBold
                            }
                            Canvas {
                                id: spark
                                visible: root.d.kind === "monitor"
                                Layout.fillWidth: true
                                Layout.maximumWidth: 380
                                Layout.preferredHeight: 70
                                property var points: root.backend.spark
                                onPointsChanged: requestPaint()
                                onPaint: {
                                    const ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    if (!points || points.length < 2) return
                                    let lo = Math.min.apply(null, points), hi = Math.max.apply(null, points)
                                    const span = (hi - lo) || 1
                                    ctx.strokeStyle = theme.primary
                                    ctx.lineWidth = 1.6
                                    ctx.beginPath()
                                    for (let i = 0; i < points.length; i++) {
                                        const x = i / 89 * width, y = height - 5 - (points[i] - lo) / span * (height - 10)
                                        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
                                    }
                                    ctx.stroke()
                                }
                            }
                            Text { visible: root.d.kind === "monitor"; text: "last ~20 s, live"; color: theme.fgSubtle; font.pixelSize: 11 }
                        }
                        Loader {
                            id: motor
                            active: root.d.kind === "positioner" && root.backend.motor !== null
                            visible: active
                            Layout.fillWidth: true
                            Layout.preferredHeight: item ? item.implicitHeight : 0
                            onActiveChanged: if (active) setSource(root.backend.motorSource, { backend: root.backend.motor })
                            Component.onCompleted: if (active) setSource(root.backend.motorSource, { backend: root.backend.motor })
                        }
                        GridLayout {
                            visible: root.backend.detailName !== ""
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 3
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
                        TextButton {
                            visible: root.backend.detailName !== ""
                            text: root.d.actionText || ""
                            iconName: root.d.kind === "detector" ? "image" : root.d.kind === "monitor" ? "show_chart" : "add"
                            variant: root.d.kind === "detector" ? "primary" : "neutral"
                            onClicked: root.backend.openInWorkspace()
                        }
                    }
                }
            }
        }
    }
}
