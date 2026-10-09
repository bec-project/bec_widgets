import QtQuick
import QtQuick.Layouts

// Scan progress view. Data comes from `progressModel` (ScanProgressModel), colours from `theme`.
Item {
    id: root

    property bool compact: false
    property bool showSource: true
    property bool showElapsed: true
    property bool showRemaining: true

    readonly property color fg: theme.c["FG"] || "#e0e0e0"
    readonly property color muted: theme.c["DISABLED_FG"] || "#888888"
    readonly property color track: theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.07)
    readonly property color stateColor: theme.c[progressModel.stateColorKey] || "#0a60ff"
    // chip text needs more contrast than the bar fill on light backgrounds
    readonly property color stateInk: theme.dark ? stateColor : Qt.darker(stateColor, 1.5)

    implicitHeight: compact ? 22 : 58
    implicitWidth: compact ? 220 : 320


    // ---------- progress track, shared by both layouts ----------
    component Bar: Rectangle {
        id: bar
        radius: height / 2
        color: root.track
        clip: true

        Rectangle {
            id: fill
            visible: !progressModel.indeterminate
            height: parent.height
            radius: parent.radius
            width: Math.max(progressModel.fraction > 0 ? height : 0, parent.width * progressModel.fraction)
            color: root.stateColor
            Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 200 } }

            // soft sheen that travels along the fill while the scan is running
            Rectangle {
                visible: progressModel.state === "running" && fill.width > 24
                width: 40; height: parent.height; radius: parent.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.28) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                NumberAnimation on x {
                    from: -40; to: fill.width; duration: 1600; loops: Animation.Infinite
                    running: progressModel.state === "running"
                }
            }
        }

        // indeterminate: a segment sliding back and forth until the point count is known
        Rectangle {
            visible: progressModel.indeterminate
            width: parent.width * 0.3; height: parent.height; radius: parent.radius
            color: root.stateColor
            SequentialAnimation on x {
                running: progressModel.indeterminate; loops: Animation.Infinite
                NumberAnimation { from: 0; to: bar.width * 0.7; duration: 900; easing.type: Easing.InOutQuad }
                NumberAnimation { from: bar.width * 0.7; to: 0; duration: 900; easing.type: Easing.InOutQuad }
            }
        }
    }

    // ---------- compact: one line for status bars ----------
    RowLayout {
        visible: root.compact
        anchors.fill: parent
        anchors.leftMargin: 4; anchors.rightMargin: 4
        spacing: 6

        Rectangle {
            Layout.alignment: Qt.AlignVCenter
            width: 8; height: 8; radius: 4
            color: root.stateColor
        }
        Text {
            visible: root.showSource && progressModel.title !== ""
            text: progressModel.title
            color: root.fg
            font.pixelSize: 11
            elide: Text.ElideRight
            Layout.maximumWidth: 120
        }
        Bar { Layout.fillWidth: true; Layout.preferredHeight: 6; Layout.alignment: Qt.AlignVCenter }
        Text {
            text: progressModel.percentText
            color: root.fg
            font.pixelSize: 11
            font.features: { "tnum": 1 }
        }
        Text {
            visible: root.showRemaining && text !== ""
            text: progressModel.timeText
            color: root.muted
            font.pixelSize: 11
        }
    }

    // ---------- full layout ----------
    ColumnLayout {
        visible: !root.compact
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // state chip
            Rectangle {
                id: chip
                radius: height / 2
                implicitHeight: 20
                implicitWidth: chipRow.implicitWidth + 14
                color: Qt.rgba(root.stateColor.r, root.stateColor.g, root.stateColor.b, 0.16)
                Behavior on color { ColorAnimation { duration: 200 } }
                Row {
                    id: chipRow
                    anchors.centerIn: parent
                    spacing: 4
                    Image {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 14; height: 14
                        sourceSize: Qt.size(28, 28)
                        source: "image://material/" + progressModel.stateIcon + "?filled=1&color=" + encodeURIComponent(root.stateInk)
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: progressModel.stateLabel
                        color: root.stateInk
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
            }
            Text {
                visible: root.showSource
                Layout.fillWidth: true
                text: progressModel.title
                color: progressModel.state === "idle" ? root.muted : root.fg
                font.pixelSize: 12
                elide: Text.ElideRight
            }
            Item { visible: !root.showSource; Layout.fillWidth: true }
            Text {
                text: progressModel.percentText
                color: root.fg
                font.pixelSize: 15
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
        }

        Bar { Layout.fillWidth: true; Layout.preferredHeight: 8 }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Text {
                text: progressModel.countText !== "" ? progressModel.countText + " points" : ""
                color: root.muted
                font.pixelSize: 11
                font.features: { "tnum": 1 }
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: root.showElapsed && progressModel.active && progressModel.elapsedText !== ""
                text: progressModel.elapsedText + " elapsed"
                color: root.muted
                font.pixelSize: 11
                font.features: { "tnum": 1 }
            }
            Text {
                visible: root.showElapsed && root.showRemaining && progressModel.active && progressModel.elapsedText !== ""
                text: "·"
                color: root.muted
                font.pixelSize: 11
            }
            Text {
                visible: root.showRemaining && text !== ""
                text: progressModel.timeText
                color: progressModel.state === "running" ? root.fg : root.muted
                font.pixelSize: 11
                font.features: { "tnum": 1 }
            }
        }
    }
}
