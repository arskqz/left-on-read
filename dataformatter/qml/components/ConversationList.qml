import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The project's conversations. Selection lives in `backend.currentRow`.
ListView {
    id: list

    clip: true
    spacing: 2
    model: backend.conversations
    currentIndex: backend.currentRow
    keyNavigationEnabled: false  // arrow keys are review shortcuts
    highlightMoveDuration: 0
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

    onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)

    delegate: ItemDelegate {
        id: row

        required property int index
        required property int conversationId
        required property string preview
        required property string status
        required property int turns
        required property var tags

        readonly property bool current: ListView.isCurrentItem

        width: ListView.view.width - 10
        hoverEnabled: true
        padding: 8
        onClicked: {
            list.forceActiveFocus()  // commits an open edit before switching
            backend.setCurrentRow(index)
        }

        background: Rectangle {
            radius: Theme.smallRadius
            color: row.current ? Theme.fade(settings.highlightColor, 0.16)
                 : row.hovered ? Qt.rgba(1, 1, 1, 0.05)
                 : "transparent"
            border.width: row.current ? 1 : 0
            border.color: Theme.fade(settings.highlightColor, 0.7)
        }

        contentItem: ColumnLayout {
            spacing: 4

            RowLayout {
                spacing: 8
                Layout.fillWidth: true

                Rectangle {
                    implicitWidth: 8
                    implicitHeight: 8
                    radius: 4
                    color: Theme.statusColor(row.status)
                }
                Label {
                    text: row.preview !== "" ? row.preview : qsTr("(no user message)")
                    color: row.status === "archive" ? Theme.textDim : Theme.text
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Label {
                    text: row.turns
                    color: Theme.textDim
                    font.pixelSize: 11
                }
            }

            // Tags: small colour bars that expand to names on hover.
            Flow {
                visible: row.tags.length > 0
                spacing: 4
                Layout.fillWidth: true
                Layout.leftMargin: 16

                Repeater {
                    model: row.tags
                    delegate: Rectangle {
                        id: chip
                        required property string modelData
                        radius: height / 2
                        color: row.hovered ? Theme.fade(Theme.tagColor(modelData), 0.85) : Theme.tagColor(modelData)
                        implicitHeight: row.hovered ? chipLabel.implicitHeight + 4 : 5
                        implicitWidth: row.hovered ? chipLabel.implicitWidth + 12 : 16

                        Label {
                            id: chipLabel
                            anchors.centerIn: parent
                            visible: row.hovered
                            text: chip.modelData
                            font.pixelSize: 11
                            color: "#10131C"
                        }
                    }
                }
            }
        }
    }
}
