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
    signal collapseRequested()

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

    // FIX 3: Relative timestamp — UTC-aware, handles SQLite format
    function relativeTime(dateStr) {
        if (!dateStr) return ""
        var fixed = dateStr.replace(" ", "T") + "Z"
        var date = new Date(fixed)
        if (isNaN(date.getTime())) {
            fixed = dateStr.replace(" ", "T")
            date = new Date(fixed)
        }
        if (isNaN(date.getTime())) return "Unknown"
        var now = new Date()
        var nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        var thenDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())
        var diffDays = Math.round((nowDay - thenDay) / 86400000)
        if (diffDays <= 0) return "Today"
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

        // FIX 1: Header — + New Chat (left) + ☰ collapse (right)
        Column {
            Layout.fillWidth: true

            Row {
                width: parent.width
                height: 52

                // Left: + New Chat
                Item {
                    width: parent.width - 44
                    height: 52

                    Rectangle {
                        anchors.fill: parent
                        color: sidebar.accentColor
                        opacity: newChatMouse.containsMouse ? 0.06 : 0
                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        spacing: 8

                        Text {
                            text: "+"
                            color: sidebar.accentColor
                            font.pixelSize: 22
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: "New Chat"
                            color: sidebar.textColor
                            font.family: "Inter"
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
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

                // Right: ☰ collapse button
                Item {
                    width: 44
                    height: 52

                    Rectangle {
                        anchors.fill: parent
                        color: sidebar.accentColor
                        opacity: collapseMouse.containsMouse ? 0.06 : 0
                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "☰"
                        color: sidebar.subtleText
                        font.pixelSize: 18
                    }

                    MouseArea {
                        id: collapseMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: sidebar.collapseRequested()
                    }
                }
            }

            // Separator line
            Rectangle {
                width: parent.width
                height: 1
                color: sidebar.borderColor
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

                // FIX 2: Styled trash icon — visible on hover, on top of delegateMouse
                Item {
                    id: deleteBtn
                    width: 32
                    height: 32
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    visible: delegateMouse.containsMouse || deleteMouse.containsMouse

                    Column {
                        spacing: 1
                        anchors.centerIn: parent
                        opacity: 0.7

                        // Bin lid
                        Rectangle {
                            width: 14
                            height: 2
                            radius: 1
                            color: "#E05555"
                            anchors.horizontalCenter: parent.horizontalCenter
                        }

                        // Bin body
                        Rectangle {
                            width: 11
                            height: 9
                            radius: 1
                            color: "transparent"
                            border.color: "#E05555"
                            border.width: 1.5
                            anchors.horizontalCenter: parent.horizontalCenter

                            Row {
                                anchors.centerIn: parent
                                spacing: 2
                                Repeater {
                                    model: 3
                                    Rectangle {
                                        width: 1
                                        height: 5
                                        color: "#E05555"
                                        opacity: 0.7
                                    }
                                }
                            }
                        }
                    }

                    MouseArea {
                        id: deleteMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
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
