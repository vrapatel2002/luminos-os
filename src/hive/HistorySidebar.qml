import QtQuick
import QtQuick.Layouts
import QtQuick.LocalStorage

/*
 * HistorySidebar.qml
 * [CHANGE: gemini-cli | 2026-05-04]
 * Collapsible sidebar listing past conversations from LocalStorage.
 */

Rectangle {
    id: sidebar

    // --- Theme Properties (passed from parent) ---
    property color bgColor: "#FFFFFF"
    property color textColor: "#000000"
    property color borderColor: "#E0E0E0"
    property color accentColor: "#0078D4"
    property color subtleText: "#666666"

    // --- State ---
    property bool expanded: false
    property int currentConversationId: -1

    // --- Signals ---
    signal conversationSelected(int id)
    signal newChatRequested()

    width: expanded ? 260 : 0
    height: parent.height
    color: bgColor
    border.color: borderColor
    border.width: expanded ? 1 : 0
    clip: true

    Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutQuad } }

    // --- Database Logic ---
    function getDb() {
        return LocalStorage.openDatabaseSync("HiveChatDB", "1.0", "HIVE Chat History", 1000000)
    }

    function refresh() {
        historyModel.clear()
        var db = getDb()
        db.transaction(function(tx) {
            var rs = tx.executeSql("SELECT id, title, created_at FROM conversations ORDER BY id DESC")
            for (var i = 0; i < rs.rows.length; i++) {
                var item = rs.rows.item(i)
                historyModel.append({
                    "convId": item.id,
                    "title": item.title || "Untitled Chat",
                    "date": item.created_at
                })
            }
        })
    }

    onExpandedChanged: {
        if (expanded) refresh()
    }

    Component.onCompleted: refresh()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 16
        visible: sidebar.width > 200 // Prevent layout glitches during animation

        // --- Header / New Chat Button ---
        Rectangle {
            Layout.fillWidth: true
            height: 40
            radius: 8
            color: newChatMouse.containsMouse ? accentColor : "transparent"
            border.color: accentColor
            border.width: 1

            RowLayout {
                anchors.centerIn: parent
                spacing: 8
                Text {
                    text: "+"
                    color: newChatMouse.containsMouse ? "#FFFFFF" : accentColor
                    font.pixelSize: 18
                    font.bold: true
                }
                Text {
                    text: "New Chat"
                    color: newChatMouse.containsMouse ? "#FFFFFF" : accentColor
                    font.family: "Inter"
                    font.pixelSize: 14
                    font.weight: Font.Medium
                }
            }

            MouseArea {
                id: newChatMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sidebar.newChatRequested()
            }
        }

        // --- Conversations List ---
        ListView {
            id: historyView
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 4
            clip: true
            model: ListModel { id: historyModel }

            delegate: Rectangle {
                width: historyView.width
                height: 54
                radius: 6
                color: (convId === sidebar.currentConversationId) ? accentColor :
                       (delegateMouse.containsMouse ? borderColor : "transparent")
                
                opacity: (convId === sidebar.currentConversationId) ? 1.0 : 0.8

                Column {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 2

                    Text {
                        width: parent.width
                        text: title
                        color: (convId === sidebar.currentConversationId) ? "#FFFFFF" : textColor
                        font.family: "Inter"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        text: date
                        color: (convId === sidebar.currentConversationId) ? "#EEEEEE" : subtleText
                        font.family: "Inter"
                        font.pixelSize: 11
                    }
                }

                MouseArea {
                    id: delegateMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sidebar.conversationSelected(convId)
                }
            }
        }
    }
}
