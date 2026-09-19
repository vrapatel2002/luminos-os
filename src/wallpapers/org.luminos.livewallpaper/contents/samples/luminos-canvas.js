// Luminos sample — an ordinary canvas wallpaper, run by QML's own JS engine.
// [CHANGE: claude-code | 2026-09-19] SPEC §3.5, CONTRACTS §6
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Nothing here is Luminos-specific. It uses canvas, ctx, requestAnimationFrame,
// a mousemove listener and livelyAudioListener — the same surface a Lively
// JavaScript wallpaper expects — so a Lively .js should drop in beside it.
// Every key in luminos-canvas.properties.json arrives as window.luminos.props.

var W = canvas.width, H = canvas.height;
var mouse = { x: W / 2, y: H / 2 };
var level = 0, beatGlow = 0;

function prop(key, fallback) {
    var p = window.luminos && window.luminos.props;
    var v = p ? p[key] : undefined;
    return (v === undefined || v === null) ? fallback : v;
}

var dots = [];
function seed() {
    dots = [];
    var n = Math.max(20, Math.min(600, prop("count", 160)));
    for (var i = 0; i < n; i++) {
        dots.push({
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - 0.5) * 0.6,
            vy: (Math.random() - 0.5) * 0.6,
            r: 1 + Math.random() * 2.5
        });
    }
}
seed();

window.addEventListener("resize", function () {
    W = canvas.width; H = canvas.height; seed();
});
document.addEventListener("mousemove", function (e) {
    mouse.x = e.clientX; mouse.y = e.clientY;
});

// CONTRACTS §2: 128 bands, 0..1 — Lively's exact shape.
livelyAudioListener(function (bands) {
    var s = 0;
    for (var i = 0; i < 24; i++) s += bands[i];
    level = s / 24;
    if (level > 0.55) beatGlow = 1;
});

function frame() {
    ctx.fillStyle = prop("background", "#070912");
    ctx.fillRect(0, 0, W, H);

    var reach = prop("reach", 170) * (1 + level * 1.5);
    var tint = prop("tint", "#7dd3fc");
    var speed = prop("speed", 1);

    ctx.strokeStyle = tint;
    ctx.globalAlpha = 0.35 + beatGlow * 0.4;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (var i = 0; i < dots.length; i++) {
        var d = dots[i];
        d.x += d.vx * speed; d.y += d.vy * speed;
        if (d.x < 0) d.x += W; else if (d.x > W) d.x -= W;
        if (d.y < 0) d.y += H; else if (d.y > H) d.y -= H;
        var dx = d.x - mouse.x, dy = d.y - mouse.y;
        if (dx * dx + dy * dy < reach * reach) {
            ctx.moveTo(mouse.x, mouse.y);
            ctx.lineTo(d.x, d.y);
        }
    }
    ctx.stroke();

    ctx.globalAlpha = 1;
    ctx.fillStyle = tint;
    for (var k = 0; k < dots.length; k++) {
        var p = dots[k];
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * (1 + level * 2), 0, Math.PI * 2);
        ctx.fill();
    }

    beatGlow *= 0.90;
    canvas.requestPaint();
    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
