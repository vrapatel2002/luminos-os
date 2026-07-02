// [CHANGE: claude-code | 2026-07-01] org.luminos.monitorwidget v1.0
// Plasma replacement for the konsole/btop monitor window (saved ~55M unique RAM +
// ~5% CPU per open window). Single data feed: `luminos-monitor stats` (KEY=VALUE).
// dGPU sleep-guard lives in the script — this widget never wakes a suspended GPU.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    Theme { id: theme }

    // ── Stats (defaults shown until first poll) ─────────────────
    property string cpuTemp: "--"
    property string cpuAvg: "--"
    property string cpuLoad: "--"
    property string epp: "--"
    property string profile: "--"
    property string amdTemp: "--"
    property string amdLoad: "--"
    property string amdPpt: "--"
    property string amdFreq: "--"
    property string nvTemp: "--"
    property string nvPwr: "--"
    property string nvLoad: "--"
    property string nvState: "--"
    property string nvRuntime: "--"
    property string nvmeTemp: "--"
    property string wifiTemp: "--"
    property string fanCpu: "--"
    property string fanGpu: "--"
    property string fanMid: "--"
    property string batPct: "--"
    property string batStatus: "--"

    readonly property bool nvSleeping: nvRuntime === "suspended"

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            parseStats(data["stdout"] || "")
            disconnectSource(source)
        }
    }

    function parseStats(text) {
        var lines = text.split("\n")
        var s = {}
        for (var i = 0; i < lines.length; i++) {
            var eq = lines[i].indexOf("=")
            if (eq > 0)
                s[lines[i].slice(0, eq)] = lines[i].slice(eq + 1).trim()
        }
        if (s["CPU_TEMP"] !== undefined) {
            root.cpuTemp  = s["CPU_TEMP"]  || "--"
            root.cpuAvg   = s["CPU_AVG"]   || "--"
            root.cpuLoad  = s["CPU_LOAD"]  || "--"
            root.epp      = s["EPP"]       || "--"
            root.profile  = s["PROFILE"]   || "--"
            root.amdTemp  = s["AMD_TEMP"]  || "--"
            root.amdLoad  = s["AMD_LOAD"]  || "--"
            root.amdPpt   = s["AMD_PPT"]   || "--"
            root.amdFreq  = s["AMD_FREQ"]  || "--"
            root.nvTemp   = s["NV_TEMP"]   || "--"
            root.nvPwr    = s["NV_PWR"]    || "--"
            root.nvLoad   = s["NV_LOAD"]   || "--"
            root.nvState  = s["NV_STATE"]  || "--"
            root.nvRuntime = s["NV_RUNTIME"] || "--"
            root.nvmeTemp = s["NVME_TEMP"] || "--"
            root.wifiTemp = s["WIFI_TEMP"] || "--"
            root.fanCpu   = s["FAN_CPU"]   || "--"
            root.fanGpu   = s["FAN_GPU"]   || "--"
            root.fanMid   = s["FAN_MID"]   || "--"
            root.batPct   = s["BAT_PCT"]   || "--"
            root.batStatus = s["BAT_STATUS"] || "--"
        }
    }

    function refresh() {
        executable.connectSource("/usr/local/bin/luminos-monitor stats")
    }

    // Fast poll only while the popup is open; slow trickle for the panel chip
    Timer {
        interval: root.expanded ? 2000 : 15000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
    onExpandedChanged: if (expanded) refresh()

    function tempColor(t) {
        var v = parseFloat(t)
        if (isNaN(v)) return theme.textSecondary
        return v > 80 ? theme.error : v > 65 ? theme.warning : theme.success
    }

    // ── Compact: CPU temp + fan + dGPU dot ──────────────────────
    compactRepresentation: Item {
        Layout.minimumWidth: row.implicitWidth + 8
        Layout.minimumHeight: 24

        MouseArea {
            anchors.fill: parent
            onClicked: root.expanded = !root.expanded
        }

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 6

            PC3.Label {
                text: root.cpuTemp + "°"
                color: root.tempColor(root.cpuTemp)
                font.pixelSize: 11
                font.family: theme.fontMono
            }
            PC3.Label {
                text: root.fanCpu + "rpm"
                color: theme.textSecondary
                font.pixelSize: 11
                font.family: theme.fontMono
            }
            Rectangle {
                width: 8; height: 8; radius: 4
                color: root.nvSleeping ? theme.textDisabled : theme.warning
                PC3.ToolTip.text: root.nvSleeping
                    ? "dGPU: sleeping (0W)"
                    : "dGPU: " + root.nvState + " " + root.nvPwr + "W"
                PC3.ToolTip.visible: dotMA.containsMouse
                MouseArea {
                    id: dotMA
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

    // ── Full popup: the old terminal box, as a widget ───────────
    fullRepresentation: Item {
        width: 340
        height: col.implicitHeight + 32

        Rectangle {
            anchors.fill: parent
            color: theme.surface
            radius: theme.radiusDefault

            ColumnLayout {
                id: col
                anchors.fill: parent
                anchors.margins: theme.spaceMd
                spacing: theme.spaceSm

                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "Luminos Monitor"
                        color: theme.textPrimary
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.profile + " · " + root.epp
                        color: theme.textSecondary
                        font.pixelSize: 10
                    }
                }

                // Three device columns
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: theme.spaceSm
                    rowSpacing: 2

                    // Headers
                    PC3.Label { text: "CPU";        color: theme.accent; font.pixelSize: 11; font.bold: true }
                    PC3.Label { text: "iGPU 780M";  color: theme.accent; font.pixelSize: 11; font.bold: true }
                    PC3.Label { text: "dGPU 4050";  color: theme.accent; font.pixelSize: 11; font.bold: true }

                    // Temps
                    PC3.Label { text: root.cpuTemp + "°C"; color: root.tempColor(root.cpuTemp); font.pixelSize: 12; font.family: theme.fontMono }
                    PC3.Label { text: root.amdTemp + "°C"; color: root.tempColor(root.amdTemp); font.pixelSize: 12; font.family: theme.fontMono }
                    PC3.Label {
                        text: root.nvSleeping ? "💤" : root.nvTemp + "°C"
                        color: root.nvSleeping ? theme.success : root.tempColor(root.nvTemp)
                        font.pixelSize: 12; font.family: theme.fontMono
                    }

                    // Load
                    PC3.Label { text: root.cpuLoad + "%";  color: theme.textPrimary; font.pixelSize: 11; font.family: theme.fontMono }
                    PC3.Label { text: root.amdLoad + "%";  color: theme.textPrimary; font.pixelSize: 11; font.family: theme.fontMono }
                    PC3.Label {
                        text: root.nvSleeping ? "off" : root.nvLoad + "%"
                        color: theme.textPrimary; font.pixelSize: 11; font.family: theme.fontMono
                    }

                    // Power
                    PC3.Label { text: "avg " + root.cpuAvg + "°"; color: theme.textSecondary; font.pixelSize: 11; font.family: theme.fontMono }
                    PC3.Label { text: root.amdPpt + "W"; color: theme.textSecondary; font.pixelSize: 11; font.family: theme.fontMono }
                    PC3.Label {
                        text: root.nvSleeping ? "0W" : root.nvPwr + "W"
                        color: root.nvSleeping ? theme.success : theme.textSecondary
                        font.pixelSize: 11; font.family: theme.fontMono
                    }

                    // Freq / state
                    PC3.Label { text: "";                        font.pixelSize: 11 }
                    PC3.Label { text: root.amdFreq + "MHz"; color: theme.textDisabled; font.pixelSize: 10; font.family: theme.fontMono }
                    PC3.Label {
                        text: root.nvSleeping ? "D3cold" : root.nvState
                        color: theme.textDisabled; font.pixelSize: 10; font.family: theme.fontMono
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: theme.borderDefault }

                // Fans
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label { text: "Fans"; color: theme.textSecondary; font.pixelSize: 11 }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: "C " + root.fanCpu + " · G " + root.fanGpu + " · M " + root.fanMid
                        color: theme.textPrimary; font.pixelSize: 11; font.family: theme.fontMono
                    }
                }

                // NVMe / WiFi
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label { text: "NVMe / WiFi"; color: theme.textSecondary; font.pixelSize: 11 }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.nvmeTemp + "° / " + root.wifiTemp + "°"
                        color: theme.textPrimary; font.pixelSize: 11; font.family: theme.fontMono
                    }
                }

                // Battery
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label { text: "Battery"; color: theme.textSecondary; font.pixelSize: 11 }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.batPct + "% · " + root.batStatus
                        color: root.batStatus === "AC" ? theme.success : theme.warning
                        font.pixelSize: 11; font.family: theme.fontMono
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: theme.borderDefault }

                // Escape hatch: full btop when you actually need a process list
                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spaceSm

                    Rectangle {
                        Layout.fillWidth: true
                        height: 26; radius: theme.radiusMd
                        color: btopMA.containsMouse ? theme.surfaceOverlay : theme.surfaceElevated
                        border.color: theme.borderDefault
                        PC3.Label {
                            anchors.centerIn: parent
                            text: "btop (full)"
                            color: theme.textPrimary
                            font.pixelSize: 10
                        }
                        MouseArea {
                            id: btopMA
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                executable.connectSource("konsole -e luminos-monitor btop")
                                root.expanded = false
                            }
                        }
                    }
                }
            }
        }
    }
}
