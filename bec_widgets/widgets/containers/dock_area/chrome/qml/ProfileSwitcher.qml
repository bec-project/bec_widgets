import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// The profile switcher: search, profiles with their saved previews, and Save as, Revert, library.
Rectangle {
    id: root
    required property QtObject backend
    signal closeRequested()

    color: theme.card
    radius: 10
    border.color: theme.border
    border.width: 1

    function focusSearch() { search.forceActiveFocus(); search.selectAll() }
    function run(key) { root.closeRequested(); root.backend.request(key) }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        anchors.bottomMargin: 10
        spacing: 8

        InputField {
            id: search
            Layout.fillWidth: true
            placeholderText: "Find a profile"
            text: root.backend.query
            onTextEdited: root.backend.set_query(text)
            Keys.onDownPressed: root.backend.move_highlight(1)
            Keys.onUpPressed: root.backend.move_highlight(-1)
            Keys.onReturnPressed: (event) => root.backend.activate(-1, (event.modifiers & Qt.ControlModifier) && root.backend.hasTabs)
            Keys.onEnterPressed: (event) => root.backend.activate(-1, (event.modifiers & Qt.ControlModifier) && root.backend.hasTabs)
            Keys.onEscapePressed: root.closeRequested()
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.backend.rowModel
            currentIndex: root.backend.highlight
            highlightFollowsCurrentItem: false
            boundsBehavior: Flickable.StopAtBounds
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: ItemDelegate {
                id: row
                required property int index
                required property string name
                required property string subtitle
                required property string previewUrl
                required property bool readOnly
                required property bool isCurrent
                required property bool isOpenElsewhere
                required property string header
                readonly property bool highlighted_: ListView.isCurrentItem
                width: ListView.view.width
                height: 68 + (header !== "" ? 30 : 0)
                topPadding: header !== "" ? 30 : 0
                Text {
                    visible: row.header !== ""
                    y: 0; height: 30
                    leftPadding: 12; topPadding: 10
                    text: row.header.toUpperCase()
                    color: theme.fgSubtle
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.6
                }
                hoverEnabled: true
                onHoveredChanged: if (hovered) root.backend.set_highlight(index)
                onClicked: root.backend.activate(index, false)
                TapHandler {
                    acceptedModifiers: Qt.ControlModifier
                    onTapped: root.backend.activate(row.index, root.backend.hasTabs)
                }
                background: Rectangle {
                    x: 4; width: row.width - 8; height: 66; y: (row.header !== "" ? 30 : 0) + 1
                    radius: 7
                    color: row.highlighted_ ? Qt.tint(theme.card, Qt.alpha(theme.primary, 0.14))
                         : row.hovered ? theme.hover : "transparent"
                    border.width: row.highlighted_ ? 1 : 0
                    border.color: Qt.tint(theme.card, Qt.alpha(theme.primary, 0.5))
                }
                contentItem: RowLayout {
                    spacing: 12
                    Rectangle {
                        Layout.leftMargin: 2
                        width: 96; height: 54; radius: 5
                        color: Qt.rgba(theme.fg.r, theme.fg.g, theme.fg.b, 0.05)
                        border.color: theme.border
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: row.previewUrl
                            fillMode: Image.PreserveAspectCrop
                            smooth: true
                            visible: row.previewUrl !== ""
                        }
                        Icon {
                            anchors.centerIn: parent
                            visible: row.previewUrl === ""
                            name: "dashboard"; size: 22; color: theme.fgSubtle
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                Layout.fillWidth: true
                                text: row.name; color: theme.fg
                                font.pixelSize: 13; font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            StatusPill { visible: row.readOnly; text: "Read-only"; tone: theme.fgMuted }
                            StatusPill { visible: row.isOpenElsewhere; text: "In another tab"; tone: theme.fgMuted }
                            StatusPill { visible: row.isCurrent; text: "Open here"; tone: theme.primary }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: row.subtitle; color: theme.fgMuted; font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        Text {
            visible: list.count === 0
            Layout.fillWidth: true
            Layout.margins: 16
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.backend.emptyText
            color: theme.fgMuted
            font.pixelSize: 12
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }

        RowLayout {
            spacing: 4
            TextButton { text: "Save as…"; variant: "ghost"; iconName: "save"; tip: "Save the current layout as a profile"; onClicked: root.run("save") }
            TextButton { text: "Revert…"; variant: "ghost"; iconName: "history"; enabled: root.backend.canRevert; tip: "Go back to the saved version of this profile"; onClicked: root.run("revert") }
            TextButton { text: "All profiles…"; variant: "ghost"; iconName: "folder_open"; tip: "Open the profile library"; onClicked: root.run("library") }
            Item { Layout.fillWidth: true }
        }

        Text {
            text: "↑ ↓ choose  ·  Enter open" + (root.backend.hasTabs ? "  ·  Ctrl+Enter or Ctrl+click new tab" : "") + "  ·  Esc close"
            color: theme.fgSubtle
            font.pixelSize: 11
        }
    }
}
