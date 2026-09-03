// [CHANGE: claude-code | 2026-08-31] Wide gauge card for the Performance tab.
//
// This file does NOT exist upstream. It is placed into the overlay at
// modules/dashboard/performance/GaugeCard.qml by
// scripts/luminos-caelestia-kwin-overlay. It replaces the earlier VramCard.qml.
//
// Why it exists: it is upstream's MemoryCard - title above the ring, figure
// below it - but with the ring pinned to a fixed size instead of growing to
// fit its own text. That one change is what makes it fit a grid: upstream's
// arc came out ~108 px, this one is 83, and the card goes from 182x229 to
// roughly 134x159, which is short enough to sit in a row beside a hero card.
//
// It owns NO data source. Everything arrives as a property. That is deliberate
// for the VRAM instance: a widget that polled the GPU itself would hold the
// 4050 out of D3cold at a measured 13.46 W for as long as the tab is open (see
// BUG-151). Performance.qml's `dgpu` reads the kernel's runtime_status first
// and only runs nvidia-smi while the card is ALREADY awake. So this file must
// stay dumb.

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

StyledRect {
    id: root

    required property string icon
    required property string label
    required property color accent

    // 0..1. Drives the arc.
    required property real fraction

    // The line under the title, e.g. "7.6 / 14.9 GiB". Already formatted,
    // because Memory formats KiB and VRAM formats MiB.
    required property string value

    // The number inside the gauge. Overridable so a source with nothing
    // honest to print yet can say so instead of claiming 0%.
    property string percentText: `${Math.round(root.fraction * 100)}%`

    // Diameter of the arc. Set from PERF in the overlay script so all four
    // gauges on the tab stay the same size.
    property int gaugeSize: 83

    property color valueColour: Colours.palette.m3onSurface

    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.medium

    implicitWidth: layout.implicitWidth + Tokens.padding.medium * 2
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: root.icon
                fill: 1
                color: root.accent
                fontStyle: Tokens.font.icon.builders.medium.weight(Font.DemiBold).build() // DemiBold to fix fill issues
            }

            StyledText {
                text: root.label
                font: Tokens.font.title.medium
            }
        }

        CircularProgress {
            Layout.alignment: Qt.AlignHCenter
            implicitSize: root.gaugeSize
            startAngle: -225
            sweepAngle: 270

            fgColour: root.accent
            value: root.fraction

            Behavior on clampedVal {
                Anim {}
            }

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 0

                StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.percentText
                    font: Tokens.font.title.builders.medium.width(90).build()
                    color: root.accent
                }

                StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("Used")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }

        StyledText {
            Layout.alignment: Qt.AlignHCenter
            text: root.value
            font: Tokens.font.body.medium
            color: root.valueColour
        }
    }
}
