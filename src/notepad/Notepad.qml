// Luminos Notepad — a plain, fast text editor.
// [CHANGE: claude-code | 2026-08-05]
//
// WHY THIS EXISTS: the box had no GUI text editor at all — only nano and vim.
// Every graphical option was either GTK4 (banned, AGENTS.md §1) or dragged in a
// framework we do not otherwise use. This is Qt/QML, which the project already
// standardises on, and it runs on the stock `qml6` runtime with zero new
// packages and zero build step.
//
// HOW IT TOUCHES DISK: pure QML has no file API, so reads are XHR GET on a
// file:// URL and writes are XHR PUT. Both need QML_XHR_ALLOW_FILE_READ=1 /
// QML_XHR_ALLOW_FILE_WRITE=1, which the launcher exports. A PUT that fails
// still reports readyState DONE with status 0 — identical to a PUT that
// succeeded — so every save is verified by reading the file back and comparing
// it to the buffer. Without that read-back the UI would happily say "Saved" for
// a file it never wrote (the exact failure shape logged in BUG-088/089).

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: app

    // ── Design system (LUMINOS_DESIGN_SYSTEM.md) ──────────────────────────
    readonly property color colBg:        "#0A0A0F"
    readonly property color colSurface:   "#13131A"
    readonly property color colElevated:  "#1C1C26"
    readonly property color colAccent:    "#0080FF"
    readonly property color colText:      "#FFFFFF"
    readonly property color colTextDim:   "#8888AA"
    readonly property color colBorder:    Qt.rgba(1, 1, 1, 0.08)
    readonly property color colError:     "#FF4455"
    readonly property color colSuccess:   "#00C896"

    // ── State ─────────────────────────────────────────────────────────────
    property string currentPath: ""          // "" = untitled buffer
    property string savedText: ""            // last known on-disk contents
    readonly property bool modified: editor.text !== savedText
    property int editorFontSize: 14
    property bool wrapOn: true
    property string statusMsg: ""
    property color statusColor: colTextDim
    property bool forceClose: false

    readonly property string fileName: currentPath === ""
        ? "Untitled"
        : currentPath.substring(currentPath.lastIndexOf("/") + 1)

    width: 1000
    height: 700
    minimumWidth: 420
    minimumHeight: 300
    visible: true
    color: colBg
    title: (modified ? "• " : "") + fileName + " — Luminos Notepad"

    // ── Path <-> URL helpers ──────────────────────────────────────────────
    // XHR wants a percent-encoded file:// URL; the CLI and the status bar want
    // a plain path. Encoding is per path segment so "/" survives.
    function toUrl(p) {
        if (p.indexOf("file://") === 0)
            return p;
        var parts = p.split("/");
        for (var i = 0; i < parts.length; i++)
            parts[i] = encodeURIComponent(parts[i]);
        return "file://" + parts.join("/");
    }

    function toPath(u) {
        var s = "" + u;
        if (s.indexOf("file://") === 0)
            s = s.substring(7);
        return decodeURIComponent(s);
    }

    function setStatus(msg, col) {
        statusMsg = msg;
        statusColor = col === undefined ? colTextDim : col;
        statusClear.restart();
    }

    Timer {
        id: statusClear
        interval: 4000
        onTriggered: app.statusMsg = ""
    }

    // ── Load ──────────────────────────────────────────────────────────────
    function loadFile(path) {
        var req = new XMLHttpRequest();
        req.open("GET", toUrl(path));
        req.onreadystatechange = function () {
            if (req.readyState !== XMLHttpRequest.DONE)
                return;
            // A missing file and an empty file are indistinguishable here
            // (both: status 0, empty body). That is fine and matches notepad
            // behaviour — you get an empty buffer aimed at that path, and the
            // first save creates it.
            // savedText first: assigning editor.text re-evaluates `modified`
            // immediately, so the other order flashes a "•" modified marker in
            // the title for one frame on every open.
            app.savedText = req.responseText;
            editor.text = req.responseText;
            app.currentPath = path;
            editor.cursorPosition = 0;
            app.setStatus("Opened " + path);
        };
        req.send();
    }

    // ── Save (with read-back verification) ────────────────────────────────
    function saveFile(path) {
        var body = editor.text;
        var req = new XMLHttpRequest();
        req.open("PUT", toUrl(path));
        req.onreadystatechange = function () {
            if (req.readyState !== XMLHttpRequest.DONE)
                return;
            // Do not trust the PUT status — verify by reading it back.
            var check = new XMLHttpRequest();
            check.open("GET", toUrl(path));
            check.onreadystatechange = function () {
                if (check.readyState !== XMLHttpRequest.DONE)
                    return;
                if (check.responseText === body) {
                    app.currentPath = path;
                    app.savedText = body;
                    app.setStatus("Saved " + path, app.colSuccess);
                    if (app.forceClose)
                        app.close();
                } else {
                    app.forceClose = false;
                    app.setStatus("SAVE FAILED — " + path + " does not match the buffer (permissions? read-only mount?)", app.colError);
                }
            };
            check.send();
        };
        req.send(body);
    }

    function save() {
        if (currentPath === "")
            saveAsDialog.open();
        else
            saveFile(currentPath);
    }

    function newFile() {
        editor.text = "";
        savedText = "";
        currentPath = "";
        setStatus("New file");
    }

    // ── Find ──────────────────────────────────────────────────────────────
    function findNext(backwards) {
        var needle = findField.text;
        if (needle === "")
            return;
        var hay = editor.text.toLowerCase();
        var n = needle.toLowerCase();
        var idx;
        if (backwards) {
            idx = hay.lastIndexOf(n, Math.max(0, editor.selectionStart - 1));
            if (idx < 0)
                idx = hay.lastIndexOf(n);
        } else {
            idx = hay.indexOf(n, editor.selectionEnd);
            if (idx < 0)
                idx = hay.indexOf(n);   // wrap to top
        }
        if (idx < 0) {
            setStatus("Not found: " + needle, colError);
            return;
        }
        editor.select(idx, idx + needle.length);
        editor.forceActiveFocus();
    }

    // ── Startup: take a path from the command line (after `--`) ───────────
    Component.onCompleted: {
        var args = Qt.application.arguments;
        var sep = args.indexOf("--");
        if (sep >= 0 && sep + 1 < args.length)
            loadFile(args[sep + 1]);
        editor.forceActiveFocus();
    }

    // ── Unsaved-changes guard ─────────────────────────────────────────────
    onClosing: function (close) {
        if (modified && !forceClose) {
            close.accepted = false;
            unsavedDialog.open();
        }
    }

    // ── Shortcuts ─────────────────────────────────────────────────────────
    Shortcut { sequence: StandardKey.New;    onActivated: app.newFile() }
    Shortcut { sequence: StandardKey.Open;   onActivated: openDialog.open() }
    Shortcut { sequence: StandardKey.Save;   onActivated: app.save() }
    Shortcut { sequence: StandardKey.SaveAs; onActivated: saveAsDialog.open() }
    Shortcut { sequence: StandardKey.Quit;   onActivated: app.close() }
    Shortcut { sequence: StandardKey.ZoomIn; onActivated: app.editorFontSize = Math.min(48, app.editorFontSize + 1) }
    Shortcut { sequence: StandardKey.ZoomOut; onActivated: app.editorFontSize = Math.max(7, app.editorFontSize - 1) }
    Shortcut { sequence: "Ctrl+0";           onActivated: app.editorFontSize = 14 }
    Shortcut {
        sequence: StandardKey.Find
        onActivated: {
            findBar.visible = true;
            findField.forceActiveFocus();
            findField.selectAll();
        }
    }
    Shortcut { sequence: StandardKey.FindNext;     onActivated: app.findNext(false) }
    Shortcut { sequence: StandardKey.FindPrevious; onActivated: app.findNext(true) }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            findBar.visible = false;
            editor.forceActiveFocus();
        }
    }

    // ── Layout ────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Toolbar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: app.colElevated

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: app.colBorder
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 6

                ToolBtn { text: "New";     tip: "Ctrl+N";       onClicked: app.newFile() }
                ToolBtn { text: "Open";    tip: "Ctrl+O";       onClicked: openDialog.open() }
                ToolBtn { text: "Save";    tip: "Ctrl+S";       accent: app.modified; onClicked: app.save() }
                ToolBtn { text: "Save As"; tip: "Ctrl+Shift+S"; onClicked: saveAsDialog.open() }

                Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 20; color: app.colBorder }

                ToolBtn {
                    text: "Find"
                    tip: "Ctrl+F"
                    accent: findBar.visible
                    onClicked: {
                        findBar.visible = !findBar.visible;
                        if (findBar.visible)
                            findField.forceActiveFocus();
                        else
                            editor.forceActiveFocus();
                    }
                }
                ToolBtn {
                    text: "Wrap"
                    tip: "Toggle word wrap"
                    accent: app.wrapOn
                    onClicked: app.wrapOn = !app.wrapOn
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: app.fileName + (app.modified ? " •" : "")
                    color: app.modified ? app.colAccent : app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 13
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: 340
                }
            }
        }

        // Find bar
        Rectangle {
            id: findBar
            visible: false
            Layout.fillWidth: true
            implicitHeight: 40
            color: app.colSurface

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: app.colBorder
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 10
                spacing: 8

                Text {
                    text: "Find"
                    color: app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 12
                }

                Rectangle {
                    Layout.preferredWidth: 280
                    Layout.preferredHeight: 26
                    radius: 5
                    color: app.colBg
                    border.width: 1
                    border.color: findField.activeFocus ? app.colAccent : app.colBorder

                    TextInput {
                        id: findField
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        verticalAlignment: TextInput.AlignVCenter
                        color: app.colText
                        selectionColor: app.colAccent
                        font.family: "Inter"
                        font.pixelSize: 13
                        clip: true
                        onAccepted: app.findNext(false)
                    }
                }

                ToolBtn { text: "Prev"; tip: "Shift+F3"; onClicked: app.findNext(true) }
                ToolBtn { text: "Next"; tip: "F3";       onClicked: app.findNext(false) }
                Item { Layout.fillWidth: true }
            }
        }

        // Editor
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                id: editor
                background: Rectangle { color: app.colBg }
                color: app.colText
                selectionColor: app.colAccent
                selectedTextColor: "#FFFFFF"
                font.family: "JetBrains Mono"
                font.pixelSize: app.editorFontSize
                wrapMode: app.wrapOn ? TextArea.WrapAnywhere : TextArea.NoWrap
                selectByMouse: true
                persistentSelection: true
                leftPadding: 14
                topPadding: 10
                rightPadding: 14
                bottomPadding: 10
                tabStopDistance: font.pixelSize * 2.4
            }
        }

        // Status bar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 26
            color: app.colElevated

            Rectangle {
                width: parent.width
                height: 1
                color: app.colBorder
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 14

                Text {
                    text: app.statusMsg !== ""
                          ? app.statusMsg
                          : (app.currentPath === "" ? "unsaved buffer" : app.currentPath)
                    color: app.statusMsg !== "" ? app.statusColor : app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 11
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }

                Text {
                    // lineCount is display lines; with wrap off it equals real lines.
                    text: "Ln " + (editor.text.substring(0, editor.cursorPosition).split("\n").length)
                          + ", Col " + (editor.cursorPosition - editor.text.lastIndexOf("\n", editor.cursorPosition - 1))
                    color: app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 11
                }

                Text {
                    text: editor.text.length + " chars"
                    color: app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 11
                }

                Text {
                    text: app.editorFontSize + "px"
                    color: app.colTextDim
                    font.family: "Inter"
                    font.pixelSize: 11
                }
            }
        }
    }

    // ── Dialogs ───────────────────────────────────────────────────────────
    FileDialog {
        id: openDialog
        title: "Open file"
        fileMode: FileDialog.OpenFile
        onAccepted: app.loadFile(app.toPath(selectedFile))
    }

    FileDialog {
        id: saveAsDialog
        title: "Save file as"
        fileMode: FileDialog.SaveFile
        onAccepted: app.saveFile(app.toPath(selectedFile))
        onRejected: app.forceClose = false
    }

    Dialog {
        id: unsavedDialog
        title: "Unsaved changes"
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Save | Dialog.Discard | Dialog.Cancel

        Label {
            text: "“" + app.fileName + "” has unsaved changes."
            color: app.colText
            font.family: "Inter"
        }

        onAccepted: {                       // Save
            app.forceClose = true;
            app.save();
        }
        onDiscarded: {
            app.forceClose = true;
            app.close();
        }
    }

    // ── Toolbar button ────────────────────────────────────────────────────
    component ToolBtn: Rectangle {
        id: btn
        property string text: ""
        property string tip: ""
        property bool accent: false
        signal clicked

        implicitWidth: label.implicitWidth + 20
        implicitHeight: 26
        radius: 5
        color: btn.accent
               ? Qt.rgba(0, 0.5, 1, 0.16)
               : (mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent")
        border.width: 1
        border.color: btn.accent ? Qt.rgba(0, 0.5, 1, 0.5) : app.colBorder

        Text {
            id: label
            anchors.centerIn: parent
            text: btn.text
            color: btn.accent ? app.colAccent : app.colText
            font.family: "Inter"
            font.pixelSize: 12
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }

        ToolTip.visible: mouse.containsMouse && btn.tip !== ""
        ToolTip.text: btn.tip
        ToolTip.delay: 600
    }
}
