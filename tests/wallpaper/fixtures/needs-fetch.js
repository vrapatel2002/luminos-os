// Fixture for canvasjs_contract.qml — a script the shim deliberately cannot run.
// CONTRACTS §6 promises this fails AT LOAD, naming the feature.
var data = fetch("https://example.invalid/wallpaper.json");
requestAnimationFrame(function () {});
