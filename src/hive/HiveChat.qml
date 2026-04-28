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
    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Dynamic model name
    property string activeModel: "HIVE"

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

    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Load active model name from file
    function loadActiveModel() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "file:///tmp/hive-active-model");
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                // For file:/// local files, status is often 0 on success
                var name = xhr.responseText.trim();
                if (name.length > 0) {
                    activeModel = name.charAt(0).toUpperCase() + name.substring(1);
                    console.log("[HIVE] Active model loaded:", activeModel);
                }
            }
        };
        xhr.send();
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
                        "content": activeModel + " is ready.",
                        "isStatus": true
                    });
                } else {
                    chatModel.append({
                        "role": "assistant",
                        "content": "Waking up...",
                        "isStatus": true
                    });
                }
            }
        };
        hc.ontimeout = function() {
            chatModel.append({
                "role": "assistant",
                "content": "Waking up...",
                "isStatus": true
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
                spacing: 16 // Spacing between messages
                topMargin: 20
                bottomMargin: footerBar.height + 40 // Prevent last message from being hidden behind input bar
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

                delegate: Column {
                    id: delegateCol
                    width: ListView.view ? ListView.view.width - 40 : 0
                    spacing: 4
                    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Add top margin when separator is shown
                    topPadding: (model.role === "user" && model.index > 0 && !model.isStatus) ? 16 : 8

                    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Conversation Block Separators
                    Loader {
                        active: model.role === "user" && model.index > 0 && !model.isStatus
                        width: parent.width
                        // Ensure 8px space below the 1px line (spacing 4 + height 5 = 9? No, height 5 means 4px extra)
                        // If spacing is 4, and I want 8px total below: 1px line + 4px space inside item + 4px spacing = 9.
                        // Wait, user said 8px below it.
                        // I'll use a height that accounts for the spacing.
                        height: active ? 5 : 0 
                        sourceComponent: Component {
                            Item {
                                width: parent.width
                                height: 5
                                Rectangle {
                                    width: parent.width * 0.9
                                    height: 1
                                    color: separatorColor
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                }
                            }
                        }
                    }

                    Item {
                        width: parent.width
                        height: msgBubble.height + 8

                        Rectangle {
                            id: msgBubble
                            width: Math.min(
                                (model.role === "assistant" && !model.isStatus ? messageText.implicitWidth : msgText.implicitWidth) + 32,
                                parent.width * (model.role === "user" ? 0.75 : 0.8)
                            )
                            height: (model.role === "assistant" && !model.isStatus ? messageText.implicitHeight : msgText.implicitHeight) + 24
                            anchors.right: model.role === "user" ? parent.right : undefined
                            anchors.left: model.role === "assistant" ? parent.left : undefined
                            color: model.role === "user" ? userBubble : "transparent" // [CHANGE: gemini-cli | 2026-04-28] Use userBubble
                            radius: 18 // Bubble radius

                            Text {
                                id: msgText
                                visible: model.role !== "assistant" || model.isStatus
                                anchors.centerIn: parent
                                width: parent.width - 32
                                text: model.content
                                color: textColor // [CHANGE: gemini-cli | 2026-04-28] Use textColor
                                font.family: "Inter"
                                font.pixelSize: 14 // Message font size
                                wrapMode: Text.Wrap
                                textFormat: Text.RichText // Enables bold (<b>)
                                lineHeight: 1.6 // User message line height
                            }

                            TextEdit {
                                id: messageText
                                visible: model.role === "assistant" && !model.isStatus
                                anchors.centerIn: parent
                                width: parent.width - 32
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
                            }
                        }
                    }

                    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Show model label under AI messages
                    Text {
                        id: modelLabel
                        visible: model.role === "assistant" && !model.isStatus
                        text: activeModel
                        font.pixelSize: 11
                        color: subtleText // [CHANGE: gemini-cli | 2026-04-28] Use subtleText
                        leftPadding: 4
                        anchors.left: parent.left
                    }

                    // [CHANGE: gemini-cli | 2026-04-28] Copy Button for AI messages (Wayland fixed)
                    Row {
                        id: copyRowContainer
                        spacing: 6
                        topPadding: 2
                        visible: model.role === "assistant" && !model.isStatus
                        opacity: 1.0 // Always visible but subtle
                        
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
                                    // [CHANGE: gemini-cli | 2026-04-28] Use selectable TextEdit for reliable Wayland clipboard
                                    messageText.selectAll();
                                    messageText.copy();
                                    messageText.deselect();
                                    copyLabel.copied = true;
                                    copyResetTimer.restart();
                                }
                            }

                            Timer {
                                id: copyResetTimer
                                interval: 2000
                                onTriggered: copyLabel.copied = false
                            }
                        }
                    }

                    // Hover detection area for the entire message turn (optional now, but kept for consistency)
                    MouseArea {
                        id: aiMessageHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton  // don't eat clicks
                        visible: model.role === "assistant" && !model.isStatus
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
                    // [CHANGE: gemini-cli | 2026-04-28] Issue 2: Dynamic footer label
                    text: activeModel + " · HIVE" // Small bottom label
                    color: labelText // [CHANGE: gemini-cli | 2026-04-28] Use labelText
                    font.family: "Inter"
                    font.pixelSize: 11 // Bottom label font size
                    anchors.right: inputBg.right
                    anchors.rightMargin: 16
                    anchors.top: inputBg.bottom
                    anchors.topMargin: 6
                }

                // ============================================
                // SECTION: Category Chips
                // PURPOSE: Quick prompt prefixes
                // TUNE: Chip colors, borders, and hover states
                // ============================================
                RowLayout {
                    anchors.top: inputBg.bottom
                    anchors.topMargin: 20
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 8 // Gap between chips
                    opacity: root.chatStarted ? 0 : 1
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } } // Chip fade duration

                    Repeater {
                        model: [
                            { icon: "</>", label: "Code", prefix: "Help me write code for " },
                            { icon: "🌐", label: "Learn", prefix: "Explain to me " },
                            { icon: "📊", label: "Strategize", prefix: "Help me plan " },
                            { icon: "✏️", label: "Write", prefix: "Help me write " },
                            { icon: "⚙️", label: "System", prefix: "On this system, " }
                        ]

                        Rectangle {
                            id: chipRect
                            width: chipRow.implicitWidth + 16
                            height: 28 // Chip height
                            radius: 14 // Chip corner radius
                            color: chipMouse.containsMouse ? hoverColor : surfaceColor // [CHANGE: gemini-cli | 2026-04-28] Theme colors
                            border.width: 1 // Chip border width
                            border.color: chipMouse.containsMouse ? borderHoverColor : borderColor // [CHANGE: gemini-cli | 2026-04-28] Theme colors

                            Behavior on color { ColorAnimation { duration: 100 } }
                            Behavior on border.color { ColorAnimation { duration: 100 } }

                            RowLayout {
                                id: chipRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text { text: modelData.icon; font.pixelSize: 12 } // Chip icon
                                Text {
                                    text: modelData.label
                                    color: labelText // [CHANGE: gemini-cli | 2026-04-28] Use labelText
                                    font.family: "Inter"
                                    font.pixelSize: 13 // Chip text size
                                }
                            }

                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    textInput.text = modelData.prefix
                                    textInput.forceActiveFocus()
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
        chatModel.append({ "role": "user", "content": msg })

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
                            chatModel.append({ "role": "assistant", "content": formatMarkdown(aiText) })
                            // Persist AI response to DB
                            saveMessage(currentConversationId, "assistant", aiText)
                        } else {
                            console.log("[HIVE] ERROR: No choices in response")
                            chatModel.append({ "role": "assistant", "content": "<i>HIVE returned an empty response.</i>" })
                        }
                    } catch(e) {
                        console.log("[HIVE] ERROR: JSON parse failed:", e)
                        chatModel.append({ "role": "assistant", "content": "<i>Error parsing HIVE response.</i>" })
                    }
                } else if (xhr.status === 0) {
                    console.log("[HIVE] ERROR: Connection refused (status 0) — server may not be running")
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE is waking up... give me a moment.</i><br><b>Tip:</b> If it doesn't wake automatically, check /tmp/hive-server.log" })
                } else {
                    console.log("[HIVE] ERROR: HTTP", xhr.status)
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE returned an error (" + xhr.status + ")</i>" })
                }
            }
        }

        xhr.ontimeout = function() {
            console.log("[HIVE] ERROR: Request timed out after 30s")
            isTyping = false
            chatModel.append({ "role": "assistant", "content": "<i>HIVE didn't respond within 30 seconds. The model may not be loaded.</i>" })
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

        var payload = {
            "model": "nexus",
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
            "isStatus": true
        });
        
        checkServerHealth()
        
        textInput.forceActiveFocus()
    }
}
