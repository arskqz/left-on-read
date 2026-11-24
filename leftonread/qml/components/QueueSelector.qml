import QtQuick
import QtQuick.Controls
import ".."

// Which conversations the Review list shows; keep / archive / skip move through it.
// Tag and Finder queues come with Phase 3.
ComboBox {
    id: root

    readonly property var queues: [
        { value: "all", label: qsTr("All conversations"), count: backend.counts.total },
        { value: "unreviewed", label: qsTr("Unreviewed"), count: backend.counts.unreviewed },
        { value: "keep", label: qsTr("Kept"), count: backend.counts.keep },
        { value: "archive", label: qsTr("Archived (re-review)"), count: backend.counts.archive },
    ]

    objectName: "queueSelector"
    enabled: backend.hasProject
    focusPolicy: Qt.NoFocus  // keep the review keys working after a pick
    model: queues.map(q => ({ value: q.value, text: q.label + "  ·  " + (q.count ?? 0) }))
    textRole: "text"
    valueRole: "value"
    currentIndex: Math.max(0, queues.findIndex(q => q.value === backend.queue))
    onActivated: (index) => backend.setQueue(queues[index].value)

    ToolTip.visible: hovered && !popup.visible
    ToolTip.delay: 600
    ToolTip.text: qsTr("Review queue. The list keeps its rows during a pass; pick the queue again to refresh it.")

    background: Rectangle {
        implicitHeight: 32
        radius: Theme.smallRadius
        color: root.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.04)
        border.width: 1
        border.color: root.popup.visible ? settings.highlightColor : Qt.rgba(1, 1, 1, 0.12)
    }
}
