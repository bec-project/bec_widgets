import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Every BecUi control in the states a widget uses, laid out like a production panel.
Rectangle {
    id: root
    color: theme.bg
    implicitWidth: 760
    implicitHeight: grid.implicitHeight + 32

    GridLayout {
        id: grid
        anchors.fill: parent
        anchors.margins: 16
        columns: 2
        columnSpacing: 12
        rowSpacing: 12

        Card {
            title: "Buttons"
            subtitle: "TextButton · IconButton"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            RowLayout {
                spacing: 8
                TextButton { text: "Start scan"; variant: "primary"; iconName: "play_arrow" }
                TextButton { text: "Resume"; variant: "success"; iconName: "play_arrow" }
                TextButton { text: "Stop"; variant: "danger"; iconName: "stop" }
            }
            RowLayout {
                spacing: 8
                TextButton { text: "Settings"; iconName: "tune" }
                TextButton { text: "Abort queue"; variant: "dangerOutline"; iconName: "cancel" }
                TextButton { text: "Details"; variant: "ghost" }
            }
            RowLayout {
                spacing: 8
                TextButton { text: "Submitting"; variant: "primary"; busy: true }
                TextButton { text: "Disabled"; enabled: false }
                TextButton { text: "Compact"; compact: true; iconName: "refresh" }
            }
            RowLayout {
                spacing: 4
                IconButton { iconName: "pause"; tip: "Pause" }
                IconButton { iconName: "push_pin"; tip: "Pin"; checkable: true; checked: true }
                IconButton { iconName: "content_copy"; tip: "Copy" }
                IconButton { iconName: "delete"; tip: "Remove"; danger: true }
                IconButton { iconName: "more_vert"; tip: "More"; enabled: false }
            }
        }

        Card {
            title: "Status"
            subtitle: "StatusPill · Badge · Spinner · LinearProgress"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            Flow {
                Layout.fillWidth: true
                spacing: 6
                StatusPill { text: "Idle"; tone: "neutral"; outlined: true }
                StatusPill { text: "Running"; tone: "info"; pulse: true }
                StatusPill { text: "Done"; tone: "success" }
                StatusPill { text: "Paused"; tone: "warning" }
                StatusPill { text: "Failed"; tone: "danger" }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                StatusPill { text: "Moving"; tone: "info"; iconName: "sync" }
                StatusPill { text: "Limit"; tone: "warning"; iconName: "warning" }
                StatusPill { text: "Offline"; tone: "danger"; iconName: "cloud_off" }
                StatusPill { text: "Stale"; tone: "stale"; iconName: "schedule"; outlined: true }
            }
            RowLayout {
                spacing: 10
                Text { text: "Inbox"; color: theme.fg; font.pixelSize: theme.fontBody }
                Divider { vertical: true; Layout.preferredHeight: 14; Layout.fillHeight: false }
                Badge { count: 3 }
                Badge { count: 128; tone: "warning" }
                Badge { count: 7; tone: "primary" }
                Item { Layout.fillWidth: true }
                Spinner { size: 16 }
                Text { text: "Connecting"; color: theme.fgMuted; font.pixelSize: theme.fontSmall }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 10
                rowSpacing: 8
                Text { text: "Scan 42"; color: theme.fgMuted; font.pixelSize: theme.fontSmall }
                LinearProgress { Layout.fillWidth: true; value: 0.64 }
                Text { text: "Readout"; color: theme.fgMuted; font.pixelSize: theme.fontSmall }
                LinearProgress { Layout.fillWidth: true; value: 1; tone: "success" }
                Text { text: "Beam"; color: theme.fgMuted; font.pixelSize: theme.fontSmall }
                LinearProgress { Layout.fillWidth: true; value: 0.28; tone: "warning" }
                Text { text: "Waiting"; color: theme.fgMuted; font.pixelSize: theme.fontSmall }
                LinearProgress { id: busyBar; Layout.fillWidth: true; indeterminate: true }
            }
        }

        Card {
            title: "Inputs"
            subtitle: "FormField · fields · SegmentedControl"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            SearchField { Layout.fillWidth: true; placeholderText: "Search devices"; shortcutHint: "Ctrl K" }
            RowLayout {
                spacing: 10
                FormField {
                    Layout.fillWidth: true
                    label: "Start"; unit: "mm"; required: true; helper: "Within soft limits"
                    InputField { text: "-5.000"; suffix: "mm" }
                }
                FormField {
                    Layout.fillWidth: true
                    label: "Steps"; required: true; error: "Must be at least 2"
                    InputField { text: "1"; invalid: true }
                }
            }
            RowLayout {
                spacing: 10
                FormField {
                    Layout.fillWidth: true
                    label: "Motor"
                    SelectField { model: ["samx", "samy", "samz"] }
                }
                FormField {
                    Layout.fillWidth: true
                    label: "Relative"
                    SwitchField { text: checked ? "On" : "Off"; checked: true }
                }
            }
            SegmentedControl {
                model: [{ text: "All", count: 24 }, { text: "Errors", count: 2 }, { text: "Warnings", count: 5 }]
                currentIndex: 1
            }
        }

        Card {
            title: "Feedback"
            subtitle: "Banner · EmptyState"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            Banner { Layout.fillWidth: true; tone: "info"; text: "Scan queued behind 2 others." }
            Banner { Layout.fillWidth: true; tone: "warning"; title: "Beam intensity low"; text: "Ring current is 12 mA below nominal."; closable: true }
            Banner { Layout.fillWidth: true; tone: "danger"; title: "Device server not responding"; text: "Last heartbeat 40 s ago."; actionText: "Retry" }
            Banner { Layout.fillWidth: true; tone: "success"; text: "Configuration saved." }
        }

        Card {
            title: "Cards"
            subtitle: "titles, collapsible sections"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            headerExtras: [
                IconButton { iconName: "refresh"; tip: "Refresh"; compact: true },
                IconButton { iconName: "more_vert"; tip: "More"; compact: true }
            ]
            Card {
                Layout.fillWidth: true
                title: "Scan arguments"
                titleStyle: "caption"
                collapsible: true
                color: theme.sunken
                RowLayout {
                    spacing: 8
                    InputField { Layout.fillWidth: true; text: "samx"; iconName: "precision_manufacturing" }
                    InputField { Layout.preferredWidth: 90; text: "0.5"; suffix: "s" }
                }
            }
            Card {
                Layout.fillWidth: true
                title: "Metadata"
                titleStyle: "caption"
                collapsible: true
                expanded: false
                color: theme.sunken
            }
        }

        Card {
            title: "Empty state"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            fillContent: true
            Item { Layout.fillHeight: true }
            EmptyState {
                Layout.alignment: Qt.AlignHCenter
                iconName: "playlist_play"
                title: "Queue is empty"
                text: "Scans you submit appear here with their progress."
                actionText: "Open scan control"
                actionIcon: "add"
            }
            Item { Layout.fillHeight: true }
        }
    }
}
