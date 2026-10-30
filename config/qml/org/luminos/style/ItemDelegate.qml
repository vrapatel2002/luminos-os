/*
    Derived from org.kde.desktop's ItemDelegate.qml
    SPDX-FileCopyrightText: 2017 Marco Martin <mart@kde.org>
    SPDX-FileCopyrightText: 2017 The Qt Company Ltd.
    SPDX-FileCopyrightText: 2023 ivan tkachenko <me@ratijas.tk>
    SPDX-FileCopyrightText: 2025 Nate Graham <nate@kde.org>

    SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-or-later
*/

// [CHANGE: claude-code | 2026-09-03] Luminos OS — STEP 1: SHAPE ONLY.
//
// Everything in this file is a verbatim copy of the org.kde.desktop delegate
// EXCEPT the `background:` block at the bottom. No padding, no spacing, no
// height and no font is touched here — those are step 2 (size).
//
// The shape being copied is Caelestia's ConnectedRect
// (reference_code/caelestia-shell-2.2.0/modules/nexus/common/ConnectedRect.qml):
// a run of rows is drawn as ONE big rounded slab that has been sliced, so the
// corners at the outside of the run are large and the corners where rows meet
// are nearly square.
//
//   outer corner = Tokens.rounding.extraLarge  = 28
//   inner corner = Tokens.rounding.extraSmall  = 4
//
// This is the part DECISION 72 got wrong: it set one uniform radius (16) on all
// four corners of every row, which is a different shape, not a smaller version
// of the same one.

import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
// [CHANGE: claude-code | 2026-09-03] The stock file writes a bare `Label`, which
// works there because org.kde.desktop's own qmldir declares `Label 1.0 Label.qml`.
// Inside a style module an unqualified type name is resolved against THAT
// module's qmldir first, so a partial style that declares only ItemDelegate gets
// `Label is not a type`. Qualifying it sends Label back through the normal style
// lookup (i.e. the fallback style) instead. No recursion: ItemDelegate itself is
// never referenced from here.
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

