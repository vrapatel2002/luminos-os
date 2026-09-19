/*
    Luminos Live Wallpaper — audio spectrum scene.  SPEC §3.1.
    [CHANGE: claude-code | 2026-09-19]  DECISION 117, props 118.
    SPDX-License-Identifier: GPL-3.0-or-later

    Bars, not a Canvas: a Canvas repaint is a CPU raster of the whole surface, and
    at 2880×1800 that is the wrong trade sixty times a second.

    N bars from the 128 contract bands, max within each group. The contract stays
    128 because that is Lively's number and ports depend on it; how many are DRAWN
    is a setting (Spectrum.properties.json), default 64.
*/
import QtQuick

Item {
    id: scene
    anchors.fill: parent

    // ---- scene interface, CONTRACTS §1 ---------------------------------
    property bool running: true
    property var audio: null
    property var props: ({})
    property real cursorX: -1
    property real cursorY: -1

    function p(key, fallback) {
        var v = scene.props ? scene.props[key] : undefined;
        return (v === undefined || v === null) ? fallback : v;
    }

    readonly property var barChoices: [32, 64, 128]
    readonly property int visualBars: scene.barChoices[scene.p("bars", 1)] || 64
    readonly property real sensitivity: scene.p("sensitivity", 1)
    readonly property var bands: (scene.audio && scene.audio.bands) ? scene.audio.bands : null
    readonly property bool live: !!(scene.audio && scene.audio.active)

    // Max within the group, not mean: a mean smears a single loud band into
    // nothing, and the peaks are the part an eye reads as "the music".
    function level(i) {
        var b = scene.bands;
        if (!b || b.length < 128)
            return 0;
        var g = 128 / scene.visualBars, start = i * g, m = 0;
        for (var k = 0; k < g; k++)
            if (b[start + k] > m)
                m = b[start + k];
        m *= scene.sensitivity;
        return m > 1 ? 1 : m;
    }

    // Not faked when there is no provider: flat bars, and the log says why. An
    // idle shimmer would make a broken audio path look like a quiet room —
    // BUG-163's lesson. Delayed 3s because the provider loads asynchronously, and
    // a warning that fires on every start is one people scroll past.
    onLiveChanged: settleWarn.restart()
    onRunningChanged: settleWarn.restart()
    Timer {
        id: settleWarn
        interval: 3000
        onTriggered: {
            // Only an accusation when the scene is MEANT to be running. A wallpaper
            // frozen by ObscurePolicy — any maximized window covering the desktop —
            // has no provider by design, and warning there made a healthy box report
            // a broken audio path and burned a selftest FAIL on nothing.
            // [CHANGE: claude-code | 2026-09-19]
            if (!scene.live && scene.running)
                console.warn("[LUMINOS-WP] spectrum: audio is on but no provider arrived in 3s — bars will stay flat");
        }
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
                    GradientStop { position: 0.0; color: scene.p("highColor", "#a78bfa") }
                    GradientStop { position: 1.0; color: scene.p("lowColor", "#38bdf8") }
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
                if (scene.running && scene.p("beatFlash", true) && scene.audio && scene.audio.beat)
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
