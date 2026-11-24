import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// Opening screen: recent projects on the left, create / open in the middle.
RowLayout {
    id: root

    property bool sidebarOpen: true
    signal toggleSidebar()
    signal newRequested()
    signal openRequested()

    spacing: Theme.gap

    Sidebar {
        title: qsTr("Recent projects")
        open: root.sidebarOpen
        onToggleRequested: root.toggleSidebar()
        Layout.fillHeight: true
        Layout.preferredWidth: implicitWidth

        ListView {
            id: recentList
            anchors.fill: parent
            clip: true
            spacing: 2
            model: settings.recentProjects
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            Label {
                visible: recentList.count === 0
                text: qsTr("No recent projects yet.")
                color: Theme.textDim
                x: 4
            }

            delegate: ItemDelegate {
                id: entry
                required property var modelData

                width: ListView.view.width - 10
                hoverEnabled: true
                padding: 8
                onClicked: if (modelData.exists) backend.openProject(modelData.url)
                ToolTip.visible: hovered
                ToolTip.delay: 600
                ToolTip.text: modelData.exists ? modelData.path : qsTr("Not found: %1").arg(modelData.path)

                background: Rectangle {
                    radius: Theme.smallRadius
                    color: entry.hovered ? Theme.fade(settings.highlightColor, 0.12) : "transparent"
                }

                contentItem: RowLayout {
                    spacing: 6
                    Label {
                        text: entry.modelData.name
                        color: entry.modelData.exists ? Theme.text : Theme.textDim
                        font.strikeout: !entry.modelData.exists
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    ToolButton {
                        id: removeButton
                        text: "×"
                        focusPolicy: Qt.NoFocus
                        onClicked: settings.removeRecent(entry.modelData.path)
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Remove from the list")
                        contentItem: Label {
                            text: removeButton.text
                            font.pixelSize: 16
                            color: removeButton.hovered ? settings.highlightColor : Theme.textDim
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Item {
                            implicitWidth: 24
                            implicitHeight: 24
                        }
                    }
                }
            }
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 10

            Label {
                text: "dataformatter"
                color: Theme.text
                font.pixelSize: 26
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 14
            }
            ThemedButton {
                text: qsTr("Create new  (Ctrl+N)")
                accent: true
                Layout.preferredWidth: 240
                Layout.alignment: Qt.AlignHCenter
                onClicked: root.newRequested()
            }
            ThemedButton {
                text: qsTr("Open file  (Ctrl+O)")
                Layout.preferredWidth: 240
                Layout.alignment: Qt.AlignHCenter
                onClicked: root.openRequested()
            }
        }
    }
}
