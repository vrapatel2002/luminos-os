/*
    Native port of contents/samples/luminos-particles.html.
    [CHANGE: claude-code | 2026-09-16] DECISION 113
    SPDX-License-Identifier: GPL-3.0-or-later

    Deliberately a faithful Canvas port rather than QtQuick.Particles. The
    sample's behaviour is a spring toward a drifting home plus a cursor repel;
    QtQuick.Particles is GPU-driven but models emitters and affectors, not
    per-particle springs, so it would have been a different-looking wallpaper
    wearing the same name. A GPU rewrite is worth doing as its own change, with
    its own before/after, not smuggled in here.
*/
import QtQuick

Canvas {
    id: cv
    anchors.fill: parent
    property bool running: true
    property real cursorX: -1e9
    property real cursorY: -1e9

    renderStrategy: Canvas.Cooperative
    renderTarget: Canvas.FramebufferObject

    property var parts: []
    property real clock: 0

    function seed() {
        var W = cv.width, H = cv.height;
        if (W <= 0 || H <= 0)
            return;
        var n = Math.min(140, Math.floor(W * H / 24000));
        var p = [];
        for (var i = 0; i < n; i++)
            p.push({
                x: Math.random() * W, y: Math.random() * H,
                bx: Math.random() * W, by: Math.random() * H,
                hx: 0, hy: 0,
                ph: Math.random() * 6.283,
                fr: 0.4 + Math.random() * 0.6,
                amp: 20 + Math.random() * 40,
                vx: 0, vy: 0
            });
        cv.parts = p;
    }
    Component.onCompleted: seed()
    onWidthChanged: seed()
    onHeightChanged: seed()

    Timer {
        interval: 33; repeat: true
        running: cv.running && cv.available
        onTriggered: { cv.clock += 33; cv.requestPaint(); }
    }

    onPaint: {
        var ctx = cv.getContext("2d");
        if (!ctx || cv.parts.length === 0)
            return;
        var W = cv.width, H = cv.height;
        // Translucent wash instead of a clear: that is what leaves the trails.
        ctx.fillStyle = "rgba(5,6,10,0.35)";
        ctx.fillRect(0, 0, W, H);

        var ts = cv.clock * 0.00035;
        var mx = cv.cursorX, my = cv.cursorY, R = 140;
        for (var i = 0; i < cv.parts.length; i++) {
            var p = cv.parts[i];
            p.hx = p.bx + Math.cos(ts * p.fr + p.ph) * p.amp;
            p.hy = p.by + Math.sin(ts * p.fr * 1.3 + p.ph) * p.amp;
            p.vx += (p.hx - p.x) * 0.006;
            p.vy += (p.hy - p.y) * 0.006;
            var dx = p.x - mx, dy = p.y - my, d2 = dx * dx + dy * dy;
            if (d2 < R * R) {
                var d = Math.sqrt(d2) || 1, f = (R - d) / R * 4;
                p.vx += dx / d * f; p.vy += dy / d * f;
            }
            p.vx *= 0.90; p.vy *= 0.90;
            p.x += p.vx; p.y += p.vy;
            var sp = Math.min(1, (Math.abs(p.vx) + Math.abs(p.vy)) / 6);
            ctx.fillStyle = Qt.hsla((190 + sp * 120) / 360, 0.90, (55 + sp * 25) / 100, 1);
            ctx.beginPath();
            ctx.arc(p.x, p.y, 1.6 + sp * 2, 0, 6.283);
            ctx.fill();
        }
    }
}
