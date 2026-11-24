import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

// Finder: conversation queue | tools | dataset data.
// Search, replace and word statistics arrive in Phases 3 and 4.
RowLayout {
    id: root

    property bool sidebarOpen: true
    signal toggleSidebar()

    spacing: Theme.gap

    component DataRow: RowLayout {
        property alias name: nameLabel.text
        property alias value: valueLabel.text
        Layout.fillWidth: true
        Label { id: nameLabel; color: Theme.textDim; Layout.fillWidth: true }
        Label { id: valueLabel; color: Theme.text; elide: Text.ElideMiddle; Layout.maximumWidth: 180 }
    }

    Sidebar {
        title: qsTr("Queue")
        open: root.sidebarOpen
        onToggleRequested: root.toggleSidebar()
        Layout.fillHeight: true
        Layout.preferredWidth: implicitWidth

        ConversationList {
            anchors.fill: parent
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        ColumnLayout {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 40
            spacing: 10

            Label {
                text: qsTr("Tools")
                color: Theme.text
                font.pixelSize: 16
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 6
            }
            ThemedButton {
                text: qsTr("Search")
                enabled: false
                tip: qsTr("Coming in Phase 3")
                Layout.preferredWidth: 200
            }
            ThemedButton {
                text: qsTr("Replace")
                enabled: false
                tip: qsTr("Coming in Phase 3")
                Layout.preferredWidth: 200
            }
            Label {
                text: qsTr("Search and replace arrive in Phase 3.")
                color: Theme.textDim
                font.pixelSize: 11
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }

    Rectangle {
        color: Theme.panel
        radius: Theme.radius
        Layout.preferredWidth: 280
        Layout.fillHeight: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.gap
            spacing: 6

            Label {
                text: qsTr("Dataset")
                color: Theme.text
                font.pixelSize: 16
                Layout.bottomMargin: 4
            }
            DataRow { name: qsTr("Conversations"); value: backend.counts.total }
            DataRow { name: qsTr("Kept"); value: backend.counts.keep }
            DataRow { name: qsTr("Archived"); value: backend.counts.archive }
            DataRow { name: qsTr("Unreviewed"); value: backend.counts.unreviewed }
            DataRow { name: qsTr("Schema"); value: backend.schemaLabel }
            DataRow { name: qsTr("Source"); value: backend.sourceName }

            Label {
                text: qsTr("Most used words")
                color: Theme.text
                Layout.topMargin: 18
            }
            Label {
                text: qsTr("Word and phrase statistics arrive in Phase 4.")
                color: Theme.textDim
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
        }
    }
}
