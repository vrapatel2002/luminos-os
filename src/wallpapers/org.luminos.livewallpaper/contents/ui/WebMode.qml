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
import "audio"   // AudioBridge imports only QtQuick; the provider arrives by URL (DECISION 112) [CHANGE: claude-code | 2026-11-08]
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

    // [CHANGE: claude-code | 2026-11-08] BUG-236: the page's audio (Lively's
    // livelyAudioListener) is opt-in, the same AudioReactive switch as QML mode.
    property bool audioReactive: false

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
        // [CHANGE: claude-code | 2026-11-07] M6: a frozen page cannot load the new
        // URL, and the old frame must go; onLoadingChanged re-freezes with a fresh grab.
        web.lifecycleState = WebEngineView.LifecycleState.Active;
        webRoot.frozenShown = false;
        webRoot.frozenGrab = null;
    }

    // [CHANGE: claude-code | 2026-11-07] Active first: a reload while Frozen would
    // leave the new renderer running with QtWebEngine still reporting Frozen.
    Timer {
        id: revive; interval: 10000
        onTriggered: { web.lifecycleState = WebEngineView.LifecycleState.Active; web.reload(); }
    }

    // [CHANGE: claude-code | 2026-11-07] docs/focus round 3. Chromium refuses
    // Frozen for a VISIBLE page ("failed to transition from Active to Frozen
    // state: page is visible"), so this freeze never worked. Now: grab the frame,
    // show it above the view, hide the view, then freeze. No grab within 1 s →
    // freeze anyway, over the background colour.
    property bool frozenShown: false
    property var frozenGrab: null   // keeps the grab's url alive; null releases it
    function freeze(grab) {
        freezeWait.stop();
        if (webRoot.shouldPlay) return;   // a late grab after a flip back to play
        if (grab) webRoot.frozenGrab = grab;
        webRoot.frozenShown = true;       // hides the view (binding below) ...
        web.lifecycleState = WebEngineView.LifecycleState.Frozen; // ... so this is allowed
    }
    Timer { id: freezeWait; interval: 1000; onTriggered: webRoot.freeze(null) }
    Timer { id: settle; interval: 1000; onTriggered: web.applyState() } // [CHANGE: claude-code | 2026-11-07] H3

    anchors.fill: parent

    WebEngineView {
        id: web
        anchors.fill: parent
        visible: !webRoot.failed && !webRoot.frozenShown // [CHANGE: claude-code | 2026-11-07]
        url: webRoot.webSource
        // [CHANGE: claude-code | 2026-11-08] BUG-236: real input never reaches the
        // view (the desktop's icon layer is above it); PageInput forwards it instead.
        enabled: false
        backgroundColor: webRoot.bgColor
        settings.showScrollBars: false
        settings.playbackRequiresUserGesture: false

        // [CHANGE: claude-code | 2026-11-07] docs/focus SPEC Part W: 30 fps cap.
        // The panel runs at 120 Hz and so did every page. Queued callbacks run
        // as one batch on the first real frame ≥ 33 ms after the last batch,
        // with the browser's own (monotonic) timestamp. Page code is unchanged.
        userScripts.collection: [{
            name: "luminos-raf-30fps",
            injectionPoint: WebEngineScript.DocumentCreation,
            worldId: WebEngineScript.MainWorld,
            runsOnSubFrames: true,
            sourceCode: "(function(){var raf=window.requestAnimationFrame.bind(window),"
                + "q={},next=1,pending=0,last=-1e9;"
                + "function pump(t){pending=0;"
                + "if(t-last<33){pending=raf(pump);return;}"
                + "last=t;var run=q;q={};"
                + "for(var id in run){try{run[id](t);}catch(e){window.reportError(e);}}}"
                + "window.requestAnimationFrame=function(cb){var id=next++;q[id]=cb;"
                + "if(!pending)pending=raf(pump);return id;};"
                + "window.cancelAnimationFrame=function(id){delete q[id];};})();"
        }]

        // [CHANGE: claude-code | 2026-11-07] see freeze() above.
        function applyState() {
            if (webRoot.shouldPlay) {
                freezeWait.stop();
                web.lifecycleState = WebEngineView.LifecycleState.Active;
                webRoot.frozenShown = false;
                webRoot.frozenGrab = null;
            } else if (web.loading) {
                // H3 [CHANGE: claude-code | 2026-11-07]: nothing painted yet; settle re-applies
            } else if (webRoot.frozenShown) {
                webRoot.freeze(null);     // already hidden (e.g. a reload): just re-freeze
            } else {
                freezeWait.restart();
                // [CHANGE: claude-code | 2026-11-08] grab at device pixels (2x panel): the default
                // grabs at logical size, which looked low-res.
                var dpr = Screen.devicePixelRatio || 1;
                if (!web.grabToImage(function (g) { webRoot.freeze(g); },
                                     Qt.size(Math.round(web.width * dpr), Math.round(web.height * dpr))))
                    webRoot.freeze(null);
            }
        }
        onLoadingChanged: function(info) {
            var ok = (info.status === WebEngineView.LoadSucceededStatus);
            // [CHANGE: claude-code | 2026-11-07] H3: give the page 1 s to paint its first
            // frame before it is grabbed. A failed load settles too, so it never stays Active.
            if (info.status !== WebEngineView.LoadStartedStatus)
                settle.restart();
            if (ok)
                webRoot.rendererDead = false;
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

    // The last frame while frozen. Under the poster, so a failure still shows it.
    // [CHANGE: claude-code | 2026-11-07]
    Image {
        anchors.fill: parent
        visible: webRoot.frozenShown && !webRoot.failed
        source: webRoot.frozenGrab ? webRoot.frozenGrab.url : ""
        cache: false
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

    onShouldPlayChanged: {
        if (!webRoot.shouldPlay)
            lively.tv("stop()");   // the pause rule: the TV's stream and decoder go first
        web.applyState();
    }

    // ---- BUG-236 [CHANGE: claude-code | 2026-11-08] ---------------------------
    // Everything below exists only while the wallpaper plays (the pause rule) and
    // only for a page that asked for it.
    readonly property bool live: webRoot.shouldPlay && lively.ready && !webRoot.failed

    // Now playing → livelyCurrentTrack, and the TV's video.
    property var trackCache: ({})
    Loader {
        id: nowPlaying
        active: webRoot.live && lively.wantsTrack
        source: "NowPlaying.qml"
        onLoaded: item.cache = webRoot.trackCache
    }
    Connections {
        target: nowPlaying.item
        ignoreUnknownSignals: true
        function onTrack(info) { lively.sendTrack(info); }
        function onPlayback(playing, seconds) { lively.tvState(playing, seconds); }
    }

    // Audio → livelyAudioListener, 24 times a second (the pages draw at 24 fps).
    // On a TV page the FFT also stops while nothing is playing.
    AudioBridge {
        id: audio
        audioEnabled: webRoot.audioReactive && lively.wantsAudio
        running: webRoot.live && (!nowPlaying.item || nowPlaying.item.playing)
    }
    Timer {
        interval: 42; repeat: true
        running: webRoot.live && audio.audio.active
        onTriggered: lively.sendAudio(audio.audio.bands)
    }

    // Cursor → the page. Moves are coalesced to at most 30 a second; presses go at once.
    property point cursor: Qt.point(-1, -1)
    property point sentCursor: Qt.point(-2, -2)
    property bool held: false
    function flushMove() {
        if (webRoot.cursor === webRoot.sentCursor)
            return;
        webRoot.sentCursor = webRoot.cursor;
        lively.pointer("move", webRoot.cursor.x, webRoot.cursor.y, webRoot.held);
    }
    Timer { id: moveTick; interval: 33; onTriggered: webRoot.flushMove() }
    Loader {
        id: pageInput
        active: webRoot.live
        source: "PageInput.qml"
        onLoaded: {
            item.target = webRoot;
            item.clicks = Qt.binding(() => webRoot.interactive);
        }
    }
    Connections {
        target: pageInput.item
        ignoreUnknownSignals: true
        function onMoved(x, y) {
            webRoot.cursor = Qt.point(x, y);
            if (!moveTick.running) moveTick.start();
        }
        function onPressed(x, y) {
            webRoot.cursor = Qt.point(x, y);
            webRoot.flushMove();
            webRoot.held = true;
            lively.pointer("down", x, y, true);
        }
        function onReleased(x, y) {
            webRoot.cursor = Qt.point(x, y);
            webRoot.flushMove();
            webRoot.held = false;
            lively.pointer("up", x, y, false);
        }
    }
}
