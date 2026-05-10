// Luminos Smart Maximize Toggle
// Press maximize = fullscreen
// Press again = 80% centered

var previousGeometry = {};

workspace.windowMaximizedChanged.connect(
  function(window, h, v) {
    if (h && v) {
      // Just maximized — store was-geometry
      previousGeometry[window.windowId] = {
        stored: true
      };
    }
  }
);

// When unmaximizing set to 80% centered
workspace.windowAdded.connect(function(window) {
  window.clientMaximizedStateChanged.connect(
    function(win, h, v) {
      if (!h && !v) {
        var screen = workspace.clientArea(
          KWin.MaximizeArea,
          win.screen,
          workspace.currentDesktop
        );
        var w = screen.width * 0.80;
        var h = screen.height * 0.85;
        var x = screen.x + (screen.width - w) / 2;
        var y = screen.y + (screen.height - h) / 2;
        win.frameGeometry = {
          x: Math.round(x),
          y: Math.round(y),
          width: Math.round(w),
          height: Math.round(h)
        };
      }
    }
  );
});
