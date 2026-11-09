/*
    Luminos Live Wallpaper — the cursor, for a web wallpaper.
    [CHANGE: claude-code | 2026-11-08] BUG-236.  SPDX-License-Identifier: GPL-3.0-or-later

    The desktop's icon layer sits ABOVE the wallpaper and takes every pointer event,
    so the page never saw the mouse at all (0 events, measured). This item moves itself
    to the top of the window and only WATCHES: a HoverHandler with blocking:false and a
    PointHandler's passive grab never take an event away from the icons below, so
    desktop clicks, drags and icon hover work exactly as before.
*/
import QtQuick

Item {
    id: input

    property Item target: null                // the web view's item; coordinates map into it
    property bool clicks: false               // WebInteractive: forward presses too
    signal moved(real x, real y)
    signal pressed(real x, real y)
    signal released(real x, real y)

    parent: target && target.Window.window ? target.Window.window.contentItem : null
    anchors.fill: parent
    z: 1000000

    function at(p) { return input.mapToItem(input.target, p.x, p.y); }

    HoverHandler {
        blocking: false
        onPointChanged: { var q = input.at(point.position); input.moved(q.x, q.y); }
    }
    PointHandler {
        enabled: input.clicks
        acceptedButtons: Qt.LeftButton
        onActiveChanged: {
            var q = input.at(point.position);
            if (active) input.pressed(q.x, q.y); else input.released(q.x, q.y);
        }
        onPointChanged: if (active) { var q = input.at(point.position); input.moved(q.x, q.y); }
    }
}
