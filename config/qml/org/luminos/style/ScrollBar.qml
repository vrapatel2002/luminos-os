/*
    Replaces org.kde.desktop's ScrollBar.qml
    SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-or-later
*/

// [CHANGE: claude-code | 2026-09-03] Luminos OS — hide the scrollbar, KEEP the
// scrolling.
//
// This is a stub, not a deletion, and the difference matters. Scrolling in Qt
// Quick is done by the Flickable underneath; the ScrollBar is only an indicator
// you can also drag. But ScrollView still *binds* to its scrollbar — it writes
// `size`, `position` and `orientation` into it and reads `implicitWidth` back to
// decide how much room to leave for it. Setting `ScrollBar.vertical: null` makes
// those bindings fail and can leave the view mis-padded, so the object has to go
// on existing. It just has no size and nothing to paint.
//
// Consequences, on purpose:
//   - wheel, touch, drag-to-flick, keyboard and Home/End all still work — they
//     are Flickable behaviour and this file cannot reach them
//   - dragging the bar itself is gone, because there is no bar to grab
//   - views get back the ~12px that was reserved for the bar
//
// Scope: every Qt Quick app that goes through this style. QWidget scrollbars
// (Dolphin's sidebar, Kate, anything not QML) are a different code path and are
// unaffected — expect them to keep their bars.
//
// Revert: delete this file and re-run scripts/luminos-qml-style-build, which
// will symlink the upstream one back in.

import QtQuick
import QtQuick.Templates as T

T.ScrollBar {
    id: controlRoot

    // Zero implicit size is what actually does the hiding AND reclaims the space:
    // measured against stock, bar width 21 -> 0 and the list went 279 -> 300 wide.
    implicitWidth: 0
    implicitHeight: 0
    padding: 0

    // Not interactive: an invisible-but-live bar would still swallow clicks in a
    // strip at the edge of the content, which is a genuinely confusing bug.
    interactive: false

    // Belt and braces only — do NOT rely on this. ScrollView assigns `visible`
    // on its own scrollbars, so this binding gets overwritten and the bar still
    // reports visible: true. It draws nothing regardless, because it is 0 wide
    // and has no contentItem or background.
    visible: false

    contentItem: Item {}
    background: null
}
