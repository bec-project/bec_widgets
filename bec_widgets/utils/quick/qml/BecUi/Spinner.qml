import QtQuick
import QtQuick.Shapes

// Small indeterminate spinner: a rotating arc in the given colour.
Item {
    id: root
    property bool running: true
    property int size: 16
    property color color: theme.primary
    property real lineWidth: Math.max(1.5, size / 8)

    implicitWidth: size
    implicitHeight: size
    visible: running

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        RotationAnimator on rotation {
            from: 0; to: 360
            duration: 900
            loops: Animation.Infinite
            running: root.running && root.visible
        }
        ShapePath {
            strokeColor: Qt.alpha(root.color, 0.2)
            strokeWidth: root.lineWidth
            fillColor: "transparent"
            PathAngleArc {
                centerX: root.size / 2; centerY: root.size / 2
                radiusX: (root.size - root.lineWidth) / 2; radiusY: radiusX
                startAngle: 0; sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.lineWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.size / 2; centerY: root.size / 2
                radiusX: (root.size - root.lineWidth) / 2; radiusY: radiusX
                startAngle: -90; sweepAngle: 100
            }
        }
    }
}
