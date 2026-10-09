import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import BecUi

// Curve settings of a waveform: X axis strip, curve list with nested fits, and an inspector
// for the selected curve. All state lives in the Python CurveDialogModel (via `backend`).
Rectangle {
    id: root
    required property var backend
    readonly property var sel: backend.selected
    readonly property bool hasSel: sel.uid !== undefined && sel.uid >= 0

    color: theme.bg

    function openPicker(purpose, item) {
        const p = item.mapToItem(null, 0, 0)
        root.backend.openPicker(purpose, p.x, p.y, item.width, item.height)
    }

    Shortcut { sequences: [StandardKey.New]; onActivated: root.openPicker("add", addButton) }

    component Caption: Text {
        color: theme.fgMuted
        font.pixelSize: theme.fontSmall
        font.weight: Font.Medium
    }

    // checkable tile showing a line style or a symbol
    component SampleTile: AbstractButton {
        id: tile
        property string penStyle: "solid"
        property string symbol: "none"
        property color sampleColor: theme.fg
        property bool selected: false
        property string tip: ""
        implicitWidth: symbol === "none" ? 46 : 34
        implicitHeight: 30
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        Accessible.name: tip
        Accessible.role: Accessible.RadioButton
        ToolTip.visible: hovered && tip !== ""
        ToolTip.text: tip
        ToolTip.delay: 500
        background: Rectangle {
            radius: theme.radiusSmall
            color: tile.selected ? theme.toneTint("primary") : theme.field
            border.width: tile.selected || tile.visualFocus ? 2 : 1
            border.color: tile.selected || tile.visualFocus ? theme.primary : tile.hovered ? theme.fgSubtle : theme.border
        }
        contentItem: Item {
            CurveSample {
                anchors.centerIn: parent
                visible: tile.symbol === "none"
                width: parent.width - 16
                height: 10
                peak: false
                color: tile.selected ? tile.sampleColor : theme.fg
                penStyle: tile.penStyle
                penWidth: 2.2
            }
            CurveSample {
                anchors.centerIn: parent
                visible: tile.symbol !== "none" && tile.symbol !== ""
                width: 14
                height: 14
                peak: false
                penWidth: 0.01
                color: tile.selected ? tile.sampleColor : theme.fg
                symbol: tile.symbol === "none" ? "" : tile.symbol
                symbolSize: 11
                maxSymbol: 11
            }
            Rectangle {
                anchors.centerIn: parent
                visible: tile.symbol === ""
                width: 16; height: 1.5; rotation: -45
                color: theme.fgMuted
            }
        }
    }

    component ValueSlider: RowLayout {
        id: vs
        property int from: 1
        property int to: 20
        property int value: 1
        property string tip: ""
        signal moved(int value)
        spacing: 8
        Slider {
            id: slider
            Layout.fillWidth: true
            from: vs.from
            to: Math.max(vs.to, vs.value)
            stepSize: 1
            snapMode: Slider.SnapAlways
            value: vs.value
            Accessible.name: vs.tip
            onMoved: vs.moved(Math.round(value))
            background: Rectangle {
                x: slider.leftPadding
                y: slider.topPadding + slider.availableHeight / 2 - height / 2
                width: slider.availableWidth
                height: 4
                radius: 2
                color: theme.track
                Rectangle {
                    width: slider.visualPosition * parent.width
                    height: parent.height
                    radius: 2
                    color: slider.enabled ? theme.primary : theme.fgSubtle
                }
            }
            handle: Rectangle {
                x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                y: slider.topPadding + slider.availableHeight / 2 - height / 2
                width: 16; height: 16; radius: 8
                color: theme.card
                border.width: slider.visualFocus ? 3 : 2
                border.color: slider.enabled ? theme.primary : theme.fgSubtle
            }
        }
        Text {
            Layout.preferredWidth: 38
            text: Math.round(slider.value) + " px"
            color: theme.fgMuted
            font.pixelSize: theme.fontSmall
            horizontalAlignment: Text.AlignRight
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 10

        // ---- X axis ---------------------------------------------------------------------
        Card {
            Layout.fillWidth: true
            title: "X axis"
            titleStyle: "caption"
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                SegmentedControl {
                    model: root.backend.xModes
                    currentIndex: root.backend.xModeIndex
                    Accessible.name: "X axis mode"
                    onActivated: (index) => root.backend.setXMode(index)
                }
                PickerField {
                    id: xDevice
                    visible: root.backend.xModeIndex === 3
                    Layout.fillWidth: true
                    Layout.minimumWidth: 160
                    text: root.backend.xDevice
                    placeholder: "Select device…"
                    invalid: root.backend.xInvalid
                    onRequested: root.openPicker("xdevice", xDevice)
                }
                PickerField {
                    id: xSignal
                    visible: root.backend.xModeIndex === 3
                    Layout.fillWidth: true
                    Layout.minimumWidth: 160
                    iconName: "sensors"
                    text: root.backend.xSignal
                    placeholder: "Select signal…"
                    onRequested: root.openPicker("xsignal", xSignal)
                }
                Text {
                    Layout.fillWidth: true
                    Layout.horizontalStretchFactor: 2
                    text: root.backend.xHelp
                    color: root.backend.xInvalid ? theme.dangerText : theme.fgMuted
                    font.pixelSize: theme.fontSmall
                    wrapMode: Text.WordWrap
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // ---- curve list -------------------------------------------------------------
            Rectangle {
                Layout.preferredWidth: 330
                Layout.fillHeight: true
                color: theme.card
                radius: theme.radiusLarge
                border.color: theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            text: "Curves"
                            color: theme.fg
                            font.pixelSize: theme.fontTitle
                            font.weight: Font.DemiBold
                        }
                        Badge { count: root.backend.curveCount; tone: "neutral"; showZero: false }
                        Item { Layout.fillWidth: true }
                        ComboBox {
                            id: paletteBox
                            implicitWidth: 138
                            implicitHeight: theme.controlHeight
                            model: root.backend.palettes
                            textRole: "name"
                            currentIndex: {
                                const list = root.backend.palettes
                                for (let i = 0; i < list.length; ++i)
                                    if (list[i].name === root.backend.palette) return i
                                return 0
                            }
                            hoverEnabled: true
                            ToolTip.visible: hovered && !popup.visible
                            ToolTip.text: "Palette for curve colours. Choosing one recolours every curve."
                            ToolTip.delay: 500
                            Accessible.name: "Colour palette"
                            onActivated: (index) => root.backend.setPalette(root.backend.palettes[index].name)
                            background: FieldFrame {
                                focused: paletteBox.activeFocus || paletteBox.popup.visible
                                hovered: paletteBox.hovered
                            }
                            contentItem: RowLayout {
                                spacing: 6
                                Item { implicitWidth: 3 }
                                Row {
                                    Repeater {
                                        model: root.backend.palettes.length > paletteBox.currentIndex ? root.backend.palettes[paletteBox.currentIndex].stops : []
                                        Rectangle { width: 8; height: 12; color: modelData }
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: paletteBox.currentText
                                    color: theme.fg
                                    font.pixelSize: theme.fontBody
                                    elide: Text.ElideRight
                                }
                            }
                            indicator: Icon {
                                x: paletteBox.width - width - 6
                                y: (paletteBox.height - height) / 2
                                name: "expand_more"; size: 18; color: theme.fgMuted
                            }
                            delegate: ItemDelegate {
                                id: palOption
                                required property int index
                                required property var modelData
                                width: paletteBox.width
                                height: 30
                                highlighted: paletteBox.highlightedIndex === index
                                contentItem: RowLayout {
                                    spacing: 8
                                    Row {
                                        Repeater {
                                            model: palOption.modelData.stops
                                            Rectangle { width: 8; height: 12; color: modelData }
                                        }
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: palOption.modelData.name
                                        color: theme.fg
                                        font.pixelSize: theme.fontBody
                                    }
                                }
                                background: Rectangle { color: palOption.highlighted ? theme.hover : "transparent" }
                            }
                            popup: Popup {
                                y: paletteBox.height + 2
                                width: paletteBox.width
                                implicitHeight: contentItem.implicitHeight + 8
                                padding: 4
                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: paletteBox.popup.visible ? paletteBox.delegateModel : null
                                }
                                background: Rectangle { color: theme.card; border.color: theme.border; radius: theme.radiusSmall + 2 }
                            }
                        }
                        IconButton {
                            iconName: "format_color_fill"
                            tip: "Recolour all curves from the palette"
                            compact: true
                            onClicked: root.backend.recolorAll()
                        }
                    }
                    TextButton {
                        id: addButton
                        objectName: "addButton"
                        Layout.fillWidth: true
                        text: "Add curve"
                        iconName: "add"
                        variant: "primary"
                        tip: "Pick a device to plot (Ctrl+N)"
                        onClicked: root.openPicker("add", addButton)
                    }
                    ListView {
                        id: curveList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.backend.rows
                        boundsBehavior: Flickable.StopAtBounds
                        focus: true
                        activeFocusOnTab: true
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 8 }
                        Keys.onPressed: (event) => {
                            if (event.key === Qt.Key_Down) { root.backend.move(1); event.accepted = true }
                            else if (event.key === Qt.Key_Up) { root.backend.move(-1); event.accepted = true }
                            else if ((event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) && root.hasSel) {
                                root.backend.remove(root.sel.uid); event.accepted = true
                            }
                        }
                        delegate: Item {
                            id: rowItem
                            required property var modelData
                            required property int index
                            readonly property var r: modelData
                            width: ListView.view.width
                            height: r.depth ? 48 : 52
                            Accessible.role: Accessible.ListItem
                            Accessible.name: r.title + ", " + r.subtitle
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 2
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                radius: 8
                                color: rowItem.r.selected ? theme.toneTint("primary") : rowMouse.containsMouse ? theme.hover : "transparent"
                                border.width: rowItem.r.selected ? 1.5 : 0
                                border.color: theme.primary
                            }
                            // tree connector for fits
                            Rectangle {
                                visible: rowItem.r.depth > 0
                                x: 20; y: -4; width: 1.5; height: parent.height / 2 + 4
                                color: theme.separator
                            }
                            Rectangle {
                                visible: rowItem.r.depth > 0
                                x: 20; y: parent.height / 2; width: 10; height: 1.5
                                color: theme.separator
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14 + (rowItem.r.depth ? 22 : 0)
                                anchors.rightMargin: 14
                                spacing: 12
                                CurveSample {
                                    implicitWidth: 40; implicitHeight: 20
                                    color: rowItem.r.color
                                    penStyle: rowItem.r.penStyle
                                    penWidth: rowItem.r.penWidth
                                    symbol: rowItem.r.symbol
                                    symbolSize: rowItem.r.symbolSize
                                    maxWidth: 3; maxSymbol: 7
                                    peak: rowItem.r.kind !== "custom"
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        Layout.fillWidth: true
                                        text: rowItem.r.title
                                        color: theme.fg
                                        font.pixelSize: theme.fontBody
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: rowItem.r.error !== "" ? rowItem.r.error : rowItem.r.subtitle
                                        color: rowItem.r.error !== "" ? theme.dangerText : theme.fgMuted
                                        font.pixelSize: theme.fontSmall
                                        elide: Text.ElideRight
                                    }
                                }
                                Rectangle {
                                    readonly property string label: rowItem.r.tag === "history" ? rowItem.r.subtitle.split("· ").pop() : rowItem.r.tag
                                    visible: label !== "" && label !== "fit"
                                    implicitWidth: tagText.implicitWidth + 14
                                    implicitHeight: 20
                                    radius: 10
                                    color: (theme.name, theme.toneTint(rowItem.r.tag === "custom" ? "highlight" : "info"))
                                    Text {
                                        id: tagText
                                        anchors.centerIn: parent
                                        text: parent.label
                                        color: (theme.name, theme.toneText(rowItem.r.tag === "custom" ? "highlight" : "info"))
                                        font.pixelSize: theme.fontCaption
                                        font.weight: Font.DemiBold
                                    }
                                }
                                Icon {
                                    visible: rowItem.r.error !== ""
                                    name: "error"; filled: true; size: 18
                                    color: theme.dangerText
                                }
                            }
                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { curveList.forceActiveFocus(); root.backend.select(rowItem.r.uid) }
                                ToolTip.visible: containsMouse && rowItem.r.error !== ""
                                ToolTip.text: rowItem.r.error
                                ToolTip.delay: 400
                            }
                        }
                    }
                    Banner {
                        Layout.fillWidth: true
                        visible: root.backend.problems.length > 0
                        tone: "warning"
                        title: root.backend.problems.length === 1 ? "1 problem to fix before applying"
                            : root.backend.problems.length + " problems to fix before applying"
                        text: root.backend.problems.slice(0, 3).join("\n")
                    }
                }
            }

            // ---- inspector --------------------------------------------------------------
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                EmptyState {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 40, 380)
                    visible: !root.hasSel
                    iconName: "show_chart"
                    title: "No curves yet"
                    text: "Add a device to plot it against the X axis. Fits and colours are set per curve."
                    actionText: "Add curve"
                    actionIcon: "add"
                    onActionTriggered: root.openPicker("add", addButton)
                }

                ScrollView {
                    id: inspector
                    anchors.fill: parent
                    visible: root.hasSel
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    ColumnLayout {
                        width: inspector.availableWidth - 6
                        spacing: 10

                        // header
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 2
                            Layout.rightMargin: 2
                            spacing: 12
                            Rectangle {
                                implicitWidth: 84; implicitHeight: 44
                                radius: 8
                                color: theme.field
                                border.color: theme.border
                                CurveSample {
                                    anchors.fill: parent
                                    anchors.margins: 7
                                    anchors.leftMargin: 8; anchors.rightMargin: 8
                                    color: root.sel.color || "#888888"
                                    penStyle: root.sel.penStyle || "solid"
                                    penWidth: root.sel.penWidth || 1
                                    symbol: root.sel.symbol || ""
                                    symbolSize: root.sel.symbolSize || 1
                                    maxWidth: 6; maxSymbol: 12
                                    peak: root.sel.kind !== "custom"
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    Layout.fillWidth: true
                                    text: root.sel.title || ""
                                    color: theme.fg
                                    font.pixelSize: theme.fontTitle
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: root.sel.subtitle || ""
                                    color: theme.fgMuted
                                    font.pixelSize: theme.fontSmall
                                    elide: Text.ElideRight
                                }
                            }
                            TextButton {
                                visible: root.sel.kind !== "dap"
                                text: "Add fit"
                                iconName: "add"
                                compact: true
                                tip: "Fit a model to this curve"
                                onClicked: root.backend.addFit(root.sel.uid)
                            }
                            IconButton {
                                visible: root.sel.kind !== "custom"
                                iconName: "delete"
                                danger: true
                                tip: root.sel.kind === "dap" ? "Remove fit" : "Remove curve and its fits"
                                onClicked: root.backend.remove(root.sel.uid)
                            }
                        }

                        // data source of a device curve
                        Card {
                            Layout.fillWidth: true
                            visible: root.sel.kind === "device"
                            title: "Data"
                            titleStyle: "caption"
                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 12
                                rowSpacing: 10
                                FormField {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    label: "Device"
                                    required: true
                                    error: root.sel.deviceError || ""
                                    PickerField {
                                        id: deviceField
                                        text: root.sel.device || ""
                                        placeholder: "Select device…"
                                        invalid: (root.sel.deviceError || "") !== ""
                                        onRequested: root.openPicker("device", deviceField)
                                    }
                                }
                                FormField {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    label: "Signal"
                                    required: true
                                    error: root.sel.signalError || ""
                                    PickerField {
                                        id: signalField
                                        iconName: "sensors"
                                        text: root.sel.signal || ""
                                        placeholder: "Select signal…"
                                        invalid: (root.sel.signalError || "") !== ""
                                        onRequested: root.openPicker("signal", signalField)
                                    }
                                }
                                FormField {
                                    Layout.columnSpan: 2
                                    Layout.fillWidth: true
                                    label: "Data from"
                                    helper: "Live follows the running scan; an earlier scan shows its stored data."
                                    error: root.sel.scanError || ""
                                    SelectField {
                                        model: root.sel.scanLabels || []
                                        currentIndex: root.sel.scanIndex || 0
                                        invalid: (root.sel.scanError || "") !== ""
                                        Accessible.name: "Data from"
                                        onActivated: (index) => root.backend.setScan(root.sel.uid, index)
                                    }
                                }
                            }
                        }

                        // command-line curve
                        Banner {
                            Layout.fillWidth: true
                            visible: root.sel.kind === "custom"
                            tone: "info"
                            title: "Curve sent from the command line"
                            text: "Its data came from plot(x=..., y=...), so only its look can be changed here. Remove it from the command line."
                        }

                        // fits of a curve
                        Card {
                            Layout.fillWidth: true
                            visible: root.sel.kind === "device" || root.sel.kind === "custom"
                            title: "Fits"
                            titleStyle: "caption"
                            Text {
                                Layout.fillWidth: true
                                visible: (root.sel.fits || []).length === 0
                                text: "No fits. Add one to fit a model such as a Gaussian to this curve."
                                color: theme.fgMuted
                                font.pixelSize: theme.fontSmall
                                wrapMode: Text.WordWrap
                            }
                            Repeater {
                                model: root.sel.fits || []
                                delegate: AbstractButton {
                                    id: fitLink
                                    required property var modelData
                                    implicitHeight: theme.controlHeightCompact
                                    implicitWidth: fitRow.implicitWidth + 18
                                    hoverEnabled: true
                                    Accessible.name: "Edit " + modelData.title
                                    onClicked: root.backend.select(modelData.uid)
                                    background: Rectangle { radius: theme.radiusSmall; color: fitLink.hovered ? theme.hover : "transparent" }
                                    contentItem: RowLayout {
                                        id: fitRow
                                        spacing: 8
                                        CurveSample {
                                            implicitWidth: 32; implicitHeight: 14
                                            color: fitLink.modelData.color
                                            penStyle: fitLink.modelData.penStyle
                                            penWidth: 2
                                        }
                                        Text {
                                            text: fitLink.modelData.title
                                            color: theme.fg
                                            font.pixelSize: theme.fontSmall
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }
                            }
                        }

                        // fit model
                        Card {
                            Layout.fillWidth: true
                            visible: root.sel.kind === "dap"
                            title: "Fit"
                            titleStyle: "caption"
                            FormField {
                                Layout.fillWidth: true
                                label: "Model"
                                required: true
                                error: root.sel.modelError || ""
                                SelectField {
                                    model: root.sel.models || []
                                    currentIndex: root.sel.modelIndex || 0
                                    Accessible.name: "Fit model"
                                    onActivated: (index) => root.backend.setPrimaryModel(root.sel.uid, root.sel.models[index])
                                }
                            }
                            Caption { text: "Combine with" }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 6
                                Repeater {
                                    model: root.sel.extras || []
                                    delegate: AbstractButton {
                                        id: chip
                                        required property var modelData
                                        implicitHeight: 26
                                        implicitWidth: chipText.implicitWidth + 26
                                        hoverEnabled: true
                                        focusPolicy: Qt.TabFocus
                                        Accessible.role: Accessible.CheckBox
                                        Accessible.name: "Add " + modelData.name + " to a composite fit"
                                        onClicked: root.backend.toggleExtraModel(root.sel.uid, modelData.name)
                                        background: Rectangle {
                                            radius: 13
                                            color: chip.modelData.checked ? theme.toneTint("primary") : theme.field
                                            border.width: chip.visualFocus ? 2 : 1
                                            border.color: chip.modelData.checked || chip.visualFocus ? theme.primary : chip.hovered ? theme.fgSubtle : theme.border
                                        }
                                        contentItem: Text {
                                            id: chipText
                                            text: chip.modelData.label
                                            color: theme.fg
                                            font.pixelSize: theme.fontSmall
                                            font.weight: chip.modelData.checked ? Font.DemiBold : Font.Normal
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: root.sel.composite || ""
                                color: theme.fgMuted
                                font.pixelSize: theme.fontSmall
                                wrapMode: Text.WordWrap
                            }
                            TextButton {
                                visible: (root.sel.parentUid || -1) >= 0
                                text: "Fits " + (root.sel.parentTitle || "")
                                iconName: "arrow_back"
                                variant: "ghost"
                                compact: true
                                tip: "Select the fitted curve"
                                onClicked: root.backend.select(root.sel.parentUid)
                            }
                        }

                        // appearance
                        Card {
                            Layout.fillWidth: true
                            title: "Appearance"
                            titleStyle: "caption"
                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 14
                                rowSpacing: 12

                                Caption { text: "Colour" }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Repeater {
                                        model: root.sel.swatches || []
                                        delegate: AbstractButton {
                                            id: swatch
                                            required property var modelData
                                            readonly property bool current: (root.sel.color || "").toLowerCase() === modelData.toLowerCase()
                                            implicitWidth: 26; implicitHeight: 26
                                            focusPolicy: Qt.TabFocus
                                            hoverEnabled: true
                                            Accessible.name: "Colour " + modelData
                                            ToolTip.visible: hovered
                                            ToolTip.text: modelData
                                            ToolTip.delay: 500
                                            onClicked: root.backend.setStyle(root.sel.uid, "color", modelData)
                                            background: Rectangle {
                                                radius: 13
                                                color: "transparent"
                                                border.width: swatch.current || swatch.visualFocus ? 2 : 0
                                                border.color: swatch.current ? theme.fg : theme.primary
                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 16; height: 16; radius: 8
                                                    color: swatch.modelData
                                                    border.color: Qt.rgba(0, 0, 0, 0.16)
                                                }
                                            }
                                        }
                                    }
                                    Item { implicitWidth: 6 }
                                    TextButton {
                                        text: "Custom…"
                                        iconName: "colorize"
                                        variant: "ghost"
                                        compact: true
                                        tip: "Pick any colour"
                                        onClicked: root.backend.pickCustomColor(root.sel.uid)
                                    }
                                    Item { Layout.fillWidth: true }
                                }

                                Caption { text: "Line" }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Repeater {
                                        model: root.backend.penStyles
                                        delegate: SampleTile {
                                            required property var modelData
                                            penStyle: modelData.value
                                            tip: modelData.label + " line"
                                            sampleColor: root.sel.color || theme.fg
                                            selected: root.sel.penStyle === modelData.value
                                            onClicked: root.backend.setStyle(root.sel.uid, "pen_style", modelData.value)
                                        }
                                    }
                                    Item { implicitWidth: 10 }
                                    ValueSlider {
                                        Layout.fillWidth: true
                                        from: 1; to: 10
                                        value: root.sel.penWidth || 1
                                        tip: "Line width"
                                        onMoved: (v) => root.backend.setStyle(root.sel.uid, "pen_width", v)
                                    }
                                }

                                Caption { text: "Symbol" }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Repeater {
                                        model: root.backend.symbols
                                        delegate: SampleTile {
                                            required property var modelData
                                            symbol: modelData.value
                                            tip: modelData.label
                                            sampleColor: root.sel.color || theme.fg
                                            selected: (root.sel.symbol || "") === modelData.value
                                            onClicked: root.backend.setStyle(root.sel.uid, "symbol", modelData.value)
                                        }
                                    }
                                    Item { implicitWidth: 10 }
                                    ValueSlider {
                                        Layout.fillWidth: true
                                        enabled: (root.sel.symbol || "") !== ""
                                        from: 1; to: 20
                                        value: root.sel.symbolSize || 1
                                        tip: "Symbol size"
                                        onMoved: (v) => root.backend.setStyle(root.sel.uid, "symbol_size", v)
                                    }
                                }
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
