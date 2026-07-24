/*
    Luminos Live Wallpaper — image / GIF / video / YouTube / web (HTML-JS-WebGL).
    One KDE wallpaper plugin. Pauses on battery and when nothing can see it (see
    ObscurePolicy). Web wallpapers can be mouse-reactive and can read live system
    stats via window.luminos.
    [CHANGE: claude-code | 2026-07-22, occlusion policy 2026-07-24]
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtMultimedia
import QtWebEngine
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.taskmanager as TaskManager

WallpaperItem {
    id: root

    readonly property string mode: root.configuration.WallpaperMode

    // ---- pause guards ----------------------------------------------------
    property bool acPluggedIn: true
    property bool acDataValid: false
    readonly property bool onBattery: acDataValid && !acPluggedIn
    // Cover level of the desktop, debounced. 0 = desktop visible,
    // 1 = hidden by a maximized window, 2 = hidden by a fullscreen window.
    // [CHANGE: claude-code | 2026-07-24]
    property int coverLevel: 0

    // ObscurePolicy: 0 never freeze, 1 freeze only under a fullscreen window,
    // 2 freeze whenever the desktop is hidden at all (default).
    readonly property bool notVisible: {
        var p = root.configuration.ObscurePolicy;
        if (p <= 0) return false;
        if (p === 1) return coverLevel >= 2;
        return coverLevel >= 1;
    }

    readonly property bool shouldPlay: {
        if (root.configuration.PauseOnBattery && onBattery)
            return false;
        if (notVisible)
            return false;
        return true;
    }

    // ---- helpers ---------------------------------------------------------
    function toUrl(s) {
        if (!s || s.length === 0)
            return "";
        if (s.indexOf("://") !== -1)
            return s;
        if (s.charAt(0) === "/")
            return "file://" + s;
        return s;
    }
    function isGif(s) { return ("" + s).toLowerCase().indexOf(".gif") >= 0; }
    function isYouTube(s) {
        s = ("" + s).toLowerCase();
        return s.indexOf("youtube.com") >= 0 || s.indexOf("youtu.be") >= 0;
    }
    readonly property string imageSource: toUrl(root.configuration.Image)
    readonly property string webSource: toUrl(root.configuration.WebUrl)
    // Direct file → file://; YouTube → resolved by yt-dlp into resolvedVideo.
    readonly property string effectiveVideo:
        isYouTube(root.configuration.Video) ? resolvedVideo : toUrl(root.configuration.Video)
    property string resolvedVideo: ""

    // Windows-parity fit modes (see config combo):
    // 0 Stretch (default, fills screen edge-to-edge), 1 Fit (keep proportions),
    // 2 Fill (crop to fill), 3 Center, 4 Tile. [CHANGE: claude-code | 2026-07-23]
    function imageFill(m) {
        switch (m) {
        case 1: return Image.PreserveAspectFit;
        case 2: return Image.PreserveAspectCrop;
        case 3: return Image.Pad;
        case 4: return Image.Tile;
        default: return Image.Stretch;
        }
    }
    // VideoOutput has no Tile/Center; those fall back to Stretch (still fills the screen).
    function videoFill(m) {
        switch (m) {
        case 1: return VideoOutput.PreserveAspectFit;
        case 2: return VideoOutput.PreserveAspectCrop;
        default: return VideoOutput.Stretch;
        }
    }

    Component.onCompleted: {
        root.loading = false;
        maybeResolveYouTube();
    }
    onModeChanged: maybeResolveYouTube()

    Rectangle {
        anchors.fill: parent
        color: root.configuration.BackgroundColor
    }

    // =====================================================================
    //  BATTERY
    // =====================================================================
    P5Support.DataSource {
        id: pmSource
        engine: "powermanagement"
        connectedSources: ["AC Adapter"]
        onDataChanged: {
            var ac = data["AC Adapter"];
            if (ac !== undefined && ac["Plugged in"] !== undefined) {
                root.acPluggedIn = ac["Plugged in"];
                root.acDataValid = true;
            }
        }
    }

    // =====================================================================
    //  OBSCURED — pause when a window on the current desktop covers us
    // =====================================================================
    TaskManager.VirtualDesktopInfo { id: vdInfo }
    TaskManager.ActivityInfo { id: actInfo }

    TaskManager.TasksModel {
        id: tasksModel
        filterByVirtualDesktop: true
        virtualDesktop: vdInfo.currentDesktop
        filterByActivity: true
        activity: actInfo.currentActivity
        filterByScreen: false
    }

    // Fullscreen and maximized are graded separately: a fullscreen window hides
    // the desktop AND the panels, a maximized one only hides the desktop. The old
    // code OR-ed them into one bool, so the two cases could not be told apart.
    // [CHANGE: claude-code | 2026-07-24]
    Instantiator {
        id: windows
        model: tasksModel
        delegate: QtObject {
            required property var model
            readonly property int cover: model.IsMinimized ? 0
                                       : model.IsFullScreen ? 2
                                       : model.IsMaximized ? 1 : 0
            onCoverChanged: coverDebounce.restart()
            Component.onCompleted: coverDebounce.restart()
            Component.onDestruction: coverDebounce.restart()
        }
    }

    // Window state churns during alt-tab / window moves. Settle first, so the
    // video decoder is not stopped and restarted several times a second.
    Timer {
        id: coverDebounce
        interval: 400
        onTriggered: {
            var level = 0;
            for (var i = 0; i < windows.count; i++) {
                var o = windows.objectAt(i);
                if (o && o.cover > level)
                    level = o.cover;
            }
            root.coverLevel = level;
        }
    }

    // =====================================================================
    //  YOUTUBE RESOLVER (needs yt-dlp; inert if not installed)
    // =====================================================================
    P5Support.DataSource {
        id: ytResolver
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source);
            var out = ("" + (data["stdout"] || "")).trim();
            if (out.length > 0)
                root.resolvedVideo = out.split("\n")[0];
        }
        function resolve(url) {
            // Must be a *muxed* progressive mp4 (single self-contained file). YouTube's
            // higher-res streams are video-only DASH whose googlevideo URLs are locked to
            // the extractor's client User-Agent — QtMultimedia's ffmpeg can't send that
            // header, so they return HTTP 403 (black). Muxed tops out at 360p (itag 18)
            // but actually plays. True 1080p needs a download-and-cache path (see HANDOFF).
            // [CHANGE: claude-code | 2026-07-22]
            connectSource("yt-dlp -f 'best[ext=mp4][height<=1080]/best[ext=mp4]/best' -g '" + url + "'");
        }
    }
    function maybeResolveYouTube() {
        if (root.mode === "video" && isYouTube(root.configuration.Video)) {
            root.resolvedVideo = "";
            ytResolver.resolve(root.configuration.Video);
        }
    }

    // =====================================================================
    //  LIVE SYSTEM STATS → window.luminos  (web mode, opt-in)
    // =====================================================================
    P5Support.DataSource {
        id: statsSource
        engine: "executable"
        interval: (root.mode === "web" && root.configuration.InjectSystemStats && root.shouldPlay) ? 2000 : 0
        connectedSources: (root.mode === "web" && root.configuration.InjectSystemStats) ? ["luminos-monitor stats"] : []
        onNewData: (source, data) => root.injectStats("" + (data["stdout"] || ""))
    }
    function injectStats(raw) {
        var w = modeLoader.item;
        if (!w || !w.webView)
            return;
        var obj = {};
        var lines = raw.split("\n");
        for (var i = 0; i < lines.length; i++) {
            var eq = lines[i].indexOf("=");
            if (eq > 0)
                obj[lines[i].substring(0, eq).trim()] = lines[i].substring(eq + 1).trim();
        }
        w.webView.runJavaScript(
            "window.luminos=" + JSON.stringify(obj) +
            ";window.dispatchEvent(new CustomEvent('luminos-stats',{detail:window.luminos}));");
    }

    // =====================================================================
    //  CURSOR FORWARDING → synthetic mousemove into the web page
    //  (only when the page is NOT fully interactive)
    // =====================================================================
    property real cursorX: -1
    property real cursorY: -1
    property real lastCursorX: -2
    property real lastCursorY: -2
    Timer {
        interval: 40; repeat: true
        running: root.mode === "web" && !root.configuration.WebInteractive && root.shouldPlay
        onTriggered: {
            if (root.cursorX === root.lastCursorX && root.cursorY === root.lastCursorY)
                return;
            root.lastCursorX = root.cursorX;
            root.lastCursorY = root.cursorY;
            var w = modeLoader.item;
            if (w && w.webView)
                w.webView.runJavaScript(
                    "(function(){var e=new MouseEvent('mousemove',{clientX:" +
                    Math.round(root.cursorX) + ",clientY:" + Math.round(root.cursorY) +
                    ",bubbles:true});document.dispatchEvent(e);window.dispatchEvent(e);})();");
        }
    }

    // =====================================================================
    //  RENDER MODES
    // =====================================================================
    Loader {
        id: modeLoader
        anchors.fill: parent
        sourceComponent: root.mode === "video" ? videoComp
                       : root.mode === "web"   ? webComp
                       : imageComp
    }

    // ---- IMAGE / GIF ----------------------------------------------------
    Component {
        id: imageComp
        Loader {
            anchors.fill: parent
            sourceComponent: root.isGif(root.imageSource) ? gifComp : stillComp
        }
    }
    Component {
        id: stillComp
        Image {
            anchors.fill: parent
            source: root.imageSource
            fillMode: root.imageFill(root.configuration.FillMode)
            asynchronous: true
            cache: true
            smooth: true
        }
    }
    Component {
        id: gifComp
        AnimatedImage {
            anchors.fill: parent
            source: root.imageSource
            fillMode: root.imageFill(root.configuration.FillMode)
            playing: root.shouldPlay
            cache: true
            smooth: true
        }
    }

    // ---- VIDEO / YOUTUBE ------------------------------------------------
    Component {
        id: videoComp
        Item {
            anchors.fill: parent
            readonly property bool active: root.shouldPlay

            MediaPlayer {
                id: player
                source: root.effectiveVideo
                loops: MediaPlayer.Infinite
                videoOutput: vOut
                audioOutput: AudioOutput {
                    muted: root.configuration.MuteAudio
                    volume: root.configuration.MuteAudio ? 0.0 : 1.0
                }
            }
            VideoOutput {
                id: vOut
                anchors.fill: parent
                fillMode: root.videoFill(root.configuration.FillMode)
            }
            onActiveChanged: active ? player.play() : player.pause()
            Component.onCompleted: if (active) player.play()

            // Suspend/resume recovery. Timers don't tick while suspended, so a
            // wall-clock gap far larger than the interval means the machine just
            // resumed — the MediaPlayer's GPU decode surface is dead and shows a
            // frozen frame. Re-seat the source to rebuild the pipeline, then play.
            // Nothing runs during sleep; this only fires on the first wake tick.
            // [CHANGE: claude-code | 2026-07-24]
            Timer {
                interval: 1000; repeat: true; running: true
                property double last: Date.now()
                onTriggered: {
                    var now = Date.now();
                    if (now - last > 3000 && active) {
                        player.stop();
                        player.source = "";
                        player.source = root.effectiveVideo;
                        player.play();
                    }
                    last = now;
                }
            }
        }
    }

    // ---- WEB (HTML / JS / WebGL) ---------------------------------------
    Component {
        id: webComp
        Item {
            anchors.fill: parent
            property alias webView: web

            WebEngineView {
                id: web
                anchors.fill: parent
                url: root.webSource
                // Full interactivity steals desktop clicks, so it is opt-in.
                enabled: root.configuration.WebInteractive
                backgroundColor: root.configuration.BackgroundColor
                settings.showScrollBars: false
                settings.playbackRequiresUserGesture: false

                function applyState() {
                    web.lifecycleState = root.shouldPlay
                        ? WebEngineView.LifecycleState.Active
                        : WebEngineView.LifecycleState.Frozen;
                }
                Connections {
                    target: root
                    function onShouldPlayChanged() { web.applyState(); }
                }
                onLoadingChanged: function(info) {
                    if (info.status === WebEngineView.LoadSucceededStatus)
                        web.applyState();
                }
            }

            // Cursor-follow without stealing clicks (non-interactive mode).
            MouseArea {
                anchors.fill: parent
                enabled: !root.configuration.WebInteractive
                visible: enabled
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
                propagateComposedEvents: true
                onPositionChanged: function(m) {
                    root.cursorX = m.x;
                    root.cursorY = m.y;
                }
            }
        }
    }
}
