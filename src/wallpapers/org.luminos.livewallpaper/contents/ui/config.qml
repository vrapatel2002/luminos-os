/*
    Luminos Live Wallpaper — configuration panel (shown inside KDE Wallpaper settings).
    [CHANGE: claude-code | 2026-07-22]
    [CHANGE: claude-code | 2026-09-20]  DECISION 129 — ONE PICKER.
    SPDX-License-Identifier: GPL-3.0-or-later

    Shawn: "just select file and it sets the wallpaper according to file
    selected. simple that's it."

    So there is no Type selector any more. There used to be one, and it was the
    source of most of this plugin's usability bugs: the person had to know that a
    .html is a "web" wallpaper and a .frag is a "qml" one before the file picker
    would even offer the right files, and picking the wrong type left them
    staring at a row that asked for a file they did not have. The file already
    knows what it is. `Scene.modeForFile()` reads it, and that table is tested —
    which a combo box never was.

    Everything the old panel could still do, it still does; the controls nobody
    changes are behind one "Advanced" toggle, closed by default.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import org.kde.kquickcontrols as KQuickControls
import org.kde.kirigami as Kirigami
// [CHANGE: claude-code | 2026-09-19] DECISION 118 — SPEC §3.2
import QtCore
import org.kde.plasma.plasma5support as P5Support
import QtQuick.Effects
import "props"
import "scene.js" as Scene

// [CHANGE: claude-code | 2026-11-09] DECISION 183 — Luminos look (approved prototype
// docs/windowstyle/mock/desktop-settings.html): a "now showing" card with a preview and the actions,
// the installed wallpapers as a grid, the wallpaper's own settings, then power/sound switches and a
// folded "More options". Every setting, key and code path below is unchanged — only layout.
ColumnLayout {
    id: root
    spacing: 3

    // Assigned by the KDE wallpaper KCM; declared so assignment doesn't warn.
    property var configDialog
    property var wallpaperConfiguration

    // --- config keys (auto-bound by KDE) ---
    property string cfg_WallpaperMode
    property string cfg_WallpaperModeDefault: "image"
    property string cfg_QmlScene
    property string cfg_QmlSceneDefault: "shader"
    property string cfg_Image
    property string cfg_ImageDefault: ""
    property string cfg_Video
    property string cfg_VideoDefault: ""
    property string cfg_WebUrl
    property string cfg_WebUrlDefault: ""
    property int cfg_FillMode
    property int cfg_FillModeDefault: 0
    property color cfg_BackgroundColor
    property color cfg_BackgroundColorDefault: "#000000"
    property bool cfg_PauseOnBattery
    property bool cfg_PauseOnBatteryDefault: true
    property int cfg_ObscurePolicy
    property int cfg_ObscurePolicyDefault: 3 // [CHANGE: claude-code | 2026-11-07]
    property bool cfg_MuteAudio
    property bool cfg_MuteAudioDefault: true
    property bool cfg_WebInteractive
    property bool cfg_WebInteractiveDefault: false
    property bool cfg_InjectSystemStats
    property bool cfg_InjectSystemStatsDefault: false
    // [CHANGE: claude-code | 2026-09-19] DECISION 117
    property bool cfg_AudioReactive
    property bool cfg_AudioReactiveDefault: false
    property string cfg_SceneProperties
    property string cfg_ScenePropertiesDefault: "{}"

    // Set when a gallery click could not be honoured, shown under the grid.
    // [CHANGE: claude-code | 2026-09-20] BUG-185.
    property string pickProblem: ""

    // Which entry path the wallpaper is ACTUALLY showing, so the gallery can mark
    // it. One place, because the cfg_ keys live here and a gallery that worked it
    // out for itself would be a second copy of the answer.
    readonly property string activeEntry:
          root.cfg_WallpaperMode === "web"   ? root.cfg_WebUrl
        : root.cfg_WallpaperMode === "video" ? root.cfg_Video
        : root.cfg_WallpaperMode === "qml"   ? root.cfg_QmlScene
        : root.cfg_Image

    // A package's `type` decides which mode shows it. One place, so the gallery
    // need not know about config keys and config.qml need not know about
    // manifests. [CHANGE: claude-code | 2026-09-19] SPEC §3.3
    function usePackage(type, entryPath) {
        var m = Scene.modeForType(type);
        if (m === null) {
            // BUG-183/BUG-185: a click that changes nothing must say so, and a
            // journal line is not saying so — nobody reads the journal while
            // clicking a wallpaper.
            root.pickProblem = i18n("This page could not use a \"%1\" wallpaper. It is " +
                "running an older copy of the plugin — close System Settings and open it again.",
                type);
            console.warn("[LUMINOS-WP] no mode for package type", type, "— cached QML? (BUG-171)");
            return;
        }
        root.apply(m, entryPath);
    }

    // The one place a chosen thing becomes settings. Both the file picker and the
    // gallery end up here, so they cannot disagree. [CHANGE: claude-code | 2026-09-20]
    function apply(m, path) {
        root.pickProblem = "";
        root.cfg_WallpaperMode = m.mode;
        if (m.key === "QmlScene")
            root.cfg_QmlScene = path;
        else if (m.key === "Video")
            root.cfg_Video = path;
        else if (m.key === "WebUrl")
            root.cfg_WebUrl = path;
        else
            root.cfg_Image = path;
    }

    // DECISION 129: the file decides. Empty path is not an error — it is someone
    // clearing the box — but an unrecognised one must say so, by name.
    function useFile(path) {
        var clean = ("" + path).trim();
        if (clean.length === 0) {
            root.pickProblem = "";
            return;
        }
        var m = Scene.modeForFile(clean);
        if (m === null) {
            root.pickProblem = i18n("Luminos does not know how to show %1.", clean);
            return;
        }
        root.apply(m, clean);
    }

    // What the wallpaper is showing now, in one string, whatever the mode. Also
    // what the gallery marks as current.
    readonly property string currentFile: root.activeEntry
    readonly property var currentKind: Scene.modeForFile(root.currentFile)
    readonly property bool hasOwnSettings:
        sceneProps.loaded && Object.keys(sceneProps.schema).length > 0

    function localPath(url) {
        var s = "" + url;
        return s.indexOf("file://") === 0 ? s.substring(7) : s;
    }


    readonly property real pageWidth: Kirigami.Units.gridUnit * 40
    readonly property bool showsVideoFile: !root.currentPackage && root.cfg_WallpaperMode === "video"
        && (root.cfg_Video.charAt(0) === "/" || root.cfg_Video.indexOf("file://") === 0)
    onCfg_VideoChanged: if (root.showsVideoFile) thumbTimer.restart() // a newly picked video gets its own still
    readonly property var currentPackage: {
        const items = gallery.items || [];
        for (let i = 0; i < items.length; ++i)
            if (("" + items[i].entryPath) === root.activeEntry) return items[i];
        return null;
    }
    readonly property string currentTitle: root.currentPackage ? (root.currentPackage.title || root.currentPackage.id)
        : root.currentFile.length ? root.currentFile.replace(/\/+$/, "").split("/").pop().replace(/\.[^.]+$/, "")
        : i18n("Built-in scene")
    function surprise() {
        const items = (gallery.items || []).filter(it => it.playable === true && ("" + it.entryPath) !== root.activeEntry);
        if (items.length === 0) return;
        const it = items[Math.floor(Math.random() * items.length)];
        root.usePackage("" + it.type, "" + it.entryPath);
    }

    // [CHANGE: claude-code | 2026-09-20] BUG-185. Above everything, because if
    // this page is stale then nothing below it does what it says.
    StaleCheck { id: staleCheck }
    Kirigami.InlineMessage {
        Layout.fillWidth: true
        Layout.maximumWidth: root.pageWidth
        Layout.alignment: Qt.AlignHCenter
        Layout.leftMargin: 24; Layout.rightMargin: 24
        visible: staleCheck.stale
        type: Kirigami.MessageType.Warning
        text: i18n("This page is running an older copy of the wallpaper plugin — it was " +
                   "updated after this window opened. Close System Settings completely and " +
                   "open it again, or changes made here may not take effect.")
    }

    ColumnLayout {
        id: pageColumn
        Layout.fillWidth: true
        Layout.maximumWidth: root.pageWidth
        Layout.alignment: Qt.AlignHCenter
        Layout.leftMargin: 24; Layout.rightMargin: 24
        Layout.bottomMargin: 24
        spacing: 3

        // ================= NOW SHOWING =================
        LxRows.Section { text: i18n("Now showing") }
        LxRows.Card {
            first: true; last: false
            topPadding: 18; bottomPadding: 18
            contentItem: GridLayout {
                columns: pageColumn.width > Kirigami.Units.gridUnit * 30 ? 2 : 1
                columnSpacing: 22; rowSpacing: 14

                Rectangle { // the preview, like a little monitor
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 13
                    Layout.preferredHeight: Layout.preferredWidth * 9 / 16
                    Layout.alignment: Qt.AlignVCenter
                    radius: 12
                    color: "#0b0b0e"
                    border.width: 5; border.color: "#0b0b0e"
                    Rectangle { id: previewMask; anchors.fill: previewArea; radius: 8; visible: false; layer.enabled: true }
                    Item {
                        id: previewArea
                        anchors.fill: parent; anchors.margins: 5
                        layer.enabled: true
                        layer.effect: MultiEffect { maskEnabled: true; maskSource: previewMask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
                        Image {
                            id: previewImage
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            visible: source.toString().length > 0
                            source: root.currentPackage && root.currentPackage.previewPath ? "file://" + root.currentPackage.previewPath
                                  : (root.cfg_WallpaperMode === "image" && root.cfg_Image.length) ? (root.cfg_Image.charAt(0) === "/" ? "file://" + root.cfg_Image : root.cfg_Image)
                                  : ""
                        }
                        // a video shows its first frame (decoded once, then paused — no second player running)
                        // a video gets one still frame, made once by ffmpeg into ~/.cache (no second player
                        // runs inside the settings window; KDE also builds this page as a throw-away copy)
                        Image {
                            id: previewThumb
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: false
                            visible: root.showsVideoFile && source.toString().length > 0 && status === Image.Ready
                        }
                        P5Support.DataSource {
                            id: thumbRunner
                            engine: "executable"
                            property string target: ""
                            onNewData: function (src, data) {
                                disconnectSource(src);
                                if (("" + data["stdout"]).indexOf("LXTHUMB_OK") >= 0)
                                    previewThumb.source = "file://" + thumbRunner.target;
                            }
                        }
                        Timer {
                            id: thumbTimer
                            interval: 600
                            running: root.showsVideoFile
                            repeat: false
                            onTriggered: {
                                if (!root.showsVideoFile) return;
                                const v = root.localPath(root.cfg_Video);
                                const out = StandardPaths.writableLocation(StandardPaths.GenericCacheLocation).toString().replace("file://", "")
                                          + "/luminos/wallpaper-thumbs/" + Qt.md5(v) + ".jpg";
                                thumbRunner.target = out;
                                const q = s => "'" + ("" + s).replace(/'/g, "'\\''") + "'";
                                thumbRunner.connectSource("sh -c " + q("mkdir -p \"$(dirname " + q(out) + ")\" && { [ -s " + q(out) + " ] || ffmpeg -nostdin -loglevel error -y -ss 3 -i " + q(v) + " -frames:v 1 -vf scale=640:-2 " + q(out) + "; } && echo LXTHUMB_OK"));
                            }
                        }
                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: 48; height: 48
                            visible: !previewThumb.visible && previewImage.source.toString().length === 0
                            source: root.cfg_WallpaperMode === "web" ? "internet-web-browser-symbolic"
                                  : root.cfg_WallpaperMode === "qml" ? "applications-graphics-symbolic"
                                  : root.cfg_WallpaperMode === "video" ? "video-x-generic-symbolic" : "image-x-generic-symbolic"
                            opacity: 0.5
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.currentTitle
                        font.pixelSize: 19
                        font.weight: Font.Medium
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        opacity: 0.65
                        elide: Text.ElideMiddle
                        text: root.currentKind === null ? i18n("Pick a picture, video, web page, shader or script")
                            : root.currentKind.what + (root.hasOwnSettings ? i18n(" · has its own settings below") : "")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: root.pickProblem.length > 0
                        wrapMode: Text.WordWrap
                        color: Kirigami.Theme.negativeTextColor
                        text: root.pickProblem
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 10
                        spacing: 8
                        QQC2.Button {
                            text: i18n("Choose file…")
                            icon.name: "document-open"
                            onClicked: fileDialog.open()
                        }
                        QQC2.Button {
                            text: i18n("Surprise me")
                            icon.name: "media-playlist-shuffle"
                            enabled: (gallery.items || []).length > 1
                            onClicked: root.surprise()
                            QQC2.ToolTip.text: i18n("Picks a random installed wallpaper — press Apply to keep it")
                            QQC2.ToolTip.visible: hovered
                        }
                    }
                }
            }
        }
        LxRows.Card { // typed paths and web / YouTube addresses still work
            first: false; last: true
            contentItem: RowLayout {
                spacing: 12
                Kirigami.Icon { source: "link"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                QQC2.TextField {
                    id: fileField
                    Layout.fillWidth: true
                    text: root.currentFile
                    placeholderText: i18n("File path, web or YouTube address…")
                    onEditingFinished: root.useFile(text)
                    background: Rectangle { radius: height / 2; color: Qt.alpha(Kirigami.Theme.textColor, 0.06) }
                    leftPadding: 14; rightPadding: 14
                }
            }
        }

        // ================= INSTALLED =================
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 14
            LxRows.Section {
                Layout.topMargin: 0
                Layout.fillWidth: true
                text: gallery.busy ? i18n("Working…")
                    : (gallery.items || []).length === 0 ? i18n("No wallpapers installed yet")
                    : i18np("%1 installed wallpaper", "%1 installed wallpapers", gallery.items.length)
            }
            QQC2.Button {
                text: i18n("Install…")
                icon.name: "document-import"
                flat: true
                onClicked: gallery.openInstall()
            }
        }
        LxRows.Card {
            first: true; last: true
            topPadding: 12; bottomPadding: 12; leftPadding: 12; rightPadding: 12
            contentItem: WallpaperGallery {
                id: gallery
                currentEntry: root.activeEntry
                onPicked: function (type, entryPath) { root.usePackage(type, entryPath); }
            }
        }

        // ================= THE WALLPAPER'S OWN SETTINGS (SPEC §3.2) =================
        LxRows.Section {
            visible: root.propsMode && Object.keys(sceneProps.schema).length > 0
            text: i18n("This wallpaper")
        }
        PropertyEditor {
            Layout.fillWidth: true
            visible: root.propsMode && root.hasOwnSettings // a wallpaper with no settings shows nothing here
            schema: sceneProps.schema
            values: sceneProps.props
            problem: sceneProps.problem
            onChanged: function (key, value) {
                root.cfg_SceneProperties = sceneProps.withValue(root.propsId, key, value);
            }
        }

        // ================= PICTURE =================
        LxRows.Section { text: i18n("Picture") }
        LxRows.Card {
            first: true; last: true
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Fit"); subtitle: i18n("How it fills the screen") }
                QQC2.ComboBox {
                    model: [ i18n("Stretch"), i18n("Keep proportions"), i18n("Fill and crop"),
                             i18n("Centre"), i18n("Tile") ]
                    currentIndex: root.cfg_FillMode
                    onActivated: root.cfg_FillMode = currentIndex
                }
            }
        }

        // ================= POWER AND SOUND =================
        LxRows.Section { text: i18n("Power and sound") }
        LxRows.Card {
            first: true; last: false; clickable: true
            onClicked: root.cfg_PauseOnBattery = !root.cfg_PauseOnBattery
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Pause on battery"); subtitle: i18n("Saves power when unplugged") }
                QQC2.Switch { checked: root.cfg_PauseOnBattery; onToggled: root.cfg_PauseOnBattery = checked }
            }
        }
        LxRows.Card {
            first: false; last: false
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Stop when hidden"); subtitle: i18n("Stops drawing while windows cover the desktop") }
                QQC2.ComboBox {
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 14
                    model: [ i18n("Never"), i18n("Only under a fullscreen window"),
                             i18n("Whenever a window covers the desktop"),
                             i18n("Only while I'm looking at the desktop") ] // [CHANGE: claude-code | 2026-11-07]
                    currentIndex: root.cfg_ObscurePolicy
                    onActivated: root.cfg_ObscurePolicy = currentIndex
                }
            }
        }
        LxRows.Card {
            first: false; last: false; clickable: true
            onClicked: root.cfg_MuteAudio = !root.cfg_MuteAudio
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Mute the wallpaper"); subtitle: i18n("Videos and pages play without sound") }
                QQC2.Switch { checked: root.cfg_MuteAudio; onToggled: root.cfg_MuteAudio = checked }
            }
        }
        LxRows.Card {
            first: false; last: true; clickable: true
            onClicked: root.cfg_AudioReactive = !root.cfg_AudioReactive
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("React to what is playing"); subtitle: i18n("Audio-reactive wallpapers move with your music") }
                QQC2.Switch { checked: root.cfg_AudioReactive; onToggled: root.cfg_AudioReactive = checked }
            }
        }

        // ================= MORE OPTIONS (closed by default) =================
        LxRows.Card {
            id: advanced
            property bool expanded: false
            Layout.topMargin: 12
            first: true; last: !advanced.expanded; clickable: true
            onClicked: advanced.expanded = !advanced.expanded
            Accessible.name: i18n("More options")
            contentItem: RowLayout {
                spacing: 10
                Kirigami.Icon {
                    source: "go-next-symbolic"
                    implicitWidth: 16; implicitHeight: 16
                    rotation: advanced.expanded ? 90 : 0
                    Behavior on rotation { NumberAnimation { duration: 120 } }
                    opacity: 0.7
                }
                QQC2.Label { text: i18n("More options"); Layout.fillWidth: true; opacity: 0.85 }
            }
        }
        LxRows.Card {
            visible: advanced.expanded
            first: false; last: false; clickable: true
            onClicked: root.cfg_WebInteractive = !root.cfg_WebInteractive
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Let web wallpapers take clicks"); subtitle: i18n("Off = clicks always go to your desktop icons") }
                QQC2.Switch { checked: root.cfg_WebInteractive; onToggled: root.cfg_WebInteractive = checked }
            }
        }
        LxRows.Card {
            visible: advanced.expanded
            first: false; last: false; clickable: true
            onClicked: root.cfg_InjectSystemStats = !root.cfg_InjectSystemStats
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Give pages live system stats"); subtitle: i18n("CPU, memory and temperature for system-monitor wallpapers") }
                QQC2.Switch { checked: root.cfg_InjectSystemStats; onToggled: root.cfg_InjectSystemStats = checked }
            }
        }
        LxRows.Card {
            visible: advanced.expanded
            first: false; last: false
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Background colour"); subtitle: i18n("Shows around a \"Keep proportions\" picture") }
                KQuickControls.ColorButton {
                    property bool armed: false
                    Component.onCompleted: { color = root.cfg_BackgroundColor; armed = true; }
                    // Set once, never bound — a bound colour strands the dialog (BUG-174).
                    onColorChanged: if (armed) root.cfg_BackgroundColor = color
                }
            }
        }
        LxRows.Card {
            visible: advanced.expanded
            first: false; last: true
            contentItem: RowLayout {
                spacing: 12
                LxRows.TitleText { title: i18n("Built-in scene"); subtitle: i18n("Used when no file is chosen") }
                QQC2.ComboBox {
                    textRole: "text"
                    valueRole: "val"
                    model: [
                        { text: i18n("Shader — animated rings"), val: "shader" },
                        { text: i18n("Spectrum — audio bars"),   val: "spectrum" },
                        { text: i18n("Aurora"),                  val: "aurora" },
                        { text: i18n("Particles"),               val: "particles" },
                        { text: i18n("System monitor"),          val: "sysmon" }
                    ]
                    onActivated: root.apply({ mode: "qml", key: "QmlScene" }, currentValue)
                }
            }
        }
    }

    // ---- the wallpaper's own settings: data side (unchanged) ----
    readonly property bool propsMode: root.cfg_WallpaperMode === "qml"
                                   || root.cfg_WallpaperMode === "web"
    readonly property string propsId: root.cfg_WallpaperMode === "web"
                                    ? root.cfg_WebUrl : root.cfg_QmlScene

    PropertyStore {
        id: sceneProps
        sceneId: root.propsId
        savedJson: root.cfg_SceneProperties
        sceneUrl: {
            if (root.cfg_WallpaperMode === "web")
                return root.cfg_WebUrl;
            var base = Scene.propsBaseFor(root.cfg_QmlScene);
            return Scene.isAbsolute(base) ? base : Qt.resolvedUrl(base);
        }
    }

    // ---- the one file picker -------------------------------------------
    Dialogs.FileDialog {
        id: fileDialog
        title: i18n("Choose a wallpaper file")
        nameFilters: [ i18n("Wallpapers (%1)", Scene.fileDialogPatterns().join(" ")),
                       i18n("All files (*)") ]
        onAccepted: root.useFile(root.localPath(selectedFile))
    }
}
