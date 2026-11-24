import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Shown for a few seconds after archiving: "Why? 1 repetitive · 2 ...".
// Picking a reason is optional; review carries on underneath.
Rectangle {
    id: root

    property int conversationId: -1
    property bool keysEnabled: true  // off while the user is typing
    readonly property bool active: visible && conversationId >= 0

    function show(id) {
        conversationId = id
        visible = true
        timer.restart()
    }
    function dismiss() {
        visible = false
        conversationId = -1
    }
    function pick(index) {
        const reasons = backend.archiveReasons
        if (!active || index < 0 || index >= reasons.length)
            return
        backend.setArchiveReason(conversationId, reasons[index])
        dismiss()
    }

    visible: false
    radius: Theme.radius
    color: Theme.panel
    border.color: Theme.fade(Theme.archive, 0.6)
    implicitWidth: row.implicitWidth + 28
    implicitHeight: row.implicitHeight + 16

    Timer {
        id: timer
        interval: 6000
        onTriggered: root.dismiss()
    }

    Shortcut { sequence: "1"; enabled: root.active && root.keysEnabled; onActivated: root.pick(0) }
    Shortcut { sequence: "2"; enabled: root.active && root.keysEnabled; onActivated: root.pick(1) }
    Shortcut { sequence: "3"; enabled: root.active && root.keysEnabled; onActivated: root.pick(2) }
    Shortcut { sequence: "4"; enabled: root.active && root.keysEnabled; onActivated: root.pick(3) }
    Shortcut { sequence: "Escape"; enabled: root.active; onActivated: root.dismiss() }

    HoverHandler { onHoveredChanged: hovered ? timer.stop() : timer.restart() }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 12

        Label {
            text: qsTr("Archived. Why?")
            color: Theme.text
        }
        Repeater {
            model: backend.archiveReasons

            Label {
                id: reason
                required property int index
                required property string modelData
                text: (index + 1) + " " + modelData
                color: reasonArea.containsMouse ? settings.highlightColor : Theme.textDim

                MouseArea {
                    id: reasonArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.pick(reason.index)
                }
            }
        }
        Label {
            text: "✕"
            color: closeArea.containsMouse ? settings.highlightColor : Theme.textDim
            MouseArea {
                id: closeArea
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.dismiss()
            }
            ToolTip.visible: closeArea.containsMouse
            ToolTip.delay: 500
            ToolTip.text: qsTr("No reason (Esc)")
        }
    }
}
