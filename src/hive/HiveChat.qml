import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.LocalStorage

// [CHANGE: antigravity | 2026-04-28]
// Added: LocalStorage chat persistence, debug console.log, activity marker
Window {
    id: root
    visible: true
    // ============================================
    // SECTION: Window Properties
    // PURPOSE: Defines the main application window size and background
    // TUNE: Adjust width, height, and color to change window appearance
    // ============================================
    width: 820          // Window width in logical px — adjust for wider/narrower
    height: 620         // Window height in logical px — adjust for taller/shorter
    color: bgColor    // [CHANGE: gemini-cli | 2026-04-28] Dynamic background
    title: "HIVE Chat"

    // [CHANGE: gemini-cli | 2026-04-28] Issue 1: System theme detection
    SystemPalette { id: sysPalette; colorGroup: SystemPalette.Active }
    
    property bool isDark: {
        var c = sysPalette.window;
        var luminance = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b;
        return luminance < 0.5;
    }

    // Background
    property color bgColor: isDark ? "#1E1E1E" : "#FAF9F6"
    // Surface (input bar, chips background)
    property color surfaceColor: isDark ? "#2A2A2A" : "#FFFFFF"
    // Input border / chip border
    property color borderColor: isDark ? "#444444" : "#E5E2DC"
    // Primary text
    property color textColor: isDark ? "#E8E6E3" : "#2D2B28"
    // Subtle/placeholder text
    property color subtleText: isDark ? "#888580" : "#A39E96"
    // Label text (chips, "Nexus · HIVE")
    property color labelText: isDark ? "#9A9590" : "#5A5650"
    // User message bubble
    property color userBubble: isDark ? "#333028" : "#F0EDE8"
    // AI message area (no bubble, just text on bg)
    property color aiBubble: isDark ? "#1E1E1E" : "#FAF9F6"
    // Accent (warm orange — same in both themes)
    property color accentColor: "#D4784A"
    // Separator line between conversation blocks
    property color separatorColor: isDark ? "#333333" : "#E8E5E0"
    // Scrollbar
    property color scrollbarColor: isDark ? "#555555" : "#CCCCCC"
    // Additional theme-aware colors for hover states
    property color hoverColor: isDark ? "#3A3A3A" : "#F5F3EF"
    property color borderHoverColor: isDark ? "#555555" : "#D1CEC8"

    // Main state variables
    property bool sidebarExpanded: false
    property bool chatStarted: false
    property var conversationHistory: []
    property bool isTyping: false
    property int currentConversationId: -1
    property string activeChip: ""         // "" or "Code"/"Learn"/"Strategize"/"Write"/"System"
    property string lastAgent: "Nexus"     // updated from daemon response; drives footer label

    // [CHANGE: gemini-cli | 2026-05-04] Greeting state with instant fallback
    property string greetingText: getTimeBasedGreeting()

    function getTimeBasedGreeting() {
        var hour = new Date().getHours()
        if (hour < 12) return "Morning, Vratik ✳"
        if (hour < 17) return "Afternoon, Vratik ✳"
        return "Evening, Vratik ✳"
    }

    function addStatusMessage(text) {
        chatModel.append({
            "role": "assistant",
            "content": "<i>" + text + "</i>",
            "isStatus": true,
            "agentName": "",
            "thinkingTime": ""
        });
    }

    // [CHANGE: gemini-cli | 2026-05-03] In-place status update helper
    function updateLastStatus(text) {
        var found = false;
        // Search last 3 items for an existing status message
        var start = Math.max(0, chatModel.count - 3);
        for (var i = chatModel.count - 1; i >= start; i--) {
            if (chatModel.get(i).isStatus === true) {
                chatModel.setProperty(i, "content", "<i>" + text + "</i>");
                found = true;
                break;
            }
        }
        if (!found) {
            addStatusMessage(text);
        }
    }

    // [CHANGE: gemini-cli | 2026-05-03] Remove last status message before assistant response
    function removeLastStatus() {
        var start = Math.max(0, chatModel.count - 3);
        for (var i = chatModel.count - 1; i >= start; i--) {
            if (chatModel.get(i).isStatus === true) {
                chatModel.remove(i);
                break;
            }
        }
    }

    // [CHANGE: gemini-cli | 2026-05-03] Progress polling timer and logic
    Timer {
        id: progressTimer
        interval: 500
        repeat: true
        running: false
        onTriggered: pollProgress()
    }

    function pollProgress() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "http://localhost:8078/progress");
        xhr.timeout = 2000;
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                try {
                    var response = JSON.parse(xhr.responseText);
                    var stage = response.stage;
                    var elapsed_ms = response.elapsed_ms;
                    
                    if (stage === "idle") {
                        progressTimer.running = false;
                        return;
                    }

                    console.log("HIVE-PROGRESS:", stage, elapsed_ms + "ms");

                    var secs = (elapsed_ms / 1000).toFixed(1) + "s";
                    var msg = "";

                    switch (stage) {
                        case "routing_check":     msg = "Nexus is thinking…"; break;
                        case "swapping_to_nexus": msg = "Loading Nexus… (" + secs + ")"; break;
                        case "swapping_to_bolt":  msg = "Loading Bolt… (" + secs + ")"; break;
                        case "swapping_to_nova":  msg = "Loading Nova… (" + secs + ")"; break;
                        case "generating_nexus":  msg = "Nexus is responding… (" + secs + ")"; break;
                        case "generating_bolt":   msg = "Bolt is responding… (" + secs + ")"; break;
                        case "generating_nova":   msg = "Nova is responding… (" + secs + ")"; break;
                        case "routing_to_bolt":   msg = "Routing to Bolt…"; break;
                        case "routing_to_nova":   msg = "Routing to Nova…"; break;
                        default:                  msg = stage; break;
                    }

                    updateLastStatus(msg);

                } catch (e) {
                    console.log("HIVE-ERROR: Progress parse failed:", e);
                }
            }
        };
        xhr.send();
    }

    // [CHANGE: gemini-cli | 2026-04-28] Issue 3: Ping health and show status
    function checkServerHealth() {
        var hc = new XMLHttpRequest();
        hc.open("GET", "http://localhost:8078/health");
        hc.timeout = 3000;
        hc.onreadystatechange = function() {
            if (hc.readyState === XMLHttpRequest.DONE) {
                if (hc.status === 200) {
                    chatModel.append({
                        "role": "assistant",
                        "content": "HIVE is ready.",
                        "isStatus": true,
                        "agentName": "",
                        "thinkingTime": ""
                    });
                } else {
                    chatModel.append({
                        "role": "assistant",
                        "content": "Waking up...",
                        "isStatus": true,
                        "agentName": "",
                        "thinkingTime": ""
                    });
                }
            }
        };
        hc.ontimeout = function() {
            chatModel.append({
                "role": "assistant",
                "content": "Waking up...",
                "isStatus": true,
                "agentName": "",
                "thinkingTime": ""
            });
        };
        hc.send();
    }

    // ============================================
    // SECTION: LocalStorage Database
    // PURPOSE: Persist chat messages to SQLite via Qt's built-in LocalStorage.
    //          Two tables: conversations (id, title, created_at)
    //                      messages (id, conversation_id, role, content, created_at)
    //          Save only — no load, no sidebar. History UI comes later.
    // ============================================
    function getDb() {
        return LocalStorage.openDatabaseSync(
            "HiveChatDB",   // DB identifier
            "1.0",          // Version
            "HIVE Chat History",
            1000000         // Estimated size in bytes (~1MB)
        )
    }

    function initDb() {
        var db = getDb()
        db.transaction(function(tx) {
            tx.executeSql("CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )")
            tx.executeSql("CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )")
        })
        console.log("[HIVE DB] Database initialized")
    }

    function createConversation() {
        var db = getDb()
        var newId = -1
        db.transaction(function(tx) {
            tx.executeSql("INSERT INTO conversations (title) VALUES (?)", ["New chat"])
            var result = tx.executeSql("SELECT last_insert_rowid() as id")
            if (result.rows.length > 0) {
                newId = result.rows.item(0).id
            }
        })
        console.log("[HIVE DB] Created conversation:", newId)
        return newId
    }

    function saveMessage(conversationId, role, content) {
        if (conversationId < 0) return
        var db = getDb()
        db.transaction(function(tx) {
            tx.executeSql(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                [conversationId, role, content]
            )
        })
        console.log("[HIVE DB] Saved message:", role, "len:", content.length)
    }

    function loadConversation(id) {
        var db = getDb()
        chatModel.clear()
        conversationHistory = []
        root.currentConversationId = id
        chatStarted = true
        db.readTransaction(function(tx) {
            var rs = tx.executeSql(
                "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
                [id]
            )
            for (var i = 0; i < rs.rows.length; i++) {
                var row = rs.rows.item(i)
                chatModel.append({
                    "role": row.role,
                    "content": row.content,
                    "agentName": "",
                    "isStatus": false,
                    "thinkingTime": ""
                })
                conversationHistory.push({"role": row.role, "content": row.content})
            }
        })
        sidebarExpanded = false
        sidebar.refresh()
    }

    function updateConversationTitle(conversationId, firstMessage) {
        if (conversationId < 0) return
        var title = firstMessage.substring(0, 50)
        if (firstMessage.length > 50) title += "..."
        var db = getDb()
        db.transaction(function(tx) {
            tx.executeSql(
                "UPDATE conversations SET title = ? WHERE id = ?",
                [title, conversationId]
            )
        })
        console.log("[HIVE DB] Updated title:", title)
    }

    Item {
        id: mainContent
        anchors.fill: parent
        anchors.margins: 0 // Content fills the window

        HistorySidebar {
            id: sidebar
            expanded: sidebarExpanded
            currentConversationId: root.currentConversationId
            bgColor: root.bgColor
            textColor: root.textColor
            borderColor: root.borderColor
            accentColor: root.accentColor
            subtleText: root.subtleText
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            z: 10
            onConversationSelected: function(id) { loadConversation(id) }
            onNewChatRequested: {
                chatModel.clear()
                createConversation()
                sidebar.refresh()
            }
        }

        // ============================================
        // SECTION: Window Fade
        // PURPOSE: Animates the content instead of the window to avoid Wayland opacity spam
        // TUNE: Fade duration
        // ============================================
        SequentialAnimation on opacity {
            id: fadeInAnim
            running: true
            NumberAnimation { from: 0; to: 1; duration: 200; easing.type: Easing.OutQuad } // Window open fade-in duration
        }

        Rectangle {
            id: bgRect
            anchors.fill: parent
            color: bgColor // [CHANGE: gemini-cli | 2026-04-28] Dynamic background
        }

        // ============================================
        // SECTION: Landing State (Greeting)
        // PURPOSE: Shows the initial welcome message
        // TUNE: Adjust colors, fonts, and icons for greeting
        // ============================================

        Rectangle {
            id: hamburgerBtn
            width: 32; height: 32
            radius: 6
            color: "transparent"
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.margins: 8
            z: 11
            Text {
                anchors.centerIn: parent
                text: "☰"
                color: root.subtleText
                font.pixelSize: 18
            }
            MouseArea {
                anchors.fill: parent
                onClicked: root.sidebarExpanded = !root.sidebarExpanded
            }
        }

        Item {
            id: landingView
            anchors.fill: parent
            opacity: root.chatStarted ? 0 : 1
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } } // Greeting fade duration

            ColumnLayout {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -40
                spacing: 24 // Spacing between greeting and input bar

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12 // Spacing between icon and greeting text

                    Text {
                        text: "✳" // Sparkle/asterisk icon
                        color: accentColor // [CHANGE: gemini-cli | 2026-04-28] Use accentColor
                        font.pixelSize: 40 // Icon size
                    }

                    Text {
                        text: root.greetingText
                        color: textColor // [CHANGE: gemini-cli | 2026-04-28] Use textColor
                        font.family: "Inter" // Greeting font
                        font.pixelSize: 36 // Greeting font size
                        font.weight: Font.Normal
                        font.letterSpacing: -0.5 // Letter spacing (tighter)
                    }
                }
            }
        }

        // ============================================
        // SECTION: Chat State (Messages)
        // PURPOSE: Shows the conversation history
        // TUNE: Adjust chat bubbles, padding, and text colors
        // ============================================
        // [CHANGE: gemini-cli | 2026-04-28] Fix Bug 3: Chat now anchors to parent.bottom and clips behind input bar
        ScrollView {
            id: chatView
            anchors.top: parent.top
            anchors.topMargin: 8
            anchors.bottom: footerBar.top
            anchors.bottomMargin: 2
            anchors.left: parent.left
            anchors.leftMargin: 0
            anchors.right: parent.right
            clip: true

            opacity: root.chatStarted ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } } // Chat view fade duration

            // Hide standard scrollbar, use custom logic or default KDE look if possible
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            // [CHANGE: gemini-cli | 2026-04-28] Fix Bug 1: Optimized ListView for smooth scrolling (Trackpad)
            ListView {
                id: messageList
                anchors.fill: parent
                model: ListModel { id: chatModel }
                spacing: 6 // [CHANGE: gemini-cli | 2026-04-28] Reduced spacing between turns
                topMargin: 16
                bottomMargin: 16

                cacheBuffer: 1000
                clip: true
                // [CHANGE: gemini-cli | 2026-04-28] Issue 1: Replace flick physics with WheelHandler for Trackpad
                interactive: false
                boundsBehavior: Flickable.StopAtBounds

                WheelHandler {
                    id: scrollHandler
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: function(event) {
                        // Use angleDelta for discrete scroll, pixelDelta for smooth trackpad
                        var delta = event.pixelDelta.y !== 0 ? event.pixelDelta.y : event.angleDelta.y / 2;

                        // Apply directly — negative delta = scroll down
                        var newY = messageList.contentY - delta;

                        // Clamp to bounds
                        var minY = messageList.originY;
                        var maxY = messageList.contentHeight - messageList.height + messageList.originY;

                        if (maxY < minY) maxY = minY;

                        messageList.contentY = Math.max(minY, Math.min(maxY, newY));
                    }
                }

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    interactive: true
                    minimumSize: 0.05
                }

                // [CHANGE: antigravity | 2026-04-28] Full delegate rewrite — responsive layout, no hardcoded heights
                delegate: Column {
                    id: delegateCol
                    // [CHANGE: gemini-cli | 2026-05-01] Pre-parse segments for repeater
                    property var segments: parseMessageSegments(model.content || "")
                    x: 24
                    width: ListView.view ? ListView.view.width - 48 : 0
                    spacing: 0  // We control spacing with explicit spacer Items

                    // ── PART 1: Separator (only before user messages, not first message) ──
                    Item {
                        width: parent.width
                        height: 25  // 12px above + 1px line + 12px below
                        visible: model.role === "user" && model.index > 0 && !model.isStatus

                        Rectangle {
                            width: parent.width * 0.9
                            height: 1
                            color: separatorColor
                            anchors.centerIn: parent
                        }
                    }

                    // ── PART 1.5: Thinking trace (collapsible) ──
                    // [CHANGE: antigravity | 2026-04-28] Phase 5.5: Collapsible thinking/reasoning trace
                    Column {
                        id: thinkingTrace
                        width: parent.width
                        visible: model.role === "thinking"
                        spacing: 0

                        // Header row — click to toggle expand/collapse
                        Item {
                            width: parent.width
                            height: thinkingHeader.implicitHeight + 8

                            Text {
                                id: thinkingHeader
                                property bool expanded: false
                                text: (expanded ? "▼ " : "▶ ") + (model.agentName || "HIVE") + " · Thinking (" + (model.thinkingTime || "...") + ")"
                                color: subtleText
                                font.family: "Inter"
                                font.pixelSize: 12
                                font.italic: true
                                anchors.verticalCenter: parent.verticalCenter
                                leftPadding: 4
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: thinkingHeader.expanded = !thinkingHeader.expanded
                            }
                        }

                        // Expandable content box
                        Rectangle {
                            id: thinkingBody
                            width: parent.width * 0.85
                            visible: thinkingHeader.expanded
                            implicitHeight: thinkingBodyText.implicitHeight + 16
                            color: root.isDark ? "#252525" : "#F5F3EF"
                            border.width: 1
                            border.color: borderColor
                            radius: 8

                            Text {
                                id: thinkingBodyText
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 8
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                text: model.content
                                color: subtleText
                                font.family: "Inter"
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                lineHeight: 1.3
                            }
                        }

                        // Small spacer after thinking trace
                        Item { width: 1; height: 4 }
                    }

                    // ── PART 2: Message bubble (not for thinking traces) ──
                    Item {
                        id: bubbleRow
                        width: parent.width
                        visible: model.role !== "thinking"
                        // Height determined entirely by the bubble's natural size
                        implicitHeight: model.role === "thinking" ? 0 : (msgBubble.implicitHeight > 0 ? msgBubble.implicitHeight : 40)

                        Rectangle {
                            id: msgBubble
                            // Width: simple percentage width to avoid implicitWidth wrap issues
                            width: parent.width * (model.role === "user" ? 0.75 : 0.85)

                            // Height: entirely driven by childrenRect
                            implicitHeight: bubbleContent.childrenRect.height + 24  // 12px top + 12px bottom padding

                            // Alignment: user right, AI/status left
                            anchors.right: model.role === "user" ? parent.right : undefined
                            anchors.left: model.role !== "user" ? parent.left : undefined

                            color: model.role === "user" ? userBubble : "transparent"
                            radius: 18

                            // Inner content Column — positions text with padding
                            Column {
                                id: bubbleContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                anchors.top: parent.top
                                anchors.topMargin: 12

                                // User messages + status: plain Text (not selectable)
                                Text {
                                    id: msgText
                                    visible: model.role !== "assistant" || model.isStatus
                                    width: parent.width
                                    text: model.content
                                    color: model.isStatus ? subtleText : textColor
                                    font.family: "Inter"
                                    font.pixelSize: 14
                                    font.italic: model.isStatus ? true : false
                                    wrapMode: Text.Wrap
                                    textFormat: Text.RichText
                                    lineHeight: 1.4
                                    // Height is NEVER set — determined by wrapMode
                                }

                                // AI messages (non-status): Column + Repeater for code block support
                                // [CHANGE: gemini-cli | 2026-05-01] Added multi-segment rendering with code block copy buttons
                                Column {
                                    id: messageSegments
                                    visible: model.role === "assistant" && !model.isStatus
                                    width: parent.width
                                    spacing: 8

                                    Repeater {
                                        model: segments
                                        delegate: Column {
                                            id: segmentData
                                            width: parent.width
                                            spacing: 0

                                            // Text Segment
                                            TextEdit {
                                                id: textSeg
                                                visible: modelData.type === "text"
                                                width: parent.width
                                                height: visible ? contentHeight : 0
                                                text: formatMarkdown(modelData.content || "")
                                                readOnly: true
                                                selectByMouse: true
                                                wrapMode: TextEdit.Wrap
                                                textFormat: TextEdit.RichText
                                                font.family: "Inter"
                                                font.pixelSize: 14
                                                color: textColor
                                                selectedTextColor: surfaceColor
                                                selectionColor: accentColor
                                            }

                                            // Code Segment
                                            Rectangle {
                                                id: codeSeg
                                                visible: modelData.type === "code"
                                                width: parent.width
                                                height: visible ? (codeHeader.height + codeContent.contentHeight + 24) : 0
                                                radius: 8
                                                color: isDark ? "#1A1A1A" : "#F5F3EF"
                                                border.color: isDark ? "#333333" : "#E0DDD8"
                                                border.width: 1

                                                // Code Header Row
                                                Rectangle {
                                                    id: codeHeader
                                                    width: parent.width
                                                    height: 32
                                                    color: isDark ? "#252525" : "#EBE8E3"
                                                    radius: 8
                                                    // Only top corners rounded for header
                                                    Rectangle {
                                                        width: parent.width; height: 8; anchors.bottom: parent.bottom; color: parent.color
                                                    }

                                                    Text {
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 12
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: modelData.lang || "code"
                                                        color: subtleText
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: 12
                                                    }

                                                    Rectangle {
                                                        id: codeCopy
                                                        anchors.right: parent.right
                                                        anchors.rightMargin: 8
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 28; height: 28; radius: 4
                                                        color: codeCopyMouse.containsMouse ? borderColor : "transparent"

                                                        Text {
                                                            id: codeCopyIcon
                                                            anchors.centerIn: parent
                                                            text: "📋"
                                                            font.pixelSize: 14
                                                        }

                                                        MouseArea {
                                                            id: codeCopyMouse
                                                            anchors.fill: parent
                                                            hoverEnabled: true
                                                            cursorShape: Qt.PointingHandCursor
                                                            onClicked: {
                                                                var xhr = new XMLHttpRequest();
                                                                xhr.open("POST", "http://localhost:8078/copy");
                                                                xhr.setRequestHeader("Content-Type", "application/json");
                                                                xhr.send(JSON.stringify({"text": modelData.content}));
                                                                codeCopyIcon.text = "✓";
                                                                codeCopyTimer.restart();
                                                            }
                                                        }
                                                        Timer {
                                                            id: codeCopyTimer
                                                            interval: 2000
                                                            onTriggered: codeCopyIcon.text = "📋"
                                                        }
                                                    }
                                                }

                                                TextEdit {
                                                    id: codeContent
                                                    anchors.top: codeHeader.bottom
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.margins: 12
                                                    text: modelData.content || ""
                                                    readOnly: true
                                                    selectByMouse: true
                                                    textFormat: TextEdit.PlainText
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: 13
                                                    color: textColor
                                                    wrapMode: TextEdit.Wrap
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ── PART 3: Model label (AI messages only, not status, not thinking) ──
                    // [CHANGE: antigravity | 2026-04-28] Phase 4: per-message agent name
                    Text {
                        id: modelLabel
                        visible: model.role === "assistant" && !model.isStatus
                        text: model.agentName || "Nexus"
                        font.pixelSize: 11
                        color: subtleText
                        topPadding: 4
                        leftPadding: 4
                    }

                    // ── PART 4: Copy button (AI messages only, not status, not thinking) ──
                    Row {
                        id: copyRowContainer
                        spacing: 6
                        topPadding: 2
                        visible: model.role === "assistant" && !model.isStatus

                        Rectangle {
                            id: copyRect
                            width: copyRow.width + 12
                            height: copyRow.height + 6
                            radius: 4
                            color: copyMouseArea.containsMouse ? borderColor : "transparent"
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Row {
                                id: copyRow
                                anchors.centerIn: parent
                                spacing: 4

                                Text {
                                    id: copyLabel
                                    text: "📋 Copy"
                                    font.pixelSize: 11
                                    color: subtleText

                                    property bool copied: false

                                    states: State {
                                        name: "copied"
                                        when: copyLabel.copied
                                        PropertyChanges {
                                            target: copyLabel
                                            text: "✓ Copied"
                                            color: accentColor
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: copyMouseArea
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: {
                                    var xhr = new XMLHttpRequest();
                                    xhr.open("POST", "http://localhost:8078/copy");
                                    xhr.setRequestHeader("Content-Type", "application/json");
                                    xhr.onreadystatechange = function() {
                                        if (xhr.readyState === XMLHttpRequest.DONE) {
                                            if (xhr.status === 200) {
                                                copyLabel.copied = true;
                                            } else {
                                                copyLabel.text = "⚠ Failed";
                                                copyLabel.color = accentColor;
                                            }
                                            copyResetTimer.restart();
                                        }
                                    };
                                    xhr.send(JSON.stringify({"text": model.content}));
                                }
                            }

                            Timer {
                                id: copyResetTimer
                                interval: 2000
                                onTriggered: copyLabel.copied = false
                            }
                        }
                    }

                    // ── PART 5: Bottom spacer — consistent gap after every message ──
                    Item {
                        width: 1
                        height: 6
                    }
                }

                onCountChanged: {
                    var lastIndex = chatModel.count - 1;
                    if (lastIndex >= 0) {
                        var item = chatModel.get(lastIndex);
                        var isFinalAssistant = (item.role === "assistant" && item.isStatus === false);
                        var isNearBottom = (contentHeight - contentY - height < 150);
                        
                        // Force scroll for final answer; otherwise respect threshold
                        if (isFinalAssistant || isNearBottom) {
                            Qt.callLater(function() {
                                messageList.positionViewAtIndex(chatModel.count - 1, ListView.End);
                            });
                        }
                    }
                }
            }
        }

        // Typing Indicator
        Item {
            id: typingIndicator
            // [CHANGE: gemini-cli | 2026-05-03] Hide dots if a status message is already showing
            property bool hasStatus: {
                var start = Math.max(0, chatModel.count - 3);
                for (var i = chatModel.count - 1; i >= start; i--) {
                    if (chatModel.get(i).isStatus === true) return true;
                }
                return false;
            }
            visible: root.isTyping && root.chatStarted && !hasStatus
            width: 50
            height: 20
            anchors.left: chatView.left
            anchors.leftMargin: 20
            anchors.bottom: footerBar.top
            anchors.bottomMargin: 15
            z: 5

            Row {
                spacing: 4
                Repeater {
                    model: 3
                    Rectangle {
                        width: 6; height: 6; radius: 3
                        color: subtleText // [CHANGE: gemini-cli | 2026-04-28] Use subtleText

                        SequentialAnimation on scale {
                            loops: Animation.Infinite
                            running: typingIndicator.visible
                            PauseAnimation { duration: index * 200 }
                            NumberAnimation { to: 1.5; duration: 200; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 200; easing.type: Easing.InOutQuad }
                            PauseAnimation { duration: (2 - index) * 200 }
                        }
                    }
                }
            }
        }

        // ============================================
        // SECTION: Input Area
        // PURPOSE: Search/Chat input field
        // TUNE: Adjust dimensions, borders, colors
        // ============================================
        // [CHANGE: gemini-cli | 2026-04-28] Fix Bug 3: Input bar layered on top with solid background
        Rectangle {
            id: footerBar
            width: parent.width
            height: 110
            color: bgColor // [CHANGE: gemini-cli | 2026-04-28] Use bgColor
            anchors.bottom: parent.bottom
            z: 10

            Item {
                id: inputContainer
                width: parent.width * 0.85 // Input bar width (85% of window)
                height: 52
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter

                Rectangle {
                    id: inputBg
                    anchors.fill: parent
                    color: surfaceColor // [CHANGE: gemini-cli | 2026-04-28] Use surfaceColor
                    radius: 26 // Input bar border radius (pill)
                    border.width: 1.5 // Input bar border width
                    border.color: textInput.activeFocus ? accentColor : borderColor // [CHANGE: gemini-cli | 2026-04-28] Use theme colors

                    Behavior on border.color { ColorAnimation { duration: 200 } } // Focus transition duration

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 12
                        spacing: 8

                        // [CHANGE: gemini-cli | 2026-04-28] Fix Bug 2: Center buttons and text perfectly
                        Text {
                            text: "⊕" // Plus icon placeholder
                            color: subtleText // [CHANGE: gemini-cli | 2026-04-28] Use subtleText
                            font.pixelSize: 20
                            Layout.alignment: Qt.AlignVCenter
                        }

                        TextField {
                            id: textInput
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            placeholderText: "How can I help you today?" // Input placeholder text
                            placeholderTextColor: subtleText // [CHANGE: gemini-cli | 2026-04-28] Use subtleText
                            color: textColor // [CHANGE: gemini-cli | 2026-04-28] Use textColor
                            font.family: "Inter"
                            font.pixelSize: 15 // Input text size
                            background: Item {} // Remove default background
                            leftPadding: 4
                            rightPadding: 4

                            onAccepted: root.sendMessage()
                        }

                        Rectangle {
                            width: 28; height: 28; radius: 14
                            color: textInput.text.trim() === "" ? hoverColor : accentColor // [CHANGE: gemini-cli | 2026-04-28] Use hoverColor and accentColor
                            Layout.alignment: Qt.AlignVCenter
                            Behavior on color { ColorAnimation { duration: 150 } } // Send button transition

                            Text {
                                anchors.centerIn: parent
                                text: "↑" // Send arrow icon
                                color: textInput.text.trim() === "" ? subtleText : surfaceColor // [CHANGE: gemini-cli | 2026-04-28] Use surfaceColor when active
                                font.pixelSize: 16
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sendMessage()
                            }
                        }
                    }
                }

                Text {
                    // Footer label: reads agent from last response; defaults to Nexus
                    text: lastAgent + " · HIVE"
                    color: labelText
                    font.family: "Inter"
                    font.pixelSize: 11
                    anchors.right: inputBg.right
                    anchors.rightMargin: 16
                    anchors.top: inputBg.bottom
                    anchors.topMargin: 6
                    Behavior on text { enabled: false } // no animation on text swap
                }

                // ============================================
                // SECTION: Category Chips
                // PURPOSE: Quick prompt prefixes — chip value travels with next chat request
                // TUNE: Chip colors, borders, and hover states
                // ============================================
                RowLayout {
                    anchors.top: inputBg.bottom
                    anchors.topMargin: 20
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 8
                    opacity: root.chatStarted ? 0 : 1
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }

                    Repeater {
                        model: [
                            { icon: "</>", label: "Code",       modelId: "bolt",  agent: "Bolt"  },
                            { icon: "🌐",  label: "Learn",      modelId: "nova",  agent: "Nova"  },
                            { icon: "📊",  label: "Strategize", modelId: "nova",  agent: "Nova"  },
                            { icon: "✏️",  label: "Write",      modelId: "nexus", agent: "Nexus" },
                            { icon: "⚙️",  label: "System",     modelId: "nexus", agent: "Nexus" }
                        ]

                        Rectangle {
                            id: chipRect
                            property bool isActive: root.activeChip === modelData.label
                            width: chipRow.implicitWidth + 16
                            height: 28
                            radius: 14
                            color: isActive ? accentColor :
                                   chipMouse.containsMouse ? hoverColor : surfaceColor
                            border.width: isActive ? 0 : 1
                            border.color: chipMouse.containsMouse ? borderHoverColor : borderColor
                            opacity: 1.0

                            Behavior on color { ColorAnimation { duration: 150 } }
                            Behavior on border.color { ColorAnimation { duration: 100 } }
                            Behavior on opacity { NumberAnimation { duration: 150 } }

                            RowLayout {
                                id: chipRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: modelData.icon
                                    font.pixelSize: 12
                                }
                                Text {
                                    text: modelData.label
                                    color: chipRect.isActive ? "#FFFFFF" : labelText
                                    font.family: "Inter"
                                    font.pixelSize: 13
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }
                            }

                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    // Chip selection is silent — value travels with next send
                                    root.activeChip = (root.activeChip === modelData.label) ? "" : modelData.label;
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    function closeWindow() {
        var fadeOut = Qt.createQmlObject('import QtQuick 2.0; NumberAnimation { target: mainContent; property: "opacity"; to: 0; duration: 150; easing.type: Easing.InQuad }', root) // Window close fade-out duration
        fadeOut.finished.connect(Qt.quit)
        fadeOut.start()
    }

    // Handle Escape key
    Shortcut {
        sequence: "Escape"
        onActivated: closeWindow()
    }

    // Process chat interaction
    function sendMessage() {
        var msg = textInput.text.trim()
        if (msg === "") return

        console.log("HIVE-SEND:", msg.substring(0, 80), "chip:", activeChip)

        if (!chatStarted) {
            chatStarted = true
            updateConversationTitle(currentConversationId, msg)
        }

        // Add to UI
        chatModel.append({ "role": "user", "content": msg, "isStatus": false, "agentName": "", "thinkingTime": "" })
        Qt.callLater(function() { messageList.positionViewAtIndex(chatModel.count - 1, ListView.End); });

        // Add to history
        conversationHistory.push({ "role": "user", "content": msg })

        // Persist to DB
        saveMessage(currentConversationId, "user", msg)

        textInput.text = ""
        isTyping = true

        sendToHive()
    }

    function formatMarkdown(text) {
        // Basic Markdown support for bold and code backticks
        // Since we are using RichText, we can replace syntax.
        // Replace ``` code blocks
        var formatted = text.replace(/```([\s\S]*?)```/g, "<pre style='background-color: " + hoverColor + "; border-radius: 8px; padding: 12px; font-family: \"JetBrains Mono\"; font-size: 13px;'>$1</pre>")
        // Replace `code`
        formatted = formatted.replace(/`([^`]+)`/g, "<code style='background-color: " + hoverColor + "; font-family: \"JetBrains Mono\";'>$1</code>")
        // Replace **bold**
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        // Newlines to <br>
        formatted = formatted.replace(/\n/g, "<br>")
        return formatted
    }

    // [CHANGE: gemini-cli | 2026-05-01] Split message into text and code segments
    function parseMessageSegments(text) {
        if (!text) return [{type: "text", content: ""}];
        var segments = [];
        var parts = text.split("```");
        for (var i = 0; i < parts.length; i++) {
            if (i % 2 === 0) {
                // Text segment
                if (parts[i].length > 0 || parts.length === 1) {
                    segments.push({type: "text", content: parts[i]});
                }
            } else {
                // Code segment
                var part = parts[i];
                var firstNewline = part.indexOf("\n");
                var lang = "";
                var content = part;
                if (firstNewline !== -1) {
                    lang = part.substring(0, firstNewline).trim();
                    content = part.substring(firstNewline + 1).trim();
                }
                segments.push({type: "code", lang: lang, content: content});
            }
        }
        return segments;
    }

    // [CHANGE: claude-code | 2026-05-02] Repointed to hive-daemon on :8078; single POST, daemon owns orchestration
    function sendToHive() {
        var userMsg = conversationHistory.length > 0
            ? conversationHistory[conversationHistory.length - 1].content
            : "";

        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:8078/chat", true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.timeout = 180000;

        // [CHANGE: gemini-cli | 2026-05-03] Start progress polling
        progressTimer.running = true;

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                isTyping = false;
                progressTimer.running = false;

                if (xhr.status === 200) {
                    try {
                        var response = JSON.parse(xhr.responseText);
                        if (response.error) {
                            console.log("HIVE-ERROR: daemon error:", response.error)
                            removeLastStatus();
                            addStatusMessage(response.error);
                            return;
                        }

                        var agent = response.agent || "Nexus";
                        var content = response.content || "";

                        console.log("HIVE-RESPONSE:", agent, "routed:", response.routed, "ms:", response.thinking_time_ms)

                        // [CHANGE: gemini-cli | 2026-05-03] Clean up status message before response lands
                        removeLastStatus();

                        // Thinking trace — single entry regardless of routing
                        if (response.routed) {
                            var nexusSecs   = ((response.nexus_time_ms      || 0) / 1000).toFixed(1) + "s";
                            var specSecs    = ((response.specialist_time_ms || 0) / 1000).toFixed(1) + "s";
                            var totalSecs   = (((response.nexus_time_ms || 0) + (response.specialist_time_ms || 0)) / 1000).toFixed(1) + "s";
                            chatModel.append({
                                "role": "thinking",
                                "content": "Nexus → routing decision (" + nexusSecs + ")\n" + agent + " → answering (" + specSecs + ")",
                                "agentName": "Routing to " + agent,
                                "isStatus": false,
                                "thinkingTime": totalSecs
                            });
                        } else {
                            var thinkSecs = ((response.thinking_time_ms || 0) / 1000).toFixed(1) + "s";
                            chatModel.append({
                                "role": "thinking",
                                "content": "Direct response",
                                "agentName": agent,
                                "isStatus": false,
                                "thinkingTime": thinkSecs
                            });
                        }

                        // Assistant message
                        lastAgent = agent;
                        conversationHistory.push({"role": "assistant", "content": content});
                        chatModel.append({
                            "role": "assistant",
                            "content": formatMarkdown(content),
                            "isStatus": false,
                            "agentName": agent,
                            "thinkingTime": ""
                        });
                        saveMessage(currentConversationId, "assistant", content);

                    } catch(e) {
                        console.log("HIVE-ERROR: JSON parse failed:", e)
                        removeLastStatus();
                        addStatusMessage("Error parsing HIVE response.");
                    }
                } else if (xhr.status === 0) {
                    console.log("HIVE-ERROR:", xhr.status, "connection refused")
                    removeLastStatus();
                    addStatusMessage("HIVE daemon is not responding. Try again.");
                } else {
                    console.log("HIVE-ERROR:", xhr.status, xhr.responseText.substring(0, 100))
                    removeLastStatus();
                    addStatusMessage("HIVE returned an error (" + xhr.status + ").");
                }
            }
        };

        xhr.ontimeout = function() {
            isTyping = false;
            progressTimer.running = false;
            console.log("HIVE-ERROR: timeout after 180s")
            removeLastStatus();
            addStatusMessage("HIVE daemon is not responding. Try again.");
        };

        // History: last 10 turns before current message, no thinking/status entries
        var history = [];
        var histStart = Math.max(0, conversationHistory.length - 11);
        for (var i = histStart; i < conversationHistory.length - 1; i++) {
            var item = conversationHistory[i];
            if (!item.isStatus) {
                history.push({"role": item.role, "content": item.content});
            }
        }

        var payload = {
            "message": userMsg,
            "chip": activeChip !== "" ? activeChip : null,
            "history": history
        };

        xhr.send(JSON.stringify(payload));
    }

    // [CHANGE: gemini-cli | 2026-05-02] Defer non-visual init to speed up first paint
    function deferredInit() {
        initDb()
        currentConversationId = createConversation()
        console.log("[HIVE] New conversation ID:", currentConversationId)
        checkServerHealth()

        // [CHANGE: gemini-cli | 2026-05-03] Refresh greeting cache in background
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:8078/greeting/refresh", true);
        xhr.send();
    }

    // [CHANGE: gemini-cli | 2026-05-04] Load greeting from daemon cache async
    function loadGreeting() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "http://localhost:8078/greeting", true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                try {
                    var response = JSON.parse(xhr.responseText);
                    if (response.greeting) {
                        // [CHANGE: gemini-cli | 2026-05-04] Defensive word count guard
                        if (response.greeting.split(/\s+/).length > 5) {
                            console.log("[HIVE] Greeting too long, ignoring:", response.greeting)
                            return
                        }

                        root.greetingText = response.greeting;
                        // Also update the initial message in model if it was a greeting
                        if (chatModel.count > 0 && chatModel.get(0).isStatus) {
                            chatModel.setProperty(0, "content", response.greeting);
                        }
                    }
                } catch (e) {
                    console.log("[HIVE] Async greeting parse failed");
                }
            }
        };
        xhr.send();
    }

    Component.onCompleted: {
        console.log("[HIVE] HiveChat.qml loaded")

        chatModel.append({
            "role": "assistant",
            "content": root.greetingText,
            "isStatus": true,
            "agentName": "",
            "thinkingTime": ""
        });

        textInput.forceActiveFocus()

        // Non-visual work runs on next event loop tick
        Qt.callLater(deferredInit)
        Qt.callLater(loadGreeting)
    }
}
