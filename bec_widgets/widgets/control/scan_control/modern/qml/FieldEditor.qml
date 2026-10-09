import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// One scan input. Picks the editor from spec.kind and reports changes through edited().
Item {
    id: editor

    property var spec: ({})
    property var value
    property string units
    property string error
    property var devices: []
    signal edited(var value)

    implicitHeight: 32
    implicitWidth: 120
    Layout.fillWidth: true
    ToolTip.visible: hover.hovered && (error.length > 0 || (spec.tooltip || "").length > 0)
    ToolTip.text: error.length > 0 ? error : (spec.tooltip || "")
    ToolTip.delay: 600
    HoverHandler { id: hover }

    Loader {
        anchors.fill: parent
        sourceComponent: {
            switch (editor.spec.kind) {
            case "device": return deviceEditor
            case "int":
            case "float": return numberEditor
            case "bool": return boolEditor
            case "choice": return choiceEditor
            default: return textEditor
            }
        }
    }

    Component {
        id: numberEditor
        TextField {
            id: field
            readonly property bool isInt: editor.spec.kind === "int"
            function format(v) {
                if (v === undefined || v === null || v === "") return ""
                return isInt ? String(Math.round(v)) : String(Number(v))
            }
            function sync() { if (!activeFocus) text = format(editor.value) }
            function commit() {
                if (acceptableInput) editor.edited(isInt ? parseInt(text) : parseFloat(text))
                else text = format(editor.value)
            }
            function step(direction) {
                var v = (parseFloat(text) || 0) + direction * (isInt ? 1 : Math.pow(10, -Math.min(editor.spec.decimals, 2)))
                v = Math.min(Math.max(v, editor.spec.minimum), editor.spec.maximum)
                text = format(isInt ? v : Number(v.toFixed(editor.spec.decimals)))
                commit()
            }
            Component.onCompleted: sync()
            Connections { target: editor; function onValueChanged() { field.sync() } }
            onEditingFinished: commit()
            onActiveFocusChanged: if (!activeFocus) commit()
            Keys.onUpPressed: step(1)
            Keys.onDownPressed: step(-1)
            validator: isInt ? intValidator : doubleValidator
            IntValidator { id: intValidator; bottom: editor.spec.minimum; top: editor.spec.maximum }
            DoubleValidator {
                id: doubleValidator
                bottom: editor.spec.minimum
                top: editor.spec.maximum
                decimals: editor.spec.decimals
                notation: DoubleValidator.StandardNotation
                locale: "C"
            }
            horizontalAlignment: TextInput.AlignRight
            rightPadding: unitText.text.length > 0 ? unitText.implicitWidth + 14 : 8
            leftPadding: 8
            color: theme.fg
            selectionColor: theme.primary
            selectedTextColor: theme.onPrimary
            font.pixelSize: 13
            background: FieldBackground { focused: field.activeFocus; invalid: !field.acceptableInput && field.text.length > 0 }
            Text {
                id: unitText
                text: editor.units
                color: theme.muted
                font.pixelSize: 12
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Component {
        id: textEditor
        TextField {
            id: field
            function sync() { if (!activeFocus) text = editor.value === undefined ? "" : String(editor.value) }
            Component.onCompleted: sync()
            Connections { target: editor; function onValueChanged() { field.sync() } }
            onEditingFinished: editor.edited(text)
            placeholderText: editor.spec.placeholder || ""
            placeholderTextColor: theme.muted
            leftPadding: 8
            color: theme.fg
            selectionColor: theme.primary
            selectedTextColor: theme.onPrimary
            font.pixelSize: 13
            background: FieldBackground { focused: field.activeFocus }
        }
    }

    Component {
        id: boolEditor
        Item {
            Switch {
                id: toggle
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                checked: !!editor.value
                onToggled: editor.edited(checked)
                Accessible.name: editor.spec.label
                indicator: Rectangle {
                    implicitWidth: 36
                    implicitHeight: 20
                    x: toggle.leftPadding
                    y: (toggle.height - height) / 2
                    radius: 10
                    color: toggle.checked ? theme.primary : theme.field
                    border.color: toggle.checked ? theme.primary : theme.border
                    border.width: toggle.visualFocus ? 2 : 1
                    Rectangle {
                        x: toggle.checked ? parent.width - width - 3 : 3
                        anchors.verticalCenter: parent.verticalCenter
                        width: 14; height: 14; radius: 7
                        color: toggle.checked ? theme.onPrimary : theme.muted
                        Behavior on x { NumberAnimation { duration: 120 } }
                    }
                }
                contentItem: Text {
                    leftPadding: toggle.indicator.width + 8
                    text: toggle.checked ? "On" : "Off"
                    color: theme.muted
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    Component {
        id: choiceEditor
        ComboBox {
            id: combo
            model: editor.spec.choices
            currentIndex: Math.max(0, (editor.spec.choices || []).indexOf(editor.value === null ? "" : String(editor.value)))
            displayText: currentText.length > 0 ? currentText : "None"
            onActivated: editor.edited(currentText)
            font.pixelSize: 13
            background: FieldBackground { focused: combo.activeFocus || combo.popup.visible }
            contentItem: Text {
                leftPadding: 8
                text: combo.displayText
                color: combo.currentText.length > 0 ? theme.fg : theme.muted
                font: combo.font
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }

    Component {
        id: deviceEditor
        ComboBox {
            id: combo
            editable: true
            model: editor.devices
            font.pixelSize: 13
            function sync() { if (!contentItem.activeFocus) editText = editor.value || "" }
            function commit() { if (editText !== (editor.value || "")) editor.edited(editText) }
            Component.onCompleted: sync()
            Connections { target: editor; function onValueChanged() { combo.sync() } }
            onActivated: commit()
            onAccepted: commit()
            Connections { target: combo.contentItem; function onActiveFocusChanged() { if (!combo.contentItem.activeFocus) combo.commit() } }
            background: FieldBackground { focused: combo.contentItem.activeFocus || combo.popup.visible; invalid: editor.error.length > 0 && editor.value }
            contentItem: TextField {
                leftPadding: 8
                text: combo.editText
                placeholderText: "Device"
                placeholderTextColor: theme.muted
                color: theme.fg
                selectionColor: theme.primary
                selectedTextColor: theme.onPrimary
                font: combo.font
                background: null
                validator: combo.validator
                inputMethodHints: Qt.ImhNoAutoUppercase
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
