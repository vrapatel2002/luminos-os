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

    // ---- BUG-236 [CHANGE: claude-code | 2026-11-08] -----------------------
    // What the page can take, asked once per load. Nothing below runs for a page
    // that does not define the matching function.
    property bool wantsTrack: false
    property bool wantsAudio: false
    property bool silent: false

    function probe() {
        api.view.runJavaScript(
            "JSON.stringify({t:typeof livelyCurrentTrack==='function',a:typeof livelyAudioListener==='function',"
            + "p:typeof setMouseParallax==='function'})", function (r) {
                var f = JSON.parse(r || "{}");
                api.wantsTrack = !!f.t;
                api.wantsAudio = !!f.a;
                // Living Room ships mouse parallax but never switches it on itself.
                if (f.p)
                    api.view.runJavaScript("try{setMouseParallax();}catch(e){}");
            });
    }

    // Lively's double-JSON shape. The Video field is ours: it never reaches the page.
    function sendTrack(info) {
        var pass = info ? { Title: info.Title, Artist: info.Artist || "", Thumbnail: info.Thumbnail } : null;
        api.call("livelyCurrentTrack", JSON.stringify(JSON.stringify(pass)));
        api.tv(info && info.Video ? "start(" + JSON.stringify(info.Video) + ")" : "stop()");
    }

    // 128 bands. A run of silence is sent once, then not at all.
    function sendAudio(bands) {
        var loud = false, out = new Array(bands.length);
        for (var i = 0; i < bands.length; i++) {
            out[i] = Math.round(bands[i] * 100) / 100;
            if (out[i] > 0) loud = true;
        }
        if (!loud && api.silent)
            return;
        api.silent = !loud;
        api.call("livelyAudioListener", "[" + out.join(",") + "]");
    }

    // A mouse as the page's own code expects it: to the element under the point,
    // bubbling, pointer event then mouse event — what a browser fires for a real one.
    function pointer(kind, x, y, down) {
        if (!api.view || !api.ready)
            return;
        api.view.runJavaScript("(function(t,x,y,b){var el=document.elementFromPoint(x,y)||document.body,"
            + "o={clientX:x,clientY:y,screenX:x,screenY:y,button:0,buttons:b,bubbles:true,cancelable:true,view:window};"
            + "el.dispatchEvent(new PointerEvent('pointer'+t,Object.assign({pointerId:1,isPrimary:true,pointerType:'mouse'},o)));"
            + "el.dispatchEvent(new MouseEvent('mouse'+t,o));})(" + JSON.stringify(kind) + ","
            + Math.round(x) + "," + Math.round(y) + "," + (down ? 1 : 0) + ")");
    }

    // The TV's moving picture: a muted local <video> (the helper's on-disk copy — a
    // file:// video does not taint the page's WebGL canvas) drawn into its screen canvas
    // (canvasArtist — the rocksdanister media pages re-upload it every frame). Only the
    // frames the video produces are drawn; a paused video costs nothing; stop() drops
    // the stream and the decoder.
    readonly property string tvShim: "(function(){if(window.__ltv)return;"
        + "var v=document.createElement('video'),on=false,want={p:false,s:0};v.muted=true;v.playsInline=true;"
        + "function ok(){return typeof canvasArtist!=='undefined'&&typeof ctxArtist!=='undefined';}"
        + "function draw(){if(!on)return;if(v.readyState>=2&&ok()){var cw=canvasArtist.width,ch=canvasArtist.height,"
        + "k=Math.max(cw/v.videoWidth,ch/v.videoHeight),w=v.videoWidth*k,h=v.videoHeight*k;"
        + "ctxArtist.drawImage(v,(cw-w)/2,(ch-h)/2,w,h);}v.requestVideoFrameCallback(draw);}"
        + "function apply(){if(!on||v.readyState<1)return;if(Math.abs(v.currentTime-want.s)>1.5)v.currentTime=want.s;"
        + "if(want.p)v.play().catch(function(){});else v.pause();}"
        + "v.addEventListener('loadedmetadata',apply);"
        + "window.__ltv={start:function(u){if(!ok())return;on=true;if(v.src!==u)v.src=u;v.requestVideoFrameCallback(draw);apply();},"
        + "state:function(p,s){want={p:p,s:s};apply();},"
        + "stop:function(){if(!on)return;on=false;v.pause();v.removeAttribute('src');v.load();}};})();"

    function tv(cmd) {
        if (api.view && api.ready)
            api.view.runJavaScript(api.tvShim + "window.__ltv." + cmd + ";");
    }
    function tvState(playing, seconds) {
        api.tv("state(" + (playing ? "true" : "false") + "," + seconds.toFixed(2) + ")");
    }

    onReadyChanged: {
        if (!api.ready) {
            api.sent = ({});
            api.wantsTrack = false;
            api.wantsAudio = false;
            api.silent = false;
        } else {
            api.push(true);
            api.sendPlayback();
            api.probe();
        }
    }
    onValuesChanged: api.push(false)
    onPlayingChanged: api.sendPlayback()
}
