/*
    Luminos Live Wallpaper — the web renderer, in a file of its own.
    SPDX-License-Identifier: GPL-3.0-or-later

    [CHANGE: claude-code | 2026-09-16] DECISION 112.

    THIS FILE EXISTS FOR ONE REASON: the `import QtWebEngine` below.

    It used to sit at the top of main.qml, which meant plasmashell mapped
    libQt6WebEngineCore.so - the whole of Chromium, ~130-150 MB - on every login,
    in EVERY mode. The mode switching was already correct: `modeLoader` uses
    sourceComponent, so a WebEngineView is never CREATED while a video is
    playing, and no Chromium child processes spawn. But a QML `import` is not
    conditional. It runs when the file containing it is loaded, and main.qml is
    always loaded.

    A QML file that is never loaded never runs its imports. So the web renderer
    lives here and main.qml reaches it through a Loader by FILENAME. In image,
    GIF, video and YouTube mode, Chromium is now never mapped at all.

    Nothing about the web wallpaper's behaviour changed - the body below is the
    old `webComp` verbatim. The only edit is that it no longer reaches out to
    `root`: it cannot, from a separate file, so the four things it needs arrive
    as properties bound by the Loader in main.qml.
*/
import QtQuick
import QtWebEngine
// PropertyStore imports nothing but QtQuick; the file read behind it is a
// subprocess, not a browser. Safe to pull in here. [CHANGE: claude-code | 2026-09-20]
import "props"
import org.kde.plasma.plasma5support as P5Support

Item {
    id: webRoot

    // Bound by main.qml's Loader.onLoaded. Plain properties rather than
    // `required`, because a Loader can only pass required properties through
    // setSource(), which cannot carry bindings - and these must stay live.
    property url webSource
    property bool interactive: false
    property color bgColor: "black"
    property bool shouldPlay: true
    // The raw SceneProperties config string, passed through untouched — the
    // same key QML mode uses, keyed by the page's URL. BUG-183.
    property string sceneProperties: "{}"

    // Cursor position, written here and read by main.qml's injector.
    property real cursorX: 0
    property real cursorY: 0

    property alias webView: web

    // [CHANGE: claude-code | 2026-11-06] BUG-199. A page that cannot draw shows a
    // still instead of nothing: the greeter restarted inside a suspend gets no GPU,
    // three.js gets no WebGL, and the lock screen was black until the next restart.
    // Two flags: Chromium keeps the GPU off for the life of the process, so no
    // WebGL lasts until the URL changes, while a dead renderer ends at the reload's
    // LoadSucceeded - which arrives AFTER that reloaded page's WebGL error.
    property bool noWebGL: false
    property bool rendererDead: false
    readonly property bool failed: noWebGL || rendererDead
    property string thumbnailUrl: ""
    // Only a local page has files beside it.
    readonly property string pageDir: {
        var s = "" + webRoot.webSource;
        return s.indexOf("file://") === 0 ? s.substring(0, s.lastIndexOf("/") + 1) : "";
    }

    function logFailure(why) {
        if (!webRoot.failed)
            console.warn("[LUMINOS-WP] web wallpaper cannot draw, showing its poster:", why);
    }

    onWebSourceChanged: {
        revive.stop();
        webRoot.noWebGL = false;
        webRoot.rendererDead = false;
        webRoot.thumbnailUrl = "";
    }

    Timer { id: revive; interval: 10000; onTriggered: web.reload() }

    anchors.fill: parent

    WebEngineView {
        id: web
        anchors.fill: parent
        visible: !webRoot.failed
        url: webRoot.webSource
        // Full interactivity steals desktop clicks, so it is opt-in.
        enabled: webRoot.interactive
        backgroundColor: webRoot.bgColor
        settings.showScrollBars: false
        settings.playbackRequiresUserGesture: false

        function applyState() {
            web.lifecycleState = webRoot.shouldPlay
                ? WebEngineView.LifecycleState.Active
                : WebEngineView.LifecycleState.Frozen;
        }
        onLoadingChanged: function(info) {
            var ok = (info.status === WebEngineView.LoadSucceededStatus);
            if (ok) {
                web.applyState();
                webRoot.rendererDead = false;
            }
            // A Lively page draws nothing until its properties arrive, so this
            // must flip on load and OFF on a reload — see LivelyApi.qml.
            lively.ready = ok;
        }
        onJavaScriptConsoleMessage: function(level, message) {
            if (message.indexOf("WebGL context could not be created") !== -1
                    || message.indexOf("Error creating WebGL context") !== -1) {
                webRoot.logFailure(message);
                webRoot.noWebGL = true;
            }
            // Having a handler turns off WebEngine's own "js:" journal lines,
            // which is where BUG-183 and BUG-199 were read from. Keep them, at
            // warn so that no logging rule can filter out the quieter levels.
            console.warn("js:", message);
        }
        onRenderProcessTerminated: function(status, exitCode) {
            if (status === WebEngineView.NormalTerminationStatus)
                return;
            webRoot.logFailure("renderer exited, status " + status + " code " + exitCode);
            webRoot.rendererDead = true;
            revive.restart();
        }
    }

    // Above the hidden view. No poster and no thumbnail leaves main.qml's
    // BackgroundColor showing through, as before.
    Image {
        anchors.fill: parent
        visible: webRoot.failed
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        source: !webRoot.failed || !webRoot.pageDir ? ""
            : webRoot.thumbnailUrl || webRoot.pageDir + "poster.png"
        onStatusChanged: {
            if (status === Image.Error && !webRoot.thumbnailUrl)
                thumbnail.read();
        }
    }

    // QML cannot read a local file itself (BUG-170), so a subprocess does, and
    // only on the failure path. The page may sit in a subfolder; LivelyInfo.json
    // and its Thumbnail live in the wallpaper's root, the nearest folder up that
    // has one. Lively writes these files, BOMs and all.
    P5Support.DataSource {
        id: thumbnail
        engine: "executable"
        function read() {
            var page = decodeURIComponent(("" + webRoot.webSource).substring(7));
            connectSource("python3 -c 'import json,sys,pathlib;"
                + "f=next(d/\"LivelyInfo.json\" for d in pathlib.Path(sys.argv[1]).parents"
                + " if (d/\"LivelyInfo.json\").exists());"
                + "t=json.loads(f.read_text(encoding=\"utf-8-sig\")).get(\"Thumbnail\");"
                + "print((f.parent/t).as_uri() if t else \"\")' '"
                + page.replace(/'/g, "'\\''") + "' 2>/dev/null");
        }
        onNewData: function(source, data) {
            disconnectSource(source);
            webRoot.thumbnailUrl = ("" + (data["stdout"] || "")).trim();
        }
    }

    // CONTRACTS §4. Defaults from the page's own LivelyProperties.json (or a
    // properties.json beside it), saved values on top.
    PropertyStore {
        id: propStore
        sceneUrl: webRoot.webSource
        sceneId: "" + webRoot.webSource
        savedJson: webRoot.sceneProperties
    }

    LivelyApi {
        id: lively
        view: web
        schema: propStore.schema
        values: propStore.props
        playing: webRoot.shouldPlay
    }

    onShouldPlayChanged: web.applyState()

    // Cursor-follow without stealing clicks (non-interactive mode).
    MouseArea {
        anchors.fill: parent
        enabled: !webRoot.interactive
        visible: enabled
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        onPositionChanged: function(m) {
            webRoot.cursorX = m.x;
            webRoot.cursorY = m.y;
        }
    }
}
