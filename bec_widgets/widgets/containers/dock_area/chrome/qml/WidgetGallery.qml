import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// The Add widget gallery: search, placement, and the widgets grouped by category.
Rectangle {
    id: root
    required property QtObject backend
    signal closeRequested()

    color: theme.card
    radius: 10
    border.color: theme.border
    border.width: 1

    function focusSearch() { search.forceActiveFocus(); search.selectAll() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        anchors.bottomMargin: 10
        spacing: 10

        InputField {
            id: search
            Layout.fillWidth: true
            placeholderText: "Search widgets, e.g. plot, motor, queue"
            text: root.backend.query
            onTextEdited: root.backend.set_query(text)
            Keys.onDownPressed: root.backend.move_highlight(1)
            Keys.onUpPressed: root.backend.move_highlight(-1)
            Keys.onReturnPressed: root.backend.activate()
            Keys.onEnterPressed: root.backend.activate()
            Keys.onEscapePressed: root.closeRequested()
        }

        RowLayout {
            spacing: 4
            Text { text: "Place"; color: theme.fgMuted; font.pixelSize: 12; rightPadding: 4 }
            Repeater {
                model: root.backend.placementModel
                delegate: AbstractButton {
                    id: chip
                    required property string key
                    required property string label
                    required property string hint
                    required property bool available
                    enabled: available
                    readonly property bool selected: root.backend.placement === key
                    implicitHeight: 26
                    implicitWidth: chipText.implicitWidth + 18
                    hoverEnabled: true
                    opacity: enabled ? 1 : 0.45
                    onClicked: root.backend.set_placement(key)
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: hint
                    background: Rectangle {
                        radius: 6
                        color: chip.selected ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.2))
                             : chip.hovered ? theme.hover : "transparent"
                        border.color: chip.selected ? theme.primary : theme.border
                    }
                    contentItem: Text {
                        id: chipText
                        text: chip.label
                        color: theme.fg
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
            Item { Layout.fillWidth: true }
        }

        Text {
            text: "Goes: " + root.backend.placementSummary
            color: theme.fgMuted
            font.pixelSize: 12
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.backend.itemModel
            currentIndex: root.backend.highlight
            highlightFollowsCurrentItem: false
            boundsBehavior: Flickable.StopAtBounds
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            section.property: "category"
            section.delegate: Text {
                required property string section
                width: ListView.view.width
                height: 30
                leftPadding: 12
                topPadding: 10
                text: section.toUpperCase()
                color: theme.fgSubtle
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.6
            }

            delegate: ItemDelegate {
                id: row
                required property int index
                required property string name
                required property string description
                required property string iconName
                required property string widgetClass
                readonly property bool isCurrent: ListView.isCurrentItem
                width: ListView.view.width
                height: 50
                hoverEnabled: true
                onHoveredChanged: if (hovered) root.backend.set_highlight(index)
                onClicked: root.backend.activate(index)
                ToolTip.visible: hovered
                ToolTip.delay: 800
                ToolTip.text: description + "\nClass: " + widgetClass
                background: Rectangle {
                    x: 4; width: parent.width - 8; height: parent.height - 2; y: 1
                    radius: 7
                    color: row.isCurrent ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.14))
                         : row.hovered ? theme.hover : "transparent"
                    border.width: row.isCurrent ? 1 : 0
                    border.color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.5))
                }
                contentItem: RowLayout {
                    spacing: 12
                    Rectangle {
                        Layout.leftMargin: 8
                        width: 32; height: 32; radius: 7
                        color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.18))
                        Icon { anchors.centerIn: parent; name: row.iconName; color: theme.primary; size: 18 }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: row.name; color: theme.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Text {
                            Layout.fillWidth: true
                            text: row.description; color: theme.fgMuted; font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        Text {
            visible: list.count === 0
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: "No widget matches. Try another word."
            color: theme.fgMuted
            font.pixelSize: 12
        }

        Text {
            text: "↑ ↓ choose  ·  Enter add  ·  Esc close"
            color: theme.fgSubtle
            font.pixelSize: 11
        }
    }
}
