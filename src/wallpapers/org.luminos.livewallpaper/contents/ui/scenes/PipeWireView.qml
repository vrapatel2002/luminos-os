/*
    The only file that imports org.kde.pipewire.  SPEC §3.6.
    [CHANGE: claude-code | 2026-09-19]  SPDX-License-Identifier: GPL-3.0-or-later

    Separate and loaded BY URL for the DECISION 112 reason: a QML import runs when
    the file DECLARING it is loaded, so naming kpipewire in Producer.qml would pull
    it into plasmashell for every wallpaper, including a still image — and would
    make the whole plugin fail to load on a machine without it.

    PipeWireSourceItem scales the stream itself; it has NO `fillMode` (assigning
    one cost a load failure that then reported "kpipewire is not available", which
    was a lie my own error message told). Its real surface is small and worth
    using rather than guessing at: `state`, `ready`, `streamSize`, `paintedRect`,
    `usingDmaBuf`.
*/
import QtQuick
import org.kde.pipewire as PipeWire

PipeWire.PipeWireSourceItem {
    id: view
}
