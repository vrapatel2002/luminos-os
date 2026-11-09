/*
    Luminos Live Wallpaper — the installed-wallpaper gallery.  SPEC §3.3.
    [CHANGE: claude-code | 2026-09-19]  DECISION 123, CONTRACTS §5.
    SPDX-License-Identifier: GPL-3.0-or-later

    Its own file, not more of config.qml: that one is already 449 lines and is
    exempt from SPEC §9 by name (BUG-179), and growing it further would be
    spending an exemption someone else granted.

    Reads `tools/luminos-wallpaper-gallery` — inside the package, because the
    config page must work from an installed KPackage with no repo beside it, the
    same rule DECISION 119 set for the shader baker.

    A package we cannot play is shown GREYED WITH ITS REASON, never hidden. A
    wallpaper that vanishes after importing reads as a failed import.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

ColumnLayout {
    id: gallery

    // (type, absolute entry path) for something the user picked.
    signal picked(string type, string entryPath)

    // The entry path the wallpaper is ACTUALLY showing, so the grid can say which
    // tile is the current one. [CHANGE: claude-code | 2026-09-20] BUG-185 — there
    // was no selected state at all: a click changed a config key and nothing on
    // screen, so "I clicked it and nothing happened" was a correct description of
    // a working gallery.
    property string currentEntry: ""

    property var items: []
    property string problem: ""
    property bool busy: false

    function toolPath(name) {
        var u = "" + Qt.resolvedUrl("../tools/" + name);
        return u.indexOf("file://") === 0 ? u.substring(7) : u;
    }
    function shQuote(s) { return "'" + ("" + s).replace(/'/g, "'\\''") + "'"; }

    function refresh() {
        gallery.busy = true;
        runner.connectSource("python3 " + gallery.shQuote(gallery.toolPath("luminos-wallpaper-gallery")));
    }
    function install(path) {
        gallery.busy = true;
        runner.connectSource("python3 " + gallery.shQuote(gallery.toolPath("luminos-wallpaper-install"))
                             + " install " + gallery.shQuote(path));
    }

    Component.onCompleted: gallery.refresh()

    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (src, data) {
            disconnectSource(src);
            gallery.busy = false;
            var out = ("" + (data["stdout"] || "")).trim();
            if (src.indexOf("luminos-wallpaper-install") >= 0) {
                // The installer answers OK <id> or ERR <line>.
                if (out.indexOf("ERR ") === 0)
                    gallery.problem = out.substring(4);
                else
                    gallery.problem = "";
                gallery.refresh();
                return;
            }
            try {
                gallery.items = JSON.parse(out.length > 0 ? out : "[]");
                gallery.problem = "";
            } catch (e) {
                // Never an empty grid with no explanation — BUG-170's lesson.
                gallery.items = [];
                gallery.problem = i18n("could not read the installed wallpapers");
            }
        }
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183: the count + Install button moved to config.qml's
    // section header (it calls openInstall()); the grid shows every tile (no inner scrolling inside the
    // page's own scroll) and ends with an "Add wallpaper" tile.
    function openInstall() { importDialog.open(); }

    QQC2.Label {
        visible: gallery.problem.length > 0
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Kirigami.Theme.negativeTextColor
        font: Kirigami.Theme.smallFont
        text: i18n("Could not install that: %1", gallery.problem)
    }

    GridView {
        id: grid
        Layout.fillWidth: true
        readonly property int columns: Math.max(2, Math.floor(width / (Kirigami.Units.gridUnit * 9)))
        cellWidth: Math.floor(width / columns)
        cellHeight: Math.round(cellWidth * 10 / 16) + 52
        Layout.preferredHeight: Math.ceil(count / columns) * cellHeight
        interactive: false
        model: gallery.items.concat([{ add: true }])

        delegate: GalleryTile {
            required property var modelData
            width: grid.cellWidth
            height: grid.cellHeight
            tileData: modelData
            currentEntry: gallery.currentEntry
            onPicked: function (type, entryPath) { gallery.picked(type, entryPath); }
            onAddRequested: importDialog.open()
        }
    }

    Dialogs.FileDialog {
        id: importDialog
        title: i18n("Pick a wallpaper folder's manifest, or a .zip")
        nameFilters: [ i18n("Wallpaper packages (luminos-wallpaper.json LivelyInfo.json *.zip)"),
                       i18n("All files (*)") ]
        onAccepted: {
            var p = ("" + selectedFile).replace("file://", "");
            // A folder is picked by choosing the manifest inside it.
            gallery.install(p.replace(/\/(luminos-wallpaper|LivelyInfo)\.json$/, ""));
        }
    }
}
