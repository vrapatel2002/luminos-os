import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    // [CHANGE: claude-code | 2026-06-14] Tokenized — colors/radii from design/luminos-tokens.json
    Theme { id: theme }

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
                    ? theme.error
                    : root.currentMode === "Balanced"
                    ? theme.warning : theme.success
            }

            PC3.Label {
                color: theme.textPrimary
                font.pixelSize: 11
                text: root.currentMode
            }

            PC3.Label {
                color: parseFloat(root.currentTemp) > 70
                    ? theme.error : theme.textPrimary
                font.pixelSize: 11
                text: "🌡" + root.currentTemp
            }

            PC3.Label {
                color: theme.textSecondary
                font.pixelSize: 11
                text: "🌀" + root.fanSpeed
            }

            Rectangle {
                width: 8; height: 8
                radius: 4
                color: root.nvidiaAwake
                    ? theme.warning : theme.textDisabled
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
            color: theme.surface
            radius: theme.radiusDefault

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                PC3.Label {
                    text: "Luminos Power"
                    color: theme.textPrimary
                    font.pixelSize: 13
                    font.bold: true
                }

                // Mode row
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "Mode"
                        color: theme.textSecondary
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: 80; height: 22
                        radius: theme.radiusFull
                        color: root.currentMode === "Performance"
                            ? Qt.rgba(theme.error.r, theme.error.g, theme.error.b, 0.13)
                            : root.currentMode === "Balanced"
                            ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.13)
                            : Qt.rgba(theme.success.r, theme.success.g, theme.success.b, 0.13)
                        border.color:
                            root.currentMode === "Performance" ? theme.error
                            : root.currentMode === "Balanced" ? theme.warning
                            : theme.success
                        PC3.Label {
                            anchors.centerIn: parent
                            text: root.currentMode
                            color: theme.textPrimary
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
                            color: theme.textSecondary
                            font.pixelSize: 11
                        }
                        Item { Layout.fillWidth: true }
                        PC3.Label {
                            text: root.currentTemp
                            color: theme.textPrimary
                            font.pixelSize: 11
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 6; radius: 3
                        color: theme.trackColor
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
                                return t > 80 ? theme.error
                                    : t > 65 ? theme.warning
                                    : theme.success
                            }
                        }
                    }
                }

                // Fan speed
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "Fan Speed"
                        color: theme.textSecondary
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.fanSpeed
                        color: theme.accent
                        font.pixelSize: 11
                    }
                }

                // NVIDIA status
                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label {
                        text: "NVIDIA GPU"
                        color: theme.textSecondary
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    PC3.Label {
                        text: root.nvidiaAwake ?
                            "⚡ Active" : "💤 Sleeping"
                        color: root.nvidiaAwake ?
                            theme.warning : theme.success
                        font.pixelSize: 11
                    }
                }

                // Manual mode buttons
                PC3.Label {
                    text: "Manual Override"
                    color: theme.textDisabled
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
                            height: 28; radius: theme.radiusMd
                            color: root.currentMode === modelData
                                ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.13)
                                : theme.surfaceElevated
                            border.color:
                                root.currentMode === modelData
                                ? theme.accent : theme.trackColor
                            PC3.Label {
                                anchors.centerIn: parent
                                text: modelData
                                color: theme.textPrimary
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
