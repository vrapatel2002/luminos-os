// luminos-gpu-picker.qml — Luminos GPU Selector dialog
// [CHANGE: claude-code | 2026-07-03] DECISION 25 — replaces the plain kdialog menu with a
// styled Chrome-style GPU picker. Self-contained (inline palette from design/luminos-tokens).
//
// Invoked by:  qml6 luminos-gpu-picker.qml
// Inputs (env):  LUMINOS_PICKER_APP  = app name shown in the header
//                LUMINOS_PICKER_ONBATTERY = "1" to show the battery warning on NVIDIA
// Output: process EXIT CODE encodes both the GPU choice and the "remember" flag:
//    10 = AMD iGPU, once        11 = AMD iGPU, always
//    20 = NVIDIA dGPU, once     21 = NVIDIA dGPU, always
//    10 (default) on cancel / close / Esc — safe default is the efficient iGPU.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

ApplicationWindow {
    id: win
    visible: true
    flags: Qt.Dialog | Qt.FramelessWindowHint
    color: "transparent"
    width: 560
    height: 440
    // center on primary screen
    x: Screen.width / 2 - width / 2
    y: Screen.height / 2 - height / 2

    // ── palette (Luminos tokens) ────────────────────────────────
    readonly property color bgBase:         "#0A0A0F"
    readonly property color surface:        "#13131A"
    readonly property color surfaceElev:    "#1C1C26"
    readonly property color textPrimary:    "#FFFFFF"
    readonly property color textSecondary:  "#8888AA"
    readonly property color border:         Qt.rgba(1, 1, 1, 0.08)
    readonly property color amdColor:       "#00C896"   // success green
    readonly property color nvidiaColor:    "#76B900"   // NVIDIA green
    readonly property color accent:         "#0080FF"
    readonly property color warning:        "#FFB020"

    // selection state: "igpu" or "nvidia"
    property string choice: "nvidia"   // pre-highlight the performance option; user confirms
    property bool remember: false

    // Inputs come as positional CLI args after the .qml path:
    //   qml6 luminos-gpu-picker.qml -- "<app name>" "<0|1 onBattery>"
    QtObject {
        id: picker
        property string appName: "An application"
        property bool onBattery: false
    }
    Component.onCompleted: {
        // Collect positional args: drop the runtime exe, any flags, and the .qml path.
        var args = Qt.application.arguments
        var pos = []
        for (var i = 0; i < args.length; i++) {
            var a = args[i]
            if (a.indexOf("-") === 0) continue
            if (a.indexOf(".qml") >= 0) continue
            if (a.indexOf("qml6") >= 0 || a === "qml" || a.indexOf("qmlscene") >= 0) continue
            pos.push(a)
        }
        if (pos.length >= 1 && pos[0].length) picker.appName = pos[0]
        if (pos.length >= 2) picker.onBattery = (pos[1] === "1")
    }

    function finish() {
        var base = choice === "nvidia" ? 20 : 10
        Qt.exit(base + (remember ? 1 : 0))
    }
    function cancel() { Qt.exit(10) }

    // Esc closes with safe default
    Shortcut { sequence: "Escape"; onActivated: win.cancel() }
    Shortcut { sequence: "Return"; onActivated: win.finish() }

    // ── window body ─────────────────────────────────────────────
    Rectangle {
        id: card
        anchors.fill: parent
        radius: 16
        color: win.bgBase
        border.color: win.border
        border.width: 1

        // subtle top glow
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 3
            radius: 16
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: win.amdColor }
                GradientStop { position: 1.0; color: win.nvidiaColor }
            }
        }

        // drag anywhere to move
        MouseArea {
            anchors.fill: parent
            property point start
            onPressed: (m) => start = Qt.point(m.x, m.y)
            onPositionChanged: (m) => {
                win.x += m.x - start.x
                win.y += m.y - start.y
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 20

            // header
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: "Select a graphics processor"
                    color: win.textPrimary
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    font.family: "Inter"
                }
                Text {
                    text: "\u201C" + picker.appName + "\u201D wants to use the GPU"
                    color: win.textSecondary
                    font.pixelSize: 14
                    font.family: "Inter"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // the two cards
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 16

                // AMD card
                GpuCard {
                    id: amdCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    accentColor: win.amdColor
                    title: "AMD Radeon 780M"
                    subtitle: "Integrated"
                    tagline: "Battery saver \u00B7 always on"
                    detail: "Best for everyday apps. No extra power, no wake."
                    badge: "RECOMMENDED"
                    selected: win.choice === "igpu"
                    onClicked: win.choice = "igpu"
                    onDoubleClicked: { win.choice = "igpu"; win.finish() }
                }

                // NVIDIA card
                GpuCard {
                    id: nvCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    accentColor: win.nvidiaColor
                    title: "NVIDIA RTX 4050"
                    subtitle: "Discrete"
                    tagline: "High performance"
                    detail: picker.onBattery
                        ? "Fast, but heavy on battery. Wakes the dGPU (\u224815\u201390W)."
                        : "Fast for games, render & compute. Wakes the dGPU."
                    badge: picker.onBattery ? "USES BATTERY" : "PERFORMANCE"
                    badgeWarn: picker.onBattery
                    selected: win.choice === "nvidia"
                    onClicked: win.choice = "nvidia"
                    onDoubleClicked: { win.choice = "nvidia"; win.finish() }
                }
            }

            // remember + actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // remember toggle
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: rememberRow.width + 20
                    height: 34
                    radius: 8
                    color: rememberMA.containsMouse ? win.surfaceElev : "transparent"
                    RowLayout {
                        id: rememberRow
                        anchors.centerIn: parent
                        spacing: 8
                        Rectangle {
                            width: 18; height: 18; radius: 5
                            color: win.remember ? win.accent : "transparent"
                            border.color: win.remember ? win.accent : win.textSecondary
                            border.width: 2
                            Text {
                                anchors.centerIn: parent
                                text: "\u2713"; color: "white"; font.pixelSize: 12
                                visible: win.remember
                            }
                        }
                        Text {
                            text: "Remember for this app"
                            color: win.textSecondary
                            font.pixelSize: 13
                            font.family: "Inter"
                        }
                    }
                    MouseArea {
                        id: rememberMA
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.remember = !win.remember
                    }
                }

                Item { Layout.fillWidth: true }

                PillButton {
                    text: "Cancel"
                    primary: false
                    onClicked: win.cancel()
                }
                PillButton {
                    text: win.choice === "nvidia" ? "Use NVIDIA" : "Use AMD"
                    primary: true
                    accentColor: win.choice === "nvidia" ? win.nvidiaColor : win.amdColor
                    onClicked: win.finish()
                }
            }
        }
    }

    // ── reusable GPU card component ─────────────────────────────
    component GpuCard: Rectangle {
        id: gpuCard
        property color accentColor: "#0080FF"
        property string title: ""
        property string subtitle: ""
        property string tagline: ""
        property string detail: ""
        property string badge: ""
        property bool badgeWarn: false
        property bool selected: false
        signal clicked()
        signal doubleClicked()

        radius: 14
        color: selected ? Qt.rgba(gpuCard.accentColor.r, gpuCard.accentColor.g, gpuCard.accentColor.b, 0.10)
                        : win.surface
        border.color: selected ? gpuCard.accentColor : win.border
        border.width: selected ? 2 : 1
        Behavior on border.color { ColorAnimation { duration: 120 } }
        Behavior on color { ColorAnimation { duration: 120 } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                // GPU glyph chip
                Rectangle {
                    width: 42; height: 42; radius: 10
                    color: Qt.rgba(gpuCard.accentColor.r, gpuCard.accentColor.g, gpuCard.accentColor.b, 0.18)
                    Text {
                        anchors.centerIn: parent
                        text: "\u25A6"          // ▦ processor-ish glyph
                        color: gpuCard.accentColor
                        font.pixelSize: 22
                    }
                }
                Item { Layout.fillWidth: true }
                // radio dot
                Rectangle {
                    width: 20; height: 20; radius: 10
                    color: "transparent"
                    border.color: gpuCard.selected ? gpuCard.accentColor : win.textSecondary
                    border.width: 2
                    Rectangle {
                        anchors.centerIn: parent
                        width: 10; height: 10; radius: 5
                        color: gpuCard.accentColor
                        visible: gpuCard.selected
                    }
                }
            }

            Text {
                text: gpuCard.subtitle
                color: gpuCard.accentColor
                font.pixelSize: 11
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                font.family: "Inter"
            }
            Text {
                text: gpuCard.title
                color: win.textPrimary
                font.pixelSize: 17
                font.weight: Font.DemiBold
                font.family: "Inter"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                text: gpuCard.tagline
                color: win.textSecondary
                font.pixelSize: 13
                font.family: "Inter"
            }

            Item { Layout.fillHeight: true }

            Text {
                text: gpuCard.detail
                color: win.textSecondary
                font.pixelSize: 12
                font.family: "Inter"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                opacity: 0.85
            }

            // badge
            Rectangle {
                visible: gpuCard.badge.length > 0
                radius: 6
                color: gpuCard.badgeWarn ? Qt.rgba(1, 0.69, 0.125, 0.15)
                                    : Qt.rgba(gpuCard.accentColor.r, gpuCard.accentColor.g, gpuCard.accentColor.b, 0.15)
                implicitWidth: badgeText.width + 16
                implicitHeight: 22
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: gpuCard.badge
                    color: gpuCard.badgeWarn ? win.warning : gpuCard.accentColor
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    font.family: "Inter"
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: gpuCard.clicked()
            onDoubleClicked: gpuCard.doubleClicked()
            onEntered: if (!gpuCard.selected) gpuCard.border.color = Qt.rgba(1,1,1,0.20)
            onExited: if (!gpuCard.selected) gpuCard.border.color = win.border
        }
    }

    // ── pill button component ───────────────────────────────────
    component PillButton: Rectangle {
        id: pb
        property string text: ""
        property bool primary: true
        property color accentColor: "#0080FF"
        signal clicked()
        implicitWidth: pbText.width + 40
        implicitHeight: 40
        radius: 20
        color: pb.primary
               ? (pbMA.containsMouse ? Qt.lighter(pb.accentColor, 1.1) : pb.accentColor)
               : (pbMA.containsMouse ? win.surfaceElev : "transparent")
        border.color: pb.primary ? "transparent" : win.border
        border.width: 1
        Behavior on color { ColorAnimation { duration: 100 } }
        Text {
            id: pbText
            anchors.centerIn: parent
            text: pb.text
            color: pb.primary ? "#0A0A0F" : win.textSecondary
            font.pixelSize: 14
            font.weight: Font.DemiBold
            font.family: "Inter"
        }
        MouseArea {
            id: pbMA
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: pb.clicked()
        }
    }
}
