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
import "props"
import "scene.js" as Scene

ColumnLayout {
    id: root

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
    property int cfg_ObscurePolicyDefault: 2
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

    // [CHANGE: claude-code | 2026-09-20] BUG-185. Above everything, because if
    // this page is stale then nothing below it does what it says.
    StaleCheck { id: staleCheck }
    Kirigami.InlineMessage {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        visible: staleCheck.stale
        type: Kirigami.MessageType.Warning
        text: i18n("This page is running an older copy of the wallpaper plugin — it was " +
                   "updated after this window opened. Close System Settings completely and " +
                   "open it again, or changes made here may not take effect.")
    }

    // =====================================================================
    //  THE ONLY CONTROL THAT MATTERS: pick a file.
    // =====================================================================
    RowLayout {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        QQC2.TextField {
            id: fileField
            Layout.fillWidth: true
            text: root.currentFile
            placeholderText: i18n("Pick a picture, video, web page, shader or script…")
            // Typed text is accepted too, so a YouTube or web address still works
            // without a second box for it.
            onEditingFinished: root.useFile(text)
        }
        QQC2.Button {
            text: i18n("Choose file…")
            icon.name: "document-open"
            onClicked: fileDialog.open()
        }
    }
    QQC2.Label {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        wrapMode: Text.WordWrap
        font: Kirigami.Theme.smallFont
        visible: root.pickProblem.length === 0
        opacity: 0.8
        // "nothing else to set" has to be TRUE. A wallpaper that ships its own
        // properties (Rain has sixteen) has plenty else to set, and saying
        // otherwise sends someone looking for a control they were told was not
        // there. [CHANGE: claude-code | 2026-09-20]
        text: root.currentKind === null
            ? i18n("Pick any picture, video, .html page, .frag shader, .js canvas script or "
                   + ".qml scene. A YouTube or web address works too.")
            : root.hasOwnSettings
            ? i18n("%1 — this one has its own settings, below.", root.currentKind.what)
            : i18n("%1 — nothing else to set.", root.currentKind.what)
    }
    QQC2.Label {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        wrapMode: Text.WordWrap
        visible: root.pickProblem.length > 0
        color: Kirigami.Theme.negativeTextColor
        font: Kirigami.Theme.smallFont
        text: root.pickProblem
    }

    // =====================================================================
    //  INSTALLED WALLPAPERS — the other way to pick one.  SPEC §3.3
    // =====================================================================
    Kirigami.Separator {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        Layout.topMargin: Kirigami.Units.largeSpacing
    }
    WallpaperGallery {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        currentEntry: root.activeEntry
        onPicked: function (type, entryPath) { root.usePackage(type, entryPath); }
    }

    // =====================================================================
    //  THE WALLPAPER'S OWN SETTINGS (SPEC §3.2) — Rain's sliders live here.
    // =====================================================================
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
    Kirigami.Separator {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        Layout.topMargin: Kirigami.Units.largeSpacing
        visible: root.propsMode && Object.keys(sceneProps.schema).length > 0
    }
    Kirigami.Heading {
        visible: root.propsMode && Object.keys(sceneProps.schema).length > 0
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        level: 3
        text: i18n("This wallpaper's own settings")
    }
    PropertyEditor {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        visible: root.propsMode
        schema: sceneProps.schema
        values: sceneProps.props
        problem: sceneProps.problem
        onChanged: function (key, value) {
            root.cfg_SceneProperties = sceneProps.withValue(root.propsId, key, value);
        }
    }

    // =====================================================================
    //  ADVANCED — closed by default. Nothing here is needed to set a wallpaper.
    // =====================================================================
    Kirigami.Separator {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40
        Layout.topMargin: Kirigami.Units.largeSpacing
    }
    QQC2.CheckBox {
        id: advanced
        text: i18n("Advanced options")
        checked: false
    }
    Kirigami.FormLayout {
        visible: advanced.checked
        Layout.fillWidth: true
        // Without a cap the form grows to its widest child, which on a maximised
        // dialog drags every row to the right. [CHANGE: claude-code | 2026-09-19] BUG-169
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40

        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Built-in scene:")
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
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Fit:")
            model: [ i18n("Stretch"), i18n("Keep proportions"), i18n("Fill and crop"),
                     i18n("Centre"), i18n("Tile") ]
            currentIndex: root.cfg_FillMode
            onActivated: root.cfg_FillMode = currentIndex
        }
        KQuickControls.ColorButton {
            Kirigami.FormData.label: i18n("Background colour:")
            property bool armed: false
            Component.onCompleted: { color = root.cfg_BackgroundColor; armed = true; }
            // Set once, never bound — a bound colour strands the dialog (BUG-174).
            onColorChanged: if (armed) root.cfg_BackgroundColor = color
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Save power:")
            text: i18n("Pause on battery")
            checked: root.cfg_PauseOnBattery
            onToggled: root.cfg_PauseOnBattery = checked
        }
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Stop rendering when hidden:")
            model: [ i18n("Never"), i18n("Only under a fullscreen window"),
                     i18n("Whenever a window covers the desktop") ]
            currentIndex: root.cfg_ObscurePolicy
            onActivated: root.cfg_ObscurePolicy = currentIndex
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Sound:")
            text: i18n("Mute the wallpaper")
            checked: root.cfg_MuteAudio
            onToggled: root.cfg_MuteAudio = checked
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Audio:")
            text: i18n("React to what is playing")
            checked: root.cfg_AudioReactive
            onToggled: root.cfg_AudioReactive = checked
        }
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Web pages:")
            text: i18n("Let the page take clicks")
            checked: root.cfg_WebInteractive
            onToggled: root.cfg_WebInteractive = checked
        }
        QQC2.CheckBox {
            text: i18n("Give the page live system stats")
            checked: root.cfg_InjectSystemStats
            onToggled: root.cfg_InjectSystemStats = checked
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
