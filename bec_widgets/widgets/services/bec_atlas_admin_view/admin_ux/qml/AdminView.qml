import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Admin view: staff sign-in, the active experiment, and switching it in three guided steps
// (review, confirm, log in as the experiment's Linux account). Mirrors admin_view_qwidget.py.
Rectangle {
    id: root
    required property var backend
    readonly property var s: backend.state
    readonly property var wizard: s.wizard || ({})
    readonly property var plan: wizard.plan || ({})
    readonly property var target: wizard.targetInfo || ({})
    readonly property string mono: "DejaVu Sans Mono"

    color: theme.bg

    function toneColor(tone) {
        return tone === "ok" ? theme.success : tone === "warning" ? theme.warning
            : tone === "danger" ? theme.danger : theme.accent
    }
    function tint(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // ---- small building blocks ------------------------------------------------------------
    component Txt: Text {
        property string role: ""
        color: role === "muted" ? theme.fgMuted : role === "subtle" ? theme.fgSubtle
            : role === "error" ? theme.danger : theme.fg
        font.pixelSize: role === "h1" ? 22 : role === "h2" ? 16 : role === "subtle" ? 12 : 13
        font.weight: role === "h1" ? Font.Bold : role === "h2" ? Font.DemiBold
            : role === "strong" ? Font.DemiBold : Font.Normal
        wrapMode: Text.Wrap
    }

    component Chip: Rectangle {
        property string text: ""
        property bool big: false
        implicitWidth: chipText.implicitWidth + (big ? 24 : 12)
        implicitHeight: chipText.implicitHeight + (big ? 8 : 2)
        radius: big ? 6 : 4
        color: tint(theme.primary, big ? 0.18 : 0.14)
        border.width: big ? 1 : 0
        border.color: tint(theme.primary, 0.5)
        Text {
            id: chipText
            anchors.centerIn: parent
            text: parent.text
            color: theme.fg
            font.family: root.mono
            font.pixelSize: parent.big ? 20 : 13
            font.weight: parent.big ? Font.Bold : Font.DemiBold
        }
    }

    component Banner: Rectangle {
        id: banner
        property string tone: "info"
        property string title: ""
        property string text: ""
        readonly property color toneColor: root.toneColor(tone)
        implicitHeight: bannerRow.implicitHeight + 20
        radius: 8
        color: tint(toneColor, 0.14)
        border.color: tint(toneColor, 0.45)
        RowLayout {
            id: bannerRow
            anchors.fill: parent
            anchors.margins: 10
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Icon {
                Layout.alignment: Qt.AlignTop
                name: banner.tone === "ok" ? "check_circle" : banner.tone === "warning" ? "warning"
                    : banner.tone === "danger" ? "error" : "info"
                color: banner.toneColor
                size: 20
            }
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Txt { text: banner.title; role: "strong"; Layout.fillWidth: true }
                Txt { text: banner.text; role: "muted"; visible: banner.text !== ""; Layout.fillWidth: true }
            }
        }
    }

    component NumberDot: Rectangle {
        property string text: ""
        property int size: 22
        width: size; height: size; radius: size / 2
        color: tint(theme.primary, 0.2)
        Text {
            anchors.centerIn: parent
            text: parent.text
            color: theme.fg
            font.pixelSize: parent.size > 20 ? 12 : 11
            font.weight: Font.Bold
        }
    }

    component ActiveCard: Card {
        title: "Active experiment"
        padding: 16
        readonly property var active: s.active || ({})
        RowLayout {
            visible: s.hasActive
            spacing: 8
            Txt { text: active.pgroup || ""; role: "h1" }
            StatusPill { text: "Active"; tone: theme.success }
        }
        Txt { visible: s.hasActive; text: active.title || ""; role: "strong"; Layout.fillWidth: true }
        GridLayout {
            visible: s.hasActive
            columns: 2
            columnSpacing: 16
            rowSpacing: 6
            Layout.fillWidth: true
            Txt { text: "PI"; role: "muted" }
            Txt { text: active.pi || ""; Layout.fillWidth: true }
            Txt { text: "Linux login"; role: "muted" }
            Chip { text: active.linuxAccount || "unknown" }
            Txt { text: "Data saved to"; role: "muted" }
            Chip { text: active.dataAccount || "" }
            Txt { text: "Beamtime"; role: "muted" }
            Txt { text: active.beamtime || ""; Layout.fillWidth: true }
        }
        Txt { visible: !s.hasActive; text: "BEC reports no active experiment."; role: "muted" }
    }

    component NoticeBanner: Banner {
        visible: !!s.notice && s.notice.tone !== undefined
        tone: s.notice ? (s.notice.tone || "info") : "info"
        title: s.notice ? (s.notice.title || "") : ""
        text: s.notice ? (s.notice.text || "") : ""
    }

    component Segmented: Rectangle {
        id: seg
        property var options: []
        property string value: ""
        signal picked(string value)
        implicitWidth: segRow.implicitWidth + 2
        implicitHeight: 32
        radius: 6
        color: "transparent"
        border.color: theme.border
        Row {
            id: segRow
            x: 1; y: 1
            height: parent.height - 2
            Repeater {
                model: seg.options
                delegate: AbstractButton {
                    required property var modelData
                    readonly property bool selected: modelData[0] === seg.value
                    height: segRow.height
                    implicitWidth: segText.implicitWidth + 24
                    hoverEnabled: true
                    onClicked: seg.picked(modelData[0])
                    background: Rectangle {
                        radius: 5
                        color: parent.selected ? tint(theme.primary, 0.18) : parent.hovered ? theme.hover : "transparent"
                    }
                    contentItem: Text {
                        id: segText
                        text: parent.modelData[1]
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: parent.selected ? theme.fg : theme.fgMuted
                        font.pixelSize: 13
                        font.weight: parent.selected ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }

    // ---- layout -------------------------------------------------------------------------
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 56
            color: theme.card
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 10
                Icon { name: "admin_panel_settings"; color: theme.primary; size: 26 }
                ColumnLayout {
                    spacing: 0
                    Txt { text: "Beamline admin"; role: "h2" }
                    Txt { text: s.deploymentName + (s.realm ? " · " + s.realm : ""); role: "muted" }
                }
                Item { Layout.fillWidth: true }
                StatusPill {
                    text: s.signedIn ? s.email + " · " + s.remaining + " left" : "Not signed in"
                    tone: s.signedIn ? theme.success : theme.fgSubtle
                }
                TextButton {
                    visible: s.signedIn
                    text: "Sign out"
                    iconName: "logout"
                    onClicked: backend.logout()
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: s.signedIn ? 1 : 0

            // ---- signed out: the active experiment plus the sign-in card --------------------
            Item {
                RowLayout {
                    anchors.top: parent.top
                    anchors.topMargin: 24
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width - 48, 980)
                    spacing: 16
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 12
                        ActiveCard { Layout.fillWidth: true }
                        NoticeBanner { Layout.fillWidth: true }
                    }
                    Card {
                        id: signIn
                        title: "Staff sign-in"
                        padding: 20
                        Layout.preferredWidth: 360
                        Layout.alignment: Qt.AlignTop
                        function submit() {
                            backend.login(user.text, pass.text)
                            pass.text = ""
                        }
                        Txt {
                            text: "Sign in with your PSI account to switch the active experiment. "
                                + "Your account needs owner rights on " + s.deploymentName + "."
                            role: "muted"
                            Layout.fillWidth: true
                        }
                        Item { implicitHeight: 4 }
                        InputField {
                            id: user
                            placeholderText: "PSI username"
                            Layout.fillWidth: true
                            focus: true
                            onAccepted: pass.forceActiveFocus()
                        }
                        InputField {
                            id: pass
                            placeholderText: "Password"
                            echoMode: TextInput.Password
                            Layout.fillWidth: true
                            onAccepted: signIn.submit()
                        }
                        Txt { visible: s.signInError !== ""; text: s.signInError; role: "error"; Layout.fillWidth: true }
                        TextButton {
                            text: s.signingIn ? "Signing in…" : "Sign in"
                            variant: "primary"
                            iconName: "login"
                            enabled: !s.signingIn
                            Layout.fillWidth: true
                            onClicked: signIn.submit()
                        }
                        Txt {
                            text: "Signing in does not change anything yet. Switching the experiment asks for confirmation first."
                            role: "subtle"
                            Layout.fillWidth: true
                        }
                    }
                }
            }

            // ---- signed in: navigation plus the experiment section ----------------------
            RowLayout {
                spacing: 0
                Rectangle {
                    Layout.preferredWidth: 184
                    Layout.fillHeight: true
                    color: theme.card
                    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: theme.border }
                    Column {
                        anchors.fill: parent
                        anchors.margins: 10
                        anchors.topMargin: 14
                        spacing: 4
                        Repeater {
                            model: s.sections
                            delegate: AbstractButton {
                                required property var modelData
                                width: parent.width
                                height: 34
                                enabled: modelData.enabled
                                hoverEnabled: true
                                readonly property bool current: modelData.id === s.section
                                onClicked: backend.openSection(modelData.id)
                                background: Rectangle {
                                    radius: 6
                                    color: parent.current ? tint(theme.primary, 0.18) : parent.hovered ? theme.hover : "transparent"
                                }
                                contentItem: RowLayout {
                                    spacing: 8
                                    Item { implicitWidth: 2 }
                                    Icon { name: modelData.icon; size: 18; color: modelData.enabled ? theme.fg : theme.fgSubtle }
                                    Text {
                                        text: modelData.label + (modelData.badge ? "   ·  " + modelData.badge : "")
                                        color: modelData.enabled ? theme.fg : theme.fgSubtle
                                        font.pixelSize: 13
                                        font.weight: parent.parent.current ? Font.DemiBold : Font.Normal
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                    }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: wizard.open ? 1 : 0

                    // -- browse: active experiment, guidance and the switch list --
                    ColumnLayout {
                        spacing: 12
                        Item { implicitHeight: 4 }
                        RowLayout {
                            Layout.leftMargin: 20
                            Layout.rightMargin: 20
                            spacing: 12
                            ActiveCard { Layout.fillWidth: true; Layout.preferredWidth: 300; Layout.alignment: Qt.AlignTop }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 200
                                Layout.alignment: Qt.AlignTop
                                spacing: 12
                                NoticeBanner { Layout.fillWidth: true }
                                Card {
                                    title: "How switching works"
                                    padding: 14
                                    spacing: 6
                                    Layout.fillWidth: true
                                    Repeater {
                                        model: s.howItWorks
                                        delegate: RowLayout {
                                            required property var modelData
                                            required property int index
                                            spacing: 8
                                            Layout.fillWidth: true
                                            NumberDot { text: index + 1; size: 20; Layout.alignment: Qt.AlignTop }
                                            Txt { text: modelData; role: "muted"; Layout.fillWidth: true }
                                        }
                                    }
                                }
                            }
                        }
                        Card {
                            title: "Switch experiment"
                            padding: 16
                            spacing: 10
                            fillContent: true
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.leftMargin: 20
                            Layout.rightMargin: 20
                            Layout.bottomMargin: 16
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                InputField {
                                    placeholderText: "Search p-group, title, PI or account"
                                    text: s.query
                                    Layout.fillWidth: true
                                    Layout.rightMargin: 8
                                    onTextEdited: backend.setQuery(text)
                                }
                                Segmented {
                                    options: [["upcoming", "Upcoming"], ["all", "All"]]
                                    value: s.scope
                                    onPicked: (value) => backend.setScope(value)
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 12
                                ListView {
                                    id: list
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 300
                                    Layout.fillHeight: true
                                    clip: true
                                    spacing: 4
                                    model: backend.rows
                                    ScrollBar.vertical: ScrollBar {}
                                    delegate: Rectangle {
                                        required property string pgroup
                                        required property string title
                                        required property string pi
                                        required property string beamtime
                                        required property string status
                                        required property string statusLabel
                                        readonly property bool selected: (s.selected || {}).pgroup === pgroup
                                        width: list.width - 4
                                        height: 52
                                        radius: 8
                                        color: selected ? tint(theme.primary, 0.14) : rowMouse.containsMouse ? theme.hover : "transparent"
                                        border.color: selected ? tint(theme.primary, 0.6) : "transparent"
                                        MouseArea {
                                            id: rowMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: backend.selectExperiment(pgroup)
                                        }
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            spacing: 10
                                            Text {
                                                Layout.alignment: Qt.AlignTop
                                                Layout.topMargin: 8
                                                text: pgroup
                                                color: theme.fg
                                                font.family: root.mono
                                                font.pixelSize: 13
                                                font.weight: Font.DemiBold
                                            }
                                            ColumnLayout {
                                                spacing: 2
                                                Layout.fillWidth: true
                                                Text { text: title; color: theme.fg; font.pixelSize: 13; elide: Text.ElideRight; Layout.fillWidth: true }
                                                Text { text: pi + "  ·  " + beamtime; color: theme.fgMuted; font.pixelSize: 13; elide: Text.ElideRight; Layout.fillWidth: true }
                                            }
                                            StatusPill {
                                                visible: ["active", "now", "next", "past"].indexOf(status) >= 0
                                                text: statusLabel
                                                tone: status === "active" ? theme.success : status === "now" ? theme.warning
                                                    : status === "next" ? theme.primary : theme.fgSubtle
                                            }
                                        }
                                    }
                                    Txt {
                                        anchors.top: parent.top
                                        anchors.topMargin: 8
                                        visible: list.count === 0
                                        role: "muted"
                                        text: s.loadingExperiments ? "Loading experiments…"
                                            : s.totalCount > 0 ? "No experiment matches the search."
                                            : "Atlas lists no experiments for this beamline."
                                    }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 200
                                    Layout.fillHeight: true
                                    radius: 8
                                    color: theme.field
                                    border.color: theme.border
                                    readonly property var sel: s.selected || ({})
                                    readonly property bool has: sel.pgroup !== undefined
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        anchors.topMargin: 12
                                        spacing: 6
                                        Txt { visible: parent.parent.has; text: parent.parent.sel.pgroup || ""; role: "h2" }
                                        Txt { visible: parent.parent.has; text: parent.parent.sel.title || ""; role: "strong"; Layout.fillWidth: true }
                                        Txt { visible: parent.parent.has; text: "PI: " + (parent.parent.sel.pi || ""); role: "muted" }
                                        Txt { visible: parent.parent.has; text: parent.parent.sel.beamtime || ""; role: "muted"; Layout.fillWidth: true }
                                        Txt {
                                            visible: parent.parent.has
                                            textFormat: Text.StyledText
                                            text: "Group logs in as <b>" + (parent.parent.sel.linuxAccount || "unknown") + "</b>"
                                            Layout.fillWidth: true
                                        }
                                        Txt {
                                            visible: parent.parent.has && (parent.parent.sel.abstract || "") !== ""
                                            text: parent.parent.sel.abstract || ""
                                            role: "subtle"
                                            maximumLineCount: 4
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        Txt { visible: !parent.parent.has; text: "Select an experiment to see its details."; role: "muted" }
                                        Item { Layout.fillHeight: true }
                                        TextButton {
                                            visible: parent.parent.has
                                            variant: "primary"
                                            iconName: "swap_horiz"
                                            enabled: s.canSwitch
                                            text: parent.parent.sel.isActive ? "This is the active experiment"
                                                : "Switch to " + parent.parent.sel.pgroup + "…"
                                            Layout.fillWidth: true
                                            onClicked: backend.startSwitch("")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // -- the guided switch: review, confirm, log in --
                    Item {
                        Flickable {
                            anchors.fill: parent
                            contentHeight: wizardCard.implicitHeight + 32
                            clip: true
                            Card {
                                id: wizardCard
                                y: 16
                                padding: 20
                                spacing: 14
                                width: Math.max(560, Math.min(780, root.width - 184 - 40))
                                x: (parent.width - width) / 2
                                ColumnLayout {
                                    spacing: 2
                                    Txt { text: wizard.phase === "done" ? "Experiment switched" : "Switch experiment"; role: "h2" }
                                    Txt { text: (wizard.fromPgroup || "") + " → " + (target.pgroup || ""); role: "muted" }
                                }
                                // stepper
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Repeater {
                                        model: wizard.steps || []
                                        delegate: RowLayout {
                                            required property var modelData
                                            required property int index
                                            readonly property bool finished: index < wizard.step || (wizard.phase === "done" && index === wizard.step)
                                            readonly property bool current: index === wizard.step && wizard.phase !== "done"
                                            spacing: 8
                                            Layout.fillWidth: index > 0
                                            Rectangle {
                                                visible: index > 0
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 24
                                                height: 2
                                                color: index <= wizard.step ? theme.success : theme.border
                                            }
                                            Rectangle {
                                                width: 24; height: 24; radius: 12
                                                color: parent.finished ? theme.success : parent.current ? theme.primary : theme.track
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: parent.parent.finished ? "✓" : index + 1
                                                    color: parent.parent.finished || parent.parent.current ? "white" : theme.fgMuted
                                                    font.pixelSize: 12
                                                    font.weight: Font.Bold
                                                }
                                            }
                                            Text {
                                                text: modelData
                                                color: parent.finished || parent.current ? theme.fg : theme.fgMuted
                                                font.pixelSize: 13
                                                font.weight: parent.finished || parent.current ? Font.DemiBold : Font.Normal
                                            }
                                        }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }

                                // step 1: review
                                ColumnLayout {
                                    visible: wizard.step === 0
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Txt {
                                        text: "Check that this is the right experiment. Switching also changes which Linux account the group uses on this computer."
                                        role: "muted"
                                        Layout.fillWidth: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Item { Layout.preferredWidth: 110 }
                                        Txt { text: "Now"; role: "subtle"; Layout.fillWidth: true; Layout.preferredWidth: 100 }
                                        Item { Layout.preferredWidth: 16 }
                                        Txt { text: "After switching"; role: "subtle"; Layout.fillWidth: true; Layout.preferredWidth: 100 }
                                    }
                                    Repeater {
                                        model: plan.changes || []
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 30
                                            radius: 6
                                            color: modelData.key ? tint(theme.warning, 0.16) : "transparent"
                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 8
                                                anchors.rightMargin: 8
                                                spacing: 0
                                                Txt { text: modelData.label; role: modelData.key ? "strong" : "muted"; Layout.preferredWidth: 102; wrapMode: Text.NoWrap }
                                                Txt { text: modelData.before; role: "muted"; elide: Text.ElideRight; wrapMode: Text.NoWrap; Layout.fillWidth: true; Layout.preferredWidth: 100 }
                                                Icon { name: "arrow_forward"; size: 16; color: theme.fgSubtle; Layout.rightMargin: 12; Layout.leftMargin: 4 }
                                                Item {
                                                    Layout.fillWidth: true
                                                    Layout.preferredWidth: 100
                                                    implicitHeight: 22
                                                    Chip { visible: modelData.key; text: modelData.after; anchors.verticalCenter: parent.verticalCenter }
                                                    Txt { visible: !modelData.key; text: modelData.after; role: "strong"; elide: Text.ElideRight; wrapMode: Text.NoWrap; width: parent.width; anchors.verticalCenter: parent.verticalCenter }
                                                }
                                            }
                                        }
                                    }
                                }

                                // step 2: what happens, then confirm
                                ColumnLayout {
                                    visible: wizard.step === 1
                                    Layout.fillWidth: true
                                    spacing: 10
                                    Txt { text: "What happens when you switch"; role: "strong" }
                                    Repeater {
                                        model: plan.consequences || []
                                        delegate: RowLayout {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            spacing: 10
                                            Icon { name: modelData.icon; size: 20; color: root.toneColor(modelData.tone); Layout.alignment: Qt.AlignTop }
                                            ColumnLayout {
                                                spacing: 1
                                                Layout.fillWidth: true
                                                Txt { text: modelData.title; role: "strong"; Layout.fillWidth: true }
                                                Txt { text: modelData.text; role: "muted"; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: 44
                                        radius: 8
                                        color: tint(theme.warning, 0.14)
                                        border.color: tint(theme.warning, 0.5)
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            spacing: 10
                                            Icon { name: "login"; size: 22; color: theme.warning }
                                            Txt { text: "Afterwards the group must log in to this computer as"; role: "strong"; wrapMode: Text.NoWrap }
                                            Chip { text: plan.linuxAccount || "" }
                                            Item { Layout.fillWidth: true }
                                        }
                                    }
                                    CheckBox {
                                        id: ack
                                        checked: !!wizard.ack
                                        enabled: wizard.phase !== "switching"
                                        text: plan.ackText || ""
                                        onToggled: backend.setAcknowledged(checked)
                                        indicator: Rectangle {
                                            x: ack.leftPadding
                                            y: (ack.height - height) / 2
                                            width: 18; height: 18; radius: 4
                                            color: ack.checked ? theme.primary : theme.field
                                            border.color: ack.checked ? theme.primary : theme.fgSubtle
                                            Text { anchors.centerIn: parent; visible: ack.checked; text: "✓"; color: "white"; font.pixelSize: 13; font.weight: Font.Bold }
                                        }
                                        contentItem: Text {
                                            leftPadding: ack.indicator.width + 10
                                            text: ack.text
                                            color: theme.fg
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                    Banner {
                                        visible: (wizard.error || "") !== ""
                                        tone: "danger"
                                        title: "The switch failed"
                                        text: wizard.error || ""
                                        Layout.fillWidth: true
                                    }
                                }

                                // step 3: log in as the experiment account
                                ColumnLayout {
                                    visible: wizard.step === 2
                                    Layout.fillWidth: true
                                    spacing: 10
                                    Banner {
                                        tone: "ok"
                                        title: (target.pgroup || "") + " is now the active experiment"
                                        text: "New scans are saved for the new experiment. One step is left on this computer:"
                                        Layout.fillWidth: true
                                    }
                                    RowLayout {
                                        spacing: 10
                                        Txt { text: "Log in as"; role: "h2" }
                                        Chip { text: plan.linuxAccount || ""; big: true }
                                    }
                                    Repeater {
                                        model: plan.loginSteps || []
                                        delegate: RowLayout {
                                            required property var modelData
                                            required property int index
                                            Layout.fillWidth: true
                                            spacing: 10
                                            NumberDot { text: index + 1; Layout.alignment: Qt.AlignTop }
                                            ColumnLayout {
                                                spacing: 1
                                                Layout.fillWidth: true
                                                Txt { text: modelData.title; role: "strong"; Layout.fillWidth: true }
                                                Txt { text: modelData.text; role: "muted"; Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 4
                                    TextButton {
                                        visible: wizard.phase !== "done" && wizard.phase !== "switching"
                                        text: "Cancel"
                                        variant: "ghost"
                                        onClicked: backend.closeWizard()
                                    }
                                    Item { Layout.fillWidth: true }
                                    TextButton {
                                        visible: wizard.step > 0 && wizard.phase !== "done" && wizard.phase !== "switching"
                                        text: "Back"
                                        iconName: "arrow_back"
                                        onClicked: backend.back()
                                    }
                                    TextButton {
                                        text: wizard.step === 0 ? "Next"
                                            : wizard.step === 1 ? (wizard.phase === "switching" ? "Switching…" : "Switch to " + (target.pgroup || ""))
                                            : "Done"
                                        variant: wizard.step === 1 ? "danger" : "primary"
                                        iconName: wizard.step === 0 ? "arrow_forward" : wizard.step === 1 ? "swap_horiz" : "check"
                                        busy: wizard.phase === "switching"
                                        enabled: wizard.step !== 1 || !!wizard.canConfirm
                                        onClicked: wizard.step === 0 ? backend.next()
                                            : wizard.step === 1 ? backend.confirm() : backend.closeWizard()
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
