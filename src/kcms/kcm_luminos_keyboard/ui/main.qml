// Luminos OS — Keyboard Backlight KCM UI
// [CHANGE: claude-code | 2026-04-26]

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: root

    Kirigami.FormLayout {
        anchors.centerIn: parent
        width: parent.width

        // ── Color ──────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.label: i18n("Color")
            Kirigami.FormData.isSection: true
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Hex color:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.TextField {
                id: colorField
                text: kcm.color
                placeholderText: "ffffff"
                maximumLength: 6
                onEditingFinished: kcm.color = text
                implicitWidth: Kirigami.Units.gridUnit * 6
            }

            Rectangle {
                width: Kirigami.Units.gridUnit * 2
                height: Kirigami.Units.gridUnit
                color: "#" + colorField.text
                radius: 4
                border.color: Kirigami.Theme.separatorColor
                border.width: 1
            }
        }

        // ── Brightness ────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.label: i18n("Brightness")
            Kirigami.FormData.isSection: true
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Level:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.Slider {
                id: brightnessSlider
                from: 1; to: 3; stepSize: 1
                value: kcm.brightness
                onMoved: kcm.brightness = Math.round(value)
                Layout.fillWidth: true
                implicitWidth: Kirigami.Units.gridUnit * 10
            }

            QQC2.Label {
                text: Math.round(brightnessSlider.value) + "/3"
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
            }
        }

        // ── Mode ──────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.label: i18n("Animation Mode")
            Kirigami.FormData.isSection: true
        }

        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Mode:")
            id: modeCombo
            model: [
                { text: i18n("Static (solid color)"),  value: "static"        },
                { text: i18n("Breathe (fade in/out)"), value: "breathe"       },
                { text: i18n("Rainbow cycle"),         value: "rainbow-cycle" },
                { text: i18n("Pulse"),                 value: "pulse"         },
                { text: i18n("Off"),                   value: "none"          }
            ]
            textRole: "text"
            currentIndex: {
                for (var i = 0; i < model.length; i++) {
                    if (model[i].value === kcm.mode) return i;
                }
                return 0;
            }
            onActivated: kcm.mode = model[currentIndex].value
        }

        // ── Preview ───────────────────────────────────────
        Kirigami.Separator { Kirigami.FormData.isSection: true }

        QQC2.Button {
            Kirigami.FormData.label: ""
            text: i18n("Preview (apply without saving)")
            icon.name: "view-preview"
            onClicked: kcm.preview()
        }
    }
}
