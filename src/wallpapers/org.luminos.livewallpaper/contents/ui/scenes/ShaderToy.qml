/*
    Luminos Live Wallpaper — drop in any Shadertoy .frag.  SPEC §3.4.
    [CHANGE: claude-code | 2026-09-19] DECISION 119.
    SPDX-License-Identifier: GPL-3.0-or-later

    Qt 6 has no inline GLSL, so the shader is compiled at runtime by
    `luminos-shader-bake` (cached by content hash — a wallpaper you come back to
    compiles nothing). The baker also reports which properties.json keys became
    uniforms, and THAT is what makes SPEC §3.2's promise real for an arbitrary
    shader: a QML object cannot gain a property at runtime, so the ShaderEffect is
    built from generated source with the right property list already in it.

    A uniform name arrives over a pipe and is spliced into generated QML, so it is
    re-validated here even though the baker validated it first.
*/
import QtQuick
import "../audio"
import "../props"

Item {
    id: scene
    anchors.fill: parent

    // ---- scene interface, CONTRACTS §1 (+ `source`, this scene's own) ----
    property bool running: true
    property var audio: null
    property var props: ({})
    property string source: ""
    property real cursorX: 0
    property real cursorY: 0

    property var effect: null
    property string failure: ""

    readonly property var nameOk: /^[A-Za-z_][A-Za-z0-9_]{0,31}$/

    function p(key, fallback) {
        var v = scene.props ? scene.props[key] : undefined;
        return (v === undefined || v === null) ? fallback : v;
    }
    // Shader floats: a checkbox arrives as a bool, a dropdown as an index.
    function n(key, fallback) {
        var v = scene.p(key, fallback);
        if (v === true) return 1;
        if (v === false) return 0;
        var f = Number(v);
        return isNaN(f) ? 0 : f;
    }
    function a(key) {
        var v = scene.audio ? Number(scene.audio[key]) : 0;
        return isNaN(v) ? 0 : v;
    }
    function audioActive() { return (scene.audio && scene.audio.active) ? 1 : 0; }

    function declFor(spec) {
        var bits = ("" + spec).split(":");
        if (bits.length !== 2 || !scene.nameOk.test(bits[0]))
            return "";
        return bits[1] === "vec4"
            ? '    property color ' + bits[0] + ': scene.p("' + bits[0] + '", "#ffffff")\n'
            : '    property real ' + bits[0] + ': scene.n("' + bits[0] + '", 0)\n';
    }

    function build(qsbPath, uniforms) {
        scene.failure = "";
        if (scene.effect) { scene.effect.destroy(); scene.effect = null; }
        var decls = "", list = uniforms.length > 0 ? uniforms.split(" ") : [];
        for (var i = 0; i < list.length; i++)
            decls += scene.declFor(list[i]);
        var src = 'import QtQuick\nShaderEffect {\n    anchors.fill: parent\n'
            + '    property real iTime: 0\n'
            + '    property vector2d iResolutionXY: Qt.vector2d(width, height)\n'
            + '    property vector4d iMouse: Qt.vector4d(scene.cursorX, height - scene.cursorY, 0, 0)\n'
            + '    property real iBass: scene.a("bass")\n'
            + '    property real iMid: scene.a("mid")\n'
            + '    property real iTreble: scene.a("treble")\n'
            + '    property real iAudioActive: scene.audioActive()\n'
            + '    property variant iChannel0: audioTex.texture\n'
            + decls
            + '    fragmentShader: "file://' + qsbPath + '"\n'
            + '    NumberAnimation on iTime { from: 0; to: 36000; duration: 36000000;\n'
            + '        loops: Animation.Infinite; running: scene.running }\n}\n';
        try {
            scene.effect = Qt.createQmlObject(src, holder, "luminos-shadertoy");
        } catch (e) {
            scene.fail("the generated shader item would not load: " + e);
        }
    }

    function fail(why) {
        if (scene.effect) { scene.effect.destroy(); scene.effect = null; }
        scene.failure = "" + why;
        console.warn("[LUMINOS-WP] shader:", scene.failure);
    }

    Rectangle { anchors.fill: parent; color: "#05060a" }

    ShaderBaker {
        source: scene.source
        onReady: function (qsbPath, uniforms) { scene.build(qsbPath, uniforms); }
        onFailed: function (why) { scene.fail(why); }
    }

    AudioTexture {
        id: audioTex
        bands: (scene.audio && scene.audio.bands) ? scene.audio.bands : null
    }

    Item { id: holder; anchors.fill: parent }

    // SPEC §6: never a black desktop. A shader that will not compile falls back
    // to the Canvas aurora and says why in the journal — the message is the
    // compiler's own line, so it is worth reading.
    Loader {
        anchors.fill: parent
        active: scene.failure.length > 0
        source: "Aurora.qml"
        onLoaded: item.running = Qt.binding(() => scene.running)
    }
}
