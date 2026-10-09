import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import BecUi

// Concentric progress rings with a center readout and a legend.
// backend: RingViewBackend (rings model, centerText, centerCaption, highlighted, showLegend).
Rectangle {
    id: root
    required property QtObject backend

    readonly property int ringCount: backend.rings.count
    readonly property bool wide: width >= height * 1.35
    readonly property bool legendVisible: backend.showLegend && ringCount > 0
        && (wide ? width > 260 : height > 230)

    color: theme.bg
    implicitWidth: 240
    implicitHeight: 240

    GridLayout {
        anchors.fill: parent
        anchors.margins: 8
        flow: root.wide ? GridLayout.LeftToRight : GridLayout.TopToBottom
        columnSpacing: 16
        rowSpacing: 10

        // ---- rings --------------------------------------------------------------------
        Item {
            id: dial
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 60
            Layout.minimumHeight: 60
            readonly property real side: Math.min(width, height)
            readonly property real baseRadius: (side - 2 * root.backend.maxLineWidth) / 2

            Repeater {
                id: ringRepeater
                model: root.backend.rings
                delegate: Shape {
                    id: ring
                    required property int index
                    required property color color
                    required property color trackColor
                    required property real fraction
                    required property int lineWidth
                    required property int gap
                    required property int startAngle
                    required property int direction
                    required property bool highlighted

                    readonly property real radius: Math.max(1, dial.baseRadius - gap)
                    readonly property real width_: lineWidth + (highlighted ? 3 : 0)
                    property real shownFraction: fraction
                    Behavior on shownFraction { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    opacity: root.backend.highlighted >= 0 && !highlighted ? 0.4 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 140 } }

                    ShapePath {
                        strokeColor: ring.trackColor
                        strokeWidth: ring.width_
                        fillColor: "transparent"
                        capStyle: ShapePath.FlatCap
                        PathAngleArc {
                            centerX: dial.width / 2; centerY: dial.height / 2
                            radiusX: ring.radius; radiusY: ring.radius
                            startAngle: 0; sweepAngle: 360
                        }
                    }
                    ShapePath {
                        strokeColor: ring.color
                        strokeWidth: ring.width_
                        fillColor: "transparent"
                        capStyle: ring.shownFraction > 0.001 ? ShapePath.RoundCap : ShapePath.FlatCap
                        PathAngleArc {
                            centerX: dial.width / 2; centerY: dial.height / 2
                            radiusX: ring.radius; radiusY: ring.radius
                            startAngle: -ring.startAngle
                            sweepAngle: -ring.direction * 360 * Math.min(ring.shownFraction, 0.9999)
                        }
                    }
                }
            }

            // center readout
            Column {
                anchors.centerIn: parent
                width: Math.max(10, 2 * (dial.baseRadius - root.backend.innerOffset) * 0.8)
                spacing: 2
                visible: root.ringCount > 0
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: root.backend.centerText
                    color: theme.fg
                    font.pixelSize: Math.max(12, Math.min(34, dial.side * 0.13))
                    font.weight: Font.DemiBold
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 10
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    visible: text !== "" && dial.side > 120
                    text: root.backend.centerCaption
                    color: theme.fgMuted
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            // hover picking: find the ring under the pointer by its radius
            HoverHandler {
                id: hover
                onPointChanged: pick(point.position)
                onHoveredChanged: if (!hovered) root.backend.setHighlighted(-1)
                function pick(pos) {
                    const dx = pos.x - dial.width / 2
                    const dy = pos.y - dial.height / 2
                    const distance = Math.sqrt(dx * dx + dy * dy)
                    let best = -1
                    let bestDelta = 1e9
                    for (let i = 0; i < root.ringCount; ++i) {
                        const item = ringRepeater.itemAt(i)
                        if (!item) continue
                        const delta = Math.abs(distance - item.radius)
                        if (delta <= item.lineWidth / 2 + 2 && delta < bestDelta) {
                            best = i
                            bestDelta = delta
                        }
                    }
                    root.backend.setHighlighted(best)
                }
            }

            // empty state
            Column {
                anchors.centerIn: parent
                visible: root.ringCount === 0
                spacing: 10
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(96, dial.side * 0.5); height: width; radius: width / 2
                    color: "transparent"
                    border.color: theme.border
                    border.width: 6
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "No rings yet"
                    color: theme.fgMuted
                    font.pixelSize: 13
                }
                TextButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Add ring"
                    iconName: "add"
                    variant: "neutral"
                    onClicked: root.backend.openSettings()
                }
            }
        }

        // ---- legend -------------------------------------------------------------------
        ListView {
            id: legend
            visible: root.legendVisible
            model: root.backend.rings
            interactive: contentHeight > height
            clip: true
            spacing: 2
            Layout.fillWidth: !root.wide
            Layout.preferredWidth: root.wide ? Math.min(260, root.width * 0.45) : -1
            Layout.preferredHeight: Math.min(contentHeight, root.wide ? root.height - 16 : root.height * 0.38)
            Layout.alignment: Qt.AlignVCenter

            delegate: Rectangle {
                id: row
                required property int index
                required property string label
                required property var model
                required property string valueText
                required property string percentText
                required property bool done
                required property bool highlighted

                width: ListView.view.width
                height: 30
                radius: 6
                color: highlighted ? theme.hover : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8
                    Rectangle { width: 10; height: 10; radius: 5; color: row.model.color }
                    Text {
                        text: row.label
                        color: theme.fg
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: row.valueText
                        color: theme.fgMuted
                        font.pixelSize: 12
                        font.family: "monospace"
                    }
                    Icon {
                        visible: row.done
                        name: "check_circle"
                        filled: true
                        size: 14
                        color: theme.success
                    }
                    Text {
                        visible: !row.done
                        text: row.percentText
                        color: theme.fg
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 36
                    }
                }
                HoverHandler {
                    onHoveredChanged: root.backend.setHighlighted(hovered ? row.index : -1)
                }
            }
        }
    }
}
