/*
    Luminos Live Wallpaper — run a .js canvas wallpaper, no browser.  SPEC §3.5.
    [CHANGE: claude-code | 2026-09-19]  DECISION 122, CONTRACTS §6.
    SPDX-License-Identifier: GPL-3.0-or-later

    QML's Canvas IS `getContext('2d')`, and QML has its own JS engine, so a
    Lively-style canvas wallpaper needs no browser engine — only the browser
    GLOBALS it expects. Those come from JsShim, and the script is run through
    `new Function`, which hands it exactly the arguments named and NOTHING of this
    file's scope. That is why "not provided" is the default rather than a promise.
*/
import QtQuick
import "../js"

Item {
    id: scene
    anchors.fill: parent

    // ---- scene interface, CONTRACTS §1 (+ `source`, like ShaderToy) ------
    property bool running: true
    property var audio: null
    property var props: ({})
    property var stats: ({})
    property string source: ""
    property real cursorX: -1
    property real cursorY: -1

    readonly property var canvasItem: cv
    readonly property real dpr: Screen.devicePixelRatio
    property string failure: ""

    function fail(why) {
        scene.failure = "" + why;
        console.warn("[LUMINOS-WP] canvas:", scene.failure);
    }

    function run(js) {
        scene.failure = "";
        if (!cv.available) {
            scene.fail("the canvas was not ready — this is a Luminos bug, please report it");
            return;
        }
        var ctx = cv.getContext("2d");
        if (!ctx) {
            scene.fail("this system gave no 2d canvas context");
            return;
        }
        var win = shim.windowObject(), doc = shim.documentObject();
        try {
            // The argument list IS the contract. Anything not named here is
            // simply absent from the script's scope.
            var fn = new Function("canvas", "ctx", "window", "document", "console",
                                  "requestAnimationFrame", "cancelAnimationFrame",
                                  "livelyAudioListener", "fetch", "XMLHttpRequest",
                                  "setTimeout", "setInterval", js);
            fn(cv, ctx, win, doc, scene.jsConsole(),
               shim.raf, shim.cancelRaf,
               function (f) { shim.audioListeners.push(f); },
               shim.refuse("fetch"), shim.refuse("XMLHttpRequest"),
               shim.refuse("setTimeout"), shim.refuse("setInterval"));
        } catch (e) {
            scene.fail("the wallpaper script stopped: " + e);
        }
    }

    // Its console goes to the journal with our prefix, so a wallpaper author's
    // own logging is findable next to ours rather than lost.
    function jsConsole() {
        return {
            log: function (m) { console.log("[LUMINOS-WP] canvas js:", m); },
            warn: function (m) { console.warn("[LUMINOS-WP] canvas js:", m); },
            error: function (m) { console.warn("[LUMINOS-WP] canvas js:", m); },
            info: function (m) { console.log("[LUMINOS-WP] canvas js:", m); },
            debug: function () {}
        };
    }

    Rectangle { anchors.fill: parent; color: "#05060a" }

    // How wide the script's surface actually is, in logical pixels, before it is
    // scaled up to fill the screen.
    //
    // Qt 6's Canvas rasterises 2D commands on the CPU and uploads the result, so
    // its cost is the BACKING STORE, and on this panel (1440x900 logical at
    // devicePixelRatio 2) a full-size canvas means rastering 2880x1800 every
    // frame: measured at 72.8% of a core for the shipped sample. A browser
    // wallpaper is authored for roughly 1080p and does not notice the difference,
    // so the surface is capped and scaled. `resolution` in a properties.json
    // trades sharpness for cost, per wallpaper. [CHANGE: claude-code | 2026-09-19] BUG-178
    readonly property int maxWidth: {
        var v = Number(scene.props ? scene.props.resolution : undefined);
        return (isNaN(v) || v < 160) ? 960 : Math.min(3840, Math.round(v));
    }
    readonly property int surfaceWidth: Math.max(160, Math.min(scene.width, scene.maxWidth))
    readonly property int surfaceHeight: Math.max(120, Math.round(
        scene.surfaceWidth * (scene.height > 0 ? scene.height / scene.width : 0.625)))

    Canvas {
        id: cv
        width: scene.surfaceWidth
        height: scene.surfaceHeight
        transformOrigin: Item.TopLeft
        scale: scene.width > 0 ? scene.width / scene.surfaceWidth : 1
        // Cooperative keeps the raster on the render thread; Threaded would put
        // the script's JS on a thread that cannot see our objects.
        renderStrategy: Canvas.Cooperative
        renderTarget: Canvas.Image
        onWidthChanged: shim.dispatchResize()
        onHeightChanged: shim.dispatchResize()
        // The frame loop is paced by this, not by Qt's animation driver: see
        // JsShim.raf and BUG-178. [CHANGE: claude-code | 2026-09-19]
        onPainted: shim.tick()
    }

    JsShim {
        id: shim
        scene: scene
    }

    JsSource {
        source: scene.source
        onReady: function (js) { scene.run(js); }
        onFailed: function (why) { scene.fail(why); }
    }

    // The host gives cursor position as properties; the script expects an event.
    onCursorXChanged: shim.dispatchMouse(scene.cursorX, scene.cursorY)
    onCursorYChanged: shim.dispatchMouse(scene.cursorX, scene.cursorY)

    // CONTRACTS §2 shape, handed straight through: 128 bands, 0..1.
    property var bands: (scene.audio && scene.audio.bands) ? scene.audio.bands : null
    onBandsChanged: if (scene.bands) shim.dispatchAudio(scene.bands)

    // Unfreezing re-issues whatever the script asked for while it was stopped,
    // so the loop resumes instead of ending. See JsShim.raf.
    onRunningChanged: if (scene.running) shim.resume()

    // SPEC §6: never a black desktop.
    Loader {
        anchors.fill: parent
        active: scene.failure.length > 0
        source: "Aurora.qml"
        onLoaded: item.running = Qt.binding(() => scene.running)
    }
}
