/*
    Luminos Live Wallpaper — audio bridge.  SPEC §3.1, CONTRACTS §2.
    [CHANGE: claude-code | 2026-09-19]  DECISION 117.
    SPDX-License-Identifier: GPL-3.0-or-later

    Publishes ONE object shaped exactly like Lively's livelyAudioListener payload
    — 128 bands, 0..1 — so a Lively audio wallpaper ports here unmodified. That
    number is not a taste call: picking 64, or 0..255, would have been a silent
    incompatibility that only shows up as a wrong-looking port.

    This file imports nothing but QtQuick, on purpose. The provider lives in
    CaelestiaAudio.qml and is reached BY URL, the same rule as WebMode.qml
    (DECISION 112): a QML import runs when the file DECLARING it is loaded, so
    naming the provider type here would map libcava, aubio and PipeWire into
    plasmashell for every wallpaper — including a still image. By URL they arrive
    only when audio is switched on, and never at all on a machine where the
    provider is not installed.
*/
import QtQuick

Item {
    id: bridge

    visible: false
    width: 0
    height: 0

    // ---- inputs ---------------------------------------------------------
    // NOT `enabled`: Item already has an `enabled` property, and shadowing it made
    // Qt log `Member enabled of AudioBridge overrides a member of the base object`
    // on every load. A shadowed base property is a bug waiting for the day something
    // reads Item.enabled and gets ours. [CHANGE: claude-code | 2026-09-19]
    property bool audioEnabled: false
    // CONTRACTS §2: "The provider stops when running is false." Non-negotiable —
    // an audio wallpaper that keeps an FFT thread and a PipeWire stream alive
    // behind a fullscreen window is exactly the cost the freeze policy exists
    // to avoid. The Loader below is keyed on this, so the refcount drops and
    // Caelestia's service stops itself.
    property bool running: true
    readonly property bool wanted: bridge.audioEnabled && bridge.running

    readonly property int bandCount: 128

    // ---- output — CONTRACTS §2 -----------------------------------------
    // A QtObject rather than a rebuilt JS literal: cava ticks ~60 times a second
    // and allocating a seven-key object per tick buys nothing. A scene reads
    // audio.bands / audio.bass identically either way, and property bindings
    // keep working.
    readonly property var audio: pub

    readonly property var silence: {
        var a = [];
        for (var i = 0; i < 128; i++)
            a.push(0);
        return a;
    }

    QtObject {
        id: pub

        property var bands: bridge.silence
        property real bass: 0
        property real mid: 0
        property real treble: 0
        property bool beat: false
        property real bpm: 0
        property bool active: false
    }

    function mean(v, from, to) {
        var s = 0;
        for (var i = from; i <= to; i++)
            s += v[i];
        return s / (to - from + 1);
    }

    function silent() {
        pub.bands = bridge.silence;
        pub.bass = 0;
        pub.mid = 0;
        pub.treble = 0;
        pub.bpm = 0;
        pub.beat = false;
    }

    // Clamped on the way in rather than trusted. cava's autosens can overshoot 1
    // on a transient, and a scene that multiplies a height by 1.4 looks broken
    // in a way that is hard to trace back to here.
    function publish(values) {
        if (!values || values.length < bridge.bandCount) {
            bridge.silent();
            return;
        }
        var b = new Array(bridge.bandCount);
        for (var i = 0; i < bridge.bandCount; i++) {
            var x = values[i];
            b[i] = x > 1 ? 1 : (x > 0 ? x : 0);
        }
        pub.bands = b;
        pub.bass = bridge.mean(b, 0, 15);
        pub.mid = bridge.mean(b, 16, 63);
        pub.treble = bridge.mean(b, 64, 127);
    }

    Loader {
        id: providerLoader

        active: bridge.wanted
        asynchronous: true
        source: "CaelestiaAudio.qml"

        onStatusChanged: {
            if (status === Loader.Error) {
                // Said out loud. A wallpaper that silently shows flat bars is how
                // you spend an evening debugging cava when the real answer is that
                // the QML module is not installed.
                console.warn("[LUMINOS-WP] audio provider failed to load — is Caelestia.Services installed? "
                             + "Wallpaper continues with silence.");
                pub.active = false;
                bridge.silent();
            }
        }
        onLoaded: {
            item.bars = bridge.bandCount;
            pub.active = true;
        }
        onActiveChanged: {
            if (!active) {
                pub.active = false;
                bridge.silent();
            }
        }
    }

    Connections {
        target: providerLoader.item
        ignoreUnknownSignals: true

        function onValuesChanged() {
            bridge.publish(providerLoader.item.values);
        }
        function onBeat(bpm) {
            pub.bpm = bpm;
            pub.beat = true;
            beatOff.restart();
        }
    }

    // CONTRACTS §2: beat is "true for exactly one frame". One frame at 60 Hz is
    // 16 ms; a scene that polls instead of reacting still sees it.
    Timer {
        id: beatOff
        interval: 16
        onTriggered: pub.beat = false
    }
}
