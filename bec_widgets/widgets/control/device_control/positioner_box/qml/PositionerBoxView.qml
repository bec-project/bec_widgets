import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Positioner control card: live readback, limits, absolute move, tweak and stop.
// backend: PositionerBackend (state map, positioners list, actions).
Rectangle {
    id: root
    required property QtObject backend
    readonly property var s: backend.state

    function toneColor(tone) {
        return tone === "primary" ? theme.primary : tone === "success" ? theme.success
             : tone === "warning" ? theme.warning : tone === "danger" ? theme.danger : theme.fgMuted
    }

    color: theme.bg
    implicitWidth: 280
    implicitHeight: card.implicitHeight + 16

    Card {
        id: card
        anchors.fill: parent
        anchors.margins: 8
        spacing: 10

        // ---- header: device selector and status ------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            SelectField {
                id: selector
                visible: root.s.selectable === true
                Layout.fillWidth: true
                editable: true
                model: root.backend.positioners
                placeholder: "Select positioner"
                Component.onCompleted: root.backend.refreshPositioners()
                onActivated: (index) => root.backend.selectDevice(textAt(index))
                onAccepted: root.backend.selectDevice(editText)
                popup.onAboutToShow: root.backend.refreshPositioners()
                Connections {
                    target: root.backend
                    function onChanged() {
                        if (!selector.activeFocus)
                            selector.editText = root.s.device || ""
                    }
                }
                Accessible.name: "Positioner"
            }
            Text {
                visible: root.s.selectable !== true
                text: root.s.device || "No positioner"
                color: theme.fg
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            StatusPill {
                text: root.s.status || ""
                tone: root.toneColor(root.s.statusTone)
                pulse: root.s.moving === true
            }
        }

        // ---- readback ----------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.hasDevice === true
            Layout.fillWidth: true
            spacing: 0
            RowLayout {
                spacing: 6
                Text {
                    text: root.s.readbackText || "—"
                    color: theme.fg
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                    font.family: "monospace"
                    Layout.maximumWidth: card.width - 70
                    elide: Text.ElideRight
                }
                Text {
                    text: root.s.units || ""
                    visible: text !== ""
                    color: theme.fgMuted
                    font.pixelSize: 14
                    Layout.alignment: Qt.AlignBaseline
                }
            }
            Text {
                text: "target " + (root.s.setpointText || "")
                visible: root.s.showTarget === true
                color: theme.fgMuted
                font.pixelSize: 12
                font.family: "monospace"
            }
        }

        // ---- limits bar ----------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.hasLimits === true
            Layout.fillWidth: true
            spacing: 3
            Item {
                Layout.fillWidth: true
                implicitHeight: 14
                Rectangle {
                    id: track
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    height: 4
                    radius: 2
                    color: theme.track
                }
                Rectangle {
                    visible: root.s.target >= 0 && root.s.showTarget === true
                    x: root.s.target * (track.width - 2)
                    width: 2; height: 14
                    color: theme.fgMuted
                }
                Rectangle {
                    visible: root.s.position >= 0
                    width: 12; height: 12; radius: 6
                    x: root.s.position * (track.width - width)
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.s.atLimit ? theme.warning : theme.primary
                    border.color: theme.card
                    border.width: 2
                    Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: root.s.limitLowText || ""; color: theme.fgSubtle; font.pixelSize: 11 }
                Item { Layout.fillWidth: true }
                Text { text: root.s.limitHighText || ""; color: theme.fgSubtle; font.pixelSize: 11 }
            }
        }

        // ---- absolute move -------------------------------------------------------------------
        ColumnLayout {
            visible: root.s.hasDevice === true
            Layout.fillWidth: true
            spacing: 4
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                InputField {
                    id: target
                    Layout.fillWidth: true
                    placeholderText: "Move to…"
                    suffix: root.s.units || ""
                    readonly property string problem: root.backend.validate(text)
                    invalid: problem !== ""
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                    onAccepted: if (root.backend.moveTo(text)) { text = ""; focus = false }
                    Accessible.name: "Target position"
                }
                TextButton {
                    text: "Go"
                    variant: "primary"
                    enabled: target.text !== "" && !target.invalid
                    onClicked: if (root.backend.moveTo(target.text)) target.text = ""
                }
            }
            Text {
                readonly property string message: target.problem !== "" ? target.problem : (root.s.error || "")
                visible: message !== ""
                text: message
                color: theme.danger
                font.pixelSize: 11
            }
        }

        // ---- tweak ---------------------------------------------------------------------------
        RowLayout {
            visible: root.s.hasDevice === true
            Layout.fillWidth: true
            spacing: 6
            TextButton {
                text: "−" + (root.s.stepText || "")
                iconName: "chevron_left"
                tip: "Tweak down by the step"
                Layout.fillWidth: true
                onClicked: root.backend.tweak(-1)
            }
            InputField {
                id: step
                Layout.preferredWidth: 78
                horizontalAlignment: Text.AlignHCenter
                text: root.s.stepText || ""
                validator: DoubleValidator { bottom: 0; notation: DoubleValidator.ScientificNotation }
                onEditingFinished: if (acceptableInput && Number(text) > 0) root.backend.setStep(Number(text))
                ToolTip.visible: hovered
                ToolTip.text: "Step size"
                Accessible.name: "Step size"
            }
            TextButton {
                text: "+" + (root.s.stepText || "")
                iconName: "chevron_right"
                tip: "Tweak up by the step"
                Layout.fillWidth: true
                onClicked: root.backend.tweak(1)
            }
        }

        TextButton {
            visible: root.s.hasDevice === true
            Layout.fillWidth: true
            text: "Stop"
            iconName: "stop"
            variant: "danger"
            onClicked: root.backend.stop()
        }

        // ---- empty state -----------------------------------------------------------------------
        Text {
            visible: root.s.hasDevice !== true
            Layout.fillWidth: true
            Layout.topMargin: 12
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Choose a positioner above to see its position and move it."
            color: theme.fgMuted
            font.pixelSize: 12
        }
        Item { Layout.fillHeight: true }
    }
}
