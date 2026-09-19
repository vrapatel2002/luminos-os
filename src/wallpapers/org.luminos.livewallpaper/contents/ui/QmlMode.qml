/*
    Luminos Live Wallpaper — native QML mode. No browser involved.
    SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-16] DECISION 113.
    [CHANGE: claude-code | 2026-09-19] DECISION 117 — audio (SPEC §3.1).

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

Item {
    id: qmlRoot
    anchors.fill: parent

    // Bound by main.qml's Loader.onLoaded.
    property string scene: "shader"
    property bool shouldPlay: true
    property var stats: ({})
    property bool audioEnabled: false

    property real cursorX: 0
    property real cursorY: 0

    readonly property var builtins: ({
        "shader":    "scenes/Shader.qml",
        "aurora":    "scenes/Aurora.qml",
        "particles": "scenes/Particles.qml",
        "sysmon":    "scenes/SysMon.qml",
        "spectrum":  "scenes/Spectrum.qml"
    })

    readonly property url sceneUrl: {
        var s = ("" + qmlRoot.scene).trim();
        if (s.length === 0)
            return Qt.resolvedUrl(qmlRoot.builtins["shader"]);
        if (qmlRoot.builtins[s] !== undefined)
            return Qt.resolvedUrl(qmlRoot.builtins[s]);
        if (s.indexOf("://") !== -1)
            return s;
        if (s.charAt(0) === "/")
            return "file://" + s;
        return Qt.resolvedUrl(s);
    }

    // CONTRACTS §2. Always instantiated, never conditional: it costs one Item and
    // one QtObject, and in exchange `audio` is a stable object from the first
    // frame, with active:false, instead of flipping between null and an object
    // under every scene's bindings. `enabled` is what actually starts PipeWire.
    AudioBridge {
        id: audioBridge
        enabled: qmlRoot.audioEnabled
        running: qmlRoot.shouldPlay
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
