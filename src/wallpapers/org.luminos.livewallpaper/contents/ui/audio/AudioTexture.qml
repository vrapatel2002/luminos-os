/*
    Luminos Live Wallpaper — the spectrum as a texture a shader can sample.
    CONTRACTS §2.  [CHANGE: claude-code | 2026-09-19] DECISION 119.
    SPDX-License-Identifier: GPL-3.0-or-later

    128×1, red channel = band amplitude — Shadertoy's iChannel0 audio convention,
    so a Shadertoy audio shader runs here unmodified.

    Extracted from Shader.qml when the runtime shader loader needed the same
    thing: two copies of a texture generator is two places for the sampling
    convention to drift, and the convention is the whole point of the file.

    Drawn with 128 one-pixel fillRects rather than createImageData/putImageData:
    128 operations on a 128×1 surface cost nothing, and this uses only the part of
    Context2D that behaves the same on every Qt build. Clever here would buy
    microseconds and risk a blank texture.
*/
import QtQuick

Item {
    id: audioTexture

    width: 0
    height: 0

    // The 128 contract bands, or null. Null renders black, which is silence.
    property var bands: null

    readonly property alias texture: src

    onBandsChanged: canvas.requestPaint()

    Canvas {
        id: canvas

        width: 128
        height: 1
        visible: false
        renderStrategy: Canvas.Immediate
        renderTarget: Canvas.Image

        onPaint: {
            var ctx = getContext("2d");
            var b = audioTexture.bands;
            for (var i = 0; i < 128; i++) {
                var v = 0;
                if (b && b.length > i) {
                    v = b[i];
                    v = v > 1 ? 1 : (v > 0 ? v : 0);
                }
                ctx.fillStyle = Qt.rgba(v, v, v, 1);
                ctx.fillRect(i, 0, 1, 1);
            }
        }
        Component.onCompleted: requestPaint()
    }

    ShaderEffectSource {
        id: src
        sourceItem: canvas
        width: 128
        height: 1
        live: true
        hideSource: true
        smooth: true
    }
}
