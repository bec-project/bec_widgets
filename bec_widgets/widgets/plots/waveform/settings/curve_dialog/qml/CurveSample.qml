import QtQuick

// Small drawing of a curve in its colour, line style, width and symbol: a peak (or a flat
// line for custom data) with the symbol on three points. Mirrors paint_curve_sample().
Canvas {
    id: root
    property color color: "#888888"
    property string penStyle: "solid"
    property real penWidth: 2
    property string symbol: ""
    property real symbolSize: 6
    property real maxWidth: 4
    property real maxSymbol: 9
    property bool peak: true

    implicitWidth: 40
    implicitHeight: 20
    antialiasing: true
    onColorChanged: requestPaint()
    onPenStyleChanged: requestPaint()
    onPenWidthChanged: requestPaint()
    onSymbolChanged: requestPaint()
    onSymbolSizeChanged: requestPaint()
    onPeakChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function dash(style, w) {
        switch (style) {
        case "dash": return [4, 2]
        case "dot": return [1, 2]
        case "dashdot": return [4, 2, 1, 2]
        default: return []
        }
    }

    function drawSymbol(ctx, x, y, s, size) {
        const h = size / 2
        ctx.beginPath()
        switch (s) {
        case "o": ctx.arc(x, y, h, 0, 2 * Math.PI); break
        case "s": ctx.rect(x - h, y - h, size, size); break
        case "t": ctx.moveTo(x - h, y - h); ctx.lineTo(x + h, y - h); ctx.lineTo(x, y + h); ctx.closePath(); break
        case "d": ctx.moveTo(x, y - h); ctx.lineTo(x + h, y); ctx.lineTo(x, y + h); ctx.lineTo(x - h, y); ctx.closePath(); break
        case "star":
            for (let i = 0; i < 10; ++i) {
                const r = i % 2 === 0 ? h : h * 0.45
                const a = -Math.PI / 2 + i * Math.PI / 5
                if (i === 0) ctx.moveTo(x + r * Math.cos(a), y + r * Math.sin(a))
                else ctx.lineTo(x + r * Math.cos(a), y + r * Math.sin(a))
            }
            ctx.closePath()
            break
        case "+": ctx.moveTo(x - h, y); ctx.lineTo(x + h, y); ctx.moveTo(x, y - h); ctx.lineTo(x, y + h); break
        case "x": ctx.moveTo(x - h, y - h); ctx.lineTo(x + h, y + h); ctx.moveTo(x - h, y + h); ctx.lineTo(x + h, y - h); break
        }
        if (s === "+" || s === "x") {
            ctx.setLineDash([])
            ctx.lineWidth = Math.max(1.5, size / 4)
            ctx.strokeStyle = root.color
            ctx.stroke()
        } else {
            ctx.fillStyle = root.color
            ctx.fill()
            ctx.setLineDash([])
            ctx.lineWidth = 1
            ctx.strokeStyle = Qt.darker(root.color, 1.3)
            ctx.stroke()
        }
    }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        const size = Math.max(3, Math.min(root.symbolSize, root.maxSymbol))
        const margin = root.symbol !== "" ? size / 2 + 1 : 2
        const left = margin, right = width - margin, top = margin, bottom = height - margin
        const steps = 40
        const pts = []
        for (let i = 0; i <= steps; ++i) {
            const t = i / steps
            const h = root.peak ? Math.exp(-((t - 0.5) * (t - 0.5)) / 0.03) : 0.5
            pts.push([left + t * (right - left), bottom - h * (bottom - top)])
        }
        const lw = Math.min(Math.max(1, root.penWidth), root.maxWidth)
        ctx.lineWidth = lw
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.strokeStyle = root.color
        ctx.setLineDash(dash(root.penStyle, lw))
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (let j = 1; j < pts.length; ++j) ctx.lineTo(pts[j][0], pts[j][1])
        ctx.stroke()
        if (root.symbol !== "") {
            for (const k of [Math.floor(steps / 5), Math.floor(steps / 2), steps - Math.floor(steps / 5)])
                drawSymbol(ctx, pts[k][0], pts[k][1], root.symbol, size)
        }
    }
}
