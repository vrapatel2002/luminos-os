import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.plasma5support 0.1 as P5Support

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    property string currentMode: "Quiet"
    property string currentTemp: "0°C"
    property string fanSpeed: "0 RPM"
    property string tdp: "15W"
    property string gpuTemp: "0°C"
    property bool nvidiaAwake: false

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            var stdout = data["stdout"] || ""
            if (source.includes("luminos-power")) {
                parsePower(stdout)
            } else if (source.includes("sensors")) {
                parseSensors(stdout)
            } else if (source.includes("nvidia")) {
                root.nvidiaAwake = stdout.includes("W")
            }
            disconnectSource(source)
        }

        function exec(cmd) {
            connectSource(cmd)
        }
    }

    function parsePower(text) {
        if (text.includes("Performance"))
            root.currentMode = "Performance"
        else if (text.includes("Balanced"))
            root.currentMode = "Balanced"
        else
            root.currentMode = "Quiet"
    }

    function parseSensors(text) {
        var lines = text.split("\n")
        for (var i = 0; i < lines.length; i++) {
            var l = lines[i]
            if (l.includes("temp1") &&
                l.includes("+") &&
                !root.currentTemp.includes("°C")) {
                var match = l.match(/\+(\d+\.\d+)°C/)
                if (match)
                    root.currentTemp = match[1] + "°C"
            }
            if (l.includes("cpu_fan")) {
                var rpm = l.match(/(\d+) RPM/)
                if (rpm) root.fanSpeed = rpm[1] + " RPM"
            }
        }
    }

    function updateAll() {
        // [CHANGE: gemini-cli | 2026-05-11]
        executable.exec(
            "sudo journalctl -u luminos-power " +
            "--no-pager -n 1 | " +
            "grep -oE 'profile=[A-Za-z]+' | " +
            "cut -d= -f2"
        )
        executable.exec(
            "sensors 2>/dev/null | " +
            "grep -E 'temp1|cpu_fan'"
        )
        executable.exec(
            "nvidia-smi --query-gpu=" +
            "power.draw --format=csv,noheader " +
            "2>/dev/null | head -1"
        )
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: root.updateAll()
    }

    Component.onCompleted: root.updateAll()

    compactRepresentation: Item {
        Layout.minimumWidth: 200
        Layout.minimumHeight: 24

        RowLayout {
            anchors.fill: parent
            anchors.margins: 4
            spacing: 8

            // Mode indicator
            Rectangle {
                width: 8; height: 8
                radius: 4
                color: root.currentMode === "Performance"
                    ? "#ff4444"
                    : root.currentMode === "Balanced"
                    ? "#ffaa00" : "#00cc66"
            }

            PC3.Label {
                color: "#e0e0e0"
                font.pixelSize: 11
                text: root.currentMode
            }

            PC3.Label {
                color: parseFloat(root.currentTemp) > 70
                    ? "#ff4444" : "#e0e0e0"
                font.pixelSize: 11
                text: "🌡" + root.currentTemp
            }

            PC3.Label {
                color: "#888"
                font.pixelSize: 11
                text: "🌀" + root.fanSpeed
            }

            Rectangle {
                width: 8; height: 8
                radius: 4
                color: root.nvidiaAwake
                    ? "#ff6600" : "#444"
                visible: true
                
                PC3.ToolTip.text: root.nvidiaAwake
                    ? "NVIDIA: Active"
                    : "NVIDIA: Sleep"
                PC3.ToolTip.visible: compactMA.containsMouse
                
                MouseArea {
                    id: compactMA
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

    fullRepresentation: Item {
        width: 280
        height: 250

        Rectangle {
            anchors.fill: parent
            color: "#111111"
            radius: 10

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                PC3.Label {
                    text: "Luminos Power"
                    color: "#e0e0e0"
                    font.pixelSize: 13
                    font.bold: true
                }

                // Mode row
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "Mode"
                        color: "#888"
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: 80; height: 22
                        radius: 11
                        color: root.currentMode ===
                            "Performance" ? "#ff444422"
                            : root.currentMode ===
                            "Balanced" ? "#ffaa0022"
                            : "#00cc6622"
                        border.color:
                            root.currentMode ===
                            "Performance" ? "#ff4444"
                            : root.currentMode ===
                            "Balanced" ? "#ffaa00"
                            : "#00cc66"
                        PC3.Label {
                            anchors.centerIn: parent
                            text: root.currentMode
                            color: "#e0e0e0"
                            font.pixelSize: 11
                        }
                    }
                }

                // Temperature
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true
                    RowLayout {
                        PC3.Label {
                            text: "CPU Temp"
                            color: "#888"
                            font.pixelSize: 11
                        }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: root.currentTemp
                            color: "#e0e0e0"
                            font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: "#222"
                        Rectangle {
                            width: {
                                var t = parseFloat(
                                    root.currentTemp)
                                return parent.width *
                                    Math.min(t/100, 1)
                            }
                            height: 6; radius: 3
                            color: {
                                var t = parseFloat(
                                    root.currentTemp)
                                return t > 80 ?
                                    "#ff4444" : t > 65 ?
                                    "#ffaa00" : "#00cc66"
                            }
                        }
                    }
                }

                // Fan speed
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "Fan Speed"
                        color: "#888"
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.fanSpeed
                        color: "#0080ff"
                        font.pixelSize: 11
                    }
                }

                // NVIDIA status
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "NVIDIA GPU"
                        color: "#888"
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.nvidiaAwake ?
                            "⚡ Active" : "💤 Sleeping"
                        color: root.nvidiaAwake ?
                            "#ff6600" : "#00cc66"
                        font.pixelSize: 11
                    }
                }

                // Manual mode buttons
                PC3.Label {
                    text: "Manual Override"
                    color: "#555"
                    font.pixelSize: 10
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: ["Quiet","Balanced",
                                "Performance"]
                        Rectangle {
                            Layout.fillWidth: true
                            height: 28; radius: 6
                            color: root.currentMode
                                === modelData ?
                                "#0080ff22" : "#1a1a1a"
                            border.color:
                                root.currentMode ===
                                modelData ?
                                "#0080ff" : "#333"
                            PC3.Label {
                                anchors.centerIn: parent
                                text: modelData
                                color: "#e0e0e0"
                                font.pixelSize: 10
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    executable.exec(
                                        "asusctl profile set "
                                        + modelData)
                                    root.currentMode =
                                        modelData
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
