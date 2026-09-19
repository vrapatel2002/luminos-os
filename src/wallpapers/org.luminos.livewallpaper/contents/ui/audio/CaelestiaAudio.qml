/*
    Luminos Live Wallpaper — the one file that knows where audio comes from.
    [CHANGE: claude-code | 2026-09-19]  DECISION 117.
    SPDX-License-Identifier: GPL-3.0-or-later

    Caelestia ships a plain Qt QML module at /usr/lib/qt6/qml/Caelestia/Services
    whose qmldir declares NO Quickshell dependency — verified on the box by
    scripts/luminos-wallpaper-capabilities, not assumed. That is why this is
    twenty lines instead of a helper daemon: plasmashell can import it directly.

    Two facts about the C++ behind it, read from the source rather than guessed
    (reference_code/caelestia-shell-2.2.0/plugin/src/Caelestia/Services):

      cavaprovider.cpp   calls cava_execute() — it LINKS libcava and reads
                         PipeWire itself. It never spawns the `cava` CLI, so the
                         binary on PATH is irrelevant.
      service.hpp        Service::ref/unref refcount the thing. A provider runs
                         while at least one ServiceRef points at it and stops
                         when the last one goes away.

    That refcount is why the freeze contract costs nothing here: this whole file
    is loaded and unloaded by AudioBridge's Loader, so the refs come and go with
    it and the FFT thread stops itself.
*/
import QtQuick
import Caelestia.Services

Item {
    id: provider

    visible: false
    width: 0
    height: 0

    // Set by AudioBridge to its bandCount. 128 to match Lively exactly.
    property int bars: 128

    readonly property var values: cava.values
    readonly property real bpm: tracker.bpm

    signal beat(real bpm)

    CavaProvider {
        id: cava
        bars: provider.bars
    }

    BeatTracker {
        id: tracker
        onBeat: function (b) { provider.beat(b); }
    }

    ServiceRef { service: cava }
    ServiceRef { service: tracker }
}
