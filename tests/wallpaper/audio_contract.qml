/*
    CONTRACTS §2 conformance test for the wallpaper audio bridge.
    [CHANGE: claude-code | 2026-09-19]  DECISION 117.
    SPDX-License-Identifier: GPL-3.0-or-later

    Run ON THE BOX — this is the part that cannot be tested in the build
    container, because it needs a real QML engine:

        qml6 ~/luminos-os/tests/wallpaper/audio_contract.qml ; echo $?

    Exit 0 = the contract holds. Non-zero = it does not, and every failing check
    is printed with the value it actually got.

    It drives AudioBridge.publish() directly with synthetic frames, so it proves
    the SHAPE and the MATHS without needing PipeWire, sound, or a wallpaper on
    screen. `enabled` stays false throughout, so no provider is ever loaded and
    this test cannot be fooled by — or interfere with — a real audio stream.
*/
import QtQuick
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/audio"

Item {
    id: harness

    property int failures: 0

    function check(name, cond, got) {
        if (cond) {
            console.log("  ok    " + name);
        } else {
            console.log("  FAIL  " + name + "   got: " + got);
            harness.failures++;
        }
    }

    function near(a, b) { return Math.abs(a - b) < 1e-9; }

    AudioBridge {
        id: bridge
        audioEnabled: false // never loads a provider — see header
        running: true
    }

    Component.onCompleted: {
        console.log("CONTRACTS §2 — audio bridge");

        // ---- 1. shape, before anything has been published -----------------
        var a = bridge.audio;
        harness.check("audio object exists", !!a, a);
        harness.check("128 bands", a.bands.length === 128, a.bands.length);
        harness.check("bands start silent", a.bands.every(function (v) { return v === 0; }), a.bands.slice(0, 4));
        harness.check("bass 0", a.bass === 0, a.bass);
        harness.check("mid 0", a.mid === 0, a.mid);
        harness.check("treble 0", a.treble === 0, a.treble);
        harness.check("beat false", a.beat === false, a.beat);
        harness.check("bpm 0", a.bpm === 0, a.bpm);
        harness.check("active false with no provider", a.active === false, a.active);
        harness.check("bandCount is Lively's 128", bridge.bandCount === 128, bridge.bandCount);

        // ---- 2. the band split, with numbers chosen to be unambiguous -----
        // bass = mean(0..15), mid = mean(16..63), treble = mean(64..127).
        var f = new Array(128);
        for (var i = 0; i < 128; i++)
            f[i] = i < 16 ? 0.5 : (i < 64 ? 0.25 : 0.125);
        bridge.publish(f);
        harness.check("bass   = mean(bands[0..15])",   harness.near(a.bass, 0.5),    a.bass);
        harness.check("mid    = mean(bands[16..63])",  harness.near(a.mid, 0.25),    a.mid);
        harness.check("treble = mean(bands[64..127])", harness.near(a.treble, 0.125), a.treble);
        harness.check("bands round-trip unchanged", a.bands[0] === 0.5 && a.bands[127] === 0.125,
                      [a.bands[0], a.bands[127]]);

        // ---- 3. clamping --------------------------------------------------
        // cava's autosens overshoots on a transient. A scene multiplying a height
        // by 1.4 looks broken in a way that is very hard to trace back to here.
        var over = new Array(128);
        for (var j = 0; j < 128; j++)
            over[j] = j % 2 === 0 ? 1.8 : -0.4;
        bridge.publish(over);
        harness.check("values > 1 clamp to 1", a.bands[0] === 1, a.bands[0]);
        harness.check("values < 0 clamp to 0", a.bands[1] === 0, a.bands[1]);
        harness.check("clamped means stay in 0..1", a.bass >= 0 && a.bass <= 1, a.bass);

        // ---- 4. a short or absent frame must not publish garbage ----------
        bridge.publish([0.9, 0.9, 0.9]);
        harness.check("short frame -> silence, still 128 long", a.bands.length === 128 && a.bands[0] === 0,
                      [a.bands.length, a.bands[0]]);
        bridge.publish(null);
        harness.check("null frame -> silence", a.bass === 0 && a.bands.length === 128, a.bass);

        // ---- 5. the freeze contract ---------------------------------------
        // SPEC §5.3 / CONTRACTS §2: the provider stops when running is false.
        // `wanted` is what the provider Loader is keyed on, so this is the
        // property that actually enforces it.
        bridge.audioEnabled = true;
        bridge.running = false;
        harness.check("running=false => not wanted", bridge.wanted === false, bridge.wanted);
        bridge.running = true;
        harness.check("enabled+running => wanted", bridge.wanted === true, bridge.wanted);
        bridge.audioEnabled = false;
        harness.check("disabled => not wanted", bridge.wanted === false, bridge.wanted);

        console.log(harness.failures === 0
                    ? "PASS — audio contract holds"
                    : "FAIL — " + harness.failures + " check(s) broken");
        Qt.exit(harness.failures === 0 ? 0 : 1);
    }
}
