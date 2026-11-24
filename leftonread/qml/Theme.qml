pragma Singleton
import QtQuick

// Fixed design tokens. The user-changeable colours (background, highlight)
// live in the `settings` context property and are read from there directly.
QtObject {
    readonly property color panel: "#F02E2E2E"   // slightly see-through, so a backdrop shows
    readonly property color pane: "#F21A1716"    // conversation pane
    readonly property color control: "#3A3A40"
    readonly property color text: "#ECEEF3"
    readonly property color textDim: "#9BA1AE"
    readonly property color warning: "#F5B94A"
    readonly property color keep: "#5AD08A"
    readonly property color archive: "#E7746F"
    readonly property color unreviewed: "#5B6070"

    readonly property int radius: 12
    readonly property int smallRadius: 8
    readonly property int gap: 12
    readonly property int sidebarWidth: 290
    readonly property int collapsedWidth: 40

    function fade(c, alpha) {
        return Qt.rgba(c.r, c.g, c.b, alpha)
    }

    // Readable text colour on top of `c`.
    function onColor(c) {
        return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) > 0.55 ? "#020618" : "#FFFFFF"
    }

    function statusColor(status) {
        if (status === "keep")
            return keep
        if (status === "archive")
            return archive
        return unreviewed
    }

    // Stable colour per tag name.
    function tagColor(name) {
        let h = 0
        for (let i = 0; i < name.length; ++i)
            h = (h * 31 + name.charCodeAt(i)) % 360
        return Qt.hsla(h / 360, 0.6, 0.62, 1)
    }
}
