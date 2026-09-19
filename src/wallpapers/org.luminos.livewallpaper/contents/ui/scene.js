// Luminos Live Wallpaper — where a scene's file actually is.
// [CHANGE: claude-code | 2026-09-19] DECISION 118, shader files 119.
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
    "spectrum":  "scenes/Spectrum.qml",
    "shadertoy": "scenes/ShaderToy.qml"
};

// A .frag / .glsl typed into the scene box is not a QML file — it is a shader,
// and the scene that runs it is ShaderToy.qml. That keeps one input box for
// "point it at your own file" instead of growing a second one per file type.
// [CHANGE: claude-code | 2026-09-19] DECISION 119
function isShaderFile(scene) {
    return /\.(frag|glsl|fsh)$/i.test(("" + scene).trim());
}

// The file whose SIBLINGS hold properties.json. For a shader that is the .frag,
// not ShaderToy.qml — otherwise every shader would share one settings panel.
function propsBaseFor(scene) {
    return isShaderFile(scene) ? rawPath(scene) : pathFor(scene);
}

function pathFor(scene) {
    var s = ("" + scene).trim();
    if (s.length === 0)
        return BUILTINS["shader"];
    if (isShaderFile(s))
        return BUILTINS["shadertoy"];
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

// The scene string as a URL, with no built-in substitution — what ShaderToy.qml
// needs as its `source`, and what propsBaseFor() resolves against.
function rawPath(scene) {
    var s = ("" + scene).trim();
    if (s.indexOf("://") !== -1)
        return s;
    if (s.charAt(0) === "/")
        return "file://" + s;
    return s;
}
