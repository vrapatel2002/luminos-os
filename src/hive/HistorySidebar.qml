import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.LocalStorage

/*
 * HistorySidebar.qml
 * [CHANGE: claude-code | 2026-05-05]
 * Minimal sidebar — Claude.ai style. Relative timestamps, delete per chat,
 * slim left-border active state, no orange fill boxes.
 */

Rectangle {
    id: sidebar

    // --- Theme Properties (passed from parent) ---
    property color bgColor: "#FFFFFF"
    property color surfaceColor: "#F5F5F5"
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

    // CHANGE 2: Relative timestamp — fixes SQLite "YYYY-MM-DD HH:MM:SS" parse
    function relativeTime(dateStr) {
        var now = new Date()
        var fixed = dateStr.replace(" ", "T")
        var date = new Date(fixed)
        if (isNaN(date.getTime())) return "Unknown"
        var nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        var thenDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())
        var diffDays = Math.round((nowDay - thenDay) / 86400000)
        if (diffDays === 0) return "Today"
        if (diffDays === 1) return "Yesterday"
        if (diffDays < 7) return diffDays + " days ago"
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
    }

    onExpandedChanged: {
        if (expanded) refresh()
    }

    Component.onCompleted: refresh()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        visible: sidebar.width > 200 // Prevent layout glitches during animation

        // CHANGE 1: New Chat — slim row, no orange fill
        Item {
            Layout.fillWidth: true
            height: 52

            // Hover overlay (very subtle)
            Rectangle {
                anchors.fill: parent
                color: sidebar.accentColor
                opacity: newChatMouse.containsMouse ? 0.06 : 0
                Behavior on opacity { NumberAnimation { duration: 150 } }
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Text {
                    text: "+"
                    color: sidebar.accentColor
                    font.pixelSize: 20
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                }

                Text {
                    text: "New Chat"
                    color: sidebar.textColor
                    font.family: "Inter"
                    font.pixelSize: 14
                    font.weight: Font.Normal
                }
            }

            // Subtle bottom separator
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: sidebar.borderColor
            }

            MouseArea {
                id: newChatMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sidebar.newChatRequested()
            }
        }

        // CHANGE 5: "Recents" section header
        Text {
            text: "Recents"
            color: sidebar.subtleText
            font.family: "Inter"
            font.pixelSize: 11
            font.weight: Font.Medium
            leftPadding: 16
            topPadding: 12
            bottomPadding: 4
        }

        // CHANGE 2+3+4: Conversation list
        ListView {
            id: historyView
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            clip: true

            // CHANGE 4: Slim scrollbar
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 4
            }

            model: ListModel { id: historyModel }

            delegate: Item {
                id: delegateItem
                width: historyView.width
                height: 56

                // Hover background — subtle
                Rectangle {
                    anchors.fill: parent
                    color: sidebar.accentColor
                    opacity: delegateMouse.containsMouse ? 0.08 : 0
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                }

                // CHANGE 2: Active conversation — left border only, no full fill
                Rectangle {
                    width: 3
                    height: parent.height
                    color: sidebar.accentColor
                    visible: model.convId === sidebar.currentConversationId
                }

                // Content: title + relative timestamp
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 16
                    anchors.right: parent.right
                    anchors.rightMargin: 36
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3

                    Text {
                        width: parent.width
                        text: model.title
                        color: sidebar.textColor
                        font.family: "Inter"
                        font.pixelSize: 13
                        font.weight: Font.Normal
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        text: sidebar.relativeTime(model.date)
                        color: sidebar.subtleText
                        font.family: "Inter"
                        font.pixelSize: 11
                    }
                }

                // Main click area — placed BEFORE deleteBtn so delete sits on top
                MouseArea {
                    id: delegateMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sidebar.conversationSelected(model.convId)
                }

                // CHANGE 3+4: Trash icon — visible on hover, on top of delegateMouse
                Text {
                    id: deleteBtn
                    text: "🗑"
                    font.pixelSize: 14
                    color: sidebar.subtleText
                    visible: delegateMouse.containsMouse || deleteMouse.containsMouse
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    padding: 4

                    MouseArea {
                        id: deleteMouse
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // FIX 3: Save scroll position before refresh
                            var savedPos = historyView.contentY
                            var db = sidebar.getDb()
                            db.transaction(function(tx) {
                                tx.executeSql("DELETE FROM messages WHERE conversation_id=?", [model.convId])
                                tx.executeSql("DELETE FROM conversations WHERE id=?", [model.convId])
                            })
                            sidebar.refresh()
                            Qt.callLater(function() {
                                historyView.contentY = Math.min(savedPos,
                                    Math.max(0, historyView.contentHeight - historyView.height))
                            })
                            if (model.convId === sidebar.currentConversationId) {
                                sidebar.newChatRequested()
                            }
                        }
                    }
                }
            }
        }
    }
}