T.ItemDelegate {
    id: controlRoot

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    hoverEnabled: true

    spacing: Kirigami.Units.mediumSpacing

    // [CHANGE: claude-code | 2026-09-03] STEP 2 — SIZE. Where a row sits in its
    // run decides both its corners (step 1) and its gap (below), so it is worked
    // out once here instead of twice. A delegate with no `index` is not in a view
    // at all, so it is its own run: both first and last.
    readonly property bool __isFirstInRun: typeof index === "undefined" || index === 0
    readonly property bool __isLastInRun: typeof index === "undefined"
        || controlRoot.ListView.view?.count === index + 1

    // [CHANGE: claude-code | 2026-09-03] Nexus geometry, from NavRow.qml:30-32.
    // Stock was mediumSpacing+smallSpacing (18) all round with a squashed 6px
    // bottom, which is both taller and narrower than Nexus and asymmetric top to
    // bottom. Nexus is 12 vertical / 20 horizontal, even on every row.
    //
    // In Nexus the slab does NOT touch its container: the nav pane holds it
    // padding.large (16) in from the edge (NavLocations.qml:81, Nexus.qml:97).
    // A QQC2 style cannot add margin to somebody else's ListView, so the
    // delegate has to carry that margin itself, as a horizontal inset. Without
    // it the slab runs edge to edge and the 28px corners have nothing to round
    // against — measured in System Settings, where the sidebar has no margin of
    // its own and the rows came out as flat full-bleed bands.
    readonly property int __slabMargin: 16   // Tokens.padding.large

    padding: 12                              // Tokens.padding.medium
    // Padding is measured from the CONTROL edge but the slab starts __slabMargin
    // in, so the horizontal padding has to carry both to leave Nexus's 20px
    // between the slab edge and the text.
    horizontalPadding: 20 + __slabMargin     // Tokens.padding.largeIncreased + margin
    leftPadding: !mirrored ? horizontalPadding + (indicator ? (controlRoot.display === T.AbstractButton.TextUnderIcon ? 0 : implicitIndicatorWidth) + spacing : 0) : horizontalPadding
    rightPadding: mirrored ? horizontalPadding + (indicator ? (controlRoot.display === T.AbstractButton.TextUnderIcon ? 0 : implicitIndicatorWidth) + spacing : 0) : horizontalPadding

    readonly property int __iconSize: controlRoot.display === T.AbstractButton.TextUnderIcon ? Kirigami.Units.iconSizes.medium : Kirigami.Units.iconSizes.smallMedium
    icon.width: __iconSize
    icon.height:__iconSize

    T.ToolTip.visible: (Kirigami.Settings.tabletMode ? down : hovered) && (contentItem.truncated ?? false)
    T.ToolTip.text: action instanceof Kirigami.Action ? action.tooltip : text
    T.ToolTip.delay: Kirigami.Settings.tabletMode ? Qt.styleHints.mousePressAndHoldInterval : Kirigami.Units.toolTipDelay

    // [CHANGE: claude-code | 2026-09-03] STEP 2 — the change that makes the run
    // read as ONE card. Stock insets pull the background in from every edge by
    // (padding - smallSpacing), so each row's slab floats inside its own box with
    // ~12px of dead space above and below it. That is why step 1's 28/4 corners
    // looked like separate pills: the corners were right, the rows just were not
    // touching. Nexus does the opposite — the slab is the full row, and rows are
    // separated by a hairline 2px only.
    //
    // The gap is put on bottomInset rather than split across two rows so a run
    // never gets a stray gap above its first row or below its last.
    leftInset: TableView.view ? 0 : __slabMargin
    rightInset: TableView.view ? 0 : __slabMargin
    topInset: 0
    bottomInset: TableView.view || __isLastInRun ? 0 : 2   // Tokens.spacing.extraSmall / 2

    contentItem: GridLayout {
        LayoutMirroring.enabled: controlRoot.mirrored
        rows: controlRoot.display === T.AbstractButton.TextUnderIcon ? 2 : 1
        columns: controlRoot.display === T.AbstractButton.TextBesideIcon ? 2 : 1
        rowSpacing: controlRoot.spacing
        columnSpacing: controlRoot.spacing

        property alias truncated: textLabel.truncated

        Kirigami.Icon {
            selected: controlRoot.highlighted || controlRoot.down
            Layout.preferredHeight: controlRoot.icon.height
            Layout.preferredWidth: controlRoot.icon.width
            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
            visible: controlRoot.display !== T.AbstractButton.TextOnly
                && (controlRoot.icon.name.length > 0 || controlRoot.icon.source.toString().length > 0)
            source: controlRoot.icon.name.length > 0 ? controlRoot.icon.name : controlRoot.icon.source
        }

        QQC2.Label {
            id: textLabel

            Layout.fillWidth: true
            Layout.fillHeight: true

            Accessible.ignored: true

            text: controlRoot.text
            font: controlRoot.font
            color: controlRoot.highlighted || controlRoot.down
                ? Kirigami.Theme.highlightedTextColor
                : (controlRoot.enabled ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor)

            elide: Text.ElideRight
            visible: controlRoot.display !== T.AbstractButton.IconOnly && controlRoot.text
            wrapMode: controlRoot.display === T.AbstractButton.TextUnderIcon ? Text.Wrap : Text.NoWrap
            horizontalAlignment: controlRoot.display === T.AbstractButton.TextUnderIcon ? Text.AlignHCenter : Text.AlignLeft
            verticalAlignment: controlRoot.display === T.AbstractButton.TextUnderIcon ? Text.AlignTop : Text.AlignVCenter
        }
    }

    // [CHANGE: claude-code | 2026-09-03] The only edit. Stock draws a fully
    // transparent row and paints a uniform-radius rect only on hover/selection,
    // so there is no shape to look at until you touch it. Nexus draws every row
    // as a filled slab — without the fill the corners are invisible, so the fill
    // has to come along with the shape.
    background: Item {
        readonly property real outerRadius: 28  // Tokens.rounding.extraLarge
        readonly property real innerRadius: 4   // Tokens.rounding.extraSmall

        // [CHANGE: claude-code | 2026-09-03] STEP 2 — the negative anchor margins
        // that used to undo the stock insets are gone, because the insets are now
        // 0 (bar the 2px gap). The background Item already IS the row, so filling
        // it is enough. `isFirst`/`isLast` moved up to controlRoot so the corner
        // and the gap can never disagree about where a run ends.
        Rectangle {
            anchors.fill: parent

            topLeftRadius: controlRoot.__isFirstInRun ? parent.outerRadius : parent.innerRadius
            topRightRadius: controlRoot.__isFirstInRun ? parent.outerRadius : parent.innerRadius
            bottomLeftRadius: controlRoot.__isLastInRun ? parent.outerRadius : parent.innerRadius
            bottomRightRadius: controlRoot.__isLastInRun ? parent.outerRadius : parent.innerRadius

            // Colour is left to KDE on purpose. DECISION 72 measured that KDE and
            // Caelestia already agree on the selected-row recipe (a 30% accent
            // tint), so the palette is not the gap and is not being touched.
            color: {
                if (controlRoot.highlighted || controlRoot.down)
                    return Kirigami.Theme.highlightColor;
                if (controlRoot.hovered)
                    return Qt.alpha(Kirigami.Theme.hoverColor, 0.3);
                return Kirigami.Theme.alternateBackgroundColor;
            }
        }
    }
}
