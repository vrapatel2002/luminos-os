/*
    Native port of contents/samples/luminos-aurora.html.
    QML's Canvas exposes the same 2D context API as the browser's, so this is
    the sample's own drawing code, unchanged in substance.
    [CHANGE: claude-code | 2026-09-16] DECISION 113
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Canvas {
    id: cv
    anchors.fill: parent
    property bool running: true

    // Cooperative keeps the painting off the GUI thread; the desktop must never
    // be the reason the shell stutters.
    renderStrategy: Canvas.Cooperative
    renderTarget: Canvas.FramebufferObject

    property var blobs: []

    Component.onCompleted: {
        var cols = ["#7c3aed", "#2563eb", "#0ea5e9", "#e95420", "#10b981"];
        var b = [];
        for (var i = 0; i < cols.length; i++)
            b.push({
                col: cols[i],
                x: Math.random(), y: Math.random(),
                r: 0.35 + Math.random() * 0.25,
                sx: (Math.random() - 0.5) * 0.0006,
                sy: (Math.random() - 0.5) * 0.0006
            });
        cv.blobs = b;
    }

    // 30 fps on purpose — the sample capped itself for the same reason, and the
    // iGPU is shared with KWin and everything else.
    Timer {
        interval: 33; repeat: true
        running: cv.running && cv.available
        onTriggered: cv.requestPaint()
    }

    onPaint: {
        var ctx = cv.getContext("2d");
        if (!ctx)
            return;
        var W = cv.width, H = cv.height;
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = "#05060a";
        ctx.fillRect(0, 0, W, H);
        ctx.globalCompositeOperation = "lighter";
        for (var i = 0; i < cv.blobs.length; i++) {
            var b = cv.blobs[i];
            b.x += b.sx; b.y += b.sy;
            if (b.x < 0 || b.x > 1) b.sx *= -1;
            if (b.y < 0 || b.y > 1) b.sy *= -1;
            var x = b.x * W, y = b.y * H, rad = b.r * Math.min(W, H);
            var g = ctx.createRadialGradient(x, y, 0, x, y, rad);
            g.addColorStop(0, b.col);
            g.addColorStop(1, "transparent");
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, W, H);
        }
    }
}
