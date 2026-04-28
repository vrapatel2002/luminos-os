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
    property bool chatStarted: false
    property var conversationHistory: []
    property bool isTyping: false
    property int currentConversationId: -1
    // [CHANGE: antigravity | 2026-04-28] Phase 4: Chip routing state
    property string activeChip: ""         // "" or "Code"/"Learn"/"Strategize"/"Write"/"System"
    property string activeModel: "nexus"   // current model backend name
    property string activeAgent: "Nexus"   // display name for labels
    property bool isSwapping: false        // true during swap XHR

    // [CHANGE: gemini-cli | 2026-04-28] HIVE Team Identity
    property string systemPrompt: ""
    onActiveModelChanged: loadSystemPrompt()

    function loadSystemPrompt() {
        var model = activeModel.toLowerCase();
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "file:///home/shawn/luminos-os/config/prompts/" + model + ".txt");
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.responseText.trim().length > 0) {
                    systemPrompt = xhr.responseText.trim();
                    console.log("[HIVE] System prompt loaded for:", model);
                }
            }
        };
        xhr.send();
    }

    property string timeOfDay: {
        var hour = new Date().getHours()
        if (hour >= 5 && hour < 12) return "Morning"
        if (hour >= 12 && hour < 17) return "Afternoon"
        return "Evening"
    }

    // [CHANGE: antigravity | 2026-04-28] Phase 4: Load active model from file + set agent name
    function loadActiveModel() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "file:///tmp/hive-active-model");
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                var name = xhr.responseText.trim();
                if (name.length > 0) {
                    activeModel = name.toLowerCase();
                    activeAgent = name.charAt(0).toUpperCase() + name.substring(1);
                    console.log("[HIVE] Active model loaded:", activeModel, "agent:", activeAgent);
                }
            }
        };
        xhr.send();
    }

    // [CHANGE: antigravity | 2026-04-28] Phase 4: Model swap, greeting, and status functions
    function swapModel(chipName, modelName, agentName) {
        if (isSwapping) return;  // prevent double-tap

        // If clicking the already-active chip, deselect → back to Nexus
        if (activeChip === chipName) {
            activeChip = "";
            modelName = "nexus";
            agentName = "Nexus";
        } else {
            activeChip = chipName;
        }

        // If already on this model, just show greeting (no swap needed)
        if (activeModel === modelName) {
            showGreeting(agentName);
            return;
        }

        isSwapping = true;
        addStatusMessage("Switching to " + agentName + "...");

        var xhr = new XMLHttpRequest();
        xhr.open("GET", "http://localhost:8079/swap/" + modelName);
        xhr.timeout = 60000;
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                isSwapping = false;
                if (xhr.status === 200) {
                    try {
                        var resp = JSON.parse(xhr.responseText);
                        if (resp.status === "ready") {
                            activeModel = modelName;
                            activeAgent = agentName;
                            loadSystemPrompt();
                            showGreeting(agentName);
                            console.log("[HIVE] Swapped to:", agentName);
                        } else {
                            addStatusMessage("Failed to load " + agentName + ". Staying on " + activeAgent + ".");
                            activeChip = "";  // revert
                        }
                    } catch(e) {
                        addStatusMessage("Failed to load " + agentName + ".");
                        activeChip = "";
                    }
                } else {
                    addStatusMessage("Failed to load " + agentName + ". Staying on " + activeAgent + ".");
                    activeChip = "";  // revert
                }
            }
        };
        xhr.ontimeout = function() {
            isSwapping = false;
            addStatusMessage(agentName + " took too long to load.");
            activeChip = "";
        };
        xhr.send();
    }

    function showGreeting(agentName) {
        var greetings = {
            "Nexus": "What's on your mind?",
            "Bolt": "What are we building?",
            "Nova": "What would you like to think through?"
        };
        var msg = greetings[agentName] || "Ready.";
        chatModel.append({
            "role": "assistant",
            "content": msg,
            "isStatus": false,
            "agentName": agentName
        });
        // Greetings are NOT saved to DB or conversation history
    }

    function addStatusMessage(text) {
        chatModel.append({
            "role": "assistant",
            "content": "<i>" + text + "</i>",
            "isStatus": true,
            "agentName": ""
        });
    }

    // [CHANGE: gemini-cli | 2026-04-28] Issue 3: Ping health and show status
    function checkServerHealth() {
        var hc = new XMLHttpRequest();
        hc.open("GET", "http://localhost:8080/health");
        hc.timeout = 3000;
        hc.onreadystatechange = function() {
            if (hc.readyState === XMLHttpRequest.DONE) {
                if (hc.status === 200) {
                    chatModel.append({
                        "role": "assistant",
                        "content": activeAgent + " is ready.",
                        "isStatus": true,
                        "agentName": ""
                    });
                } else {
                    chatModel.append({
                        "role": "assistant",
                        "content": "Waking up...",
                        "isStatus": true,
                        "agentName": ""
                    });
                }
            }
        };
        hc.ontimeout = function() {
            chatModel.append({
                "role": "assistant",
                "content": "Waking up...",
                "isStatus": true,
                "agentName": ""
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
                        text: root.timeOfDay + ", Sam"
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
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 0
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
                topMargin: 20
                bottomMargin: footerBar.height + 60 // [CHANGE: gemini-cli | 2026-04-28] Extra bottom margin to ensure last message clears input bar
                leftMargin: 20
                rightMargin: 20
                
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
                    width: ListView.view ? ListView.view.width - 40 : 0
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

                    // ── PART 2: Message bubble ──
                    Item {
                        id: bubbleRow
                        width: parent.width
                        // Height determined entirely by the bubble's natural size
                        implicitHeight: msgBubble.implicitHeight > 0 ? msgBubble.implicitHeight : 40

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

                                // AI messages (non-status): selectable TextEdit for copy support
                                TextEdit {
                                    id: messageText
                                    visible: model.role === "assistant" && !model.isStatus
                                    width: parent.width
                                    text: model.content
                                    readOnly: true
                                    selectByMouse: true
                                    wrapMode: TextEdit.Wrap
                                    textFormat: TextEdit.RichText
                                    font.family: "Inter"
                                    font.pixelSize: 14
                                    color: textColor
                                    selectedTextColor: surfaceColor
                                    selectionColor: accentColor
                                    // Height is NEVER set — determined by wrapMode
                                }
                            }
                        }
                    }

                    // ── PART 3: Model label (AI messages only, not status) ──
                    // [CHANGE: antigravity | 2026-04-28] Phase 4: per-message agent name
                    Text {
                        id: modelLabel
                        visible: model.role === "assistant" && !model.isStatus
                        text: model.agentName || activeAgent
                        font.pixelSize: 11
                        color: subtleText
                        topPadding: 4
                        leftPadding: 4
                    }

                    // ── PART 4: Copy button (AI messages only, not status) ──
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
                                    // [CHANGE: antigravity | 2026-04-28] Copy via swap server /copy endpoint (wl-copy)
                                    var xhr = new XMLHttpRequest();
                                    xhr.open("POST", "http://localhost:8079/copy");
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
                    Qt.callLater(function() {
                        messageList.positionViewAtEnd()
                    })
                }
            }
        }

        // Typing Indicator
        Item {
            id: typingIndicator
            visible: root.isTyping && root.chatStarted
            width: 50
            height: 20
            anchors.left: chatView.left
            anchors.leftMargin: 20
            anchors.bottom: footerBar.top
            anchors.bottomMargin: 10
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
            height: 140
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
                    // [CHANGE: antigravity | 2026-04-28] Phase 4: Dynamic footer label with swap state
                    text: isSwapping ? "Loading..." : (activeAgent + " · HIVE")
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
                // PURPOSE: Quick prompt prefixes
                // TUNE: Chip colors, borders, and hover states
                // ============================================
                // [CHANGE: antigravity | 2026-04-28] Phase 4: Chips as model selectors
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
                            opacity: root.isSwapping ? 0.5 : 1.0

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
                                cursorShape: root.isSwapping ? Qt.ArrowCursor : Qt.PointingHandCursor
                                onClicked: {
                                    if (!root.isSwapping) {
                                        root.swapModel(modelData.label, modelData.modelId, modelData.agent);
                                    }
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

        console.log("[HIVE] Sending message:", msg.substring(0, 80))

        if (!chatStarted) {
            chatStarted = true
            // Update conversation title from first message
            updateConversationTitle(currentConversationId, msg)
        }

        // Add to UI
        chatModel.append({ "role": "user", "content": msg, "isStatus": false, "agentName": "" })

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

    function sendToHive() {
        console.log("[HIVE] sendToHive() — messages:", conversationHistory.length)
        var xhr = new XMLHttpRequest()
        xhr.open("POST", "http://localhost:8080/v1/chat/completions", true)
        xhr.setRequestHeader("Content-Type", "application/json")

        // 30 seconds timeout
        xhr.timeout = 30000

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                console.log("[HIVE] XHR done — status:", xhr.status, "len:", xhr.responseText.length)
                isTyping = false
                if (xhr.status === 200) {
                    try {
                        var response = JSON.parse(xhr.responseText)
                        if (response.choices && response.choices.length > 0) {
                            var aiText = response.choices[0].message.content
                            console.log("[HIVE] AI response received, len:", aiText.length)
                            conversationHistory.push({ "role": "assistant", "content": aiText })
                            chatModel.append({ "role": "assistant", "content": formatMarkdown(aiText), "isStatus": false, "agentName": activeAgent })
                            // Persist AI response to DB
                            saveMessage(currentConversationId, "assistant", aiText)
                        } else {
                            console.log("[HIVE] ERROR: No choices in response")
                            chatModel.append({ "role": "assistant", "content": "<i>HIVE returned an empty response.</i>", "isStatus": true, "agentName": "" })
                        }
                    } catch(e) {
                        console.log("[HIVE] ERROR: JSON parse failed:", e)
                        chatModel.append({ "role": "assistant", "content": "<i>Error parsing HIVE response.</i>", "isStatus": true, "agentName": "" })
                    }
                } else if (xhr.status === 0) {
                    console.log("[HIVE] ERROR: Connection refused (status 0) — server may not be running")
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE is waking up... give me a moment.</i><br><b>Tip:</b> If it doesn't wake automatically, check /tmp/hive-server.log", "isStatus": true, "agentName": "" })
                } else {
                    console.log("[HIVE] ERROR: HTTP", xhr.status)
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE returned an error (" + xhr.status + ")</i>", "isStatus": true, "agentName": "" })
                }
            }
        }

        xhr.ontimeout = function() {
            console.log("[HIVE] ERROR: Request timed out after 30s")
            isTyping = false
            chatModel.append({ "role": "assistant", "content": "<i>HIVE didn't respond within 30 seconds. The model may not be loaded.</i>", "isStatus": true, "agentName": "" })
        }

        // [CHANGE: gemini-cli | 2026-04-28] Only send messages that are NOT status messages
        var historyToSend = []
        
        // Prepend system prompt if available
        if (systemPrompt.length > 0) {
            historyToSend.push({ "role": "system", "content": systemPrompt })
        }

        for (var i = 0; i < conversationHistory.length; i++) {
            if (!conversationHistory[i].isStatus) {
                historyToSend.push(conversationHistory[i])
            }
        }

        // [CHANGE: antigravity | 2026-04-28] Phase 4: Use activeModel in payload
        var payload = {
            "model": activeModel,
            "messages": historyToSend,
            "stream": false
        }

        console.log("[HIVE] Sending POST to localhost:8080")
        xhr.send(JSON.stringify(payload))
    }

    Component.onCompleted: {
        console.log("[HIVE] HiveChat.qml loaded")
        initDb()
        currentConversationId = createConversation()
        console.log("[HIVE] New conversation ID:", currentConversationId)
        
        // [CHANGE: gemini-cli | 2026-04-28] Issue 2 & 3: Initialization
        loadActiveModel()
        loadSystemPrompt()
        
        var hour = new Date().getHours()
        var greeting = hour < 12 ? "Morning, Sam ✳" :
                       hour < 17 ? "Afternoon, Sam ✳" :
                       "Evening, Sam ✳"
        
        chatModel.append({
            "role": "assistant",
            "content": greeting,
            "isStatus": true,
            "agentName": ""
        });
        
        checkServerHealth()
        
        textInput.forceActiveFocus()
    }
}
