/*
    CONTRACTS §6 conformance test for the .js canvas layer.  SPEC §3.5.
    [CHANGE: claude-code | 2026-09-19]  DECISION 122.
    SPDX-License-Identifier: GPL-3.0-or-later

        QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1 \
            qml6 ~/luminos-os/tests/wallpaper/canvasjs_contract.qml ; echo $?

    It drives the REAL QmlMode, not a stand-in — BUG-173's lesson is that a test
    exercising the logic while the product is broken is worth nothing.

    Every script here stops itself after a few frames. A wallpaper loops forever,
    which is correct for a wallpaper and fatal for a test: offscreen there is no
    vsync to throttle requestAnimationFrame, so an endless loop runs flat out and
    starves the event loop the test's own timers live on. Measured: with the
    shipped sample running, a 3.5 s Timer fired at t+20.4 s.
*/
import QtQuick
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui"
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/scene.js" as Scene

Item {
    id: harness
    width: 320
    height: 200

    property int failures: 0
    property int stage: 0
    property bool done: false

    function check(name, cond, got) {
        if (cond)
            console.log("  ok    " + name);
        else {
            console.log("  FAIL  " + name + "   got: " + got);
            harness.failures++;
        }
    }

    function fixture(name) {
        var u = "" + Qt.resolvedUrl("fixtures/" + name);
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }

    function findScene(item) {
        for (var i = 0; i < item.children.length; i++) {
            var c = item.children[i];
            if (c.failure !== undefined && c.source !== undefined && c.props !== undefined)
                return c;
            var r = harness.findScene(c);
            if (r !== null) return r;
        }
        return null;
    }

    QmlMode {
        id: mode
        anchors.fill: parent
        shouldPlay: true
        audioEnabled: false
        sceneProperties: "{}"
        cursorX: 100
        cursorY: 80
    }

    Component.onCompleted: {
        console.log("CONTRACTS §6 — .js canvas wallpapers");

        // ---- routing (pure, no loading) ---------------------------------
        harness.check("a .js is recognised", Scene.isJsFile("/x/y.js") === true, Scene.isJsFile("/x/y.js"));
        harness.check("a .mjs is recognised", Scene.isJsFile("/x/y.mjs") === true, "false");
        harness.check("a .frag is NOT a js file", Scene.isJsFile("/x/y.frag") === false, "true");
        harness.check("a .js routes to CanvasJs.qml",
                      Scene.pathFor("/x/y.js") === "scenes/CanvasJs.qml", Scene.pathFor("/x/y.js"));
        harness.check("a .js is a source file, so the host hands it over",
                      Scene.isSourceFile("/x/y.js") === true, "false");
        harness.check("its settings live beside the SCRIPT, not beside CanvasJs.qml",
                      Scene.propsBaseFor("/x/y.js") === "file:///x/y.js", Scene.propsBaseFor("/x/y.js"));
        harness.check("a built-in name still routes normally",
                      Scene.pathFor("spectrum") === "scenes/Spectrum.qml", Scene.pathFor("spectrum"));

        harness.stage = 1;
        mode.scene = harness.fixture("bounded.js");
        settle.restart();
    }

    Timer {
        id: settle
        interval: 2500
        onTriggered: {
            var s = harness.findScene(mode);

            if (harness.stage === 1) {
                harness.check("a .js loads CanvasJs", s !== null, "no scene");
                harness.check("it runs with NO failure",
                              s !== null && s.failure === "", s === null ? "no scene" : s.failure);
                harness.check("the host handed the script over as `source`",
                              s !== null && ("" + s.source).indexOf("bounded.js") > 0,
                              s === null ? "no scene" : s.source);
                harness.stage = 2;
                mode.scene = harness.fixture("needs-fetch.js");
                settle.restart();
                return;
            }

            if (harness.stage === 2) {
                // CONTRACTS §6: "fails at load with a NAMED error — never a blank wallpaper".
                var why = (s === null) ? "" : ("" + s.failure);
                harness.check("an unsupported script fails rather than running",
                              why.length > 0, "no failure reported");
                harness.check("and the failure NAMES what was missing",
                              why.toLowerCase().indexOf("fetch") >= 0, why);
                harness.stage = 3;
                mode.scene = harness.fixture("missing-nothing-here.js");
                settle.restart();
                return;
            }

            // A file that is not there must say so, not show an empty desktop.
            var gone = (s === null) ? "" : ("" + s.failure);
            harness.check("a missing .js is reported by name",
                          gone.toLowerCase().indexOf("no such file") >= 0, gone);

            harness.done = true;
            console.log(harness.failures === 0
                        ? "PASS — .js canvas contract holds"
                        : "FAIL — " + harness.failures + " check(s) broken");
            Qt.exit(harness.failures === 0 ? 0 : 1);
        }
    }

    // A watchdog that shouts FAIL in a run that already passed is the very
    // instrument-lies pattern this project keeps paying for. Hence the guard.
    Timer {
        interval: 25000
        running: true
        onTriggered: {
            if (harness.done)
                return;
            console.log("FAIL — timed out at stage " + harness.stage);
            Qt.exit(1);
        }
    }
}
