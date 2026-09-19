// Fixture for canvasjs_contract.qml — exercises the whole shim and then STOPS.
// A wallpaper loops forever, which is right for a wallpaper and wrong for a test:
// under QT_QPA_PLATFORM=offscreen there is no vsync to throttle requestAnimationFrame,
// so an endless loop runs flat out and starves the event loop that the test's own
// timers live on. [CHANGE: claude-code | 2026-09-19]
var frames = 0, mouseSeen = 0, audioSeen = 0;

document.addEventListener("mousemove", function () { mouseSeen++; });
window.addEventListener("resize", function () {});
livelyAudioListener(function () { audioSeen++; });

function frame() {
    frames++;
    ctx.fillStyle = "#101820";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ff3355";
    ctx.fillRect(2, 2, 20, 12);
    canvas.requestPaint();
    if (frames < 4)
        requestAnimationFrame(frame);
    else
        console.log("BOUNDED done frames=" + frames
                    + " w=" + window.innerWidth
                    + " dpr=" + (window.devicePixelRatio > 0)
                    + " hasProps=" + (!!window.luminos && !!window.luminos.props));
}
requestAnimationFrame(frame);
