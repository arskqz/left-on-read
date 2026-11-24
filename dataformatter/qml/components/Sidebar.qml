import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Rounded side panel with a collapse arrow at the bottom.
// Children are placed in the body; give them `anchors.fill: parent`.
Rectangle {
    id: root

    property string title: ""
    property bool open: true
    default property alias content: body.data
    signal toggleRequested()

    implicitWidth: open ? Theme.sidebarWidth : Theme.collapsedWidth
    color: Theme.panel
    radius: Theme.radius
    clip: true

    Behavior on implicitWidth {
        NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.open ? Theme.gap : 4
        spacing: 8

        Label {
            visible: root.open && root.title !== ""
            text: root.title
            color: Theme.text
            font.pixelSize: 16
            Layout.fillWidth: true
            Layout.leftMargin: 4
            elide: Text.ElideRight
        }

        Item {
            id: body
            visible: root.open
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        Item {
            visible: !root.open
            Layout.fillHeight: true
        }

        ToolButton {
            id: arrow
            text: root.open ? "←" : "→"
            focusPolicy: Qt.NoFocus
            Layout.alignment: root.open ? (Qt.AlignRight | Qt.AlignBottom) : (Qt.AlignHCenter | Qt.AlignBottom)
            onClicked: root.toggleRequested()
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: root.open ? qsTr("Hide sidebar") : qsTr("Show sidebar")
            contentItem: Label {
                text: arrow.text
                font.pixelSize: 18
                color: arrow.hovered ? settings.highlightColor : Theme.text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Item {
                implicitWidth: 32
                implicitHeight: 32
            }
        }
    }
}
