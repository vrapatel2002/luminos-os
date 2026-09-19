/*
    Luminos Live Wallpaper — native QML mode. No browser involved.
    SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-16] DECISION 113.
    [CHANGE: claude-code | 2026-09-19] DECISION 117 — audio (SPEC §3.1).
    [CHANGE: claude-code | 2026-09-19] DECISION 118 — per-scene props (SPEC §3.2).
    [CHANGE: claude-code | 2026-09-19] DECISION 119 — a .frag is a scene too (SPEC §3.4).

    Web mode still exists and is still the right tool for arbitrary HTML from
    the internet. This mode is for the wallpapers we write ourselves, where
    handing the job to a browser engine was never buying anything: a Shadertoy
    fragment shader is a ShaderEffect, a canvas animation is a Canvas, and a
    stats readout is a Text. Same output, no Chromium in the process at all.

    A scene is either a built-in name or a path to any .qml file, so this is
    open the same way web mode is open - point it at your own file.
*/
import QtQuick
// Directory import, not a URL Loader, and that is deliberate: AudioBridge.qml
// imports nothing but QtQuick. The expensive import (Caelestia.Services, which
// drags in libcava, aubio and PipeWire) sits one level further down behind
// AudioBridge's own URL Loader, which is where DECISION 112's rule actually
// bites. Deferring a QtQuick-only file would buy nothing and hide the wiring.
import "audio"
import "props"
import "scene.js" as Scene

Item {
    id: qmlRoot
    anchors.fill: parent

    // Bound by main.qml's Loader.onLoaded.
    property string scene: "shader"
    property bool shouldPlay: true
    property var stats: ({})
    property bool audioEnabled: false
    // The raw SceneProperties config string, passed through untouched.
    property string sceneProperties: "{}"

    property real cursorX: 0
    property real cursorY: 0

    // The built-in map moved to scene.js so config.qml resolves scenes the SAME
    // way — it has to find this scene's properties.json to build its panel, and
    // a second copy of the map is how a settings panel ends up editing the
    // properties of a scene the wallpaper is not showing.
    readonly property url sceneUrl: {
        var path = Scene.pathFor(qmlRoot.scene);
        return Scene.isAbsolute(path) ? path : Qt.resolvedUrl(path);
    }

    // A .frag typed into the scene box loads ShaderToy.qml and hands it the file.
    // Its settings live beside the SHADER, not beside ShaderToy.qml, or every
    // shader on the machine would share one panel. [CHANGE: claude-code | 2026-09-19]
    readonly property string sceneSource: Scene.isShaderFile(qmlRoot.scene)
        ? Scene.rawPath(qmlRoot.scene) : ""
    readonly property url propsUrl: {
        var base = Scene.propsBaseFor(qmlRoot.scene);
        return Scene.isAbsolute(base) ? base : Qt.resolvedUrl(base);
    }

    // CONTRACTS §2. Always instantiated, never conditional: it costs one Item and
    // one QtObject, and in exchange `audio` is a stable object from the first
    // frame, with active:false, instead of flipping between null and an object
    // under every scene's bindings. `audioEnabled` is what actually starts PipeWire.
    AudioBridge {
        id: audioBridge
        audioEnabled: qmlRoot.audioEnabled
        running: qmlRoot.shouldPlay
    }

    // CONTRACTS §4. Defaults from the scene's properties.json, saved values on
    // top, delivered as `props`. The store is also what config.qml instantiates,
    // so the panel and the wallpaper cannot disagree about the merge.
    PropertyStore {
        id: propStore
        sceneUrl: qmlRoot.propsUrl
        sceneId: qmlRoot.scene
        savedJson: qmlRoot.sceneProperties
    }

    // Anything the desktop draws must never take the whole shell down, so the
    // background colour is painted here rather than assumed from the scene.
    Rectangle { anchors.fill: parent; color: "#05060a" }

    // CONTRACTS §1: "the host binds only what exists". The old test was
    // `item.audio !== undefined`, which is wrong for exactly the properties that
    // matter — a `property var audio` with no initialiser IS undefined, so a
    // scene that declared audio correctly would never have been given any.
    // Ask whether the property exists, not whether it happens to hold a value.
    function sceneHas(item, name) {
        return (name in item) || (item[name] !== undefined);
    }

    Loader {
        id: sceneLoader
        anchors.fill: parent
        asynchronous: true
        source: qmlRoot.sceneUrl
        onStatusChanged: {
            if (status === Loader.Error)
                console.warn("[LUMINOS-WP] scene failed to load:", qmlRoot.sceneUrl);
        }
        onLoaded: {
            // Only what the scene actually declares — a scene is free to want
            // none of these.
            if (qmlRoot.sceneHas(item, "running"))
                item.running = Qt.binding(() => qmlRoot.shouldPlay);
            if (qmlRoot.sceneHas(item, "stats"))
                item.stats = Qt.binding(() => qmlRoot.stats);
            if (qmlRoot.sceneHas(item, "audio"))
                item.audio = Qt.binding(() => audioBridge.audio);
            if (qmlRoot.sceneHas(item, "props"))
                item.props = Qt.binding(() => propStore.props);
            if (qmlRoot.sceneHas(item, "source"))
                item.source = Qt.binding(() => qmlRoot.sceneSource);
            if (qmlRoot.sceneHas(item, "cursorX"))
                item.cursorX = Qt.binding(() => qmlRoot.cursorX);
            if (qmlRoot.sceneHas(item, "cursorY"))
                item.cursorY = Qt.binding(() => qmlRoot.cursorY);
        }
    }

    // Cursor without stealing clicks — same contract as web mode's.
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        onPositionChanged: function(m) { qmlRoot.cursorX = m.x; qmlRoot.cursorY = m.y; }
    }
}
