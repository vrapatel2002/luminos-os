/*
    Luminos Live Wallpaper — Lively's web JavaScript API, from our side.
    SPEC §3.3, CONTRACTS §5.  SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-20]  BUG-183, DECISION 126.

    A Lively web wallpaper is not a page that draws itself. It is a page that
    waits to be TOLD what to draw: Lively calls `livelyPropertyListener(name,
    value)` once per saved property the moment the page finishes loading, and
    the wallpaper builds its scene out of those calls. Rain's background image,
    every slider in Medusae, the track title in the music ones — all of it
    arrives that way.

    We were never making those calls. So the pages loaded, their HTML and CSS
    and dat.gui ran, their WebGL context came up healthy — and the scene had no
    texture, so it drew black. Three hours were spent on the graphics stack for
    a bug that was never in it (BUG-183). WebGL was fine the whole time.

    The call shape is Lively's, read from its source rather than guessed
    (Lively.Player.WebView2/Extensions/WebView2/CoreWebView2Extensions.cs):
    every argument is JSON, the function is called directly, and a page that
    does not define it is simply not called.
*/
import QtQuick

Item {
    id: api

    visible: false
    width: 0
    height: 0

    // The WebEngineView. Untyped on purpose: this file must not import
    // QtWebEngine, or DECISION 112's whole point — Chromium is mapped only in
    // web mode — would be undone by the file that talks to it.
    property var view: null
    property var schema: ({})
    property var values: ({})
    property bool playing: true
    // Set by WebMode when the page has actually loaded. Calling into a page
    // that is still loading silently does nothing, which is the failure mode
    // hardest to tell from "this wallpaper is broken".
    property bool ready: false

    // What was last delivered, so a slider move sends one property and not all
    // sixteen — re-sending `mediaSelect` re-decodes a 4 MB JPEG.
    property var sent: ({})

    function call(fn, argsJson) {
        if (!api.view || !api.ready)
            return;
        api.view.runJavaScript(
            "if(typeof " + fn + "==='function'){try{" + fn + "(" + argsJson +
            ");}catch(e){console.error('" + fn + ": '+e);}}");
    }

    // A folderDropdown stores an index here and Lively sends `folder/file`, so
    // the index is turned back into the path the page expects. Everything else
    // travels as it is stored.
    function livelyValue(key) {
        var def = api.schema[key] || {};
        var raw = api.values[key];
        if (def.livelyFolder === undefined)
            return (raw === undefined) ? null : raw;
        var items = def.items || [];
        var i = Math.round(Number(raw));
        if (!(i >= 0 && i < items.length))
            return null;
        return def.livelyFolder + "/" + items[i];
    }

    // Lively's own restore path skips these two: they are user-interaction
    // controls with no state to restore (LivelyPropertyUtil.cs).
    function sendable(key) {
        var t = (api.schema[key] || {}).type;
        return t !== "button" && t !== "label";
    }

    function push(force) {
        if (!api.ready)
            return;
        var now = {};
        for (var key in api.schema) {
            if (!api.sendable(key))
                continue;
            var v = api.livelyValue(key);
            now[key] = v;
            if (force || api.sent[key] !== v)
                api.call("livelyPropertyListener",
                         JSON.stringify(key) + "," + JSON.stringify(v));
        }
        api.sent = now;
    }

    // A button has no stored value — it is an event, and Lively sends `true`.
    function press(key) {
        api.call("livelyPropertyListener", JSON.stringify(key) + ",true");
    }

    // Lively serialises this one TWICE: the page receives a JSON string and
    // parses it itself. Matching that exactly matters more than tidiness.
    function sendPlayback() {
        api.call("livelyWallpaperPlaybackChanged",
                 JSON.stringify(JSON.stringify({ IsPaused: !api.playing })));
    }

    onReadyChanged: {
        if (!api.ready)
            api.sent = ({});
        else {
            api.push(true);
            api.sendPlayback();
        }
    }
    onValuesChanged: api.push(false)
    onPlayingChanged: api.sendPlayback()
}
