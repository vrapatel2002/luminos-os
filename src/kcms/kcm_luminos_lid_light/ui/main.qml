// Luminos OS — Lid Light (Slash Ledbar) KCM UI
// [CHANGE: claude-code | 2026-06-10]

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: root

    Kirigami.FormLayout {
        width: parent.width

        // ════════════════════════════════════════════════════════════
        // ENABLE / DISABLE
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Lid Light")
            Kirigami.FormData.isSection: true
        }

        QQC2.Switch {
            Kirigami.FormData.label: qsTr("Enabled:")
            checked: kcm.enabled
            onToggled: { kcm.enabled = checked; kcm.preview() }
        }

        // ════════════════════════════════════════════════════════════
        // BRIGHTNESS
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.enabled
            Kirigami.FormData.label: qsTr("Brightness")
            Kirigami.FormData.isSection: true
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Level:")
            visible: kcm.enabled
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label { text: qsTr("Off"); opacity: 0.6 }
            QQC2.Slider {
                id: brightSlider
                from: 0; to: 255; stepSize: 1
                value: kcm.brightness
                implicitWidth: Kirigami.Units.gridUnit * 14
                onMoved: { kcm.brightness = Math.round(value); kcm.preview() }
            }
            QQC2.Label { text: qsTr("Max"); opacity: 0.6 }
            QQC2.Label {
                text: Math.round(brightSlider.value)
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
            }
        }

        // ════════════════════════════════════════════════════════════
        // ANIMATION MODE
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            visible: kcm.enabled
            Kirigami.FormData.label: qsTr("Animation")
            Kirigami.FormData.isSection: true
        }

        QQC2.ComboBox {
            id: modeCombo
            Kirigami.FormData.label: qsTr("Mode:")
            visible: kcm.enabled
            implicitWidth: Kirigami.Units.gridUnit * 14
            model: kcm.availableModes
            currentIndex: {
                var idx = model.indexOf(kcm.mode)
                return idx >= 0 ? idx : 0
            }
            onActivated: {
                kcm.mode = model[currentIndex]
                kcm.preview()
            }
        }

        // Mode description
        QQC2.Label {
            Kirigami.FormData.label: " "
            visible: kcm.enabled
            text: {
                var idx = modeCombo.currentIndex
                var descs = kcm.modeDescriptions
                return (idx >= 0 && idx < descs.length) ? descs[idx] : ""
            }
            wrapMode: Text.WordWrap
            font.italic: true
            opacity: 0.65
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Speed:")
            visible: kcm.enabled
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label { text: qsTr("Slow"); opacity: 0.6 }
            QQC2.Slider {
                id: intervalSlider
                from: 0; to: 5; stepSize: 1
                value: kcm.interval
                implicitWidth: Kirigami.Units.gridUnit * 10
                onMoved: { kcm.interval = Math.round(value); kcm.preview() }
            }
            QQC2.Label { text: qsTr("Fast"); opacity: 0.6 }
            QQC2.Label {
                text: Math.round(intervalSlider.value) + "/5"
                font.bold: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
            }
        }

        // ════════════════════════════════════════════════════════════
        // BATTERY INDICATOR
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Battery Indicator")
            Kirigami.FormData.isSection: true
        }

        QQC2.Switch {
            Kirigami.FormData.label: qsTr("Enabled:")
            checked: kcm.batteryIndicator
            onToggled: { kcm.batteryIndicator = checked; kcm.preview() }
        }

        QQC2.Label {
            Kirigami.FormData.label: " "
            text: qsTr("Maps battery % to slash brightness.\nCharging → Flow, Low ≤15% → Hazard, Otherwise → Static.")
            wrapMode: Text.WordWrap
            font.italic: true
            opacity: 0.65
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        }

        // Live battery readout
        QQC2.Label {
            Kirigami.FormData.label: qsTr("Battery:")
            visible: kcm.batteryIndicator
            text: kcm.currentBatteryPct + "% (" + kcm.currentBatteryStatus + ") → brightness " + Math.round(kcm.currentBatteryPct * 255 / 100)
            font.bold: true
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Poll interval:")
            visible: kcm.batteryIndicator
            spacing: Kirigami.Units.smallSpacing

            QQC2.SpinBox {
                id: pollSpin
                from: 5; to: 300; stepSize: 5
                value: kcm.batteryPollSecs
                onValueModified: kcm.batteryPollSecs = value
            }
            QQC2.Label {
                text: qsTr("seconds")
                opacity: 0.6
            }
        }

        // ════════════════════════════════════════════════════════════
        // EVENT TRIGGERS
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator {
            Kirigami.FormData.label: qsTr("Show Animation On")
            Kirigami.FormData.isSection: true
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Boot:")
            text: qsTr("Play animation on startup")
            checked: kcm.showOnBoot
            onToggled: kcm.showOnBoot = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Shutdown:")
            text: qsTr("Play animation on power off")
            checked: kcm.showOnShutdown
            onToggled: kcm.showOnShutdown = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Sleep:")
            text: qsTr("Play animation on suspend")
            checked: kcm.showOnSleep
            onToggled: kcm.showOnSleep = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Battery:")
            text: qsTr("Show while on battery power")
            checked: kcm.showOnBattery
            onToggled: kcm.showOnBattery = checked
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: qsTr("Low battery:")
            text: qsTr("Show low-battery warning animation")
            checked: kcm.showBatteryWarning
            onToggled: kcm.showBatteryWarning = checked
        }

        // ════════════════════════════════════════════════════════════
        // PREVIEW
        // ════════════════════════════════════════════════════════════
        Kirigami.Separator { Kirigami.FormData.isSection: true }

        QQC2.Button {
            Kirigami.FormData.label: " "
            text: qsTr("Preview")
            icon.name: "view-preview"
            enabled: kcm.enabled
            onClicked: kcm.preview()
        }
    }
}
