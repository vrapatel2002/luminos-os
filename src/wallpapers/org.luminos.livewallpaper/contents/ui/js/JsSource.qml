/*
    Luminos Live Wallpaper — get a .js wallpaper's source into QML.
    SPEC §3.5, CONTRACTS §6.  [CHANGE: claude-code | 2026-09-19] DECISION 122.
    SPDX-License-Identifier: GPL-3.0-or-later

    The same shape as ShaderBaker, for the same reason: Qt 6.11 will not let QML
    read a local file (BUG-170), so `contents/tools/luminos-wallpaper-js` reads it
    in a process and answers on stdout. That tool also REFUSES a script the shim
    cannot honour, which is CONTRACTS §6's "fails at load with a named error" —
    a missing global would otherwise throw somewhere inside a rAF loop, minutes
    later or never.

    Protocol: `OK <bytes>` on the first line and the source after it, or
    `ERR <one line>` and nothing else.
*/
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: reader

    width: 0
    height: 0

    property string source: ""

    signal ready(string js)
    signal failed(string why)

    readonly property string tool: {
        var u = "" + Qt.resolvedUrl("../../tools/luminos-wallpaper-js");
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }

    function shQuote(s) { return "'" + ("" + s).replace(/'/g, "'\\''") + "'"; }

    onSourceChanged: reader.start()
    Component.onCompleted: reader.start()

    // BUG-175: the host binds `source` in its Loader's onLoaded, which runs AFTER
    // this object completes — so an empty source at construction is normal and
    // complaining about it immediately cries wolf on every healthy load.
    Timer {
        id: emptySettle
        interval: 1500
        onTriggered: {
            if (("" + reader.source).trim().length === 0)
                reader.failed("no .js file selected");
        }
    }

    function start() {
        var f = ("" + reader.source).trim();
        if (f.length === 0) {
            emptySettle.restart();
            return;
        }
        emptySettle.stop();
        var path = f.indexOf("file://") === 0 ? f.substring(7) : f;
        runner.connectSource("python3 " + reader.shQuote(reader.tool) + " " + reader.shQuote(path));
    }

    function parse(out) {
        var text = "" + out;
        var nl = text.indexOf("\n");
        var head = (nl < 0 ? text : text.substring(0, nl)).trim();
        if (head.indexOf("ERR ") === 0) {
            reader.failed(head.substring(4));
        } else if (head.indexOf("OK ") === 0) {
            reader.ready(nl < 0 ? "" : text.substring(nl + 1));
        } else {
            reader.failed("the .js reader answered something unexpected");
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
