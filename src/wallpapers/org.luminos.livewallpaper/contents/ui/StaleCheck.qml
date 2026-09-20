/*
    Luminos Live Wallpaper — "this settings page is older than the plugin".
    SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-20]  BUG-185, DECISION 128.

    BUG-171 has now cost three separate debugging sessions, and every one of them
    started with a person clicking something and nothing happening. QQmlEngine
    caches compiled components for the life of the engine, so a System Settings
    window that was open before a deploy keeps running the OLD QML forever — and
    the old QML cannot know that, because the file it would have to read to find
    out is the file it is not running.

    It does not have to know. It knows when IT started; the tool (a fresh process
    every time) knows when the FILES were last written. If the files are newer
    than this page, this page is stale. That is the whole test, and it needs no
    version number, no build stamp and no deploy step to maintain.

    Deliberately NOT self-healing: reloading the QML behind a settings page that
    may hold unsaved changes is worse than telling someone to reopen a window.
*/
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: check

    visible: false
    width: 0
    height: 0

    // True once we are sure. Never true on a guess — a false accusation here
    // sends someone restarting an app that was fine.
    property bool stale: false
    readonly property real startedAt: Date.now() / 1000

    readonly property string tool: {
        var u = "" + Qt.resolvedUrl("../tools/luminos-wallpaper-gallery");
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }

    Component.onCompleted: probe.connectSource(
        "python3 '" + check.tool.replace(/'/g, "'\\''") + "' --plugin-mtime")

    P5Support.DataSource {
        id: probe
        engine: "executable"
        onNewData: function (src, data) {
            disconnectSource(src);
            var mtime = parseInt(("" + (data["stdout"] || "")).trim(), 10);
            if (!isFinite(mtime) || mtime <= 0)
                return;                       // cannot tell: say nothing
            // One second of slack: the page and the files can be written in the
            // same second during a deploy, and that is not staleness.
            check.stale = mtime > (check.startedAt + 1);
            if (check.stale)
                console.warn("[LUMINOS-WP] this settings page started at",
                             Math.round(check.startedAt), "but the plugin was written at",
                             mtime, "— it is running cached QML (BUG-171)");
        }
    }
}
