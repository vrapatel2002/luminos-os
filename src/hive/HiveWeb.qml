import QtQuick
import QtQuick.Window
import QtWebEngine

// ============================================================================
// HIVE Web — the OpenClaw Control UI in a native Luminos window
// [CHANGE: claude-code | 2026-08-14]
//
// PURPOSE
//   Renders OpenClaw's own Control UI (the polished dashboard normally opened
//   in Chrome at http://127.0.0.1:18789) inside a native Qt window, so the
//   refined product IS the HIVE window instead of a browser tab.
//
// WHY A WEB VIEW AND NOT A QML REWRITE
//   The Control UI is a React app shipped inside the openclaw npm package and
//   it changes every release. Re-implementing it in QML would mean re-doing
//   that work on every upgrade. Embedding it costs one file and stays current
//   for free. See LUMINOS_DECISIONS.md DECISION 71.
//
// TOKEN HANDLING — read this before changing the launcher
//   The gateway authenticates from the URL *fragment*: .../#token=<TOKEN>.
//   A fragment is never sent to the server; the JS app reads it client-side.
//
//   The token is read HERE, from a file path handed in on the command line.
//   The token itself is deliberately NOT passed as an argument, because argv
//   is world-readable through /proc/<pid>/cmdline. The path is not a secret;
//   the file it points at is chmod 600. Keep it that way.
// ============================================================================

Window {
    id: root
    visible: true
    width: 1040
    height: 780
    color: "#12100e"
    title: "HIVE"

    // ============================================
    // SECTION: Inputs
    // PURPOSE: Where the gateway lives and where its token is stored.
    // TUNE: Both are overridable from the command line by luminos-hive-popup:
    //         qml6 HiveWeb.qml -- <gatewayBase> <tokenPath>
    // ============================================
    property string gatewayBase: "http://127.0.0.1:18789"
    property string tokenPath: ""

    property string loadError: ""
    property bool ready: false

    // ------------------------------------------------------------------
    // Read the token off disk.
    //
    // QML has no getenv(), so the launcher hands us a PATH and we read the
    // file ourselves. This needs QML_XHR_ALLOW_FILE_READ=1 in the
    // environment — luminos-hive-popup already exports it.
    //
    // Note the status check: for a file:// URL Qt reports status 0 on
    // success, not 200. Checking only for 200 would reject every good read.
    // ------------------------------------------------------------------
    function readTokenFile(path) {
        if (!path)
            return "";
        var xhr = new XMLHttpRequest();
        try {
            xhr.open("GET", "file://" + path, false);
            xhr.send();
            if (xhr.status === 0 || xhr.status === 200)
                return (xhr.responseText || "").replace(/\s+$/, "");
        } catch (e) {
            console.log("HiveWeb: could not read token file:", path, e);
        }
        return "";
    }

    // Take the last two positional arguments if they look right, otherwise
    // keep the defaults. Being lenient here means launching the file by hand
    // (`qml6 HiveWeb.qml`) still shows the login form rather than nothing.
    function parseArgs() {
        var a = Qt.application.arguments;
        for (var i = 0; i < a.length; i++) {
            if (a[i].indexOf("http://") === 0 || a[i].indexOf("https://") === 0)
                root.gatewayBase = a[i].replace(/\/+$/, "");
            else if (a[i].indexOf("/") === 0 && a[i].indexOf(".qml") === -1)
                root.tokenPath = a[i];
        }
    }

    Component.onCompleted: {
        parseArgs();
        var token = readTokenFile(root.tokenPath);
        if (!token) {
            // Not fatal: the Control UI has its own token field, so we still
            // load the page and let the user paste one. Say so out loud
            // instead of showing a mystery login screen.
            console.log("HiveWeb: no token found at '" + root.tokenPath
                        + "' — loading the dashboard unauthenticated.");
            view.url = root.gatewayBase + "/";
        } else {
            view.url = root.gatewayBase + "/#token=" + token;
        }
    }

    // ============================================
    // SECTION: The web view
    // ============================================
    WebEngineView {
        id: view
        anchors.fill: parent
        // [CHANGE: claude-code | 2026-08-14] The view owns the keyboard from
        // the first frame, so you can type into the message box without
        // clicking it first. Nothing may be layered over this with
        // `focus: true` — see the Keys section at the bottom.
        focus: true
        // The page paints its own dark background; matching it here stops a
        // white flash on the first frame.
        backgroundColor: root.color

        onLoadingChanged: function (info) {
            if (info.status === WebEngineLoadingInfo.LoadSucceededStatus) {
                root.ready = true;
                root.loadError = "";
            } else if (info.status === WebEngineLoadingInfo.LoadFailedStatus) {
                root.ready = false;
                root.loadError = info.errorString || "the page failed to load";
            }
        }

        // The dashboard has no reason to open new windows, and a popup with no
        // handler is a dead end the user cannot close. Load it in place.
        onNewWindowRequested: function (request) {
            view.url = request.requestedUrl;
        }
    }

    // ============================================
    // SECTION: Failure surface
    // PURPOSE: A web view that cannot reach its server renders a blank pane.
    //          A blank pane looks identical to a hung app, so say what broke
    //          and what to run.
    // ============================================
    Rectangle {
        anchors.fill: parent
        color: root.color
        visible: root.loadError !== ""

        Column {
            anchors.centerIn: parent
            width: Math.min(parent.width - 96, 560)
            spacing: 14

            Text {
                text: "The OpenClaw gateway is not answering."
                color: "#f2e9e1"
                font.pixelSize: 20
                font.bold: true
                width: parent.width
                wrapMode: Text.WordWrap
            }
            Text {
                text: root.gatewayBase + "\n" + root.loadError
                color: "#c9a227"
                font.pixelSize: 13
                font.family: "monospace"
                width: parent.width
                wrapMode: Text.WordWrap
            }
            Text {
                text: "Start it with:\n    systemctl --user start openclaw-gateway.service\n\n"
                      + "Then press Ctrl+R here to retry."
                color: "#9c8f84"
                font.pixelSize: 13
                font.family: "monospace"
                width: parent.width
                wrapMode: Text.WordWrap
            }
        }
    }

    // ============================================
    // SECTION: Keys
    // PURPOSE: Esc closes (matching HiveChat.qml), Ctrl+R reloads.
    //
    // DO NOT go back to `Item { focus: true }` layered over the view.
    // [CHANGE: claude-code | 2026-08-14] That was the first attempt and it
    // ATE THE KEYBOARD: a focused Item covering a WebEngineView holds active
    // focus from the moment the window opens, so anything typed before you
    // first click into the page goes to the Item and is dropped. The window
    // looked alive, the gateway logged UI traffic, and not one keystroke
    // reached the message box — no error anywhere. Verified in the gateway
    // journal: zero `[model-fetch] start` lines for the whole period.
    //
    // `Shortcut` is global to the window and takes no focus, which is why
    // HiveChat.qml has always used it.
    //
    // TUNE: Escape is claimed at window level, so it closes the window rather
    //       than reaching the page. That matches the old popup's habit.
    // ============================================
    Shortcut {
        sequence: "Escape"
        onActivated: root.close()
    }

    Shortcut {
        sequence: StandardKey.Refresh
        onActivated: {
            root.loadError = "";
            view.reload();
        }
    }
}
