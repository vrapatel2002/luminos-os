pragma ComponentBehavior: Bound

// [CHANGE: claude-code | 2026-09-13]
//
// A bar entry for the two large empty stretches the default Caelestia layout
// leaves behind.  Those gaps are not a bug - the shipped `entries` list has two
// `spacer` entries, each `Layout.fillHeight: true`, and on a 1800px-tall screen
// they absorb about a third of the bar.  This is something to put in them.
//
// WHY NOT RINGS, which is what upstream uses everywhere else.
// The first version of this file was upstream's `dashboard/dash/Resources.qml`
// shape - CircularProgress with a MaterialIcon in the middle - and at bar width
// it is unusable.  The numbers, measured live rather than guessed:
// innerWidth is 32, Tokens.padding.small is 8, and Tokens.font.icon.small is
// 15pt (~20px).  CircularProgress computes arcRadius as (size - strokeWidth)/2,
// so a 24px ring with an 8px stroke leaves an 8px hole - and a 20px icon went
// into it.  It rendered as three blobs with icons spilling over the edges.
// Even at stroke 2 the clear space is 24px against a 20px glyph, which is 2px
// of margin.  A ring needs roughly 3x the icon's width and the strip does not
// have it.
//
// So: the icon at the size every other bar icon uses, and the value as a thin
// capsule underneath it.  Same shapes the rest of the bar already uses
// (StyledRect + rounding.full), just smaller.
//
// WHY THERE IS NO GPU RING - this is the important part, do not "fix" it.
// `Caelestia.Services.Gpu` has a `startNvidiaUsage()` path (confirmed in
// libcaelestia-services.so) which shells out to nvidia-smi on a tick.  The
// dashboard can afford that because TickingService is ref-counted and the
// dashboard is only referenced while it is open.  The BAR is open always, so a
// GPU ring here would poll the RTX 4050 forever and hold it out of RTD3 - that
// is BUG-047's 8W idle regression, re-introduced through the back door, and it
// would be invisible because the symptom is battery life, not a wrong number.
// The dGPU already has a readout that is safe because it is on-demand: the VRAM
// card in the dashboard.
//
// CPU and Memory are free by comparison - they read /proc.

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.Services
import qs.components
import qs.services

StyledRect {
    id: root

    // The capsule is narrower than the strip so it reads as sitting inside the
    // pill rather than spanning it edge to edge.
    readonly property int meterWidth: Tokens.sizes.bar.innerWidth - Tokens.padding.small
    readonly property int meterHeight: Tokens.padding.extraSmall

    implicitWidth: Tokens.sizes.bar.innerWidth
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2

    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.full

    // Without these the singletons never tick and every meter reads zero.
    ServiceRef {
        service: Cpu
    }

    ServiceRef {
        service: Memory
    }

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        spacing: Tokens.spacing.medium

        Meter {
            icon: "memory"
            value: Cpu.percentage
            label: Math.round(Cpu.percentage * 100).toString()
            colour: Colours.palette.m3primary
        }

        Meter {
            icon: "memory_alt"
            value: Memory.percentage
            label: Math.round(Memory.percentage * 100).toString()
            colour: Colours.palette.m3tertiary
        }

        // Temperature is not a percentage, so it is mapped onto one.  The range
        // is 30-100C, which is not arbitrary: 30C is where fan curve v5 starts
        // (AGENTS.md 12) and 100C is TJmax-adjacent (TJmax is 105C).  Starting
        // at 40 was the first attempt and it was wrong - idle sits just above
        // it, so the meter read as an empty dot and looked broken.
        // It turns red at 90C, the same threshold upstream's lock screen uses,
        // so the two never disagree about what "hot" means.
        Meter {
            readonly property real temp: Cpu.temperature

            icon: "thermostat"
            value: (temp - 30) / 70
            label: Math.round(temp) + "\u00b0"
            colour: temp > 90 ? Colours.palette.m3error : Colours.palette.m3secondary
        }
    }

    component Meter: ColumnLayout {
        id: meter

        required property string icon
        required property real value
        required property string label
        required property color colour

        readonly property real clamped: Math.max(0, Math.min(1, isNaN(value) ? 0 : value))

        Layout.alignment: Qt.AlignHCenter
        spacing: 0

        MaterialIcon {
            Layout.alignment: Qt.AlignHCenter
            text: meter.icon
            color: meter.colour
        }

        // The number, not just the bar.  At idle - which is most of the time -
        // every capsule is a 4px dot and the widget reads as broken rather than
        // as "nothing is happening".  Measured while writing this: 4.8% CPU,
        // 37.6C.  Mono so the column does not jitter between 9 and 10.
        StyledText {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: Tokens.spacing.extraSmall
            text: meter.label
            color: meter.colour
            font: Tokens.font.mono.small
        }

        StyledRect {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: root.meterWidth
            implicitHeight: root.meterHeight
            radius: Tokens.rounding.full
            color: Colours.palette.m3surfaceContainerHighest

            StyledRect {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: Math.max(root.meterHeight, parent.width * meter.clamped)
                implicitHeight: parent.height
                radius: Tokens.rounding.full
                color: meter.colour

                Behavior on implicitWidth {
                    Anim {}
                }
            }
        }
    }
}
