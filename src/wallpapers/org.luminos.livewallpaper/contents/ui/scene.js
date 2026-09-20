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
    "shadertoy": "scenes/ShaderToy.qml",
    "canvasjs":  "scenes/CanvasJs.qml",
    "producer":  "scenes/Producer.qml"
};

// A .frag / .glsl typed into the scene box is not a QML file — it is a shader,
// and the scene that runs it is ShaderToy.qml. That keeps one input box for
// "point it at your own file" instead of growing a second one per file type.
// [CHANGE: claude-code | 2026-09-19] DECISION 119
function isShaderFile(scene) {
    return /\.(frag|glsl|fsh)$/i.test(("" + scene).trim());
}

// Same idea for a Lively-style canvas wallpaper: a .js typed into the scene box
// is not a QML file, it is a script, and the scene that runs it is CanvasJs.qml.
// [CHANGE: claude-code | 2026-09-19] SPEC §3.5, DECISION 122
function isJsFile(scene) {
    return /\.(js|mjs)$/i.test(("" + scene).trim());
}

// A file the host must hand to the scene as `source` rather than load directly.
function isSourceFile(scene) {
    return isShaderFile(scene) || isJsFile(scene);
}

// The file whose SIBLINGS hold properties.json. For a shader that is the .frag,
// not ShaderToy.qml — otherwise every shader would share one settings panel.
function propsBaseFor(scene) {
    return isSourceFile(scene) ? rawPath(scene) : pathFor(scene);
}

function pathFor(scene) {
    var s = ("" + scene).trim();
    if (s.length === 0)
        return BUILTINS["shader"];
    if (isShaderFile(s))
        return BUILTINS["shadertoy"];
    if (isJsFile(s))
        return BUILTINS["canvasjs"];
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

// A package's manifest `type` (CONTRACTS §5) -> the wallpaper mode that shows it,
// and the config key that holds its path. Pure, and here rather than inside
// config.qml, so the gallery's promise can actually be tested.
// Returns null for a type we cannot show — the gallery never offers those, and a
// caller that ignores that should do nothing rather than guess.
// [CHANGE: claude-code | 2026-09-19] SPEC §3.3, DECISION 123
function modeForType(type) {
    var t = ("" + type).toLowerCase();
    if (t === "scene" || t === "shader" || t === "js")
        return { mode: "qml", key: "QmlScene" };
    if (t === "video")
        return { mode: "video", key: "Video" };
    if (t === "image" || t === "gif")
        return { mode: "image", key: "Image" };
    if (t === "web")
        return { mode: "web", key: "WebUrl" };
    return null;
}

// ---------------------------------------------------------------------------
// ONE FILE IN, ONE ANSWER OUT.  [CHANGE: claude-code | 2026-09-20] DECISION 129.
//
// Shawn: "just select file and it sets the wallpaper according to file
// selected. simple that's it". So the settings page no longer asks which KIND
// of wallpaper this is — the file says. Everything the old Type combo did is
// this table, and a table can be tested, which a combo box never was.
//
// Returns { mode, key, what } or null. `what` is shown to the person, so it
// says what will happen rather than naming an internal mode.
var FILE_KINDS = [
    { re: /\.(jpg|jpeg|png|webp|bmp|avif|jxl|tif|tiff)$/i,
      mode: "image", key: "Image",    what: "Picture" },
    { re: /\.gif$/i,
      mode: "image", key: "Image",    what: "Animated GIF" },
    { re: /\.(mp4|mkv|webm|mov|avi|m4v|mpg|mpeg|wmv)$/i,
      mode: "video", key: "Video",    what: "Video, looping" },
    { re: /\.(html?|xhtml)$/i,
      mode: "web",   key: "WebUrl",   what: "Web page (HTML/JS/WebGL)" },
    { re: /\.(frag|glsl|fsh)$/i,
      mode: "qml",   key: "QmlScene", what: "Shader, compiled on the spot" },
    { re: /\.(js|mjs)$/i,
      mode: "qml",   key: "QmlScene", what: "Canvas script (Lively style)" },
    { re: /\.qml$/i,
      mode: "qml",   key: "QmlScene", what: "QML scene" }
];

function modeForFile(pathOrUrl) {
    var s = ("" + pathOrUrl).trim();
    if (s.length === 0)
        return null;
    // A YouTube link is a video even though it has no extension at all; main.qml
    // hands it to yt-dlp. Checked BEFORE the extension table so a URL ending in
    // ".html" that is really a YouTube page is still treated as a video.
    var low = s.toLowerCase();
    if (low.indexOf("youtube.com") >= 0 || low.indexOf("youtu.be") >= 0)
        return { mode: "video", key: "Video", what: "YouTube video" };
    // Anything else remote with no usable extension is a web page: that is what
    // a browser would do with it, and web mode IS a browser.
    var bare = s.split("#")[0].split("?")[0];
    for (var i = 0; i < FILE_KINDS.length; i++) {
        if (FILE_KINDS[i].re.test(bare))
            return { mode: FILE_KINDS[i].mode, key: FILE_KINDS[i].key,
                     what: FILE_KINDS[i].what };
    }
    if (/^https?:\/\//i.test(s))
        return { mode: "web", key: "WebUrl", what: "Web page" };
    return null;
}

// The extensions the file dialog should offer, built from the SAME table, so a
// format that plays can always be picked and one that cannot is never offered.
function fileDialogPatterns() {
    return ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.avif", "*.jxl",
            "*.tif", "*.tiff", "*.gif",
            "*.mp4", "*.mkv", "*.webm", "*.mov", "*.avi", "*.m4v", "*.mpg",
            "*.mpeg", "*.wmv",
            "*.html", "*.htm", "*.xhtml",
            "*.frag", "*.glsl", "*.fsh", "*.js", "*.mjs", "*.qml"];
}
