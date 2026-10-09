// Fit summary and parameters of LMFit DAP processes.
// Data and actions come from the `fit` context object (FitDialogBridge in lmfit_dialog_qml.py).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    readonly property var s: fit ? fit.state : ({})
    readonly property var p: fit ? fit.palette : ({})
    readonly property bool compact: s.compact === true

    implicitWidth: 360
    implicitHeight: 320

    component Muted: Label {
        color: root.p.muted
        font.pixelSize: 11
    }

    component Card: Rectangle {
        color: root.p.card
        border.color: root.p.border
        radius: 8
    }

    component Tip: MouseArea {
        property string text: ""
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        ToolTip.visible: containsMouse && text.length > 0
        ToolTip.delay: 500
        ToolTip.text: text
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // Curve selector: one chip per fitted curve, the dot shows the fit quality.
        Flow {
            Layout.fillWidth: true
            visible: root.s.showCurves === true
            spacing: 4

            Repeater {
                model: root.s.curves || []

                delegate: Rectangle {
                    required property var modelData
                    readonly property bool selected: modelData.id === root.s.currentCurve

                    width: chipRow.implicitWidth + 20
                    height: 24
                    radius: 12
                    color: selected ? root.p.selection : (chipMouse.containsMouse ? root.p.field : "transparent")
                    border.color: selected ? root.p.primary : root.p.border
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 8; height: 8; radius: 4
                            color: modelData.color
                        }
                        Label {
                            text: modelData.id
                            color: root.p.fg
                            font.pixelSize: 12
                        }
                    }

                    MouseArea {
                        id: chipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: fit.selectCurve(modelData.id)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: modelData.tip
                    }
                }
            }
        }

        // Empty state
        Label {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.s.hasData !== true
            text: "No fit results yet.\nAdd a fit model to a curve to see its parameters here."
            color: root.p.muted
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.s.hasData === true
            columns: root.compact ? 2 : 1
            columnSpacing: 8
            rowSpacing: 8

            // Summary card: model, verdict, headline metrics and any warning.
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: root.compact
                Layout.preferredWidth: root.compact ? 2 : -1
                Layout.preferredHeight: root.compact ? -1 : summaryCol.implicitHeight + 20
                visible: root.s.showSummary === true

                ColumnLayout {
                    id: summaryCol
                    anchors.fill: parent
                    anchors.margins: 10
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Label {
                            Layout.fillWidth: true
                            text: root.s.model || ""
                            color: root.p.fg
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            Tip { text: root.s.modelFull || "" }
                        }
                        Rectangle {
                            implicitWidth: pillText.implicitWidth + 16
                            implicitHeight: 20
                            radius: 10
                            color: "transparent"
                            border.color: root.s.qualityColor || root.p.muted
                            Label {
                                id: pillText
                                anchors.centerIn: parent
                                text: root.s.qualityLabel || ""
                                color: root.s.qualityColor || root.p.muted
                                font.pixelSize: 11
                            }
                        }
                    }

                    Muted {
                        Layout.fillWidth: true
                        visible: text.length > 0
                        text: root.s.details || ""
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: root.s.metrics || []
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: metricCol.implicitHeight + 8
                                radius: 6
                                color: root.p.field
                                Column {
                                    id: metricCol
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    Muted { text: modelData.label }
                                    Label {
                                        text: modelData.value
                                        color: root.p.fg
                                        font.pixelSize: 15
                                        font.weight: Font.DemiBold
                                    }
                                }
                                Tip { text: modelData.tip }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        visible: (root.s.message || "").length > 0
                        implicitHeight: messageText.implicitHeight + 8
                        radius: 6
                        color: root.p.warning_bg
                        Label {
                            id: messageText
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            verticalAlignment: Text.AlignVCenter
                            text: root.s.message || ""
                            color: root.p.fg
                            wrapMode: Text.WordWrap
                        }
                    }

                    Item { Layout.fillHeight: true; visible: root.compact }
                }
            }

            // Parameter table
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: root.compact ? 3 : -1
                Layout.minimumHeight: 80
                visible: root.s.showParams === true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 6
                    anchors.bottomMargin: 6
                    spacing: 2

                    Label {
                        Layout.leftMargin: 12
                        text: "Parameters"
                        color: root.p.fg
                        font.weight: Font.DemiBold
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        spacing: 8
                        Muted { text: "Name"; Layout.preferredWidth: 76 }
                        Muted { text: "Value"; Layout.preferredWidth: 70 }
                        Muted { text: "Std error"; Layout.fillWidth: true }
                    }

                    ListView {
                        id: paramList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.s.params || []
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        delegate: Rectangle {
                            id: row
                            required property var modelData
                            width: paramList.width
                            height: 30
                            color: rowMouse.containsMouse ? root.p.field : "transparent"

                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.NoButton
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 600
                                ToolTip.text: modelData.tip
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8

                                Label {
                                    Layout.preferredWidth: 76
                                    text: modelData.name
                                    color: root.p.fg
                                    elide: Text.ElideRight
                                }
                                Label {
                                    Layout.preferredWidth: 70
                                    text: modelData.value
                                    color: root.p.fg
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Label {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    color: modelData.state === "loose" ? root.p.warning : root.p.muted
                                    text: modelData.state === "fixed" ? "fixed"
                                        : modelData.state === "derived" ? "derived"
                                        : modelData.state === "unknown" ? "no estimate"
                                        : "± " + modelData.error + (modelData.rel ? "  (" + modelData.rel + ")" : "")
                                }
                                ToolButton {
                                    id: copyButton
                                    implicitWidth: 24
                                    implicitHeight: 24
                                    opacity: rowMouse.containsMouse || hovered ? 1 : 0.35
                                    icon.source: "image://material/content_copy?color=" + root.p.muted
                                    icon.width: 14
                                    icon.height: 14
                                    icon.color: "transparent"
                                    onClicked: fit.copy(modelData.raw)
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Copy " + modelData.name + " = " + modelData.raw
                                    background: Rectangle {
                                        radius: 4
                                        color: copyButton.hovered ? root.p.border : "transparent"
                                    }
                                }
                                Button {
                                    id: moveButton
                                    visible: modelData.movable === true
                                    enabled: root.s.actionsEnabled === true
                                    implicitHeight: 24
                                    leftPadding: 8
                                    rightPadding: 10
                                    text: "Move"
                                    icon.source: "image://material/my_location?color="
                                        + (enabled ? root.p.on_primary : root.p.muted)
                                    icon.width: 14
                                    icon.height: 14
                                    icon.color: "transparent"
                                    font.pixelSize: 12
                                    palette.buttonText: enabled ? root.p.on_primary : root.p.muted
                                    onClicked: fit.move(modelData.name)
                                    ToolTip.visible: hovered
                                    ToolTip.text: enabled ? "Move to " + modelData.name + " = " + modelData.value
                                                          : "Moving is not available right now"
                                    background: Rectangle {
                                        radius: 4
                                        color: !moveButton.enabled ? root.p.field
                                             : moveButton.down ? Qt.darker(root.p.primary, 1.2)
                                             : moveButton.hovered ? Qt.lighter(root.p.primary, 1.1)
                                             : root.p.primary
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
