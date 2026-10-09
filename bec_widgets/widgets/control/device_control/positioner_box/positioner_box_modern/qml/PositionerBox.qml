import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Positioner box: device header with status, large readback with target,
// limit track, move-to field with inline validation, tweak row and stop.
Rectangle {
    id: root
    color: theme.window
    implicitWidth: 260
    implicitHeight: 280

    readonly property bool isMoving: box.moving === 1
    readonly property string moveError: box.validate(targetField.text)

    component FlatButton: Button {
        id: control
        property color tint: theme.button
        property color ink: theme.text
        property bool solid: false
        property bool neutral: true
        implicitHeight: 30
        font.pixelSize: 13
        hoverEnabled: true
        background: Rectangle {
            radius: 6
            color: !control.enabled ? Qt.alpha(control.tint, 0.15)
                 : control.solid ? (control.down ? Qt.darker(control.tint, 1.2) : control.hovered ? Qt.lighter(control.tint, 1.1) : control.tint)
                 : control.neutral ? (control.down ? Qt.alpha(theme.accent, 0.32) : control.hovered ? Qt.alpha(theme.accent, 0.16) : theme.button)
                 : (control.down ? Qt.alpha(control.tint, 0.35) : control.hovered ? Qt.alpha(control.tint, 0.22) : Qt.alpha(control.tint, 0.12))
            border.width: control.solid ? 0 : 1
            border.color: control.neutral ? Qt.alpha(theme.border, 0.63) : Qt.alpha(control.tint, 0.5)
        }
        contentItem: Row {
            spacing: 6
            anchors.centerIn: parent
            Image {
                visible: control.icon.name !== ""
                source: visible ? "image://material/" + control.icon.name + "?" + control.ink : ""
                sourceSize: Qt.size(16, 16)
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: control.text
                font: control.font
                color: control.enabled ? control.ink : theme.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    component Field: TextField {
        id: field
        property bool invalid: false
        implicitHeight: 30
        font.pixelSize: 13
        color: theme.text
        placeholderTextColor: theme.muted
        selectByMouse: true
        background: Rectangle {
            radius: 6
            color: theme.base
            border.width: field.activeFocus || field.invalid ? 2 : 1
            border.color: field.invalid ? theme.danger : field.activeFocus ? theme.accent : theme.border
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8
        enabled: box.ready

        // Header: device picker and motion status
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Rectangle {
                id: deviceChip
                Layout.preferredHeight: 26
                Layout.preferredWidth: deviceRow.implicitWidth + 16
                Layout.maximumWidth: root.width - 110
                radius: 6
                color: deviceMouse.containsMouse && box.deviceSelectable ? Qt.alpha(theme.accent, 0.15) : "transparent"
                Row {
                    id: deviceRow
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                        text: box.device || "No device"
                        color: theme.text
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        width: Math.min(implicitWidth, deviceChip.Layout.maximumWidth - 30)
                    }
                    Image {
                        visible: box.deviceSelectable
                        source: "image://material/expand_more?" + theme.muted
                        sourceSize: Qt.size(18, 18)
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: deviceMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: box.deviceSelectable
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: box.pickDevice()
                    ToolTip.visible: containsMouse && enabled
                    ToolTip.text: "Change positioner"
                    ToolTip.delay: 600
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                visible: box.moving !== -1
                Layout.preferredHeight: 22
                Layout.preferredWidth: statusRow.implicitWidth + 16
                radius: 11
                readonly property color tone: root.isMoving ? theme.warning : theme.success
                color: Qt.alpha(tone, 0.16)
                Row {
                    id: statusRow
                    anchors.centerIn: parent
                    spacing: 6
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        anchors.verticalCenter: parent.verticalCenter
                        color: parent.parent.tone
                        SequentialAnimation on opacity {
                            running: root.isMoving
                            loops: Animation.Infinite
                            onRunningChanged: if (!running) parent.opacity = 1
                            NumberAnimation { to: 0.25; duration: 500 }
                            NumberAnimation { to: 1; duration: 500 }
                        }
                    }
                    Text {
                        text: root.isMoving ? "Moving" : "Idle"
                        color: theme.text
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        // Readback and target
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Text {
                text: box.readbackText
                color: box.outOfLimits ? theme.danger : theme.text
                font.pixelSize: 26
                font.weight: Font.Medium
                font.family: "monospace"
                Layout.maximumWidth: root.width - 60
                elide: Text.ElideRight
            }
            Text {
                visible: box.units !== ""
                text: box.units
                color: theme.muted
                font.pixelSize: 14
                Layout.alignment: Qt.AlignBaseline
            }
            Item { Layout.fillWidth: true }
        }
        Text {
            Layout.topMargin: -8
            text: box.hasTarget ? "→ target " + box.targetText : "at target"
            color: box.hasTarget ? theme.accent : theme.muted
            font.pixelSize: 12
        }

        // Limit track
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            visible: box.hasLimits
            Rectangle {
                id: track
                y: 4
                width: parent.width
                height: 6
                radius: 3
                color: Qt.alpha(theme.border, 0.6)
                Rectangle {
                    visible: box.position >= 0
                    width: track.width * Math.max(box.position, 0)
                    height: parent.height
                    radius: 3
                    color: Qt.alpha(box.outOfLimits ? theme.danger : theme.accent, 0.55)
                }
            }
            Rectangle {
                visible: box.targetPosition >= 0
                width: 12; height: 12; radius: 6
                x: track.width * box.targetPosition - width / 2
                y: track.y + track.height / 2 - height / 2
                color: "transparent"
                border.width: 2
                border.color: theme.accent
            }
            Rectangle {
                visible: box.position >= 0
                width: 12; height: 12; radius: 6
                x: track.width * box.position - width / 2
                y: track.y + track.height / 2 - height / 2
                color: box.outOfLimits ? theme.danger : theme.accent
                Behavior on x { NumberAnimation { duration: 120 } }
            }
            Text {
                anchors.left: parent.left; anchors.bottom: parent.bottom
                text: box.lowText; color: theme.muted; font.pixelSize: 11
            }
            Text {
                anchors.right: parent.right; anchors.bottom: parent.bottom
                text: box.highText; color: theme.muted; font.pixelSize: 11
            }
        }
        Text {
            visible: !box.hasLimits && box.ready
            text: "No limits set"
            color: theme.muted
            font.pixelSize: 11
        }

        // Move to
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Field {
                id: targetField
                objectName: "targetField"
                Layout.fillWidth: true
                placeholderText: "Move to…"
                invalid: root.moveError !== ""
                onAccepted: root.go()
                Keys.onEscapePressed: { text = ""; focus = false }
            }
            FlatButton {
                text: "Go"
                tint: theme.accent
                neutral: false
                ink: theme.onAccent
                solid: true
                enabled: targetField.text.trim() !== "" && root.moveError === ""
                Layout.preferredWidth: 52
                onClicked: root.go()
            }
        }
        Text {
            Layout.topMargin: -4
            visible: root.moveError !== ""
            text: root.moveError
            color: theme.danger
            font.pixelSize: 11
        }

        // Tweak
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            FlatButton {
                text: "− " + box.stepText
                Layout.fillWidth: true
                onClicked: box.tweak(-1)
                ToolTip.visible: hovered
                ToolTip.text: "Move by −" + box.stepText + " " + box.units
                ToolTip.delay: 600
            }
            Field {
                id: stepField
                Layout.preferredWidth: 72
                horizontalAlignment: Text.AlignHCenter
                text: box.stepText
                validator: DoubleValidator { bottom: 0 }
                onEditingFinished: box.setStepText(text)
                WheelHandler {
                    onWheel: (event) => box.scaleStep(event.angleDelta.y > 0 ? 10 : 0.1)
                }
                Keys.onUpPressed: box.scaleStep(10)
                Keys.onDownPressed: box.scaleStep(0.1)
                ToolTip.visible: hovered
                ToolTip.text: "Step size. Scroll or ↑/↓ to change by ×10"
                ToolTip.delay: 600
            }
            FlatButton {
                text: "+ " + box.stepText
                Layout.fillWidth: true
                onClicked: box.tweak(1)
                ToolTip.visible: hovered
                ToolTip.text: "Move by +" + box.stepText + " " + box.units
                ToolTip.delay: 600
            }
        }

        Item { Layout.fillHeight: true }

        FlatButton {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            text: "Stop"
            icon.name: "stop"
            tint: theme.danger
            neutral: false
            ink: root.isMoving ? "white" : theme.danger
            solid: root.isMoving
            font.weight: Font.DemiBold
            onClicked: box.stop()
        }
    }

    function go() {
        if (box.moveTo(targetField.text)) {
            targetField.text = ""
            targetField.focus = false
        }
    }
}
