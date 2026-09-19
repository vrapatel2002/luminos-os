// Fixture for canvasjs_contract.qml — a wallpaper that loops like a real one, so
// the freeze/resume path (BUG-180) is exercised. Bounded only by the harness
// freezing it; see fixtures/bounded.js for why most fixtures stop themselves.
var n = 0;
function frame() {
    n++;
    ctx.fillStyle = (n % 2) ? "#101820" : "#182028";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    canvas.requestPaint();
    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
