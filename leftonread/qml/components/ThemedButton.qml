import QtQuick
import QtQuick.Controls
import ".."

// Flat rounded button that follows the highlight colour.
// Never takes focus, so clicking it does not steal focus from the list or an editor.
Button {
    id: control

    property bool accent: false
    property string tip: ""

    flat: true
    hoverEnabled: true
    focusPolicy: Qt.NoFocus
    padding: 8
    leftPadding: 14
    rightPadding: 14

    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500
    ToolTip.text: tip

    contentItem: Label {
        text: control.text
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        color: !control.enabled ? Theme.fade(Theme.textDim, 0.5)
             : (control.accent || control.checked) ? settings.highlightColor
             : Theme.text
    }

    background: Rectangle {
        implicitHeight: 34
        implicitWidth: 64
        radius: Theme.smallRadius
        color: control.down ? Theme.fade(settings.highlightColor, 0.25)
             : (control.hovered || control.checked) ? Theme.fade(settings.highlightColor, 0.12)
             : Qt.rgba(1, 1, 1, 0.04)
        border.width: control.checked ? 1 : 0
        border.color: settings.highlightColor
    }
}
