/*
    Native port of contents/samples/luminos-shader.html — the WebGL fragment
    shader, as a Qt ShaderEffect. Same maths, no browser.
    [CHANGE: claude-code | 2026-09-16] DECISION 113
    [CHANGE: claude-code | 2026-09-19] DECISION 117 — audio uniforms + iAudio texture
    [CHANGE: claude-code | 2026-09-19] DECISION 118 — speed/tint/audioGain from props
    SPDX-License-Identifier: GPL-3.0-or-later

    The GLSL lives in contents/shaders/luminos-shader.frag and is committed
    ALONGSIDE its compiled .qsb. Qt 6 removed inline shader source from
    ShaderEffect - `fragmentShader` is a URL to a baked file - so the .frag is
    the readable source of truth and the .qsb is a build artefact that has to be
    in the repo because there is no build step at wallpaper-install time.
*/
import QtQuick
import "../audio"

Item {
    id: scene
    anchors.fill: parent

    property bool running: true
    property real cursorX: 0
    property real cursorY: 0
    // CONTRACTS §1 — bound by the host only if declared, so it starts as a real
    // value rather than undefined.
    property var audio: null
    // CONTRACTS §1/§4 — the merged values from Shader.properties.json.
    property var props: ({})

    // Defaults live in properties.json, but a scene must still render if that
    // file is missing or a key was hand-deleted from the config.
    function p(key, fallback) {
        var v = scene.props ? scene.props[key] : undefined;
        return (v === undefined || v === null) ? fallback : v;
    }

    // The spectrum texture moved to ui/audio/AudioTexture.qml when the runtime
    // shader loader needed the same thing — one copy of the 128×1 sampling
    // convention, because the convention is the part that must not drift.
    // [CHANGE: claude-code | 2026-09-19] DECISION 119
    AudioTexture {
        id: audioTex
        bands: (scene.audio && scene.audio.bands) ? scene.audio.bands : null
    }

    ShaderEffect {
        id: fx
        anchors.fill: parent

        // Matched BY NAME to the std140 uniform block in the .frag. Order there
        // is mat4 / float qt_Opacity / float iTime / vec2 iResolution / vec2
        // iMouse / 4 floats, chosen so every vec2 lands on an 8-byte boundary
        // and the audio floats append without disturbing what came before.
        property real iTime: 0
        property vector2d iResolution: Qt.vector2d(fx.width, fx.height)
        // WebGL's origin is bottom-left; the sample flipped the mouse the same way.
        property vector2d iMouse: Qt.vector2d(scene.cursorX, fx.height - scene.cursorY)

        property real iBass: scene.audio ? scene.audio.bass : 0
        property real iMid: scene.audio ? scene.audio.mid : 0
        property real iTreble: scene.audio ? scene.audio.treble : 0
        // Every audio term in the shader is multiplied by something that is zero
        // without audio, so with no provider this renders byte-identically to the
        // pre-audio version. Adding a feature must not change the default picture.
        property real iAudioActive: (scene.audio && scene.audio.active) ? 1 : 0
        property variant iAudio: audioTex.texture

        // Bound BY NAME to uniforms in the .frag — offsets 104/108/112, read from
        // `qsb --dump`. Declaring a key in properties.json is what produces the
        // slider; this is the whole of the glue between the two.
        property real uSpeed: scene.p("speed", 1)
        property real uAudioGain: scene.p("audioGain", 1)
        property color uTint: scene.p("tint", "#d959a6")

        fragmentShader: Qt.resolvedUrl("../../shaders/luminos-shader.frag.qsb")
        visible: fx.status === ShaderEffect.Compiled

        // One long animation rather than a Timer: the clock advances on the
        // render thread and stops dead when the wallpaper is frozen.
        NumberAnimation on iTime {
            from: 0; to: 36000; duration: 36000000
            loops: Animation.Infinite
            running: scene.running
        }
    }

    // If the baked shader cannot be used on this GPU/Qt build, fall back to the
    // Canvas aurora rather than showing a black desktop. Said out loud in the
    // log, because a silent fallback is how you end up debugging the wrong thing.
    Loader {
        anchors.fill: parent
        active: fx.status === ShaderEffect.Error
        source: "Aurora.qml"
        onActiveChanged: {
            if (active)
                console.warn("[LUMINOS-WP] shader unavailable, using Aurora instead:", fx.log);
        }
        onLoaded: item.running = Qt.binding(() => scene.running)
    }
}
