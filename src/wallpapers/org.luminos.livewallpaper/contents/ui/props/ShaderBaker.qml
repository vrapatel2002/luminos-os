/*
    Luminos Live Wallpaper — run the shader compiler, hand back one answer.
    SPEC §3.4.  [CHANGE: claude-code | 2026-09-19] DECISION 119.
    SPDX-License-Identifier: GPL-3.0-or-later

    Split out of ShaderToy.qml for the 150-line scene budget (SPEC §9), and the
    seam is a real one: this is "how a shader gets compiled", the scene is "what
    the shader is drawn into". Any future package type that carries a .frag can
    use this without dragging a scene along.

    All of the risk lives in the baker, which is Python and has tests. This file
    builds one command line and parses two lines back.

    The baker ships INSIDE the plugin (contents/tools/) and is called by absolute
    path, not from PATH. Two reasons: a KPackage is meant to be self-contained, so
    installing the wallpaper cannot leave it half-working; and the lock screen
    loads the same package, where nothing would have put a script on PATH anyway.
    It is invoked through `python3` because a KPackage install is not guaranteed
    to preserve the executable bit.
*/
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: baker

    width: 0
    height: 0

    // A .frag path, with or without a file:// prefix.
    property string source: ""

    signal ready(string qsbPath, string uniforms)
    signal failed(string why)

    // Only a path this scene will actually use: absolute, ends in .qsb, and free
    // of the characters that would break out of the URL string it is spliced into.
    readonly property var pathOk: /^\/[^"'\\\n]+\.qsb$/

    // POSIX single-quoting: everything inside '...' is literal, and the only
    // escape is to close, emit a quoted quote, and reopen. The path comes from a
    // config field a person typed, so it never reaches a shell unquoted.
    function shQuote(s) { return "'" + ("" + s).replace(/'/g, "'\\''") + "'"; }

    readonly property string tool: {
        var u = "" + Qt.resolvedUrl("../../tools/luminos-shader-bake");
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }
    function propsPath(frag) { return ("" + frag).replace(/\.[^./]+$/, "") + ".properties.json"; }

    onSourceChanged: baker.start()
    Component.onCompleted: baker.start()

    function start() {
        var f = ("" + baker.source).trim();
        if (f.length === 0) {
            baker.failed("no shader file selected");
            return;
        }
        var path = f.indexOf("file://") === 0 ? f.substring(7) : f;
        runner.connectSource("python3 " + baker.shQuote(baker.tool) + " "
                             + baker.shQuote(path) + " "
                             + baker.shQuote(baker.propsPath(path)));
    }

    function parse(out) {
        var lines = ("" + out).trim().split("\n");
        var head = lines[0] || "";
        if (head.indexOf("OK ") !== 0) {
            baker.failed(head.indexOf("ERR ") === 0 ? head.substring(4)
                                                    : "the shader baker produced no answer");
            return;
        }
        var qsb = head.substring(3).trim();
        if (!baker.pathOk.test(qsb)) {
            baker.failed("the baker returned a path this scene will not use: " + qsb);
            return;
        }
        var second = lines[1] || "";
        baker.ready(qsb, second.indexOf("UNIFORMS ") === 0 ? second.substring(9).trim() : "");
    }

    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (src, data) {
            disconnectSource(src);
            baker.parse(data["stdout"] || "");
        }
    }
}
