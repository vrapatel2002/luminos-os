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

    // ── Preset color palette ───────────────────────────────────────
    readonly property var presets: [
        "#ffffff","#ffefcc","#ff0000","#ff6600","#ffff00",
        "#00ff00","#00ffff","#0000ff","#8800ff","#ff00ff",
        "#ff0088","#000000"
    ]

    // ── Color dialogs ──────────────────────────────────────────────
    ColorDialog {
        id: colorDialog1
        title: qsTr("Primary Color")
        selectedColor: "#" + kcm.color
        onAccepted: {
            var c = selectedColor.toString().replace("#","").substring(0,6)
            kcm.color = c
        }
    }
    ColorDialog {
        id: colorDialog2
        title: qsTr("Secondary Color")
        selectedColor: "#" + kcm.color2
        onAccepted: {
            var c = selectedColor.toString().replace("#","").substring(0,6)
            kcm.color2 = c
        }
    }
    ColorDialog {
        id: autoColorDialog
        title: qsTr("Add Color to Cycle")
        onAccepted: {
            var c = selectedColor.toString().replace("#","").substring(0,6)
            kcm.addAutoColor(c)
        }
    }

    // ── Helpers ────────────────────────────────────────────────────
    function colorSwatch(hex) {
        return Qt.rgba(
            parseInt(hex.substring(0,2),16)/255,
            parseInt(hex.substring(2,4),16)/255,
            parseInt(hex.substring(4,6),16)/255, 1)
    }

    Kirigami.FormLayout {
        width: parent.width

        // ════════════════════════════════════════════════════════════
        // MODE
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.label: qsTr("Effect Mode"); Kirigami.FormData.isSection: true }

        QQC2.ComboBox {
            Kirigami.FormData.label: qsTr("Mode:")
            id: modeCombo
            model: [
                {text: qsTr("Static (solid color)"),      value: "static"},
                {text: qsTr("Breathe (two-color fade)"),  value: "breathe"},
                {text: qsTr("Stars (two-color sparkle)"), value: "stars"},
                {text: qsTr("Pulse"),                     value: "pulse"},
                {text: qsTr("Rainbow Cycle (auto)"),      value: "rainbow-cycle"},
                {text: qsTr("Rainbow Wave (auto)"),       value: "rainbow-wave"},
                {text: qsTr("Highlight"),                 value: "highlight"},
                {text: qsTr("Laser"),                     value: "laser"},
                {text: qsTr("Ripple"),                    value: "ripple"},
                {text: qsTr("Comet"),                     value: "comet"},
                {text: qsTr("Flash"),                     value: "flash"},
                {text: qsTr("Rain (auto)"),               value: "rain"},
                {text: qsTr("Off"),                       value: "none"}
            ]
            textRole: "text"
            currentIndex: { for (var i = 0; i < model.length; i++) if (model[i].value === kcm.mode) return i; return 0 }
            onActivated: kcm.mode = model[currentIndex].value
        }

        // ════════════════════════════════════════════════════════════
        // PRIMARY COLOR (hidden for rainbow / rain / none)
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.hasColor
            Kirigami.FormData.label: kcm.hasColor2 ? qsTr("Primary Color") : qsTr("Color")
            Kirigami.FormData.isSection: true
        }

        // Preset palette
        Flow {
            Kirigami.FormData.label: qsTr("Presets:")
            visible: kcm.hasColor
            spacing: 4
            Repeater {
                model: root.presets
                Rectangle {
                    width: 24; height: 24; radius: 4
                    color: modelData
                    border.color: ("#" + kcm.color).toLowerCase() === modelData.toLowerCase()
                                  ? Kirigami.Theme.highlightColor : Kirigami.Theme.separatorColor
                    border.width: ("#" + kcm.color).toLowerCase() === modelData.toLowerCase() ? 2 : 1
                    MouseArea { anchors.fill: parent; onClicked: kcm.color = modelData.replace("#","") }
                }
            }
        }

        // Color picker row
        RowLayout {
            Kirigami.FormData.label: qsTr("Custom:")
            visible: kcm.hasColor
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                width: 32; height: 32; radius: 6
                color: "#" + kcm.color
                border.color: Kirigami.Theme.separatorColor; border.width: 1
                MouseArea { anchors.fill: parent; onClicked: colorDialog1.open() }
                Kirigami.Icon { anchors.centerIn: parent; source: "color-picker"; width: 16; height: 16; opacity: 0.5 }
            }

            QQC2.Label { text: "#"; opacity: 0.6 }
            QQC2.TextField {
                id: colorHex1
                text: kcm.color
                maximumLength: 6
                implicitWidth: Kirigami.Units.gridUnit * 5
                onEditingFinished: if (text.length === 6) kcm.color = text
            }

            QQC2.Button { text: qsTr("Pick Color"); icon.name: "color-management"; onClicked: colorDialog1.open() }
        }

        // ════════════════════════════════════════════════════════════
        // SECONDARY COLOR (breathe / stars only)
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.hasColor2
            Kirigami.FormData.label: qsTr("Secondary Color")
            Kirigami.FormData.isSection: true
        }

        Flow {
            Kirigami.FormData.label: qsTr("Presets:")
            visible: kcm.hasColor2
            spacing: 4
            Repeater {
                model: root.presets
                Rectangle {
                    width: 24; height: 24; radius: 4
                    color: modelData
                    border.color: ("#" + kcm.color2).toLowerCase() === modelData.toLowerCase()
                                  ? Kirigami.Theme.highlightColor : Kirigami.Theme.separatorColor
                    border.width: ("#" + kcm.color2).toLowerCase() === modelData.toLowerCase() ? 2 : 1
                    MouseArea { anchors.fill: parent; onClicked: kcm.color2 = modelData.replace("#","") }
                }
            }
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Custom:")
            visible: kcm.hasColor2
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                width: 32; height: 32; radius: 6
                color: "#" + kcm.color2
                border.color: Kirigami.Theme.separatorColor; border.width: 1
                MouseArea { anchors.fill: parent; onClicked: colorDialog2.open() }
                Kirigami.Icon { anchors.centerIn: parent; source: "color-picker"; width: 16; height: 16; opacity: 0.5 }
            }

            QQC2.TextField {
                text: kcm.color2; maximumLength: 6; implicitWidth: Kirigami.Units.gridUnit * 5
                onEditingFinished: if (text.length === 6) kcm.color2 = text
            }
            QQC2.Button { text: qsTr("Pick Color"); icon.name: "color-management"; onClicked: colorDialog2.open() }
        }

        // ════════════════════════════════════════════════════════════
        // SPEED (breathe / stars / rainbow / highlight / laser / ripple / rain)
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

            QQC2.Label { text: qsTr("Slow"); opacity: 0.7 }
            QQC2.Slider {
                id: speedSlider
                from: 0; to: 2; stepSize: 1
                value: kcm.speed
                onMoved: kcm.speed = Math.round(value)
                implicitWidth: Kirigami.Units.gridUnit * 10
            }
            QQC2.Label { text: qsTr("Fast"); opacity: 0.7 }
            QQC2.Label {
                text: ["Low","Med","High"][Math.round(speedSlider.value)]
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 3
            }
        }

        // ════════════════════════════════════════════════════════════
        // BRIGHTNESS
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.label: qsTr("Brightness"); Kirigami.FormData.isSection: true }

        RowLayout {
            Kirigami.FormData.label: qsTr("Level:")
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label { text: qsTr("Low"); opacity: 0.7 }
            QQC2.Slider {
                id: brightnessSlider
                from: 1; to: 3; stepSize: 1
                value: kcm.brightness
                onMoved: kcm.brightness = Math.round(value)
                implicitWidth: Kirigami.Units.gridUnit * 10
            }
            QQC2.Label { text: qsTr("Max"); opacity: 0.7 }
            QQC2.Label {
                text: Math.round(brightnessSlider.value) + "/3"
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
            }
        }

        // ════════════════════════════════════════════════════════════
        // AUTO COLOR CYCLE
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.label: qsTr("Auto Color Cycle"); Kirigami.FormData.isSection: true }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Auto cycle:")
            text: qsTr("Automatically rotate through colors")
            checked: kcm.autoColorEnabled
            onToggled: kcm.autoColorEnabled = checked
        }

        QQC2.Label {
            visible: kcm.autoColorEnabled
            text: qsTr("Works with any single-color mode (static, pulse, etc.) — overrides the color above on a timer.")
            wrapMode: Text.WordWrap
            font.italic: true; opacity: 0.7
            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Interval:")
            visible: kcm.autoColorEnabled
            spacing: Kirigami.Units.smallSpacing

            QQC2.Slider {
                id: intervalSlider
                from: 1; to: 60; stepSize: 1
                value: kcm.autoColorInterval
                onMoved: kcm.autoColorInterval = Math.round(value)
                implicitWidth: Kirigami.Units.gridUnit * 12
            }
            QQC2.Label { text: Math.round(intervalSlider.value) + qsTr("s"); font.bold: true }
        }

        // Auto color list
        Item {
            Kirigami.FormData.label: qsTr("Colors to cycle:")
            visible: kcm.autoColorEnabled
            implicitHeight: autoColorsRow.implicitHeight
            implicitWidth: autoColorsRow.implicitWidth

            Flow {
                id: autoColorsRow
                spacing: 4
                Repeater {
                    model: kcm.autoColors
                    Rectangle {
                        width: 32; height: 32; radius: 6
                        color: root.colorSwatch(modelData)
                        border.color: Kirigami.Theme.separatorColor; border.width: 1

                        Rectangle {
                            anchors { top: parent.top; right: parent.right; margins: -3 }
                            width: 14; height: 14; radius: 7
                            color: "#cc0000"
                            QQC2.Label {
                                anchors.centerIn: parent
                                text: "×"
                                font.pixelSize: 10; font.bold: true
                                color: "white"
                            }
                            MouseArea { anchors.fill: parent; onClicked: kcm.removeAutoColor(index) }
                        }
                    }
                }

                Rectangle {
                    width: 32; height: 32; radius: 6
                    color: "transparent"
                    border.color: Kirigami.Theme.separatorColor; border.width: 2
                    Kirigami.Icon { anchors.centerIn: parent; source: "list-add"; width: 18; height: 18; opacity: 0.6 }
                    MouseArea { anchors.fill: parent; onClicked: autoColorDialog.open() }
                }
            }
        }

        // ════════════════════════════════════════════════════════════
        // PREVIEW
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.isSection: true }

        QQC2.Button {
            Kirigami.FormData.label: ""
            text: qsTr("Preview (apply without saving)")
            icon.name: "view-preview"
            onClicked: kcm.preview()
        }
    }
}
