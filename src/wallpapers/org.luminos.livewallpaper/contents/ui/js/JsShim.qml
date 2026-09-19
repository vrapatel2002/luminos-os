/*
    Luminos Live Wallpaper — the browser-shaped surface a .js wallpaper gets.
    SPEC §3.5, CONTRACTS §6.  [CHANGE: claude-code | 2026-09-19] DECISION 122.
    SPDX-License-Identifier: GPL-3.0-or-later

    CONTRACTS §6 lists what is provided and says everything else must fail with a
    NAMED error. Two layers do that, because one is not enough:

      - `luminos-wallpaper-js` refuses the script at load and says which feature
        it wanted. That is the layer that keeps the promise.
      - Every global here that we deliberately do not implement is still PRESENT,
        as a function that throws its own name. A pattern the reader's scan misses
        (computed access, an obfuscated bundle) then dies saying `fetch is not
        available in a Luminos canvas wallpaper` rather than
        `undefined is not a function`.

    The script sees ONLY what is passed to it as arguments — `new Function` gives
    it no access to this file's scope — so "not provided" is the default and each
    entry below is a deliberate grant.
*/
import QtQuick

QtObject {
    id: shim

    // The scene that owns this: supplies the canvas, cursor, audio and props.
    required property var scene

    property var mouseListeners: []
    property var resizeListeners: []
    property var audioListeners: []

    function refuse(name) {
        return function () {
            throw new Error(name + " is not available in a Luminos canvas wallpaper "
                            + "(CONTRACTS §6 lists what is)");
        };
    }

    // ---- requestAnimationFrame -----------------------------------------
    // Driven by the canvas ACTUALLY PAINTING, not by Qt's animation driver.
    //
    // The first version used Canvas.requestAnimationFrame directly and it was a
    // disaster: the script produced paint commands faster than a 2880x1800
    // surface could be rastered, the backlog grew without bound, and plasmashell
    // went to 128.7% of a core and **2.5 GB of PSS, still climbing** — an OOM on
    // a 16 GB machine, and far worse than the Chromium this is supposed to
    // replace. Nothing capped the producer against the consumer.
    //
    // Now a callback waits for `onPainted`. The renderer sets the pace, the queue
    // holds at most one frame of callbacks, and a slow machine simply animates
    // more slowly instead of drowning. [CHANGE: claude-code | 2026-09-19] BUG-178
    property var queue: []
    property int nextId: 1

    function raf(fn) {
        if (typeof fn !== "function")
            return 0;
        var id = shim.nextId++;
        shim.queue.push({ id: id, fn: fn });
        // Held while frozen — dropping it would end the animation for good, and
        // it would never restart when the desktop came back.
        if (shim.scene.running)
            shim.scene.canvasItem.requestPaint();
        return id;
    }

    function cancelRaf(id) {
        for (var i = 0; i < shim.queue.length; i++) {
            if (shim.queue[i].id === id) {
                shim.queue.splice(i, 1);
                return;
            }
        }
    }

    // Frames per second, capped. The cost of a canvas wallpaper is dominated by
    // the PER-FRAME cycle, not by what is drawn: 160 dots -> 30 and no lines saved
    // only 76% -> 56.6% of a core, and capping the surface 2880 -> 1920 px saved
    // nothing. The lever is how OFTEN. `fps` in a properties.json raises it.
    // BUG-178.
    readonly property int minFrameMs: {
        var v = Number(shim.scene.props ? shim.scene.props.fps : undefined);
        if (isNaN(v) || v <= 0)
            return 33;
        return Math.round(1000 / Math.max(1, Math.min(120, v)));
    }
    property double lastTick: 0
    // Frames delivered to the script: how a test asks "is it animating?" without
    // eyes. BUG-180 shipped as one frame and a still picture.
    property int frames: 0

    // Called from Canvas.onPainted, and it NEVER runs a frame synchronously.
    // It used to, and that killed the loop after exactly ONE frame (BUG-180): a
    // `requestPaint()` issued from inside onPainted is swallowed — Qt marks the
    // canvas clean when the handler returns — so no second paint ever arrived and
    // onPainted, the only driver, never fired again. Going through the timer puts
    // the script's requestPaint outside the paint handler, where it lands.
    // BUG-178's back-pressure is unchanged: a frame still waits for a real paint.
    // [CHANGE: claude-code | 2026-09-19]
    function tick() {
        if (!shim.scene.running || shim.queue.length === 0)
            return;
        pace.interval = Math.max(1, shim.minFrameMs - (Date.now() - shim.lastTick));
        pace.restart();
    }

    function runDue() {
        shim.lastTick = Date.now();
        shim.frames++;
        var due = shim.queue;
        shim.queue = [];
        for (var i = 0; i < due.length; i++) {
            try {
                due[i].fn(shim.lastTick);
            } catch (e) {
                console.warn("[LUMINOS-WP] canvas js: frame threw:", e);
            }
        }
    }

    property Timer pacer: Timer {
        id: pace
        onTriggered: {
            if (shim.scene.running && shim.queue.length > 0)
                shim.runDue();
        }
    }

    // Unfreezing kicks the TIMER, not the canvas: waiting for onPainted made
    // recovery depend on the mechanism that had just stopped, so closing every
    // window left the wallpaper a still image for good. BUG-180.
    function resume() {
        if (shim.queue.length === 0)
            return;
        pace.interval = 1;
        pace.restart();
    }

    // ---- dispatch -------------------------------------------------------
    function addListener(list, type, fn) {
        if (typeof fn !== "function")
            return;
        if (type === "mousemove")
            shim.mouseListeners.push(fn);
        else if (type === "resize")
            shim.resizeListeners.push(fn);
        // Any other type is accepted and never fires: a wallpaper cannot be
        // clicked, and throwing would kill scripts registering an unused handler.
    }

    function fire(list, arg) {
        for (var i = 0; i < list.length; i++) {
            try {
                list[i](arg);
            } catch (e) {
                console.warn("[LUMINOS-WP] canvas: a listener threw:", e);
            }
        }
    }

    function dispatchMouse(x, y) {
        shim.fire(shim.mouseListeners, { clientX: x, clientY: y, pageX: x, pageY: y, x: x, y: y });
    }
    function dispatchResize() { shim.fire(shim.resizeListeners, {}); }
    function dispatchAudio(bands) { shim.fire(shim.audioListeners, bands); }

    // ---- the objects the script is handed --------------------------------
    function windowObject() {
        var c = shim.scene.canvasItem;
        return {
            innerWidth: c.width,
            innerHeight: c.height,
            devicePixelRatio: shim.scene.dpr,
            luminos: { stats: shim.scene.stats, props: shim.scene.props },
            audio: shim.scene.audio,
            requestAnimationFrame: shim.raf,
            cancelAnimationFrame: shim.cancelRaf,
            addEventListener: function (t, f) { shim.addListener(null, t, f); },
            removeEventListener: function () {},
            fetch: shim.refuse("fetch"),
            XMLHttpRequest: shim.refuse("XMLHttpRequest"),
            setTimeout: shim.refuse("setTimeout"),
            setInterval: shim.refuse("setInterval"),
            WebSocket: shim.refuse("WebSocket"),
            localStorage: undefined
        };
    }

    function documentObject() {
        return {
            addEventListener: function (t, f) { shim.addListener(null, t, f); },
            removeEventListener: function () {},
            createElement: shim.refuse("document.createElement"),
            querySelector: shim.refuse("document.querySelector"),
            getElementById: shim.refuse("document.getElementById"),
            body: undefined
        };
    }
}
