import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The selected conversation as text. Roles are labels, never editable.
// In edit mode, text messages become editable and are saved when editing finishes.
ListView {
    id: view

    property bool editing: false
    property bool showSystem: false
    property int currentTurn: -1  // turn whose text field last had focus
    signal deleteRequested(int index)

    // Put the cursor in turn `index`, or the nearest visible turn in direction `step` (+1 / -1).
    // Returns false if there is none, so the caller can keep the key for normal cursor movement.
    function focusTurn(index, step, atEnd) {
        for (let i = index; i >= 0 && i < count; i += step) {
            positionViewAtIndex(i, ListView.Contain)
            forceLayout()
            const item = itemAtIndex(i)
            if (item && !item.collapsed) {
                item.focusEditor(atEnd)
                return true
            }
        }
        return false
    }

    Connections {
        target: view.model
        function onModelReset() { view.currentTurn = -1 }
    }

    clip: true
    spacing: 18
    model: backend.messages
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

    delegate: ColumnLayout {
        id: msg

        required property int index
        required property string role
        required property string content
        required property bool editable
        required property string issue

        readonly property bool collapsed: role === "system" && !view.showSystem

        function focusEditor(atEnd) {
            editor.forceActiveFocus()
            editor.cursorPosition = atEnd ? editor.length : 0
        }

        x: 4
        width: ListView.view.width - 20
        spacing: 4

        RowLayout {
            spacing: 8
            Layout.fillWidth: true

            Label {
                text: msg.role
                font.capitalization: Font.AllUppercase
                font.pixelSize: 11
                font.letterSpacing: 1
                font.bold: true
                color: msg.role === "assistant" ? settings.highlightColor : Theme.textDim
            }
            Label {
                visible: msg.role === "system"
                text: msg.collapsed ? qsTr("▸ show") : qsTr("▾ hide")
                font.pixelSize: 11
                color: systemToggle.containsMouse ? settings.highlightColor : Theme.textDim

                MouseArea {
                    id: systemToggle
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: view.showSystem = !view.showSystem
                }
            }
            Label {
                visible: !msg.editable
                text: qsTr("(not plain text, read-only)")
                font.pixelSize: 11
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true }
            Label {
                visible: view.editing
                text: qsTr("Delete turn")
                font.pixelSize: 11
                color: deleteArea.containsMouse ? Theme.archive : Theme.textDim

                MouseArea {
                    id: deleteArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: view.deleteRequested(msg.index)
                }
                ToolTip.visible: deleteArea.containsMouse
                ToolTip.delay: 500
                ToolTip.text: qsTr("Remove this turn (Ctrl+D). Undo with Ctrl+Z.")
            }
            Label {
                visible: msg.issue !== ""
                text: "⚠ " + msg.issue
                font.pixelSize: 11
                color: Theme.warning
                elide: Text.ElideRight
                Layout.maximumWidth: msg.width / 2
            }
        }

        TextArea {
            id: editor

            visible: !msg.collapsed
            Layout.fillWidth: true
            text: msg.content
            readOnly: !(view.editing && msg.editable)
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            color: Theme.text
            selectionColor: Theme.fade(settings.highlightColor, 0.45)
            selectedTextColor: Theme.text
            leftPadding: 10
            rightPadding: 10
            topPadding: 6
            bottomPadding: 6

            background: Rectangle {
                radius: Theme.smallRadius
                color: editor.readOnly ? "transparent" : Qt.rgba(1, 1, 1, 0.05)
                border.width: editor.readOnly ? 0 : 1
                border.color: editor.activeFocus ? settings.highlightColor : Qt.rgba(1, 1, 1, 0.12)
            }

            onEditingFinished: {
                if (!readOnly)
                    backend.setMessageContent(msg.index, text)
            }
            onActiveFocusChanged: if (activeFocus) view.currentTurn = msg.index

            // Edit mode: Tab / Shift+Tab go to the next / previous turn; arrows cross
            // into the neighbouring turn from the first / last line.
            function onFirstLine() { return cursorRectangle.y <= positionToRectangle(0).y }
            function onLastLine() { return cursorRectangle.y >= positionToRectangle(length).y }

            Keys.onPressed: (event) => {
                event.accepted = false
                if (!view.editing)
                    return
                const plain = event.modifiers === Qt.NoModifier
                if (event.key === Qt.Key_Tab && plain)
                    event.accepted = view.focusTurn(msg.index + 1, 1, false) || true
                else if (event.key === Qt.Key_Backtab)
                    event.accepted = view.focusTurn(msg.index - 1, -1, true) || true
                else if (event.key === Qt.Key_Up && plain && onFirstLine())
                    event.accepted = view.focusTurn(msg.index - 1, -1, true)
                else if (event.key === Qt.Key_Down && plain && onLastLine())
                    event.accepted = view.focusTurn(msg.index + 1, 1, false)
            }
        }
    }
}
