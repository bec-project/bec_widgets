import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

// BEC status box: overall state header plus grouped, expandable service rows.
// Context properties: theme (QmlTheme), statusModel (ServiceStatusModel).
Rectangle {
    id: root
    color: theme.background
    implicitWidth: 360
    implicitHeight: header.height + list.contentHeight + 16

    property string expandedService: ""

    function toneColor(tone) {
        if (tone === "success") return theme.success
        if (tone === "warning") return theme.warning
        if (tone === "emergency") return theme.danger
        return theme.muted
    }
    function iconUrl(name, color, filled) {
        return "image://material/" + name + "?color=" + encodeURIComponent(color.toString())
                + (filled ? "&filled=1" : "")
    }

    // ---- header: overall state ----------------------------------------------------------
    Rectangle {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
        height: 56
        radius: 8
        color: Qt.rgba(root.toneColor(statusModel.tone).r, root.toneColor(statusModel.tone).g,
                       root.toneColor(statusModel.tone).b, theme.dark ? 0.16 : 0.12)
        border.color: Qt.rgba(root.toneColor(statusModel.tone).r, root.toneColor(statusModel.tone).g,
                              root.toneColor(statusModel.tone).b, 0.45)

        RowLayout {
            anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
            spacing: 10
            Rectangle {
                id: dot
                Layout.alignment: Qt.AlignVCenter
                width: 12; height: 12; radius: 6
                color: root.toneColor(statusModel.tone)
                SequentialAnimation on opacity {
                    running: statusModel.tone === "emergency"
                    loops: Animation.Infinite
                    onRunningChanged: if (!running) dot.opacity = 1
                    NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 1.0; duration: 700; easing.type: Easing.InOutQuad }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    objectName: "headline"
                    Layout.fillWidth: true
                    text: statusModel.headline
                    color: theme.text
                    font.pixelSize: 14; font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: statusModel.detail
                    color: theme.muted
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }
        }
    }

    // ---- service list -------------------------------------------------------------------
    ListView {
        id: list
        objectName: "serviceList"
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom
                  topMargin: 4; leftMargin: 8; rightMargin: 8; bottomMargin: 4 }
        clip: true
        model: statusModel
        spacing: 2
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        section.property: "group"
        section.delegate: Item {
            required property string section
            width: ListView.view.width
            height: 28
            Text {
                anchors { left: parent.left; leftMargin: 4; bottom: parent.bottom; bottomMargin: 4 }
                text: section.toUpperCase()
                color: theme.muted
                font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.8
            }
        }

        delegate: Rectangle {
            id: rowItem
            required property int index
            required property string serviceName
            required property string displayName
            required property string subtitle
            required property string status
            required property string statusLabel
            required property string tone
            required property string icon
            required property string version
            required property bool versionMismatch
            required property string uptime
            required property var details

            readonly property bool expanded: root.expandedService === serviceName
            readonly property color accent: root.toneColor(tone)

            width: ListView.view.width
            height: rowContent.height
            radius: 6
            color: hover.hovered || expanded ? theme.card : "transparent"
            border.color: expanded ? theme.border : "transparent"
            Behavior on height { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

            HoverHandler { id: hover }

            Column {
                id: rowContent
                width: parent.width

                // main line
                MouseArea {
                    width: parent.width
                    height: 44
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.expandedService = rowItem.expanded ? "" : rowItem.serviceName

                    RowLayout {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        spacing: 10

                        Image {
                            id: statusIcon
                            Layout.preferredWidth: 20; Layout.preferredHeight: 20
                            sourceSize: Qt.size(20, 20)
                            source: root.iconUrl(rowItem.icon, rowItem.accent, true)
                            RotationAnimation on rotation {
                                running: rowItem.status === "BUSY"
                                loops: Animation.Infinite
                                from: 0; to: 360; duration: 1200
                                onRunningChanged: if (!running) statusIcon.rotation = 0
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                Layout.fillWidth: true
                                text: rowItem.displayName
                                color: theme.text
                                font.pixelSize: 13
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: text.length > 0
                                text: rowItem.subtitle
                                color: theme.muted
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle {
                            visible: rowItem.versionMismatch
                            Layout.preferredHeight: 18
                            Layout.preferredWidth: mismatchText.implicitWidth + 12
                            radius: 9
                            color: "transparent"
                            border.color: theme.warning
                            ToolTip.visible: mismatchHover.hovered
                            ToolTip.text: "bec_lib " + rowItem.version + " differs from the other services"
                            HoverHandler { id: mismatchHover }
                            Text {
                                id: mismatchText
                                anchors.centerIn: parent
                                text: "v" + rowItem.version
                                color: theme.warning
                                font.pixelSize: 10
                            }
                        }
                        Rectangle {
                            Layout.preferredHeight: 20
                            Layout.preferredWidth: statusText.implicitWidth + 16
                            radius: 10
                            color: Qt.rgba(rowItem.accent.r, rowItem.accent.g, rowItem.accent.b, 0.15)
                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                text: rowItem.statusLabel
                                color: rowItem.accent
                                font.pixelSize: 11; font.bold: true
                            }
                        }
                        Image {
                            Layout.preferredWidth: 16; Layout.preferredHeight: 16
                            sourceSize: Qt.size(16, 16)
                            source: root.iconUrl("expand_more", theme.muted, false)
                            rotation: rowItem.expanded ? 180 : 0
                            Behavior on rotation { NumberAnimation { duration: 120 } }
                        }
                    }
                }

                // details
                Item {
                    visible: rowItem.expanded
                    width: parent.width
                    height: visible ? detailsGrid.implicitHeight + 16 : 0

                    GridLayout {
                        id: detailsGrid
                        anchors { left: parent.left; right: copyButton.left; top: parent.top
                                  leftMargin: 38; rightMargin: 8 }
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 3
                        Repeater {
                            model: rowItem.expanded ? rowItem.details : []
                            delegate: Text {
                                required property var modelData
                                required property int index
                                Layout.row: index
                                Layout.column: 0
                                text: modelData.key
                                color: theme.muted
                                font.pixelSize: 11
                            }
                        }
                        Repeater {
                            model: rowItem.expanded ? rowItem.details : []
                            delegate: Text {
                                required property var modelData
                                required property int index
                                Layout.row: index
                                Layout.column: 1
                                Layout.fillWidth: true
                                text: modelData.value
                                color: theme.text
                                font.pixelSize: 11
                                elide: Text.ElideMiddle
                            }
                        }
                    }
                    Rectangle {
                        id: copyButton
                        anchors { right: parent.right; top: parent.top; rightMargin: 8 }
                        width: 28; height: 28; radius: 6
                        color: copyArea.containsMouse ? Qt.rgba(theme.text.r, theme.text.g, theme.text.b, 0.08)
                                                      : "transparent"
                        ToolTip.visible: copyArea.containsMouse
                        ToolTip.text: copied ? "Copied" : "Copy details"
                        property bool copied: false
                        Image {
                            anchors.centerIn: parent
                            sourceSize: Qt.size(16, 16)
                            source: root.iconUrl(copyButton.copied ? "check" : "content_copy",
                                                 theme.muted, false)
                        }
                        MouseArea {
                            id: copyArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                statusModel.copyDetails(rowItem.serviceName)
                                copyButton.copied = true
                                copiedTimer.restart()
                            }
                        }
                        Timer { id: copiedTimer; interval: 1500; onTriggered: copyButton.copied = false }
                    }
                }
            }
        }
    }
}
