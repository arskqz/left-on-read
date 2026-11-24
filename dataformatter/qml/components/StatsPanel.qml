import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Basic numbers about the selected conversation, plus validation warnings.
Rectangle {
    id: root

    readonly property var stats: backend.currentStats

    color: Theme.panel
    radius: Theme.radius

    component Row2: RowLayout {
        property alias name: nameLabel.text
        property alias value: valueLabel.text
        Layout.fillWidth: true
        Label { id: nameLabel; color: Theme.textDim; Layout.fillWidth: true }
        Label { id: valueLabel; color: Theme.text }
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: Theme.gap
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: column
            width: flick.width
            spacing: 6

            Label {
                text: root.stats.id !== undefined ? qsTr("Conversation #%1").arg(root.stats.id) : qsTr("No conversation")
                color: Theme.text
                font.pixelSize: 15
                Layout.bottomMargin: 4
            }

            RowLayout {
                visible: root.stats.status !== undefined
                spacing: 6
                Rectangle {
                    implicitWidth: 8
                    implicitHeight: 8
                    radius: 4
                    color: Theme.statusColor(root.stats.status || "")
                }
                Label {
                    text: root.stats.status || ""
                    color: Theme.text
                }
            }

            Row2 { name: qsTr("Turns"); value: root.stats.turns ?? "" }
            Row2 { name: qsTr("Words"); value: root.stats.words ?? "" }
            Row2 { name: qsTr("Characters"); value: root.stats.chars ?? "" }

            Label {
                text: qsTr("Words per role")
                color: Theme.textDim
                font.pixelSize: 11
                Layout.topMargin: 8
                visible: (root.stats.roles || []).length > 0
            }
            Repeater {
                model: root.stats.roles || []
                delegate: Row2 {
                    required property var modelData
                    name: modelData.role
                    value: modelData.words
                }
            }

            Label {
                text: qsTr("Tags")
                color: Theme.textDim
                font.pixelSize: 11
                Layout.topMargin: 8
                visible: (root.stats.tags || []).length > 0
            }
            Flow {
                Layout.fillWidth: true
                spacing: 4
                Repeater {
                    model: root.stats.tags || []
                    delegate: Rectangle {
                        required property string modelData
                        radius: height / 2
                        color: Theme.tagColor(modelData)
                        implicitWidth: tagLabel.implicitWidth + 12
                        implicitHeight: tagLabel.implicitHeight + 4
                        Label {
                            id: tagLabel
                            anchors.centerIn: parent
                            text: parent.modelData
                            font.pixelSize: 11
                            color: "#10131C"
                        }
                    }
                }
            }

            Label {
                text: qsTr("Warnings")
                color: Theme.warning
                font.pixelSize: 11
                Layout.topMargin: 8
                visible: (root.stats.issues || []).length > 0
            }
            Repeater {
                model: root.stats.issues || []
                delegate: Label {
                    required property string modelData
                    text: "⚠ " + modelData
                    color: Theme.warning
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }
    }
}
