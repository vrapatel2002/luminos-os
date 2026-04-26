// Luminos OS — Keyboard Backlight KCM UI
// [CHANGE: claude-code | 2026-04-26]

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: root

    // 12 presets — 6 per row = clean 2-row grid
    readonly property var presets: [
        "#ffffff","#ffcc88","#ff0000","#ff6600","#ffff00","#00ff00",
        "#00ffff","#0066ff","#8800ff","#ff00ff","#ff0055","#000000"
    ]

    function hexFromDialog(c) {
        return c.toString().replace("#","").substring(0,6)
    }

    // ── Color dialogs ──────────────────────────────────────────────
    ColorDialog {
        id: colorDialog1
        title: qsTr("Pick Primary Color")
        selectedColor: "#" + kcm.color
        onAccepted: { kcm.color = hexFromDialog(selectedColor); kcm.preview() }
    }
    ColorDialog {
        id: colorDialog2
        title: qsTr("Pick Secondary Color")
        selectedColor: "#" + kcm.color2
        onAccepted: { kcm.color2 = hexFromDialog(selectedColor); kcm.preview() }
    }
    ColorDialog {
        id: autoColorDialog
        title: qsTr("Add Color to Auto Cycle")
        onAccepted: kcm.addAutoColor(hexFromDialog(selectedColor))
    }

    // ── Reusable color-grid component ──────────────────────────────
    component ColorGrid: Item {
        id: cgRoot
        property string currentHex: "ffffff"
        property var    dialog: null
        signal picked(string hex)

        implicitWidth:  gridPart.implicitWidth + Kirigami.Units.smallSpacing * 3 + swatchBox.implicitWidth
        implicitHeight: Math.max(gridPart.implicitHeight, swatchBox.implicitHeight)

        RowLayout {
            anchors.fill: parent
            spacing: Kirigami.Units.smallSpacing * 2

            // 6×2 preset grid
            Grid {
                id: gridPart
                columns: 6
                spacing: 5
                Repeater {
                    model: root.presets
                    Rectangle {
                        width: 26; height: 26; radius: 4
                        color: modelData
                        border.width: ("#" + cgRoot.currentHex).toLowerCase() === modelData.toLowerCase() ? 2 : 1
                        border.color: ("#" + cgRoot.currentHex).toLowerCase() === modelData.toLowerCase()
                                      ? Kirigami.Theme.highlightColor
                                      : Qt.rgba(0, 0, 0, 0.2)
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: cgRoot.picked(modelData.replace("#",""))
                        }
                    }
                }
            }

            // Divider
            Rectangle {
                width: 1; height: 58
                color: Kirigami.Theme.separatorColor
                opacity: 0.4
            }

            // Large current-color square — click to open picker
            ColumnLayout {
                id: swatchBox
                spacing: 3

                Rectangle {
                    width: 54; height: 54; radius: 8
                    color: "#" + cgRoot.currentHex
                    border.color: Kirigami.Theme.separatorColor; border.width: 1

                    Kirigami.Icon {
                        anchors { bottom: parent.bottom; right: parent.right; margins: 4 }
                        source: "color-picker"
                        width: 14; height: 14
                        opacity: 0.75
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { if (cgRoot.dialog) cgRoot.dialog.open() }
                        QQC2.ToolTip.text: qsTr("Click to pick any color")
                        QQC2.ToolTip.visible: containsMouse
                        QQC2.ToolTip.delay: 600
                    }
                }

                QQC2.Label {
                    text: "#" + cgRoot.currentHex.toUpperCase()
                    font.pixelSize: 10
                    opacity: 0.65
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

    // ── Main layout ────────────────────────────────────────────────
    Kirigami.FormLayout {
        width: parent.width

        // ════════════════════════════════════════════════════════════
        // EFFECT MODE + DESCRIPTION
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Effect Mode")
            Kirigami.FormData.isSection: true
        }

        QQC2.ComboBox {
            id: modeCombo
            Kirigami.FormData.label: qsTr("Mode:")
            implicitWidth: Kirigami.Units.gridUnit * 18
            model: [
                { value: "static",    text: qsTr("Static"),    desc: qsTr("Solid single color. Use Auto Cycle below to rotate through colors automatically.") },
                { value: "pulse",     text: qsTr("Pulse"),     desc: qsTr("Single color pulses in a rhythm. Choose color below.") },
                { value: "breathe",   text: qsTr("Breathe"),   desc: qsTr("Color fades in and out. Single color or enable dual mode for two-color crossfade. Adjustable speed.") },
                { value: "highlight", text: qsTr("Highlight"), desc: qsTr("Keys light up with a highlight effect. Choose color below.") },
                { value: "laser",     text: qsTr("Laser"),     desc: qsTr("Laser sweep effect across keys. Choose color below.") },
                { value: "rainbow-cycle", text: qsTr("Rainbow Cycle"), desc: qsTr("Continuous rainbow cycle across the keyboard. Adjustable speed.") },
                { value: "rainbow-wave",  text: qsTr("Rainbow Wave"),  desc: qsTr("Rainbow wave effect with adjustable speed and direction.") },
                { value: "none",      text: qsTr("Off"),       desc: qsTr("Turn off the keyboard backlight.") }
            ]
            textRole: "text"
            currentIndex: {
                for (var i = 0; i < model.length; i++)
                    if (model[i].value === kcm.mode) return i
                return 0
            }
            onActivated: {
                kcm.mode = model[currentIndex].value
                kcm.preview()
            }
        }

        // Mode description label
        QQC2.Label {
            Kirigami.FormData.label: " "
            text: modeCombo.model[modeCombo.currentIndex]
                  ? modeCombo.model[modeCombo.currentIndex].desc : ""
            wrapMode: Text.WordWrap
            font.italic: true
            opacity: 0.65
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        }

        // Direction selector — rainbow-wave only
        QQC2.ComboBox {
            id: directionCombo
            Kirigami.FormData.label: qsTr("Direction:")
            visible: kcm.hasDirection
            implicitWidth: Kirigami.Units.gridUnit * 10
            model: ["Right", "Left", "Up", "Down"]
            currentIndex: {
                var idx = model.indexOf(kcm.direction)
                return idx >= 0 ? idx : 0
            }
            onActivated: {
                kcm.direction = model[currentIndex]
                kcm.preview()
            }
        }

        // Dual-color toggle — breathe only
        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Dual color:")
            visible: kcm.mode === "breathe"
            text: qsTr("Enable two-color crossfade")
            checked: kcm.breatheDual
            onToggled: { kcm.breatheDual = checked; kcm.preview() }
        }

        // ════════════════════════════════════════════════════════════
        // PRIMARY COLOR
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.hasColor
            Kirigami.FormData.label: kcm.hasColor2 ? qsTr("Primary Color") : qsTr("Color")
            Kirigami.FormData.isSection: true
        }

        ColorGrid {
            Kirigami.FormData.label: " "
            visible: kcm.hasColor
            currentHex: kcm.color
            dialog: colorDialog1
            onPicked: (hex) => { kcm.color = hex; kcm.preview() }
        }

        // ════════════════════════════════════════════════════════════
        // SECONDARY COLOR  (breathe / stars)
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.hasColor2
            Kirigami.FormData.label: qsTr("Secondary Color")
            Kirigami.FormData.isSection: true
        }

        ColorGrid {
            Kirigami.FormData.label: " "
            visible: kcm.hasColor2
            currentHex: kcm.color2
            dialog: colorDialog2
            onPicked: (hex) => { kcm.color2 = hex; kcm.preview() }
        }

        // ════════════════════════════════════════════════════════════
        // SPEED
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.hasSpeed
            Kirigami.FormData.label: qsTr("Speed")
            Kirigami.FormData.isSection: true
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Speed:")
            visible: kcm.hasSpeed
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label { text: qsTr("Slow"); opacity: 0.6 }
            QQC2.Slider {
                id: speedSlider
                from: 0; to: 2; stepSize: 1
                value: kcm.speed
                implicitWidth: Kirigami.Units.gridUnit * 10
                onMoved: { kcm.speed = Math.round(value); kcm.preview() }
            }
            QQC2.Label { text: qsTr("Fast"); opacity: 0.6 }
            QQC2.Label {
                text: [qsTr("Low"), qsTr("Med"), qsTr("High")][Math.round(speedSlider.value)]
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 3
            }
        }

        // ════════════════════════════════════════════════════════════
        // BRIGHTNESS
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Brightness")
            Kirigami.FormData.isSection: true
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Level:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label { text: qsTr("Off"); opacity: 0.6 }
            QQC2.Slider {
                id: brightSlider
                from: 1; to: 3; stepSize: 1
                value: kcm.brightness
                implicitWidth: Kirigami.Units.gridUnit * 10
                onMoved: { kcm.brightness = Math.round(value); kcm.preview() }
            }
            QQC2.Label { text: qsTr("Max"); opacity: 0.6 }
            QQC2.Label {
                text: Math.round(brightSlider.value) + "/3"
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
            }
        }

        // ════════════════════════════════════════════════════════════
        // AUTO COLOR CYCLE
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Auto Color Cycle")
            Kirigami.FormData.isSection: true
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Enable:")
            text: qsTr("Rotate colors automatically on a timer")
            checked: kcm.autoColorEnabled
            onToggled: kcm.autoColorEnabled = checked
        }

        QQC2.Label {
            visible: kcm.autoColorEnabled
            Kirigami.FormData.label: " "
            text: qsTr("Works with Static, Pulse, and other single-color modes.")
            font.italic: true; opacity: 0.65
            wrapMode: Text.WordWrap
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Interval:")
            visible: kcm.autoColorEnabled
            spacing: Kirigami.Units.smallSpacing
            QQC2.Slider {
                id: intervalSlider
                from: 1; to: 60; stepSize: 1
                value: kcm.autoColorInterval
                implicitWidth: Kirigami.Units.gridUnit * 12
                onMoved: kcm.autoColorInterval = Math.round(value)
            }
            QQC2.Label {
                text: Math.round(intervalSlider.value) + qsTr("s")
                font.bold: true
            }
        }

        // Auto cycle color list
        Item {
            Kirigami.FormData.label: qsTr("Colors:")
            visible: kcm.autoColorEnabled
            implicitWidth: autoFlow.implicitWidth
            implicitHeight: autoFlow.implicitHeight

            Flow {
                id: autoFlow
                spacing: 5

                Repeater {
                    model: kcm.autoColors
                    Rectangle {
                        width: 32; height: 32; radius: 5
                        color: {
                            var h = modelData
                            return Qt.rgba(
                                parseInt(h.substring(0,2),16)/255,
                                parseInt(h.substring(2,4),16)/255,
                                parseInt(h.substring(4,6),16)/255, 1)
                        }
                        border.color: Kirigami.Theme.separatorColor; border.width: 1

                        Rectangle {
                            anchors { top: parent.top; right: parent.right; margins: -3 }
                            width: 14; height: 14; radius: 7
                            color: "#cc2200"
                            QQC2.Label { anchors.centerIn: parent; text: "×"; font.pixelSize: 10; font.bold: true; color: "white" }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: kcm.removeAutoColor(index) }
                        }
                    }
                }

                // Add-color cell
                Rectangle {
                    width: 32; height: 32; radius: 5
                    color: "transparent"
                    border.color: Kirigami.Theme.separatorColor; border.width: 1
                    Kirigami.Icon { anchors.centerIn: parent; source: "list-add"; width: 18; height: 18; opacity: 0.55 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: autoColorDialog.open() }
                }
            }
        }

        // ════════════════════════════════════════════════════════════
        // PREVIEW
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.isSection: true }

        QQC2.Button {
            Kirigami.FormData.label: " "
            text: qsTr("Preview")
            icon.name: "view-preview"
            onClicked: kcm.preview()
        }
    }
}
