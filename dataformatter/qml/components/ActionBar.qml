import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Edit | Keep | Archive | Skip | Tag | Controls
RowLayout {
    id: root

    property bool editing: false
    property bool hasConversation: false

    signal editToggled()
    signal keepRequested()
    signal archiveRequested()
    signal skipRequested()

    spacing: 8

    ThemedButton {
        text: root.editing ? qsTr("Done (Ctrl+E)") : qsTr("Edit (E)")
        checkable: true
        checked: root.editing
        enabled: root.hasConversation
        tip: qsTr("Edit the message text. Changes save when you leave a message.")
        onClicked: root.editToggled()
    }
    ThemedButton {
        text: qsTr("Keep (→)")
        accent: true
        enabled: root.hasConversation
        tip: qsTr("Mark as keep and go to the next unreviewed conversation")
        onClicked: root.keepRequested()
    }
    ThemedButton {
        text: qsTr("Archive (←)")
        enabled: root.hasConversation
        tip: qsTr("Move to the archive (not deleted) and go to the next unreviewed conversation")
        onClicked: root.archiveRequested()
    }
    ThemedButton {
        text: qsTr("Skip (S)")
        enabled: root.hasConversation
        tip: qsTr("Leave unreviewed and go to the next one")
        onClicked: root.skipRequested()
    }
    ThemedButton {
        text: qsTr("Tag")
        enabled: false
        tip: qsTr("Tagging arrives in Phase 3")
    }
    ThemedButton {
        text: qsTr("Controls")
        tip: qsTr("Keyboard shortcuts")
        onClicked: keysPopup.opened ? keysPopup.close() : keysPopup.open()

        Popup {
            id: keysPopup
            y: -height - 8
            x: (parent.width - width) / 2
            padding: 14
            background: Rectangle {
                color: Theme.panel
                radius: Theme.radius
                border.color: Theme.fade(settings.highlightColor, 0.4)
            }

            ColumnLayout {
                spacing: 4

                Repeater {
                    model: [
                        ["→ / K", qsTr("Keep")],
                        ["← / A", qsTr("Archive")],
                        ["S", qsTr("Skip")],
                        ["↑ / ↓", qsTr("Previous / next conversation")],
                        ["E / Ctrl+E", qsTr("Start / stop editing")],
                        ["Tab / ↑ ↓", qsTr("Next / previous turn (editing)")],
                        ["Ctrl+D", qsTr("Delete turn (editing)")],
                        ["Ctrl+Z", qsTr("Undo")]
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        spacing: 18
                        Label {
                            text: parent.modelData[0]
                            color: settings.highlightColor
                            Layout.preferredWidth: 90
                        }
                        Label {
                            text: parent.modelData[1]
                            color: Theme.text
                        }
                    }
                }
            }
        }
    }
}
