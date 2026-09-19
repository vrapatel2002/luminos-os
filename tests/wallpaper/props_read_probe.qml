/*
    Why is the Scene settings panel empty?  One command, one answer.
    [CHANGE: claude-code | 2026-09-19]  BUG-170 investigation
    SPDX-License-Identifier: GPL-3.0-or-later

        qml6 ~/luminos-os/tests/wallpaper/props_read_probe.qml ; echo $?

    PropertyStore reads a scene's properties.json with XMLHttpRequest, and an
    empty read is indistinguishable from "this scene has no settings" — which is
    exactly what the panel said. Qt has tightened local-file access through XHR
    more than once, so before redesigning the reader, find out what the engine
    actually does with a file that is definitely there.
*/
import QtQuick

Item {
    id: probe

    readonly property string installed:
        "file:///home/shawn/.local/share/plasma/wallpapers/org.luminos.livewallpaper/contents/ui/scenes/Spectrum.properties.json"
    readonly property string repo:
        "file:///home/shawn/luminos-os/src/wallpapers/org.luminos.livewallpaper/contents/ui/scenes/Spectrum.properties.json"

    property int done: 0
    property int worked: 0

    function attempt(label, url) {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return;
            var body = "";
            var err = "";
            try {
                body = xhr.responseText || "";
            } catch (e) {
                err = " (reading responseText threw: " + e + ")";
            }
            console.log("  " + label);
            console.log("      status      " + xhr.status);
            console.log("      bytes       " + body.length + err);
            if (body.length > 0) {
                probe.worked++;
                try {
                    var o = JSON.parse(body);
                    console.log("      parsed      " + Object.keys(o).length + " keys: " + Object.keys(o).join(", "));
                } catch (e2) {
                    console.log("      parsed      FAILED: " + e2);
                }
            } else {
                console.log("      ^^ EMPTY — this is the bug. The file exists; the engine returned nothing.");
            }
            probe.done++;
            if (probe.done === 2)
                probe.finish();
        };
        try {
            xhr.open("GET", url);
            xhr.send();
        } catch (e) {
            console.log("  " + label + "\n      open/send threw: " + e);
            probe.done++;
            if (probe.done === 2)
                probe.finish();
        }
    }

    function finish() {
        console.log("");
        if (probe.worked > 0)
            console.log("RESULT: XMLHttpRequest CAN read local files in this engine.");
        else
            console.log("RESULT: XMLHttpRequest CANNOT read local files here — the reader needs replacing.");
        Qt.exit(probe.worked > 0 ? 0 : 1);
    }

    Component.onCompleted: {
        console.log("PropertyStore's file read, probed directly");
        console.log("  Qt runtime  " + Qt.application.version + "  (qml6)");
        probe.attempt("installed copy", probe.installed);
        probe.attempt("repo copy", probe.repo);
    }
}
