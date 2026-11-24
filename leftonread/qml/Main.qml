import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 1240
    height: 780
    minimumWidth: 860
    minimumHeight: 540
    visible: true
    title: backend.hasProject ? backend.title + " - Left on Read" : "Left on Read"
    color: settings.backgroundColor

    property string mode: "review"  // review | finder
    property bool sidebarOpen: true
    property string exportWhich: "all"

    readonly property bool typing: {
        const item = activeFocusItem
        return item !== null && item.cursorPosition !== undefined && !item.readOnly
    }

    function startExport(which) {
        exportWhich = which
        exportDialog.open()
    }

    function setMode(newMode) {
        reviewScreen.setEditing(false)
        mode = newMode
    }

    // Saves an editor that still has focus before the window goes away.
    onClosing: contentItem.forceActiveFocus()

    palette {
        window: Theme.panel
        windowText: Theme.text
        base: Theme.pane
        alternateBase: Theme.panel
        text: Theme.text
        button: Theme.control
        buttonText: Theme.text
        brightText: "#FFFFFF"
        highlight: settings.highlightColor
        highlightedText: Theme.onColor(settings.highlightColor)
        placeholderText: Theme.textDim
        toolTipBase: Theme.control
        toolTipText: Theme.text
        light: "#4A4A52"
        midlight: "#3F3F46"
        mid: "#34343A"
        dark: "#1E1E22"
        shadow: "#000000"
        link: settings.highlightColor
    }

    background: Item {
        Image {
            anchors.fill: parent
            source: settings.backdrop
            visible: settings.backdrop !== ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
        Rectangle {  // dims the backdrop so text stays readable
            anchors.fill: parent
            visible: settings.backdrop !== ""
            color: settings.backgroundColor
            opacity: 0.55
        }
    }

    menuBar: MenuBar {
        background: Item { implicitHeight: 30 }

        Menu {
            title: qsTr("&File")
            Action {
                text: qsTr("&New project from dataset...")
                shortcut: StandardKey.New
                onTriggered: sourceDialog.open()
            }
            Action {
                text: qsTr("&Open project...")
                shortcut: StandardKey.Open
                onTriggered: openDialog.open()
            }
            Action {
                text: qsTr("&Close project")
                enabled: backend.hasProject
                onTriggered: {
                    window.setMode("review")
                    backend.close()
                }
            }
            MenuSeparator {}
            Action {
                text: qsTr("Export &all...")
                enabled: backend.hasProject
                onTriggered: window.startExport("all")
            }
            Action {
                text: qsTr("Export &kept...")
                enabled: backend.hasProject
                onTriggered: window.startExport("keep")
            }
            Action {
                text: qsTr("Export a&rchived...")
                enabled: backend.hasProject
                onTriggered: window.startExport("archive")
            }
            MenuSeparator {}
            Action {
                text: qsTr("&Quit")
                shortcut: StandardKey.Quit
                onTriggered: window.close()
            }
        }

        Menu {
            title: qsTr("&Edit")
            Action {
                text: qsTr("&Undo")
                shortcut: StandardKey.Undo
                enabled: backend.canUndo && !window.typing
                onTriggered: {
                    reviewScreen.commit()
                    backend.undo()
                }
            }
        }

        Menu {
            id: viewMenu
            title: qsTr("&View")
            Action {
                text: qsTr("&Review mode")
                checkable: true
                checked: window.mode === "review"
                enabled: backend.hasProject
                shortcut: "Ctrl+1"
                onTriggered: window.setMode("review")
            }
            Action {
                text: qsTr("&Finder mode")
                checkable: true
                checked: window.mode === "finder"
                enabled: backend.hasProject
                shortcut: "Ctrl+2"
                onTriggered: window.setMode("finder")
            }
            MenuSeparator {}
            Action {
                text: qsTr("Show &sidebar")
                checkable: true
                checked: window.sidebarOpen
                shortcut: "Ctrl+B"
                onTriggered: window.sidebarOpen = !window.sidebarOpen
            }
            MenuSeparator {}
            Menu {
                title: qsTr("&Appearance")
                Action {
                    text: qsTr("&Background colour...")
                    onTriggered: backgroundDialog.open()
                }
                Action {
                    text: qsTr("&Highlight colour...")
                    onTriggered: highlightDialog.open()
                }
                Menu {
                    id: backdropMenu
                    title: qsTr("Back&drop")

                    MenuItem {
                        text: qsTr("None")
                        checkable: true
                        checked: settings.backdrop === ""
                        onTriggered: settings.setBackdrop("")
                    }
                    Instantiator {
                        model: settings.backdrops
                        delegate: MenuItem {
                            required property string modelData
                            text: decodeURIComponent(modelData.substring(modelData.lastIndexOf("/") + 1))
                            checkable: true
                            checked: settings.backdrop === modelData
                            onTriggered: settings.setBackdrop(modelData)
                        }
                        onObjectAdded: (index, object) => backdropMenu.insertItem(index + 1, object)
                        onObjectRemoved: (index, object) => backdropMenu.removeItem(object)
                    }
                    MenuSeparator {}
                    Action {
                        text: qsTr("Open backdrops folder")
                        onTriggered: settings.openBackdropsFolder()
                    }
                    Action {
                        text: qsTr("Reload backdrops")
                        onTriggered: settings.reloadBackdrops()
                    }
                }
                MenuSeparator {}
                Action {
                    text: qsTr("&Reset to defaults")
                    onTriggered: settings.resetAppearance()
                }
            }
        }
    }

    // -- dialogs -------------------------------------------------------------

    FileDialog {
        id: sourceDialog
        title: qsTr("Choose a dataset to import")
        nameFilters: [qsTr("Datasets (*.json *.jsonl)"), qsTr("All files (*)")]
        onAccepted: {
            projectDialog.selectedFile = backend.suggestProjectUrl(selectedFile)
            projectDialog.open()
        }
    }

    FileDialog {
        id: projectDialog
        title: qsTr("Save the new project as")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "dsproj"
        nameFilters: [qsTr("Projects (*.dsproj)")]
        onAccepted: backend.newProject(sourceDialog.selectedFile, selectedFile)
    }

    FileDialog {
        id: openDialog
        title: qsTr("Open a project")
        nameFilters: [qsTr("Projects (*.dsproj)"), qsTr("All files (*)")]
        onAccepted: backend.openProject(selectedFile)
    }

    FileDialog {
        id: exportDialog
        title: qsTr("Export to")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("Datasets (*.json *.jsonl)"), qsTr("All files (*)")]
        onAccepted: {
            reviewScreen.commit()
            backend.exportTo(selectedFile, window.exportWhich)
        }
    }

    ColorDialog {
        id: backgroundDialog
        title: qsTr("Background colour")
        selectedColor: settings.backgroundColor
        onAccepted: settings.setBackgroundColor(selectedColor)
    }

    ColorDialog {
        id: highlightDialog
        title: qsTr("Highlight colour")
        selectedColor: settings.highlightColor
        onAccepted: settings.setHighlightColor(selectedColor)
    }

    Dialog {
        id: schemaDialog
        title: qsTr("Choose the dataset schema")
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Ok | Dialog.Cancel
        property alias choices: schemaBox.model

        ColumnLayout {
            Label { text: qsTr("The schema could not be detected automatically.") }
            ComboBox {
                id: schemaBox
                Layout.fillWidth: true
                Layout.preferredWidth: 360
            }
        }
        onAccepted: backend.importWithSchema(schemaBox.currentIndex)
    }

    Dialog {
        id: messageDialog
        title: "Left on Read"
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Ok
        property alias text: messageLabel.text

        Label {
            id: messageLabel
            width: Math.min(480, window.width - 80)
            wrapMode: Text.Wrap
        }
    }

    Connections {
        target: backend
        function onMessage(text) {
            messageDialog.text = text
            messageDialog.open()
        }
        function onSchemaChoiceNeeded(labels) {
            schemaDialog.choices = labels
            schemaDialog.open()
        }
        function onProjectChanged() {
            reviewScreen.editing = false
        }
    }

    // -- content -------------------------------------------------------------

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap
        anchors.topMargin: 4
        spacing: 8

        // Mode switch
        Rectangle {
            visible: backend.hasProject
            color: Theme.panel
            radius: height / 2
            implicitHeight: 32
            implicitWidth: modeRow.implicitWidth + 8
            Layout.alignment: Qt.AlignHCenter

            Row {
                id: modeRow
                anchors.centerIn: parent
                spacing: 4

                Repeater {
                    model: [["review", qsTr("Review")], ["finder", qsTr("Finder")]]
                    delegate: Rectangle {
                        id: tab
                        required property var modelData
                        readonly property bool active: window.mode === modelData[0]
                        width: 96
                        height: 26
                        radius: height / 2
                        color: active ? settings.highlightColor
                             : tabArea.containsMouse ? Theme.fade(settings.highlightColor, 0.12)
                             : "transparent"

                        Label {
                            anchors.centerIn: parent
                            text: tab.modelData[1]
                            color: tab.active ? Theme.onColor(settings.highlightColor) : Theme.text
                        }
                        MouseArea {
                            id: tabArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: window.setMode(tab.modelData[0])
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: !backend.hasProject ? 0 : window.mode === "review" ? 1 : 2

            StartScreen {
                sidebarOpen: window.sidebarOpen
                onToggleSidebar: window.sidebarOpen = !window.sidebarOpen
                onNewRequested: sourceDialog.open()
                onOpenRequested: openDialog.open()
            }
            ReviewScreen {
                id: reviewScreen
                sidebarOpen: window.sidebarOpen
                onToggleSidebar: window.sidebarOpen = !window.sidebarOpen
            }
            FinderScreen {
                sidebarOpen: window.sidebarOpen
                onToggleSidebar: window.sidebarOpen = !window.sidebarOpen
            }
        }
    }
}
