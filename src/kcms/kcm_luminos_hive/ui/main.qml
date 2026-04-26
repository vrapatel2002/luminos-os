// Luminos OS — HIVE AI Settings KCM UI
// [CHANGE: antigravity | 2026-04-26]
//
// Native KDE System Settings page for HIVE AI configuration.
// Shows mode toggle, model roster status, GPU VRAM, and shortcut config.

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: root

    // ── Mode display helpers ───────────────────────────────────────
    readonly property bool isAiMode: kcm.mode === "ai"
    readonly property string modeLabel: isAiMode ? "AI Mode" : "Normal Mode"
    readonly property string modeIcon: isAiMode ? "process-working" : "system-idle"

    // ── Header ─────────────────────────────────────────────────────
    header: Kirigami.InlineMessage {
        id: statusBanner
        type: kcm.orchestratorRunning ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
        text: kcm.orchestratorRunning ? "HIVE Orchestrator is running" : "HIVE Orchestrator is not running"
        visible: true
    }

    Kirigami.FormLayout {
        id: formLayout

        // ── Mode Toggle ────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "AI Mode"
        }

        RowLayout {
            Kirigami.FormData.label: "Current Mode:"
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Icon {
                source: root.modeIcon
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: Kirigami.Units.iconSizes.small
            }

            QQC2.Label {
                text: root.modeLabel
                font.bold: true
                color: root.isAiMode ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.textColor
            }
        }

        QQC2.Button {
            Kirigami.FormData.label: " "
            text: root.isAiMode ? "Switch to Normal Mode" : "Switch to AI Mode"
            icon.name: "system-switch-user"
            onClicked: kcm.toggleMode()
        }

        QQC2.Label {
            Kirigami.FormData.label: " "
            text: root.isAiMode
                ? "AI Mode: Nova runs on CPU, GPU models swap as needed.\nNova available for deep reasoning via !nova command."
                : "Normal Mode: All models use GPU. One model at a time (6 GB VRAM).\nLower RAM usage."
            wrapMode: Text.WordWrap
            opacity: 0.7
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }

        // ── HIVE Roster ────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "HIVE Roster"
        }

        QQC2.Label {
            Kirigami.FormData.label: "Nexus (Dolphin 3.0):"
            text: kcm.nexusStatus
            color: kcm.nexusStatus === "Running" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        QQC2.Label {
            Kirigami.FormData.label: "Bolt (Qwen Coder):"
            text: kcm.boltStatus
            color: kcm.boltStatus === "Running" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        QQC2.Label {
            Kirigami.FormData.label: "Nova (DeepSeek R1):"
            text: kcm.novaStatus
            color: kcm.novaStatus === "Running" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        QQC2.Label {
            Kirigami.FormData.label: "Eye (Qwen VL):"
            text: kcm.eyeStatus
            color: kcm.eyeStatus === "Running" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        QQC2.Label {
            Kirigami.FormData.label: "Sentinel (MobileLLM):"
            text: kcm.sentinelStatus
            color: kcm.sentinelStatus === "Running" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        // ── GPU VRAM ───────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "GPU VRAM"
        }

        QQC2.Label {
            Kirigami.FormData.label: "Used:"
            text: kcm.vramUsage
        }

        QQC2.Label {
            Kirigami.FormData.label: "Free:"
            text: kcm.vramFree
        }

        QQC2.ProgressBar {
            Kirigami.FormData.label: " "
            Layout.fillWidth: true
            from: 0
            to: 6144  // 6 GB total VRAM
            value: {
                var n = parseInt(kcm.vramUsage);
                return isNaN(n) ? 0 : n;
            }
        }

        // ── Shortcut ───────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Shortcut"
        }

        QQC2.Label {
            Kirigami.FormData.label: "HIVE Chat:"
            text: kcm.shortcutKey
            font.bold: true
        }

        // ── Refresh Button ─────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: " "
        }

        QQC2.Button {
            Kirigami.FormData.label: " "
            text: "Refresh Status"
            icon.name: "view-refresh"
            onClicked: kcm.refreshStatus()
        }
    }

    // Auto-refresh on page load
    Component.onCompleted: kcm.refreshStatus()
}
