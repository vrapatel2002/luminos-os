import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.plasmoid 2.0

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation
    
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

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: updateStats()
    }

    function updateStats() {
        var xhr = new XMLHttpRequest()
        xhr.open("GET", "http://localhost:9091/metrics")
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                parseMetrics(xhr.responseText)
            }
        }
        xhr.send()
    }

    function parseMetrics(text) {
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
        // Read /proc/meminfo via separate call
        var xhr2 = new XMLHttpRequest()
        xhr2.open("GET", "http://localhost:9091/meminfo")
        xhr2.onreadystatechange = function() {
            if (xhr2.readyState === 4 && xhr2.status === 200) {
                var d = JSON.parse(xhr2.responseText)
                s.total = d.total
                s.used = d.used
                s.available = d.available
                s.zram_used = d.zram_used
                s.zram_total = d.zram_total
                s.zram_saved = d.zram_saved
                stats = s
            }
        }
        xhr2.send()
        stats = s
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
                color: stats.available < 2 ? "#ff4444" :
                       stats.available < 4 ? "#ffaa00" : "#00cc66"
            }

            PC3.Label {
                color: "#e0e0e0"
                font.pixelSize: 11
                font.family: "Inter"
                text: {
                    var pct = Math.round(stats.used / stats.total * 100)
                    return "RAM " + pct + "%"
                }
            }

            PC3.Label {
                color: "#0080ff"
                font.pixelSize: 10
                font.family: "Inter"
                text: "❄" + stats.cold
                visible: stats.cold > 0
            }

            PC3.Label {
                color: "#888"
                font.pixelSize: 10
                font.family: "Inter"
                text: "Z:" + stats.zram_used.toFixed(1) + "G"
            }
        }
    }

    fullRepresentation: Item {
        width: 280
        height: 220

        Rectangle {
            anchors.fill: parent
            color: "#111111"
            radius: 10

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                PC3.Label {
                    text: "Luminos RAM"
                    color: "#e0e0e0"
                    font.pixelSize: 13
                    font.bold: true
                }

                // RAM bar
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true

                    RowLayout {
                        PC3.Label { text: "RAM"; color: "#888"; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: stats.used.toFixed(1) + "GB / " + stats.total.toFixed(0) + "GB"
                            color: "#e0e0e0"; font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: "#222"
                        Rectangle {
                            width: parent.width * Math.min(1.0, (stats.used / stats.total))
                            height: 6; radius: 3
                            color: stats.used/stats.total > 0.85 ? "#ff4444" :
                                   stats.used/stats.total > 0.7 ? "#ffaa00" : "#0080ff"
                        }
                    }
                }

                // ZRAM bar
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true

                    RowLayout {
                        PC3.Label { text: "ZRAM"; color: "#888"; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: stats.zram_used.toFixed(1) + "GB / " + stats.zram_total + "GB"
                            color: "#0080ff"; font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: "#222"
                        Rectangle {
                            width: parent.width * Math.min(1.0, (stats.zram_used / stats.zram_total))
                            height: 6; radius: 3
                            color: "#0080ff88"
                        }
                    }
                }

                // Hot/Cold stats
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: 8
                        color: "#1a1a1a"
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: "🔥 " + stats.hot
                                color: "#ff6644"
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Hot"
                                color: "#555"
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: 8
                        color: "#1a1a1a"
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: "❄ " + stats.cold
                                color: "#0080ff"
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Cold"
                                color: "#555"
                                font.pixelSize: 10
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48; radius: 8
                        color: "#1a1a1a"
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2
                            PC3.Label {
                                text: stats.available.toFixed(1) + "G"
                                color: "#00cc66"
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignHCenter
                            }
                            PC3.Label {
                                text: "Free"
                                color: "#555"
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
