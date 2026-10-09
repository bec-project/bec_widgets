import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Labelled button.
// variant: "primary", "danger", "success" (solid), "neutral" (outlined), "dangerOutline"
// (red outline for destructive actions that are not the main action) or "ghost" (no border).
// compact: 28 px high for toolbars and dense rows. busy: shows a spinner instead of the icon.
AbstractButton {
    id: root
    property string variant: "neutral"
    property string iconName: ""
    property string tip: ""
    property bool busy: false
    property bool compact: false

    readonly property bool solid: variant === "primary" || variant === "danger" || variant === "success"
    readonly property color baseColor: variant === "primary" ? theme.primary
        : variant === "danger" ? theme.danger
        : variant === "success" ? theme.success
        : "transparent"
    readonly property color labelColor: variant === "primary" ? theme.onPrimary
        : solid ? "white"
        : variant === "dangerOutline" ? theme.dangerText
        : theme.fg

    implicitHeight: compact ? theme.controlHeightCompact : theme.controlHeight
    implicitWidth: Math.max(compact ? 48 : 64, row.implicitWidth + (compact ? 18 : 24))
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    opacity: enabled ? 1.0 : 0.45
    Accessible.name: text
    Accessible.role: Accessible.Button

    background: Rectangle {
        radius: theme.radiusSmall
        color: root.solid ? (root.down ? Qt.darker(root.baseColor, 1.25) : root.hovered ? Qt.lighter(root.baseColor, 1.1) : root.baseColor)
            : root.variant === "dangerOutline" && (root.hovered || root.down) ? theme.dangerTint
            : (root.down ? theme.pressed : root.hovered ? theme.hover : "transparent")
        border.width: root.visualFocus ? 2 : (root.variant === "neutral" || root.variant === "dangerOutline" ? 1 : 0)
        border.color: root.visualFocus ? theme.primary
            : root.variant === "dangerOutline" ? Qt.alpha(theme.danger, 0.6) : theme.border
        Behavior on color { ColorAnimation { duration: 90 } }
    }
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Spinner {
                visible: root.busy
                running: root.busy
                size: 14
                color: root.labelColor
            }
            Icon {
                visible: root.iconName !== "" && !root.busy
                name: root.iconName
                color: root.labelColor
                size: root.compact ? 15 : 16
            }
            Text {
                text: root.text
                color: root.labelColor
                font.pixelSize: root.compact ? theme.fontSmall : theme.fontBody
                font.weight: root.solid ? Font.DemiBold : Font.Medium
                elide: Text.ElideRight
            }
        }
    }
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 500
    ToolTip.text: tip
}
