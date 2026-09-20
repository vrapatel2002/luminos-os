/*
    Does the settings page LOAD, and does one file decide everything?
    [CHANGE: claude-code | 2026-09-20]  BUG-186, DECISION 129.
    SPDX-License-Identifier: GPL-3.0-or-later

        QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1 \
            qml6 ~/luminos-os/tests/wallpaper/config_contract.qml ; echo $?

    THE FIRST CHECK IS THE POINT. config.qml shipped with a JavaScript syntax
    error — C-style implicit string concatenation, "a" "b", which JS does not
    allow — and the entire Wallpaper settings page rendered BLANK. Every other
    test passed, because not one of them had ever loaded this file: the gallery
    contract loads WallpaperGallery, the props contract loads PropertyStore, and
    the selftest greps the running wallpaper. The page a person actually opens
    was the one thing nothing opened.

    A Loader reaching Loader.Ready is a weak-looking assertion that would have
    caught it outright, which is the whole lesson (BUG-186).
*/
import QtQuick
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/scene.js" as Scene

Item {
    id: harness
    width: 900
    height: 700

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

    Loader {
        id: page
        anchors.fill: parent
        source: "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/config.qml"
    }

    Timer {
        interval: 2500
        running: true
        onTriggered: {
            console.log("DECISION 129 — the settings page, and one file deciding everything");

            // ---- 1. it loads at all -------------------------------------
            harness.check("config.qml loads (BUG-186: a syntax error here = a blank page)",
                          page.status === Loader.Ready, page.status);
            if (page.status !== Loader.Ready) {
                console.log("FAIL — the page did not load; nothing else can be checked");
                Qt.exit(1);
                return;
            }
            var pg = page.item;
            harness.check("it still declares every config key KDE binds",
                          "cfg_WallpaperMode" in pg && "cfg_Image" in pg && "cfg_Video" in pg
                          && "cfg_WebUrl" in pg && "cfg_QmlScene" in pg
                          && "cfg_SceneProperties" in pg, "a cfg_ key is missing");

            // ---- 2. the file decides -------------------------------------
            var cases = [
                ["/a/b/photo.JPG",        "image", "Image"],
                ["/a/b/loop.gif",         "image", "Image"],
                ["/a/b/clip.mp4",         "video", "Video"],
                ["/a/b/clip.MKV",         "video", "Video"],
                ["/a/rain/index.html",    "web",   "WebUrl"],
                ["/a/b/page.htm",         "web",   "WebUrl"],
                ["/a/b/toy.frag",         "qml",   "QmlScene"],
                ["/a/b/canvas.js",        "qml",   "QmlScene"],
                ["/a/b/scene.qml",        "qml",   "QmlScene"],
                ["https://youtu.be/xyz",  "video", "Video"],
                ["https://www.youtube.com/watch?v=x", "video", "Video"],
                ["https://example.com/live",          "web", "WebUrl"]
            ];
            var wrong = [];
            for (var i = 0; i < cases.length; i++) {
                var m = Scene.modeForFile(cases[i][0]);
                if (m === null || m.mode !== cases[i][1] || m.key !== cases[i][2])
                    wrong.push(cases[i][0] + " -> " + (m === null ? "null" : m.mode));
            }
            harness.check("every supported file maps to a mode and a key", wrong.length === 0, wrong);

            harness.check("every kind says what it is, in words a person can read",
                          cases.every(function (c) {
                              var m = Scene.modeForFile(c[0]);
                              return m !== null && ("" + m.what).length > 3;
                          }), "a kind has no description");

            harness.check("an unknown extension is refused, not guessed at",
                          Scene.modeForFile("/a/b/archive.zip") === null,
                          Scene.modeForFile("/a/b/archive.zip"));
            harness.check("an empty path is not an error",
                          Scene.modeForFile("") === null && Scene.modeForFile("   ") === null,
                          "empty path answered something");
            // A YouTube page whose URL happens to end in .html is still a video.
            harness.check("YouTube wins over the extension table",
                          Scene.modeForFile("https://youtube.com/a.html").mode === "video",
                          Scene.modeForFile("https://youtube.com/a.html").mode);
            // Query strings must not defeat the match.
            harness.check("a query string does not hide the extension",
                          Scene.modeForFile("/a/b/clip.mp4?x=1").mode === "video",
                          Scene.modeForFile("/a/b/clip.mp4?x=1"));

            // ---- 3. picking a file really sets the settings ---------------
            pg.useFile("/tmp/holiday.png");
            harness.check("a picture sets image mode and the image key",
                          pg.cfg_WallpaperMode === "image" && pg.cfg_Image === "/tmp/holiday.png",
                          pg.cfg_WallpaperMode + " / " + pg.cfg_Image);
            pg.useFile("/tmp/rain/index.html");
            harness.check("an html page sets web mode and the web key",
                          pg.cfg_WallpaperMode === "web" && pg.cfg_WebUrl === "/tmp/rain/index.html",
                          pg.cfg_WallpaperMode + " / " + pg.cfg_WebUrl);
            pg.useFile("/tmp/toy.frag");
            harness.check("a shader sets qml mode and the scene key",
                          pg.cfg_WallpaperMode === "qml" && pg.cfg_QmlScene === "/tmp/toy.frag",
                          pg.cfg_WallpaperMode + " / " + pg.cfg_QmlScene);
            harness.check("a good pick clears any previous complaint",
                          pg.pickProblem === "", pg.pickProblem);

            // The refusal MESSAGE cannot be checked here: it is built with i18n(),
            // which only exists where a KLocalizedContext is installed — System
            // Settings has one, a bare qml6 harness does not, so the call throws
            // in here and nowhere a person will ever be. What matters either way
            // is that a file we cannot show does not quietly become the wallpaper.
            var threw = false;
            try { pg.useFile("/tmp/mystery.zip"); } catch (e) { threw = true; }
            harness.check("an unusable file changes NOTHING",
                          pg.cfg_QmlScene === "/tmp/toy.frag"
                          && pg.cfg_WallpaperMode === "qml",
                          pg.cfg_WallpaperMode + " / " + pg.cfg_QmlScene);
            harness.check("...and it got as far as trying to explain itself",
                          threw || pg.pickProblem.indexOf("mystery.zip") >= 0,
                          "no complaint and no i18n throw — the refusal path was skipped");

            // ---- 4. the page reports what is showing ----------------------
            pg.useFile("/tmp/clip.mp4");
            harness.check("the page names the current file whatever the mode",
                          pg.currentFile === "/tmp/clip.mp4", pg.currentFile);

            // ---- 5. the seam a real click goes through --------------------
            // WallpaperGallery emits picked(type, entryPath); config.qml's
            // onPicked calls usePackage. That one line is the whole join between
            // "a tile was tapped" and "the settings changed", and until now
            // nothing crossed it: gallery_contract stops at the tap,
            // config_contract started after it.
            var gal = null;
            for (var k = 0; k < pg.children.length; k++) {
                if (pg.children[k] && "currentEntry" in pg.children[k]
                        && "items" in pg.children[k])
                    gal = pg.children[k];
            }
            harness.check("the page really does contain the gallery", gal !== null, gal);
            if (gal !== null) {
                gal.picked("web", "/tmp/from-a-tile/index.html");
                harness.check("a gallery tile's pick lands in the settings",
                              pg.cfg_WallpaperMode === "web"
                              && pg.cfg_WebUrl === "/tmp/from-a-tile/index.html",
                              pg.cfg_WallpaperMode + " / " + pg.cfg_WebUrl);
                harness.check("and the gallery is told which tile that is",
                              gal.currentEntry === "/tmp/from-a-tile/index.html",
                              gal.currentEntry);
            }

            harness.done = true;
            console.log(harness.failures === 0
                        ? "PASS — settings page contract holds"
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
