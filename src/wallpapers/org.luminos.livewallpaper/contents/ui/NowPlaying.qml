/*
    Luminos Live Wallpaper — what is playing, for a Lively page's TV.
    [CHANGE: claude-code | 2026-11-08] BUG-236.  SPDX-License-Identifier: GPL-3.0-or-later

    Loaded BY URL from WebMode, and only while the page defines livelyCurrentTrack AND
    the wallpaper is playing — so the MPRIS model (in-process, D-Bus signals, never
    polled) exists only while someone can see the TV. The helper script runs once per
    track change; its answer is cached per title in WebMode, so pausing and resuming
    the wallpaper does not run yt-dlp again.
*/
import QtQuick
import org.kde.plasma.private.mpris as Mpris
import org.kde.plasma.plasma5support as P5Support

Item {
    id: np

    signal track(var info)                    // null = nothing playing
    signal playback(bool playing, real seconds)

    property var cache: ({})                  // owned by WebMode: outlives this item
    readonly property string helper: decodeURIComponent(
        ("" + Qt.resolvedUrl("../tools/luminos-wallpaper-nowplaying")).replace("file://", ""))

    Mpris.Mpris2Model { id: model }
    readonly property var player: model.currentPlayer
    readonly property int status: player ? player.playbackStatus : Mpris.PlaybackStatus.Unknown
    readonly property bool playing: status === Mpris.PlaybackStatus.Playing
    readonly property bool live: player !== null && !!player.track
                                 && status !== Mpris.PlaybackStatus.Stopped
    readonly property string key: live ? player.track + "\n" + player.artist : ""

    // Players publish a new track in pieces (title, then artist, then cover).
    onKeyChanged: settle.restart()
    onPlayingChanged: np.report()
    Component.onCompleted: settle.restart()
    Timer { id: settle; interval: 700; onTriggered: np.lookup() }

    // A seek arrives as a position jump.
    Connections {
        target: np.player
        ignoreUnknownSignals: true
        function onPositionChanged() { np.report(); }
    }

    function report() {
        np.playback(np.playing, np.player ? np.player.position / 1e6 : 0);
    }

    function q(s) { return "'" + ("" + s).replace(/'/g, "'\\''") + "'"; }

    // Step 1 (fast): cover + which video it is. Step 2 (once per video, from disk
    // afterwards): the video file. The TV shows the cover while step 2 runs.
    function lookup() {
        if (!np.live) {
            np.track(null);
            return;
        }
        var hit = np.cache[np.player.track];
        if (hit) {
            np.deliver(hit);
            if (hit.Page && !hit.Video)
                np.fetchVideo(hit);
            return;
        }
        runner.connectSource("python3 " + np.q(np.helper) + " track " + np.q(np.player.track) + " "
                             + np.q(np.player.artUrl) + " " + np.q(np.player.identity));
    }

    function fetchVideo(info) {
        runner.connectSource("python3 " + np.q(np.helper) + " video " + np.q(info.Page)
                             + " #" + encodeURIComponent(info.Title));   // the comment keys the answer
    }

    function deliver(info) {
        info.Artist = np.player ? np.player.artist : "";
        np.track(info);
        if (np.player)
            np.player.updatePosition();
        np.report();
    }

    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (source, data) {
            disconnectSource(source);
            var out = null;
            try { out = JSON.parse(data["stdout"] || "null"); } catch (e) { out = null; }
            if (!out)
                return;
            if (out.Title !== undefined) {                     // step 1
                if (!np.live || out.Title !== np.player.track)
                    return;                                     // a stale answer for an old track
                np.cache[out.Title] = out;
                np.deliver(out);
                if (out.Page)
                    np.fetchVideo(out);
                return;
            }
            var title = decodeURIComponent(source.substring(source.lastIndexOf("#") + 1));
            var info = np.cache[title];                         // step 2
            if (!info)
                return;
            if (!out.Video) {
                info.Page = null;          // undownloadable: cover only, no retry this session
                return;
            }
            info.Video = out.Video;
            if (np.live && title === np.player.track)
                np.deliver(info);
        }
    }
}
