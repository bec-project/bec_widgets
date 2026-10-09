import QtQuick

// Skeleton shown in a dock while its widget is being built.
Rectangle {
    id: root

    property string widgetClass: ""
    property string kind: "form"          // plot | list | form
    property string loadState: "queued"   // queued | loading | paused | failed
    property string message: ""
    property int seed: 1
    property var colors: ({})
    readonly property bool animated: loadState === "queued" || loadState === "loading"
    readonly property real captionHeight: animated ? 30 : 78

    signal loadRequested()

    color: colors.window || "#1e1f22"

    // Shared shine position across the whole skeleton, in item coordinates
    property real shineX: -width
    NumberAnimation on shineX {
        running: root.animated && root.visible
        from: -root.width * 0.6
        to: root.width * 1.6
        duration: 1600
        loops: Animation.Infinite
    }

    function rand(i) {
        // Deterministic pseudo-random in [0, 1) so rows keep their shape
        var x = Math.sin((root.seed % 9973) * 12.9898 + i * 78.233) * 43758.5453
        return x - Math.floor(x)
    }

    component Block: Rectangle {
        radius: 4
        readonly property real bandLeft: (root.shineX - x - body.x - root.width * 0.35) / Math.max(width, 1)
        readonly property real bandRight: (root.shineX - x - body.x + root.width * 0.35) / Math.max(width, 1)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: Math.min(Math.max(bandLeft, -1), 2); color: root.colors.block }
            GradientStop { position: Math.min(Math.max((bandLeft + bandRight) / 2, -1), 2); color: root.animated ? root.colors.shine : root.colors.block }
            GradientStop { position: Math.min(Math.max(bandRight, -1), 2); color: root.colors.block }
        }
    }

    Item {
        id: body
        x: 14; y: 14
        width: root.width - 28
        height: root.height - 28 - root.captionHeight - 10
        visible: height > 24 && width > 40

        // Plot: toolbar, axis ticks, frame and a faint trace
        Item {
            anchors.fill: parent
            visible: root.kind === "plot"
            Repeater {
                model: 5
                Block { x: index * 26; y: 0; width: 18; height: 18 }
            }
            Item {
                id: frame
                x: 34; y: 30
                width: body.width - 34
                height: body.height - 52
                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: "transparent"
                    border.width: 2
                    border.color: root.colors.block
                }
                Canvas {
                    id: trace
                    anchors.fill: parent
                    anchors.margins: 10
                    opacity: root.animated ? 0.28 : 0.14
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        if (width < 40 || height < 20)
                            return
                        ctx.strokeStyle = root.colors.accent
                        ctx.lineWidth = 2
                        ctx.beginPath()
                        var freq = 1.5 + root.rand(1) * 2
                        var shift = root.rand(2) * Math.PI
                        for (var i = 0; i <= 64; i++) {
                            var t = i / 64
                            var v = 0.5 + 0.32 * Math.sin(t * freq * Math.PI + shift) * Math.exp(-1.2 * t)
                            if (i === 0) ctx.moveTo(t * width, v * height)
                            else ctx.lineTo(t * width, v * height)
                        }
                        ctx.stroke()
                    }
                }
            }
            Repeater {
                model: Math.max(2, Math.floor(frame.height / 48)) + 1
                Block {
                    x: 0
                    y: frame.y + index * (frame.height / Math.max(2, Math.floor(frame.height / 48))) - 4
                    width: 24; height: 8; radius: 3
                }
            }
            Repeater {
                model: Math.max(2, Math.floor(frame.width / 90)) + 1
                Block {
                    x: frame.x + index * (frame.width / Math.max(2, Math.floor(frame.width / 90))) - 14
                    y: frame.y + frame.height + 10
                    width: 28; height: 8; radius: 3
                }
            }
        }

        // List: header and rows
        Item {
            anchors.fill: parent
            visible: root.kind === "list"
            Block { x: 0; y: 0; width: body.width * 0.4; height: 14 }
            Repeater {
                model: Math.max(0, Math.floor((body.height - 46) / 30) + 1)
                Item {
                    x: 0; y: 30 + index * 30
                    width: body.width; height: 14
                    Block { x: 0; y: 0; width: 14; height: 14; radius: 7 }
                    Block { x: 24; y: 1; width: body.width * (0.35 + 0.5 * root.rand(index + 3)) - 24; height: 12 }
                    Block { x: body.width * 0.88; y: 1; width: body.width * 0.12; height: 12 }
                }
            }
        }

        // Form: labels, fields and a primary action
        Item {
            anchors.fill: parent
            visible: root.kind === "form"
            readonly property int rows: Math.max(0, Math.floor((body.height - 52) / 58) + 1)
            Repeater {
                model: parent.rows
                Item {
                    x: 0; y: index * 58
                    width: body.width; height: 42
                    Block { x: 0; y: 0; width: body.width * (0.18 + 0.15 * root.rand(index + 7)); height: 10; radius: 3 }
                    Block { x: 0; y: 16; width: body.width; height: 26; radius: 6 }
                }
            }
            Block {
                width: Math.min(140, body.width * 0.4); height: 30; radius: 6
                x: body.width - width
                y: parent.rows * 58 + 4
                visible: y + height <= body.height + 30
            }
        }
    }

    // Caption: what is loading, or why it is not
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.animated ? 22 : 18
        spacing: 6
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.widgetClass + "  ·  " + ({queued: "Waiting", loading: "Loading", paused: "Not loaded", failed: "Could not load"})[root.loadState]
            color: root.loadState === "failed" ? root.colors.danger : root.colors.muted
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, root.width - 28)
            visible: root.message.length > 0 && !root.animated
            text: root.message
            elide: Text.ElideRight
            color: root.colors.muted
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.animated
            width: actionText.implicitWidth + 28
            height: 30
            radius: 6
            color: actionArea.containsMouse ? Qt.darker(root.colors.accent, 1.1) : root.colors.accent
            Text {
                id: actionText
                anchors.centerIn: parent
                text: root.loadState === "failed" ? "Retry" : "Load now"
                color: "white"
                font.bold: true
            }
            MouseArea {
                id: actionArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.loadRequested()
            }
        }
    }
}
