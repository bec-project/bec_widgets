.pragma library
// Colour of a state tone; only problems and work in progress are coloured.
function color(theme, tone) {
    return tone === "ok" ? theme.success
         : tone === "busy" ? theme.primary
         : tone === "warn" ? theme.warning
         : tone === "err" ? theme.danger
         : tone === "stale" ? theme.fgSubtle
         : theme.fgMuted
}
function soft(theme, c, amount) {
    return Qt.rgba(theme.card.r + (c.r - theme.card.r) * amount,
                   theme.card.g + (c.g - theme.card.g) * amount,
                   theme.card.b + (c.b - theme.card.b) * amount, 1)
}
