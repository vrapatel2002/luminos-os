import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.plasma5support 0.1 as P5Support
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.plasmoid 2.0

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    // [CHANGE: claude-code | 2026-06-14] Tokenized — colors/radii from design/luminos-tokens.json
    Theme { id: theme }

    property var stats: ({
        total: 15,
        used: 10,
        available: 5,
        hot: 0,
        cold: 0,
        zram_used: 0,
        zram_total: 8,
        zram_saved: 0
    })

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            var stdout = data["stdout"]
            console.log("RAM Widget DEBUG: New data from " + sourceName)

            if (sourceName.includes("/metrics")) {
                parseMetrics(stdout)
            } else if (sourceName.includes("/meminfo")) {
                console.log("RAM Widget DEBUG: meminfo raw: " + stdout)
                parseMemInfo(stdout)
            }
            disconnectSource(sourceName)
        }
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: updateStats()
    }

    function updateStats() {
        console.log("RAM Widget DEBUG: updateStats() triggered")
        executable.connectSource("curl -s http://localhost:9091/metrics")
        executable.connectSource("curl -s http://localhost:9091/meminfo")
    }

    function parseMetrics(text) {
        if (!text) return
        var lines = text.split('\n')
        var s = stats
        for (var i = 0; i < lines.length; i++) {
            var l = lines[i]
            if (l.startsWith('#')) continue
            if (l.includes('luminos_ram_hot_set_size '))
                s.hot = parseFloat(l.split(' ')[1]) || 0
            if (l.includes('luminos_ram_cold_set_size '))
                s.cold = parseFloat(l.split(' ')[1]) || 0
        }
        stats = s
    }

    function parseMemInfo(text) {
        if (!text) return
        try {
            var d = JSON.parse(text)
            console.log("RAM Widget DEBUG: zram_used parsed: " + d.zram_used)
            var s = stats
            s.total = d.total
            s.used = d.used
            s.available = d.available
            s.zram_used = d.zram_used
            s.zram_total = d.zram_total
            s.zram_saved = d.zram_saved
            stats = s
        } catch (e) {
            console.log("RAM Widget DEBUG: Error parsing meminfo JSON: " + e)
        }
    }

    compactRepresentation: Item {
        Layout.minimumWidth: 120
        Layout.minimumHeight: 24

        RowLayout {
            anchors.fill: parent
            anchors.margins: 4
            spacing: 6

            Rectangle {
                width: 8; height: 8
                radius: 4
                color: stats.available < 2 ? theme.error :
                       stats.available < 4 ? theme.warning : theme.success
            }

            PC3.Label {
                color: theme.textPrimary
                font.pixelSize: 11
                font.family: theme.fontPrimary
                text: {
                    var pct = Math.round(stats.used / stats.total * 100)
                    return "RAM " + pct + "%"
                }
            }

            PC3.Label {
                color: theme.accent
                font.pixelSize: 10
                font.family: theme.fontPrimary
                text: "❄" + stats.cold
                visible: stats.cold > 0
            }

            PC3.Label {
                color: theme.textSecondary
                font.pixelSize: 10
                font.family: theme.fontPrimary
                text: "Z:" + stats.zram_used.toFixed(1) + "G"
            }
        }
    }

    fullRepresentation: Item {
        width: 280
        height: 220

        Rectangle {
            anchors.fill: parent
            color: theme.surface
            radius: theme.radiusDefault

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                PC3.Label {
                    text: "Luminos RAM"
                    color: theme.textPrimary
                    font.pixelSize: 13
                    font.bold: true
                }

                // RAM bar
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true

                    RowLayout {
                        PC3.Label { text: "RAM"; color: theme.textSecondary; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: stats.used.toFixed(1) + "GB / " + stats.total.toFixed(0) + "GB"
                            color: theme.textPrimary; font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: theme.trackColor
                        Rectangle {
                            width: parent.width * Math.min(1.0, (stats.used / (stats.total || 1)))
                            height: 6; radius: 3
                            color: stats.used/(stats.total || 1) > 0.85 ? theme.error :
                                   stats.used/(stats.total || 1) > 0.7 ? theme.warning : theme.accent
                        }
                    }
                }

                // ZRAM bar
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true

                    RowLayout {
                        PC3.Label { text: "ZRAM"; color: theme.textSecondary; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: stats.zram_used.toFixed(1) + "GB / " + stats.zram_total + "GB"
                            color: theme.accent; font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: theme.trackColor
                        Rectangle {
                            width: parent.width * Math.min(1.0, (stats.zram_used / (stats.zram_total || 1)))
                            height: 6; radius: 3
                            color: Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.53)
                        }
                    }
                }

                // Hot/Cold stats
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: theme.radiusMd
                        color: theme.surfaceElevated
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: "🔥 " + stats.hot
                                color: theme.warning
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Hot"
                                color: theme.textDisabled
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: theme.radiusMd
                        color: theme.surfaceElevated
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: "❄ " + stats.cold
                                color: theme.accent
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Cold"
                                color: theme.textDisabled
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: theme.radiusMd
                        color: theme.surfaceElevated
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: stats.available.toFixed(1) + "G"
                                color: theme.success
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Free"
                                color: theme.textDisabled
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
        }

        Component.onCompleted: root.updateStats()
    }
}
