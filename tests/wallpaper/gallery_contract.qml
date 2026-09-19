/*
    SPEC §3.3 — does the gallery read what is installed, and tell the truth?
    [CHANGE: claude-code | 2026-09-19]  DECISION 123, CONTRACTS §5.
    SPDX-License-Identifier: GPL-3.0-or-later

        QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1 \
            qml6 ~/luminos-os/tests/wallpaper/gallery_contract.qml ; echo $?

    Drives the REAL WallpaperGallery against whatever is actually installed, so
    it checks the product rather than the logic (BUG-173's lesson). It asserts
    SHAPE, not contents — the machine it runs on may have any packages, or none.
*/
import QtQuick
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui"
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/scene.js" as Scene

Item {
    id: harness
    width: 600
    height: 400

    property int failures: 0
    property bool done: false

    function check(name, cond, got) {
        if (cond)
            console.log("  ok    " + name);
        else {
            console.log("  FAIL  " + name + "   got: " + got);
            harness.failures++;
        }
    }

    WallpaperGallery {
        id: g
        anchors.fill: parent
    }

    Timer {
        interval: 3000
        running: true
        onTriggered: {
            console.log("SPEC §3.3 — the installed-wallpaper gallery");

            harness.check("it read the list without reporting a problem",
                          g.problem === "", g.problem);
            harness.check("it is not stuck busy", g.busy === false, g.busy);
            harness.check("the list is an array", g.items !== null && g.items.length !== undefined,
                          typeof g.items);

            var rows = g.items, bad = [], unplayable = 0;
            for (var i = 0; i < rows.length; i++) {
                var r = rows[i];
                // CONTRACTS §5: every row must carry enough to be rendered and chosen.
                if (!r.id || !r.type || r.playable === undefined || r.entryPath === undefined
                        || r.previewPath === undefined || r.why === undefined)
                    bad.push(r.id || "(no id)");
                // ...and an unplayable one must SAY WHY, never just be greyed.
                if (r.playable === false) {
                    unplayable++;
                    if (!r.why || ("" + r.why).length < 5)
                        bad.push((r.id || "?") + ": unplayable with no reason");
                }
                // A playable row must point at a file that exists, or the grid
                // offers something that cannot be selected.
                if (r.playable === true && ("" + r.entryPath).length === 0)
                    bad.push((r.id || "?") + ": playable with no entry path");
            }
            harness.check("every row is complete and honest", bad.length === 0, bad);

            // The type -> mode mapping the gallery's click depends on. Pure, so
            // it is checked here instead of by clicking a grid.
            var cases = [["scene", "qml", "QmlScene"], ["shader", "qml", "QmlScene"],
                         ["js", "qml", "QmlScene"], ["video", "video", "Video"],
                         ["image", "image", "Image"], ["gif", "image", "Image"]];
            var wrong = [];
            for (var c = 0; c < cases.length; c++) {
                var m = Scene.modeForType(cases[c][0]);
                if (m === null || m.mode !== cases[c][1] || m.key !== cases[c][2])
                    wrong.push(cases[c][0]);
            }
            harness.check("every playable type maps to a mode and a key", wrong.length === 0, wrong);
            harness.check("a producer type maps to NOTHING, so a stray click does nothing",
                          Scene.modeForType("producer") === null, Scene.modeForType("producer"));
            harness.check("an unknown type maps to nothing too",
                          Scene.modeForType("nonsense") === null, "not null");
            console.log("  ..    " + rows.length + " installed, " + unplayable + " not playable yet");

            harness.done = true;
            console.log(harness.failures === 0
                        ? "PASS — gallery contract holds"
                        : "FAIL — " + harness.failures + " check(s) broken");
            Qt.exit(harness.failures === 0 ? 0 : 1);
        }
    }

    Timer {
        interval: 20000
        running: true
        onTriggered: { if (!harness.done) { console.log("FAIL — timed out"); Qt.exit(1); } }
    }
}
