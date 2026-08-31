// [CHANGE: claude-code | 2026-08-31] VRAM card for the Performance tab.
//
// This file does NOT exist upstream. It is placed into the overlay at
// modules/dashboard/performance/VramCard.qml by
// scripts/luminos-caelestia-kwin-overlay.
//
// It is MemoryCard.qml's twin with one deliberate difference: it owns no data
// source. Everything arrives as a property from Performance.qml's `dgpu`, which
// reads the kernel's runtime_status first and only ever runs nvidia-smi while
// the card is ALREADY awake. A VRAM widget that polled the GPU itself would
// hold the 4050 out of D3cold at a measured 13.46 W for as long as the tab is
// open - see BUG-151. So this file must stay dumb.
//
// `total` is a hardware constant, so it is remembered across a sleep: once the
// card has been awake even once, "0 / 6141 MiB" while asleep is the truth, not
// a guess. Before that first wake there is nothing honest to print.

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

StyledRect {
    id: root

    required property bool awake
    required property real used   // MiB
    required property real total  // MiB

    readonly property real fraction: total > 0 ? used / total : 0
    readonly property color accent: awake ? Colours.palette.m3secondary : Colours.palette.m3onSurfaceVariant

    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.medium

    implicitWidth: layout.implicitWidth + Tokens.padding.extraLargeIncreased * 2
    implicitHeight: layout.implicitHeight + Tokens.padding.large * 2

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        RowLayout {
            Layout.leftMargin: -Tokens.padding.extraSmall
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: "developer_board"
                fill: 1
                color: root.accent
                fontStyle: Tokens.font.icon.builders.medium.weight(Font.DemiBold).build() // DemiBold to fix fill issues
            }

            StyledText {
                text: qsTr("VRAM")
                font: Tokens.font.title.medium
            }
        }

        CircularProgress {
            Layout.topMargin: Tokens.spacing.large
            Layout.alignment: Qt.AlignHCenter
            implicitSize: usageColumn.implicitHeight + thickness + Tokens.padding.largeIncreased * 2
            startAngle: -225
            sweepAngle: 270

            fgColour: root.accent
            value: root.fraction

            Behavior on clampedVal {
                Anim {}
            }

            ColumnLayout {
                id: usageColumn

                anchors.centerIn: parent
                anchors.verticalCenterOffset: Tokens.padding.extraSmall
                spacing: 0

                StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.total > 0 ? Math.round(root.fraction * 100) + "%" : "\u2013"
                    font: Tokens.font.title.builders.large.width(90).build()
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
            text: root.total > 0 ? `${Math.round(root.used)} / ${Math.round(root.total)} MiB` : qsTr("Not read yet")
            font: Tokens.font.body.medium
            color: root.awake ? Colours.palette.m3onSurface : Colours.palette.m3onSurfaceVariant
        }
    }
}
