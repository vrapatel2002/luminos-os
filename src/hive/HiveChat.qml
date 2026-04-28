import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

// [CHANGE: gemini-cli | 2026-04-27]
// Modified to use KDE native window, fix opacity spam, and connect backend
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
    color: "transparent" // Leave transparent to allow rounded corners and shadow
    title: "HIVE Chat"

    // Main state variables
    property bool chatStarted: false
    property var conversationHistory: []
    property bool isTyping: false

    property string timeOfDay: {
        var hour = new Date().getHours()
        if (hour >= 5 && hour < 12) return "Morning"
        if (hour >= 12 && hour < 17) return "Afternoon"
        return "Evening"
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
            color: "transparent" // Background handled by Window color
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
                        color: "#D4784A" // Accent color of the icon
                        font.pixelSize: 40 // Icon size
                    }

                    Text {
                        text: root.timeOfDay + ", Sam"
                        color: "#2D2B28" // Greeting text color
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
        ScrollView {
            id: chatView
            anchors.top: parent.top
            anchors.bottom: inputContainer.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
            anchors.bottomMargin: 0
            padding: 20 // Chat view padding
            
            opacity: root.chatStarted ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } } // Chat view fade duration

            // Hide standard scrollbar, use custom logic or default KDE look if possible
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            
            ListView {
                id: messageList
                anchors.fill: parent
                model: ListModel { id: chatModel }
                spacing: 16 // Spacing between messages
                
                delegate: Item {
                    width: ListView.view.width
                    height: messageColumn.height

                    Column {
                        id: messageColumn
                        width: model.role === "user" ? parent.width * 0.75 : parent.width * 0.8 // Max width
                        anchors.right: model.role === "user" ? parent.right : undefined
                        anchors.left: model.role === "assistant" ? parent.left : undefined
                        spacing: 4

                        Rectangle {
                            width: textMetrics.width + 32
                            height: textMetrics.height + 24
                            color: model.role === "user" ? "#F0EDE8" : "transparent" // User bubble color vs transparent
                            radius: 18 // User bubble radius
                            
                            // Asymmetrical tail for user
                            Rectangle {
                                visible: model.role === "user"
                                width: 18
                                height: 18
                                color: "#F0EDE8" // Tail color matches bubble
                                anchors.bottom: parent.bottom
                                anchors.right: parent.right
                                anchors.rightMargin: -4 // overlap
                                radius: 4 // Tail radius
                                z: -1
                            }

                            Text {
                                id: textMetrics
                                anchors.centerIn: parent
                                width: Math.min(messageColumn.width - 32, implicitWidth)
                                text: model.content
                                color: "#2D2B28" // Message text color
                                font.family: "Inter"
                                font.pixelSize: 14 // Message font size
                                wrapMode: Text.Wrap
                                textFormat: Text.RichText // Enables bold (<b>)
                                lineHeight: 1.6 // AI message line height
                            }
                        }
                    }

                    // Slide up animation on appear
                    Component.onCompleted: {
                        y += 5
                        opacity = 0
                        anim.start()
                    }
                    ParallelAnimation {
                        id: anim
                        NumberAnimation { target: parent; property: "y"; to: parent.y - 5; duration: 150; easing.type: Easing.OutQuad } // Slide up duration
                        NumberAnimation { target: parent; property: "opacity"; to: 1; duration: 150; easing.type: Easing.OutQuad } // Fade in duration
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
            anchors.bottom: inputContainer.top
            anchors.bottomMargin: 10

            Row {
                spacing: 4
                Repeater {
                    model: 3
                    Rectangle {
                        width: 6; height: 6; radius: 3
                        color: "#A39E96" // Typing dot color
                        
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
        Item {
            id: inputContainer
            width: parent.width * 0.85 // Input bar width (85% of window)
            height: 100
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 30
            anchors.horizontalCenter: parent.horizontalCenter

            Rectangle {
                id: inputBg
                width: parent.width
                height: 52 // Input bar min height
                anchors.top: parent.top
                color: "#FFFFFF" // Input bar background
                radius: 26 // Input bar border radius (pill)
                border.width: 1.5 // Input bar border width
                border.color: textInput.activeFocus ? "#D4784A" : "#E5E2DC" // Input bar border colors
                
                Behavior on border.color { ColorAnimation { duration: 200 } } // Focus transition duration

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "⊕" // Plus icon placeholder
                        color: "#A39E96" // Plus icon color
                        font.pixelSize: 20
                        Layout.alignment: Qt.AlignVCenter
                        Layout.leftMargin: 4
                    }

                    TextField {
                        id: textInput
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        placeholderText: "How can I help you today?" // Input placeholder text
                        placeholderTextColor: "#A39E96" // Placeholder text color
                        color: "#2D2B28" // Input text color
                        font.family: "Inter"
                        font.pixelSize: 15 // Input text size
                        background: Item {} // Remove default background
                        
                        onAccepted: root.sendMessage()
                    }

                    Rectangle {
                        Layout.alignment: Qt.AlignVCenter
                        width: 28; height: 28; radius: 14
                        color: textInput.text.trim() === "" ? "#F5F3EF" : "#D4784A" // Send button active color
                        Behavior on color { ColorAnimation { duration: 150 } } // Send button transition
                        
                        Text {
                            anchors.centerIn: parent
                            text: "↑" // Send arrow icon
                            color: textInput.text.trim() === "" ? "#A39E96" : "#FFFFFF" // Arrow color
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
                text: "Nexus · HIVE" // Small bottom label
                color: "#B5B0A8" // Bottom label color
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
                        color: chipMouse.containsMouse ? "#F5F3EF" : "#FFFFFF" // Chip bg hover state
                        border.width: 1 // Chip border width
                        border.color: chipMouse.containsMouse ? "#D1CEC8" : "#E5E2DC" // Chip border hover state
                        
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        RowLayout {
                            id: chipRow
                            anchors.centerIn: parent
                            spacing: 4
                            Text { text: modelData.icon; font.pixelSize: 12 } // Chip icon
                            Text { 
                                text: modelData.label 
                                color: "#5A5650" // Chip text color
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
    function touchLastRequest() {
        try {
            var proc = Qt.createQmlObject('import QtQuick; import QtCore; Process {}', root);
            proc.start("touch", ["/tmp/hive-last-request"]);
        } catch(e) {
            console.log("Process component unavailable:", e);
        }
    }

    function sendMessage() {
        touchLastRequest()
        var msg = textInput.text.trim()
        if (msg === "") return

        if (!chatStarted) {
            chatStarted = true
        }

        // Add to UI
        chatModel.append({ "role": "user", "content": msg })
        
        // Add to history
        conversationHistory.push({ "role": "user", "content": msg })
        
        textInput.text = ""
        isTyping = true
        
        sendToHive()
    }

    function formatMarkdown(text) {
        // Basic Markdown support for bold and code backticks
        // Since we are using RichText, we can replace syntax.
        // Replace ``` code blocks
        var formatted = text.replace(/```([\s\S]*?)```/g, "<pre style='background-color: #F5F3EF; border-radius: 8px; padding: 12px; font-family: \"JetBrains Mono\"; font-size: 13px;'>$1</pre>")
        // Replace `code`
        formatted = formatted.replace(/`([^`]+)`/g, "<code style='background-color: #F5F3EF; font-family: \"JetBrains Mono\";'>$1</code>")
        // Replace **bold**
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        // Newlines to <br>
        formatted = formatted.replace(/\n/g, "<br>")
        return formatted
    }

    function sendToHive() {
        var xhr = new XMLHttpRequest()
        xhr.open("POST", "http://localhost:8080/v1/chat/completions", true)
        xhr.setRequestHeader("Content-Type", "application/json")
        
        // 30 seconds timeout
        xhr.timeout = 30000 
        
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                isTyping = false
                if (xhr.status === 200) {
                    try {
                        var response = JSON.parse(xhr.responseText)
                        if (response.choices && response.choices.length > 0) {
                            var aiText = response.choices[0].message.content
                            conversationHistory.push({ "role": "assistant", "content": aiText })
                            chatModel.append({ "role": "assistant", "content": formatMarkdown(aiText) })
                        }
                    } catch(e) {
                        chatModel.append({ "role": "assistant", "content": "<i>Error parsing response</i>" })
                    }
                } else if (xhr.status === 0) {
                    // Connection refused or no server
                    var wakeMsgId = conversationHistory.length
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE is waking up... give me a moment.</i><br><b>Tip:</b> If it doesn't wake automatically, verify the background daemon is active." })
                    
                    try {
                        var proc = Qt.createQmlObject('import QtQuick; import QtCore; Process {}', root);
                        proc.start("/home/shawn/luminos-os/scripts/hive-start-model.sh", ["nexus"]);
                    } catch(e) {
                        console.log("Process component unavailable:", e);
                    }
                    
                    // Retry after 15 seconds
                    var timer = Qt.createQmlObject("import QtQuick; Timer { interval: 15000; repeat: false; running: true }", root);
                    timer.triggered.connect(function() {
                        // Remove the waking up message before retrying
                        if (chatModel.count > 0 && chatModel.get(chatModel.count - 1).role === "assistant" && chatModel.get(chatModel.count - 1).content.indexOf("waking up") !== -1) {
                            chatModel.remove(chatModel.count - 1);
                        }
                        sendToHive();
                        timer.destroy();
                    });
                } else {
                    chatModel.append({ "role": "assistant", "content": "<i>HIVE returned an error (" + xhr.status + ")</i>" })
                }
            }
        }
        
        xhr.ontimeout = function() {
            isTyping = false
            chatModel.append({ "role": "assistant", "content": "<i>HIVE didn't respond. The model may not be loaded.</i>" })
        }
        
        var payload = {
            "model": "nexus",
            "messages": conversationHistory,
            "stream": false
        }
        
        xhr.send(JSON.stringify(payload))
    }

    Component.onCompleted: {
        textInput.forceActiveFocus()
    }
}
