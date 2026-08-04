// LookDashboard.qml — live Hyprland look tuner for Luminos
// [CHANGE: claude-code | 2026-08-04]
//
// WHY QUICKSHELL AND NOT qml6
// Plain `qml6` has no way to run a subprocess, and every control here has to shell out to
// `luminos-look set`. Quickshell provides Quickshell.Io.Process, is already a hard dependency
// of Caelestia, and is Qt6/QML — so this adds no new toolkit and no GTK.
//
// Run:  qs -p ~/luminos-os/src/look/LookDashboard.qml
//
// EVERY CONTROL IS A LIVE PREVIEW AND WRITES NOTHING.
// Moving a slider calls `luminos-look set`, which issues `hyprctl eval` against the running
// compositor. Nothing reaches disk until Save. Revert is `hyprctl reload`, which throws away
// every live eval — so there is no way to get stuck in a look you hate.
//
// The 80 ms debounce matters: dragging a slider emits dozens of changes per second, and one
// process spawn each would flood hyprctl. Instead the timer restarts on every change and
// re-sends the COMPLETE state once it settles, which is also self-healing — a dropped update
// is corrected by the next one.

import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts

FloatingWindow {
    id: root

    title: "Luminos Look"
    implicitWidth: 470
    implicitHeight: 780
    color: root.cSurface

    // ── Palette ─────────────────────────────────────────────────────────────────────────
    // Defaults are the current Caelestia scheme, overwritten at startup from scheme.json so
    // the dashboard follows the desktop's theme instead of drifting from it.
    property color cSurface:   "#131317"
    property color cCard:      "#201f23"
    property color cCardHigh:  "#2a292e"
    property color cTrack:     "#353438"
    property color cOnSurface: "#e5e1e7"
    property color cSubtle:    "#c8c5d1"
    property color cPrimary:   "#c2c1ff"
    property color cOnPrimary: "#2a2a60"
    property color cOutline:   "#918f9a"

    property string currentPreset: "caelestia"
    property bool   ready: false        // suppresses applies while presets load the controls

    Component.onCompleted: {
        loadScheme();
        ready = true;
    }

    // Synchronous XHR rather than Quickshell's FileView: this runs once at startup, the file
    // is local, and XHR's API is stable across Qt/Quickshell versions.
    function loadScheme() {
        try {
            var home = Quickshell.env("HOME");
            if (!home)
                return;
            var xhr = new XMLHttpRequest();
            xhr.open("GET", "file://" + home + "/.local/state/caelestia/scheme.json", false);
            xhr.send();
            if (xhr.status !== 200 && xhr.status !== 0)
                return;
            var c = JSON.parse(xhr.responseText).colours;
            if (!c)
                return;
            function pick(key, fallback) {
                return c[key] ? "#" + c[key] : fallback;
            }
            root.cSurface   = pick("surface", root.cSurface);
            root.cCard      = pick("surfaceContainer", root.cCard);
            root.cCardHigh  = pick("surfaceContainerHigh", root.cCardHigh);
            root.cTrack     = pick("surfaceContainerHighest", root.cTrack);
            root.cOnSurface = pick("onSurface", root.cOnSurface);
            root.cSubtle    = pick("onSurfaceVariant", root.cSubtle);
            root.cPrimary   = pick("primary", root.cPrimary);
            root.cOnPrimary = pick("onPrimary", root.cOnPrimary);
            root.cOutline   = pick("outline", root.cOutline);
        } catch (e) {
            // A broken or missing scheme must not stop the dashboard opening — the built-in
            // palette above is already a usable fallback.
            console.log("LookDashboard: scheme load failed, using defaults:", e);
        }
    }

    // ── Command plumbing ────────────────────────────────────────────────────────────────
    Process {
        id: proc
        command: ["true"]
    }

    function run(args) {
        proc.running = false;
        proc.command = args;
        proc.running = true;
    }

    Timer {
        id: debounce
        interval: 80
        onTriggered: root.pushAll()
    }

    function touch() {
        if (root.ready)
            debounce.restart();
    }

    // Sends the complete state every time, so the compositor can never end up holding a
    // half-applied look.
    function pushAll() {
        run(["luminos-look", "set",
             "rounding="     + Math.round(sRound.value),
             "gaps_in="      + Math.round(sGapIn.value),
             "gaps_out="     + Math.round(sGapOut.value),
             "border="       + Math.round(sBorder.value),
             "blur="         + (tBlur.on ? "true" : "false"),
             "blur_size="    + Math.round(sBlurSize.value),
             "blur_passes="  + Math.round(sBlurPass.value),
             "blur_xray="    + (tXray.on ? "true" : "false"),
             "shadow="       + (tShadow.on ? "true" : "false"),
             "shadow_range=" + Math.round(sShadow.value),
             "anim="         + (tAnim.on ? "true" : "false"),
             "opacity="      + sOpacity.value.toFixed(2)]);
        root.currentPreset = "custom";
    }

    // Preset values mirror the table in `luminos-look`. They are duplicated rather than
    // shelled out for because the sliders must move to the preset's values, which means the
    // dashboard needs the numbers themselves, not just their effect.
    readonly property var presets: ({
        "caelestia":   { r: 15, gi: 5,  go: 10, b: 1, bl: true,  bs: 8,  bp: 2, bx: false, sh: true,  sr: 15, op: 0.95, an: true  },
        "soft":        { r: 20, gi: 8,  go: 16, b: 2, bl: true,  bs: 12, bp: 3, bx: false, sh: true,  sr: 25, op: 0.92, an: true  },
        "glass":       { r: 18, gi: 10, go: 20, b: 2, bl: true,  bs: 18, bp: 4, bx: true,  sh: true,  sr: 30, op: 0.80, an: true  },
        "sharp":       { r: 0,  gi: 2,  go: 4,  b: 2, bl: false, bs: 8,  bp: 1, bx: false, sh: false, sr: 0,  op: 1.00, an: true  },
        "chunky":      { r: 28, gi: 12, go: 28, b: 4, bl: true,  bs: 10, bp: 2, bx: false, sh: true,  sr: 20, op: 0.95, an: true  },
        "performance": { r: 0,  gi: 0,  go: 0,  b: 1, bl: false, bs: 1,  bp: 1, bx: false, sh: false, sr: 0,  op: 1.00, an: false }
    })

    function applyPreset(name) {
        var p = presets[name];
        if (!p)
            return;
        ready = false;                 // move every control first, apply once at the end
        sRound.value    = p.r;
        sGapIn.value    = p.gi;
        sGapOut.value   = p.go;
        sBorder.value   = p.b;
        sBlurSize.value = p.bs;
        sBlurPass.value = p.bp;
        sShadow.value   = p.sr;
        sOpacity.value  = p.op;
        tBlur.on        = p.bl;
        tXray.on        = p.bx;
        tShadow.on      = p.sh;
        tAnim.on        = p.an;
        ready = true;
        pushAll();
        root.currentPreset = name;     // set after pushAll, which would mark it "custom"
    }

    // ── Reusable controls ───────────────────────────────────────────────────────────────
    component Tweak: ColumnLayout {
        id: tw
        property string label
        property real from: 0
        property real to: 100
        property real stepSize: 1
        property real value: 0
        property int decimals: 0
        Layout.fillWidth: true
        spacing: 1

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: tw.label
                color: root.cSubtle
                font.pixelSize: 13
                Layout.fillWidth: true
            }
            Text {
                text: tw.value.toFixed(tw.decimals)
                color: root.cPrimary
                font.pixelSize: 13
                font.bold: true
            }
        }

        Item {
            Layout.fillWidth: true
            implicitHeight: 22

            Rectangle {           // track
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: 4
                radius: 2
                color: root.cTrack
            }
            Rectangle {           // fill
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * ((tw.value - tw.from) / (tw.to - tw.from))
                height: 4
                radius: 2
                color: root.cPrimary
            }
            Rectangle {           // handle
                x: parent.width * ((tw.value - tw.from) / (tw.to - tw.from)) - width / 2
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 14
                radius: 7
                color: root.cPrimary
                border.width: 2
                border.color: root.cSurface
            }

            MouseArea {
                anchors.fill: parent
                // A little vertical slack so the thin track is still easy to grab.
                anchors.topMargin: -6
                anchors.bottomMargin: -6
                onPressed: mouse => setFromX(mouse.x)
                onPositionChanged: mouse => {
                    if (pressed)
                        setFromX(mouse.x);
                }
                function setFromX(x) {
                    var frac = Math.max(0, Math.min(1, x / width));
                    var raw = tw.from + frac * (tw.to - tw.from);
                    var snapped = Math.round(raw / tw.stepSize) * tw.stepSize;
                    if (snapped !== tw.value) {
                        tw.value = snapped;
                        root.touch();
                    }
                }
            }
        }
    }

    component Toggle: RowLayout {
        id: tg
        property string label
        property bool on: true
        Layout.fillWidth: true
        spacing: 8

        Text {
            text: tg.label
            color: root.cSubtle
            font.pixelSize: 13
            Layout.fillWidth: true
        }
        Rectangle {
            width: 40
            height: 22
            radius: 11
            color: tg.on ? root.cPrimary : root.cTrack
            Behavior on color {
                ColorAnimation { duration: 120 }
            }
            Rectangle {
                width: 16
                height: 16
                radius: 8
                y: 3
                x: tg.on ? 21 : 3
                color: tg.on ? root.cOnPrimary : root.cOutline
                Behavior on x {
                    NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
                }
            }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    tg.on = !tg.on;
                    root.touch();
                }
            }
        }
    }

    component Btn: Rectangle {
        id: bt
        property string label
        property bool primary: false
        signal clicked
        implicitHeight: 34
        radius: 10
        color: bt.primary ? root.cPrimary : root.cCardHigh
        Text {
            anchors.centerIn: parent
            text: bt.label
            color: bt.primary ? root.cOnPrimary : root.cOnSurface
            font.pixelSize: 13
            font.bold: bt.primary
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onEntered: parent.opacity = 0.85
            onExited: parent.opacity = 1.0
            onClicked: bt.clicked()
        }
    }

    // ── Layout ──────────────────────────────────────────────────────────────────────────
    Flickable {
        anchors.fill: parent
        anchors.margins: 16
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: body
            width: parent.width
            spacing: 14

            // Header
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "Luminos Look"
                    color: root.cOnSurface
                    font.pixelSize: 20
                    font.bold: true
                }
                Text {
                    text: "Live preview — nothing is saved until you press Save"
                    color: root.cSubtle
                    font.pixelSize: 11
                }
            }

            // Presets
            Text {
                text: "PRESETS"
                color: root.cOnSurface
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 3
                rowSpacing: 6
                columnSpacing: 6
                Repeater {
                    model: ["caelestia", "soft", "glass", "sharp", "chunky", "performance"]
                    Btn {
                        required property string modelData
                        Layout.fillWidth: true
                        label: modelData
                        primary: root.currentPreset === modelData
                        onClicked: root.applyPreset(modelData)
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.cTrack }

            // Shape
            Text {
                text: "SHAPE"
                color: root.cOnSurface
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }
            Tweak { id: sRound;  label: "Corner rounding"; from: 0; to: 40; value: 15 }
            Tweak { id: sBorder; label: "Border width";    from: 0; to: 8;  value: 1 }
            Tweak { id: sGapIn;  label: "Gap between windows"; from: 0; to: 30; value: 5 }
            Tweak { id: sGapOut; label: "Gap to screen edge";  from: 0; to: 60; value: 10 }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.cTrack }

            // Blur & transparency
            Text {
                text: "BLUR & TRANSPARENCY"
                color: root.cOnSurface
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }
            Toggle { id: tBlur; label: "Blur behind windows"; on: true }
            Tweak {
                id: sBlurSize
                label: "Blur strength"
                from: 1
                to: 30
                value: 8
                opacity: tBlur.on ? 1 : 0.35
            }
            Tweak {
                id: sBlurPass
                label: "Blur quality (passes)"
                from: 1
                to: 5
                value: 2
                opacity: tBlur.on ? 1 : 0.35
            }
            Toggle {
                id: tXray
                label: "X-ray (blur desktop, not windows)"
                on: false
                opacity: tBlur.on ? 1 : 0.35
            }
            Tweak {
                id: sOpacity
                label: "Window opacity"
                from: 0.5
                to: 1.0
                stepSize: 0.01
                value: 0.95
                decimals: 2
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.cTrack }

            // Depth & motion
            Text {
                text: "DEPTH & MOTION"
                color: root.cOnSurface
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }
            Toggle { id: tShadow; label: "Window shadows"; on: true }
            Tweak {
                id: sShadow
                label: "Shadow size"
                from: 0
                to: 40
                value: 15
                opacity: tShadow.on ? 1 : 0.35
            }
            Toggle { id: tAnim; label: "Animations"; on: true }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.cTrack }

            // Actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Btn {
                    Layout.fillWidth: true
                    label: "Revert"
                    onClicked: {
                        root.run(["luminos-look", "reset"]);
                        root.currentPreset = "";
                    }
                }
                Btn {
                    Layout.fillWidth: true
                    label: "Save as default"
                    primary: true
                    onClicked: root.run(["luminos-look", "save-live",
                                         "rounding="     + Math.round(sRound.value),
                                         "gaps_in="      + Math.round(sGapIn.value),
                                         "gaps_out="     + Math.round(sGapOut.value),
                                         "border="       + Math.round(sBorder.value),
                                         "blur="         + (tBlur.on ? "true" : "false"),
                                         "blur_size="    + Math.round(sBlurSize.value),
                                         "blur_passes="  + Math.round(sBlurPass.value),
                                         "blur_xray="    + (tXray.on ? "true" : "false"),
                                         "shadow="       + (tShadow.on ? "true" : "false"),
                                         "shadow_range=" + Math.round(sShadow.value),
                                         "anim="         + (tAnim.on ? "true" : "false"),
                                         "opacity="      + sOpacity.value.toFixed(2)])
                }
            }
            Text {
                Layout.fillWidth: true
                text: "Revert restores your saved look and discards everything above."
                color: root.cSubtle
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }
        }
    }
}
