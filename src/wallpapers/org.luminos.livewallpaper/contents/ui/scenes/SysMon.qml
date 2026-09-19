/*
    Native port of contents/samples/luminos-sysmon.html.
    [CHANGE: claude-code | 2026-09-16] DECISION 113
    SPDX-License-Identifier: GPL-3.0-or-later

    The HTML version received these numbers by having main.qml inject
    `window.luminos` into a Chromium page over runJavaScript, twice a minute.
    Here the same DataSource hands them over as a plain object. Same numbers,
    one less browser, and no string-built JavaScript in the path.
*/
import QtQuick

Item {
    id: scene
    anchors.fill: parent

    property bool running: true
    property var stats: ({})

    function num(v) { var n = parseFloat(v); return isNaN(n) ? null : n; }
    function txt(v, dp) { var n = num(v); return n === null ? "--" : n.toFixed(dp === undefined ? 0 : dp); }
    // The sample's own scale: 30 °C reads empty, 90 °C reads full.
    function tempPct(v) { var n = num(v); return n === null ? 0 : Math.max(0, Math.min(1, (n - 30) / 60)); }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.5, 560)
        spacing: 18

        Text {
            text: "Luminos"
            color: "#f2ede4"
            font.pixelSize: 44
            font.letterSpacing: 6
            font.weight: Font.DemiBold
        }

        Repeater {
            model: [
                { label: "CPU Load", value: scene.txt(scene.stats.CPU_LOAD) + "%",  pct: (scene.num(scene.stats.CPU_LOAD) || 0) / 100 },
                { label: "CPU Temp", value: scene.txt(scene.stats.CPU_TEMP) + "°C", pct: scene.tempPct(scene.stats.CPU_TEMP) },
                { label: "iGPU Temp", value: scene.txt(scene.stats.AMD_TEMP) + "°C", pct: scene.tempPct(scene.stats.AMD_TEMP) },
                { label: "Fan CPU",  value: (scene.stats.FAN_CPU || "--") + " rpm", pct: -1 },
                { label: "Profile",  value: scene.stats.PROFILE || "--",            pct: -1 },
                { label: "dGPU",     value: (scene.stats.NV_STATE || "--")
                                            + (scene.stats.NV_PWR && scene.stats.NV_PWR !== "0.0"
                                               ? " " + scene.stats.NV_PWR + "W" : ""), pct: -1 }
            ]
            delegate: Column {
                required property var modelData
                width: parent.width
                spacing: 5
                Row {
                    width: parent.width
                    Text {
                        text: parent.parent.modelData.label
                        color: "#8c8279"; font.pixelSize: 15; font.letterSpacing: 1
                        width: parent.width / 2
                    }
                    Text {
                        text: parent.parent.modelData.value
                        color: "#f2ede4"; font.pixelSize: 15
                        horizontalAlignment: Text.AlignRight
                        width: parent.width / 2
                    }
                }
                Rectangle {
                    visible: parent.modelData.pct >= 0
                    width: parent.width; height: 3; radius: 2
                    color: "#2a2520"
                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, parent.parent.modelData.pct))
                        height: parent.height; radius: parent.radius
                        color: "#ff7a18"
                        Behavior on width { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                    }
                }
            }
        }

        Text {
            text: scene.stats.CPU_LOAD === undefined ? "waiting for luminos-monitor…" : ""
            color: "#8c8279"; font.pixelSize: 12
        }
    }
}
