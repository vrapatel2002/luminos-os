/*
    Luminos Live Wallpaper — audio spectrum scene.  SPEC §3.1.
    [CHANGE: claude-code | 2026-09-19]  DECISION 117.
    SPDX-License-Identifier: GPL-3.0-or-later

    Bars, not a Canvas. A Canvas repaint is a CPU raster of the whole surface —
    at 2880×1800 that is the wrong trade sixty times a second. Rectangles are
    composited on the GPU and only their heights change.

    64 bars drawn from 128 contract bands, pairwise max. The contract stays 128
    because that is Lively's number and ports depend on it; the DRAWING is a
    presentation choice, and 64 halves the item count without looking different
    at this width.
*/
import QtQuick

Item {
    id: scene
    anchors.fill: parent

    // ---- scene interface, CONTRACTS §1 ---------------------------------
    property bool running: true
    property var audio: null
    property real cursorX: -1
    property real cursorY: -1

    readonly property int visualBars: 64
    readonly property var bands: (scene.audio && scene.audio.bands) ? scene.audio.bands : null
    readonly property bool live: !!(scene.audio && scene.audio.active)

    function level(i) {
        var b = scene.bands;
        if (!b || b.length < 128)
            return 0;
        var a = b[i * 2], c = b[i * 2 + 1];
        return a > c ? a : c;
    }

    // Deliberately NOT faked. When there is no provider the bars sit flat and the
    // log says why. An idle shimmer here would look better and would mean a
    // broken audio path is indistinguishable from a quiet room — the same
    // mistake BUG-163 taught: a green light nobody can trust.
    onLiveChanged: {
        if (!scene.live)
            console.warn("[LUMINOS-WP] spectrum: no audio provider — bars will stay flat");
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#05060a" }
            GradientStop { position: 1.0; color: "#0b1024" }
        }
    }

    // Bass lifts the whole backdrop. Zero audio → zero opacity → exactly the
    // gradient above, so the scene degrades to something still worth looking at.
    Rectangle {
        anchors.fill: parent
        color: "#7c3aed"
        opacity: Math.min(0.30, (scene.audio ? scene.audio.bass : 0) * 0.45)
        Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    }

    Row {
        id: row
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Math.round(scene.height * 0.06)
        height: Math.round(scene.height * 0.55)
        spacing: Math.max(2, Math.round(scene.width / (scene.visualBars * 12)))

        Repeater {
            model: scene.visualBars

            Rectangle {
                id: bar
                required property int index

                readonly property real value: scene.level(bar.index)

                width: Math.max(1, (row.width - row.spacing * (scene.visualBars - 1)) / scene.visualBars)
                height: Math.max(2, bar.value * row.height)
                anchors.bottom: parent.bottom
                radius: Math.min(width, height) / 2

                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#a78bfa" }
                    GradientStop { position: 1.0; color: "#38bdf8" }
                }
                opacity: 0.55 + bar.value * 0.45

                // cava already applies its monstercat smoothing, so this is only
                // here to bridge the gap between ticks — long enough to stop the
                // stepping, short enough not to lag the music.
                Behavior on height {
                    enabled: scene.running
                    NumberAnimation { duration: 70; easing.type: Easing.OutQuad }
                }
            }
        }
    }

    // Beat: one frame of true (CONTRACTS §2), stretched into something an eye can
    // see. bpm is shown by the speed of the fade, not by a number on the desktop.
    Rectangle {
        id: flash
        anchors.fill: parent
        color: "#ffffff"
        opacity: 0

        Connections {
            target: scene.audio
            ignoreUnknownSignals: true
            function onBeatChanged() {
                if (scene.running && scene.audio && scene.audio.beat)
                    flashAnim.restart();
            }
        }
        NumberAnimation {
            id: flashAnim
            target: flash
            property: "opacity"
            from: 0.10
            to: 0
            duration: 260
            easing.type: Easing.OutQuad
        }
    }
}
