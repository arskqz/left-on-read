import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// Dataset view: conversation list | conversation text + actions | counter + stats.
RowLayout {
    id: root

    property bool sidebarOpen: true
    property bool editing: false
    signal toggleSidebar()

    readonly property bool hasConversation: backend.currentRow >= 0
    // Focus is in a message text field (editable or not).
    readonly property bool inEditor: {
        const item = Window.activeFocusItem
        return item !== null && item.cursorPosition !== undefined
    }
    readonly property bool typing: inEditor && !Window.activeFocusItem.readOnly
    // Review keys (keep / archive / skip / move between conversations) are off while editing.
    readonly property bool reviewKeys: visible && !typing && !editing && hasConversation
    // In edit mode, arrows and Tab move between turns; these catch them when no turn has focus yet.
    readonly property bool turnKeys: visible && editing && !inEditor

    // Move focus out of any editor so its pending text is saved first.
    function commit() {
        focusSink.forceActiveFocus()
    }
    function keep() { commit(); backend.keep() }
    function archive() { commit(); backend.archive() }
    function skip() { commit(); backend.skip() }
    function move(step) { commit(); backend.setCurrentRow(backend.currentRow + step) }
    function setEditing(on) {
        commit()
        editing = on && hasConversation
        if (editing)
            Qt.callLater(() => messageView.focusTurn(0, 1, false))
    }
    function deleteTurn(index) {
        commit()
        backend.deleteMessage(index)
        Qt.callLater(() => {
            if (messageView.count > 0)
                messageView.focusTurn(Math.min(index, messageView.count - 1), -1, false)
        })
    }

    objectName: "reviewScreen"
    spacing: Theme.gap

    Shortcut { sequences: ["K", "Right"]; enabled: root.reviewKeys; onActivated: root.keep() }
    Shortcut { sequences: ["A", "Left"]; enabled: root.reviewKeys; onActivated: root.archive() }
    Shortcut { sequence: "S"; enabled: root.reviewKeys; onActivated: root.skip() }
    Shortcut { sequence: "E"; enabled: root.reviewKeys; onActivated: root.setEditing(true) }
    Shortcut { sequence: "Up"; enabled: root.reviewKeys; onActivated: root.move(-1) }
    Shortcut { sequence: "Down"; enabled: root.reviewKeys; onActivated: root.move(1) }

    Shortcut { sequence: "Ctrl+E"; enabled: root.visible && root.hasConversation; onActivated: root.setEditing(!root.editing) }
    Shortcut { sequences: ["Down", "Tab"]; enabled: root.turnKeys; onActivated: messageView.focusTurn(0, 1, false) }
    Shortcut { sequences: ["Up", "Shift+Tab"]; enabled: root.turnKeys; onActivated: messageView.focusTurn(messageView.count - 1, -1, true) }
    Shortcut {
        sequence: "Ctrl+D"
        enabled: root.visible && root.editing && root.inEditor && messageView.currentTurn >= 0
        onActivated: root.deleteTurn(messageView.currentTurn)
    }

    Sidebar {
        title: qsTr("Conversations")
        open: root.sidebarOpen
        onToggleRequested: root.toggleSidebar()
        Layout.fillHeight: true
        Layout.preferredWidth: implicitWidth

        ConversationList {
            anchors.fill: parent
        }
    }

    ColumnLayout {
        spacing: 10
        Layout.fillWidth: true
        Layout.fillHeight: true

        Rectangle {
            color: Theme.pane
            radius: Theme.radius
            border.width: root.editing ? 1 : 0
            border.color: Theme.fade(settings.highlightColor, 0.5)
            Layout.fillWidth: true
            Layout.fillHeight: true

            Item { id: focusSink }  // takes focus so an open editor saves

            MessageView {
                id: messageView
                objectName: "messageView"
                anchors.fill: parent
                anchors.margins: 16
                editing: root.editing
                onDeleteRequested: (index) => root.deleteTurn(index)
            }

            Label {
                anchors.centerIn: parent
                visible: !root.hasConversation
                text: qsTr("This project has no conversations.")
                color: Theme.textDim
            }
        }

        ActionBar {
            editing: root.editing
            hasConversation: root.hasConversation
            Layout.alignment: Qt.AlignHCenter
            onEditToggled: root.setEditing(!root.editing)
            onKeepRequested: root.keep()
            onArchiveRequested: root.archive()
            onSkipRequested: root.skip()
        }
    }

    ColumnLayout {
        spacing: 10
        Layout.preferredWidth: 220
        Layout.maximumWidth: 260
        Layout.fillHeight: true

        Label {
            text: backend.reviewedCount + " / " + backend.totalCount
            color: settings.highlightColor
            font.pixelSize: 22
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
        }
        Label {
            text: qsTr("reviewed")
            color: Theme.textDim
            font.pixelSize: 11
            Layout.alignment: Qt.AlignHCenter
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            implicitHeight: 4
            radius: 2
            color: Qt.rgba(1, 1, 1, 0.1)
            Rectangle {
                height: parent.height
                radius: 2
                width: backend.totalCount > 0 ? parent.width * backend.reviewedCount / backend.totalCount : 0
                color: settings.highlightColor
            }
        }

        StatsPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 30
            Layout.bottomMargin: 46
        }
    }
}
