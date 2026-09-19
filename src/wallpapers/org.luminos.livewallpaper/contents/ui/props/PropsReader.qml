/*
    Luminos Live Wallpaper — get a scene's properties.json into QML.
    SPEC §3.2.  [CHANGE: claude-code | 2026-09-19] BUG-170, DECISION 120.
    SPDX-License-Identifier: GPL-3.0-or-later

    Qt 6.11 disables local file reads through XMLHttpRequest unless
    QML_XHR_ALLOW_FILE_READ=1 is set for the whole process. The original reader
    used XHR, got an empty string back, and could not tell "blocked" from "there
    is no file" — so the settings panel said "this scene declares no settings"
    about a scene whose settings file was sitting right there.

    So the read happens in `contents/tools/luminos-wallpaper-props`, run through
    the same executable DataSource the plugin already uses for yt-dlp and
    luminos-monitor, and this file parses one line back.

    It is loaded BY URL by PropertyStore, so if this import is unavailable in
    whatever context the panel is running in, that is a Loader.Error with a named
    message — not a broken settings dialog.
*/
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: reader

    width: 0
    height: 0

    // A scene .qml or a shader .frag, with or without file://
    property string base: ""

    // schemaJson is "" when there is simply no file beside the scene.
    signal done(string schemaJson)
    signal failed(string why)

    readonly property string tool: {
        var u = "" + Qt.resolvedUrl("../../tools/luminos-wallpaper-props");
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }

    // POSIX single-quoting: everything inside '...' is literal, and the only
    // escape is to close, emit a quoted quote, reopen.
    function shQuote(s) { return "'" + ("" + s).replace(/'/g, "'\\''") + "'"; }

    onBaseChanged: reader.start()
    Component.onCompleted: reader.start()

    function start() {
        var b = ("" + reader.base).trim();
        if (b.length === 0) {
            reader.done("");
            return;
        }
        runner.connectSource("python3 " + reader.shQuote(reader.tool) + " " + reader.shQuote(b));
    }

    function parse(out) {
        var line = ("" + out).trim();
        if (line === "NONE" || line.length === 0) {
            reader.done("");
        } else if (line.indexOf("OK ") === 0) {
            reader.done(line.substring(3));
        } else if (line.indexOf("ERR ") === 0) {
            reader.failed(line.substring(4));
        } else {
            reader.failed("the properties reader answered something unexpected");
        }
    }

    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (src, data) {
            disconnectSource(src);
            reader.parse(data["stdout"] || "");
        }
    }
}
