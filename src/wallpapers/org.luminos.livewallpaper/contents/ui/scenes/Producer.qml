/*
    Luminos Live Wallpaper — show a PipeWire video node.  SPEC §3.6, CONTRACTS §7.
    [CHANGE: claude-code | 2026-09-19]  The video half, first slice.
    SPDX-License-Identifier: GPL-3.0-or-later

    This is the consumer end of §3.6 and nothing else: it takes a node id and
    draws it. Spawning the producer (a game under `cage`), reaping it, and routing
    input are the halves still to come — deliberately, because the consumer can be
    proven on its own and everything else depends on it working.

    Useful already on its own terms: point it at any PipeWire video node and that
    is your wallpaper.

    `org.kde.pipewire` is reached BY URL through a Loader (the DECISION 112 rule),
    so a machine without kpipewire gets a named warning and the aurora fallback
    rather than a wallpaper plugin that will not load at all.
*/
import QtQuick
import "../props"

Item {
    id: scene
    anchors.fill: parent

    // ---- scene interface, CONTRACTS §1 -----------------------------------
    property bool running: true
    property var audio: null
    property var props: ({})
    property string source: ""
    property real cursorX: -1
    property real cursorY: -1

    property string failure: ""

    // The node to show. From the scene's own properties.json for now; §3.6's
    // host will hand it over when it spawns the producer.
    readonly property int nodeId: {
        var v = Number(scene.props ? scene.props.nodeId : undefined);
        return (isNaN(v) || v < 0) ? -1 : Math.round(v);
    }

    function fail(why) {
        scene.failure = "" + why;
        console.warn("[LUMINOS-WP] producer:", scene.failure);
    }

    Rectangle { anchors.fill: parent; color: "#05060a" }

    Loader {
        id: viewer
        anchors.fill: parent
        active: scene.nodeId >= 0
        source: "PipeWireView.qml"
        // Say WHICH of the two it was. The first version reported every load
        // failure as "kpipewire is not available", and then told exactly that lie
        // about a one-line mistake of mine in PipeWireView.qml — the module was
        // installed and fine. [CHANGE: claude-code | 2026-09-19]
        onStatusChanged: {
            if (status === Loader.Error)
                scene.fail("the PipeWire view would not load — either kpipewire is missing "
                           + "or the view itself is broken; the QML error is in the journal");
        }
        onLoaded: {
            item.nodeId = Qt.binding(() => scene.nodeId);
            scene.failure = "";
        }
        // Loaded is not the same as showing anything, so kpipewire's own `ready`
        // is what decides — but ONLY a not-ready node is worth a line. The first
        // version logged the happy path too, and the self test counted that
        // success message as a warning: 34 passed, 1 failed, about nothing wrong.
        // A healthy load says nothing. [CHANGE: claude-code | 2026-09-19]
        Connections {
            target: viewer.item
            ignoreUnknownSignals: true
            function onReadyChanged() {
                if (!viewer.item.ready)
                    console.warn("[LUMINOS-WP] producer: node " + scene.nodeId
                                 + " is not delivering frames");
            }
        }
    }

    // Nothing selected is not a failure — it is a scene waiting to be told what
    // to show, and saying so beats a black rectangle. BUG-175's lesson: do not
    // complain on a path that has not finished yet.
    Timer {
        interval: 1500
        running: scene.nodeId < 0
        onTriggered: scene.fail("no PipeWire node selected — set nodeId in this scene's settings")
    }

    // SPEC §6: never a black desktop.
    Loader {
        anchors.fill: parent
        active: scene.failure.length > 0
        source: "Aurora.qml"
        onLoaded: item.running = Qt.binding(() => scene.running)
    }
}
