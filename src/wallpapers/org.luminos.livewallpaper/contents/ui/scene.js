// Luminos Live Wallpaper — where a scene's file actually is.
// [CHANGE: claude-code | 2026-09-19] DECISION 118.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Shared by QmlMode.qml (which loads the scene) and config.qml (which must find
// the same scene's properties.json to build its settings panel). Two copies of
// this map is how the settings panel ends up offering a scene the wallpaper
// cannot load, or editing the properties of a different one.
//
// Returns a path that may be relative — the CALLER resolves it, because
// Qt.resolvedUrl() resolves against the file that calls it and both callers
// happen to live in contents/ui/.
.pragma library

var BUILTINS = {
    "shader":    "scenes/Shader.qml",
    "aurora":    "scenes/Aurora.qml",
    "particles": "scenes/Particles.qml",
    "sysmon":    "scenes/SysMon.qml",
    "spectrum":  "scenes/Spectrum.qml"
};

function pathFor(scene) {
    var s = ("" + scene).trim();
    if (s.length === 0)
        return BUILTINS["shader"];
    if (BUILTINS[s] !== undefined)
        return BUILTINS[s];
    if (s.indexOf("://") !== -1)
        return s;
    if (s.charAt(0) === "/")
        return "file://" + s;
    return s;
}

function isAbsolute(path) {
    return ("" + path).indexOf("://") !== -1;
}
