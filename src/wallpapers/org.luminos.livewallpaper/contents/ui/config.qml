/*
    Luminos Live Wallpaper — configuration panel (shown inside KDE Wallpaper settings).
    [CHANGE: claude-code | 2026-07-22]
    SPDX-License-Identifier: GPL-3.0-or-later
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

    // A package's `type` decides which mode shows it. One place, so the gallery
    // need not know about config keys and config.qml need not know about
    // manifests. [CHANGE: claude-code | 2026-09-19] SPEC §3.3
    function usePackage(type, entryPath) {
        var m = Scene.modeForType(type);
        if (m === null)
            return;              // never offered; the gallery emits only playable rows
        root.cfg_WallpaperMode = m.mode;
        if (m.key === "QmlScene")
            root.cfg_QmlScene = entryPath;
        else if (m.key === "Video")
            root.cfg_Video = entryPath;
        else
            root.cfg_Image = entryPath;
    }


    // Where the bundled sample web wallpapers live once installed.
    readonly property string samplesDir:
        Qt.resolvedUrl("../samples").toString().replace("file://", "")

    function localPath(url) {
        var s = "" + url;
        return s.indexOf("file://") === 0 ? s.substring(7) : s;
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true
        // Without a cap the form grows to its widest child, which on a maximised
        // dialog drags every row to the right and leaves a gap on the left.
        // [CHANGE: claude-code | 2026-09-19] BUG-169
        Layout.maximumWidth: Kirigami.Units.gridUnit * 40

        // ---- Type selector ------------------------------------------
        QQC2.ComboBox {
            id: modeCombo
            Kirigami.FormData.label: i18n("Type:")
            textRole: "text"
            valueRole: "val"
            model: [
                { text: i18n("Image"),          val: "image" },
                { text: i18n("Video"),          val: "video" },
                { text: i18n("Web (HTML / JS)"), val: "web" },
                { text: i18n("Native QML (no browser)"), val: "qml" }
            ]
            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(root.cfg_WallpaperMode))
            onActivated: root.cfg_WallpaperMode = currentValue
        }

        // ---- INSTALLED WALLPAPERS — SPEC §3.3 ----------------------
        // [CHANGE: claude-code | 2026-09-19] DECISION 123. The grid itself is
        // ui/WallpaperGallery.qml; this file is already 449 lines and exempt from
        // SPEC §9 by name (BUG-179), so it gets the wiring and nothing more.
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: i18n("Installed wallpapers")
        }
        WallpaperGallery {
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            onPicked: function (type, entryPath) { root.usePackage(type, entryPath); }
        }
        Item { Kirigami.FormData.isSection: true }

        // ---- IMAGE --------------------------------------------------
        RowLayout {
            Kirigami.FormData.label: i18n("Image file:")
            visible: root.cfg_WallpaperMode === "image"
            QQC2.TextField {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 18
                text: root.cfg_Image
                onTextEdited: root.cfg_Image = text
                placeholderText: i18n("/path/to/picture.jpg")
            }
            QQC2.Button {
                text: i18n("Browse…")
                icon.name: "document-open"
                onClicked: imageDialog.open()
            }
        }

        // ---- VIDEO --------------------------------------------------
        RowLayout {
            Kirigami.FormData.label: i18n("Video file:")
            visible: root.cfg_WallpaperMode === "video"
            QQC2.TextField {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 18
                text: root.cfg_Video
                onTextEdited: root.cfg_Video = text
                placeholderText: i18n("/path/to/clip.mp4")
            }
            QQC2.Button {
                text: i18n("Browse…")
                icon.name: "document-open"
                onClicked: videoDialog.open()
            }
        }

        // ---- WEB ----------------------------------------------------
        RowLayout {
            Kirigami.FormData.label: i18n("Web page:")
            visible: root.cfg_WallpaperMode === "web"
            QQC2.TextField {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 18
                text: root.cfg_WebUrl
                onTextEdited: root.cfg_WebUrl = text
                placeholderText: i18n("https://…  or  /path/to/index.html")
            }
            QQC2.Button {
                text: i18n("Browse…")
                icon.name: "document-open"
                onClicked: webDialog.open()
            }
        }
        QQC2.Label {
            visible: root.cfg_WallpaperMode === "web"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("Any HTML/CSS/JS or WebGL page. Local files and Shadertoy-style shaders work. YouTube links are auto-resolved for video mode. This mode loads a full browser engine — for the bundled effects, Native QML does the same thing far more cheaply.")
        }

        // ---- NATIVE QML --------------------------------------------
        // [CHANGE: claude-code | 2026-09-16] DECISION 113
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Scene:")
            visible: root.cfg_WallpaperMode === "qml"
            textRole: "text"
            valueRole: "val"
            model: [
                { text: i18n("Shader (GPU gradient)"),       val: "shader" },
                { text: i18n("Shadertoy sample (audio-reactive)"), val: "sample-shadertoy" },
                { text: i18n("Aurora (drifting blobs)"),     val: "aurora" },
                { text: i18n("Particles (cursor-reactive)"), val: "particles" },
                { text: i18n("System monitor (live stats)"), val: "sysmon" },
                { text: i18n("Spectrum (audio-reactive bars)"), val: "spectrum" },
                { text: i18n("Canvas sample (JavaScript, no browser)"), val: "sample-canvasjs" },
                { text: i18n("Shadertoy shader (pick a .frag below)"), val: "shadertoy" },
                { text: i18n("Canvas wallpaper (pick a .js below)"), val: "canvasjs" },
                { text: i18n("PipeWire node (SPEC §3.6, experimental)"), val: "producer" }
            ]
            Component.onCompleted: {
                var i = indexOfValue(root.cfg_QmlScene);
                currentIndex = i >= 0 ? i : 0;
            }
            // "shadertoy" is not a scene you can select — it is a prompt for a file.
            // Storing it would leave the wallpaper with no shader, which falls back
            // to Aurora and looks like the entry is broken.
            // [CHANGE: claude-code | 2026-09-19] DECISION 119
            onActivated: {
                if (currentValue === "shadertoy" || currentValue === "canvasjs")
                    sceneDialog.open();
                else if (currentValue === "sample-canvasjs") {
                    // Same reasoning as the shader sample: it listens to audio,
                    // audio is opt-in, so picking it opts in visibly.
                    // [CHANGE: claude-code | 2026-09-19] SPEC §3.5
                    root.cfg_QmlScene = root.samplesDir + "/luminos-canvas.js";
                    root.cfg_AudioReactive = true;
                }
                else if (currentValue === "sample-shadertoy") {
                    root.cfg_QmlScene = root.samplesDir + "/luminos-shadertoy.frag";
                    // The entry says audio-reactive, and audio is opt-in and off by
                    // default — so without this the sample renders and never reacts,
                    // which reads as broken. Choosing it IS the opt-in, and the
                    // checkbox below visibly shows what happened.
                    root.cfg_AudioReactive = true;
                }
                else
                    root.cfg_QmlScene = currentValue;
            }
        }
        RowLayout {
            Kirigami.FormData.label: i18n("…or your own file:")
            visible: root.cfg_WallpaperMode === "qml"
            QQC2.TextField {
                Layout.fillWidth: true
                placeholderText: i18n("/path/to/scene.qml, /path/to/shader.frag or /path/to/wallpaper.js")
                // A built-in is already named in the combo above; echoing its key
                // here read as "this scene is a file called spectrum", which invited
                // typing a media path into a box that takes scenes and shaders.
                // [CHANGE: claude-code | 2026-09-19]
                text: Scene.BUILTINS[root.cfg_QmlScene] !== undefined ? "" : root.cfg_QmlScene
                onEditingFinished: {
                    if (text.length > 0)
                        root.cfg_QmlScene = text;
                }
            }
            // [CHANGE: claude-code | 2026-09-19] DECISION 119 — one box, both kinds.
            QQC2.Button {
                text: i18n("Browse…")
                icon.name: "document-open"
                onClicked: sceneDialog.open()
            }
        }
        QQC2.Label {
            visible: root.cfg_WallpaperMode === "qml"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("The same effects as the web samples, drawn by Qt directly. No browser engine is loaded, so this costs far less than Web mode. A scene may declare running, stats, audio, props, cursorX and cursorY and they will be bound for it. A .frag is compiled on the spot and run as a Shadertoy shader — iTime, iResolution, iMouse and iChannel0 (the audio spectrum) are all provided. A .js runs as a canvas wallpaper against canvas, ctx, requestAnimationFrame, window.luminos and livelyAudioListener — the surface a Lively JavaScript wallpaper expects. There is no DOM, no fetch and no WebGL, and a script needing one of those says so by name instead of showing you nothing.")
        }

        // ---- NATIVE QML: audio --------------------------------------
        // [CHANGE: claude-code | 2026-09-19] DECISION 117, SPEC §3.1
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Audio:")
            visible: root.cfg_WallpaperMode === "qml"
            text: i18n("React to whatever is playing")
            checked: root.cfg_AudioReactive || root.cfg_QmlScene === "spectrum"
            enabled: root.cfg_QmlScene !== "spectrum"
            onToggled: root.cfg_AudioReactive = checked
        }
        QQC2.Label {
            visible: root.cfg_WallpaperMode === "qml"
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("This does not play anything — it listens to your speakers. Play a file in any player (VLC, mpv, Elisa) or a video in your browser and the wallpaper follows it. 128 frequency bands from the current output, the same shape Lively uses, so a Lively audio wallpaper works here unchanged. Costs a PipeWire capture stream and an FFT thread while it runs, and stops with the wallpaper when the desktop is hidden. The Spectrum scene switches it on for itself.")
        }

        // ---- WEB: bundled samples ----------------------------------
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Load sample:")
            visible: root.cfg_WallpaperMode === "web"
            textRole: "text"
            valueRole: "file"
            model: [
                { text: i18n("— pick a bundled wallpaper —"), file: "" },
                { text: i18n("Aurora (drifting blobs)"),      file: "luminos-aurora.html" },
                { text: i18n("Particles (cursor-reactive)"),  file: "luminos-particles.html" },
                { text: i18n("Shader (WebGL gradient)"),      file: "luminos-shader.html" },
                { text: i18n("System monitor (live stats)"),  file: "luminos-sysmon.html" }
            ]
            currentIndex: 0
            onActivated: {
                if (currentValue && currentValue.length > 0)
                    root.cfg_WebUrl = root.samplesDir + "/" + currentValue;
            }
        }

        // ---- WEB: interactivity + live stats -----------------------
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Web options:")
            visible: root.cfg_WallpaperMode === "web"
            text: i18n("Let the page receive mouse clicks")
            checked: root.cfg_WebInteractive
            onToggled: root.cfg_WebInteractive = checked
        }
        QQC2.Label {
            visible: root.cfg_WallpaperMode === "web"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("Off: cursor movement still reaches the page, but clicks go to the desktop icons. On: the page gets full mouse and clicks (desktop clicks are captured while it is on).")
        }
        QQC2.CheckBox {
            visible: root.cfg_WallpaperMode === "web"
            text: i18n("Expose live CPU/GPU/RAM stats to the page (window.luminos)")
            checked: root.cfg_InjectSystemStats
            onToggled: root.cfg_InjectSystemStats = checked
        }

        Item { Kirigami.FormData.isSection: true }

        // ---- Scaling (image / video) — Windows-parity fit modes -----
        // [CHANGE: claude-code | 2026-07-23]
        QQC2.ComboBox {
            id: fitCombo
            Kirigami.FormData.label: i18n("Fit:")
            visible: root.cfg_WallpaperMode !== "web"
            textRole: "text"
            valueRole: "val"
            model: [
                { text: i18n("Stretch — fill screen, no bars"), val: 0 },
                { text: i18n("Fit — keep proportions (adds bars)"), val: 1 },
                { text: i18n("Fill — crop to fill"), val: 2 },
                { text: i18n("Center"), val: 3 },
                { text: i18n("Tile"), val: 4 }
            ]
            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(root.cfg_FillMode))
            onActivated: root.cfg_FillMode = currentValue
        }
        QQC2.Label {
            visible: root.cfg_WallpaperMode !== "web"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: root.cfg_WallpaperMode === "video"
                ? i18n("Stretch fills the screen edge-to-edge. Center and Tile fall back to Stretch for video.")
                : i18n("Stretch fills the screen edge-to-edge with no black bars (slight distortion if the image shape differs from the screen).")
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Background colour:")
            // Set once, not bound: onColorChanged fires for a programmatic
            // change too, so `color: <a value this handler writes>` loops
            // ColorButton's internal ColorDialog and strands it open. BUG-174.
            // [CHANGE: claude-code | 2026-09-19]
            KQuickControls.ColorButton {
                id: colorButton
                property bool armed: false
                Component.onCompleted: {
                    color = root.cfg_BackgroundColor;
                    armed = true;
                }
                onColorChanged: {
                    if (colorButton.armed)
                        root.cfg_BackgroundColor = "" + color;
                }
            }
        }

        Item { Kirigami.FormData.isSection: true }

        // ---- Power / thermal guards ---------------------------------
        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Save power:")
            text: i18n("Freeze while on battery")
            checked: root.cfg_PauseOnBattery
            onToggled: root.cfg_PauseOnBattery = checked
        }
        // [CHANGE: claude-code | 2026-07-24] was a single checkbox that treated a
        // maximized window the same as a fullscreen one — all or nothing.
        QQC2.ComboBox {
            Kirigami.FormData.label: i18n("Stop rendering when hidden:")
            model: [ i18n("Never — keep rendering even when hidden"),
                     i18n("Only under a fullscreen window"),
                     i18n("Whenever the desktop is hidden (recommended)") ]
            currentIndex: Math.max(0, Math.min(2, root.cfg_ObscurePolicy))
            onActivated: root.cfg_ObscurePolicy = currentIndex
        }
        QQC2.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("Frames drawn behind a window are decoded, uploaded and composited on the iGPU that also runs KWin and the browser. Nobody sees them.")
        }
        QQC2.CheckBox {
            visible: root.cfg_WallpaperMode === "video"
            text: i18n("Mute video audio")
            checked: root.cfg_MuteAudio
            onToggled: root.cfg_MuteAudio = checked
        }
    }

    // ---- THE SCENE'S OWN SETTINGS  (SPEC §3.2, CONTRACTS §4) -------------
    // [CHANGE: claude-code | 2026-09-19] DECISION 118
    // Nothing here knows what any scene's settings are. The scene ships a
    // properties.json, this reads it, and the panel appears. Resolving the scene
    // through scene.js is what guarantees the panel edits the properties of the
    // scene the wallpaper will actually load.
    PropertyStore {
        id: sceneProps
        sceneId: root.cfg_QmlScene
        savedJson: root.cfg_SceneProperties
        // Beside the shader for a .frag, beside the scene otherwise — the same
        // rule QmlMode uses, from the same file. [CHANGE: claude-code | 2026-09-19]
        sceneUrl: {
            var base = Scene.propsBaseFor(root.cfg_QmlScene);
            return Scene.isAbsolute(base) ? base : Qt.resolvedUrl(base);
        }
    }

    Kirigami.Separator {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        Layout.topMargin: Kirigami.Units.largeSpacing
        visible: root.cfg_WallpaperMode === "qml"
    }
    Kirigami.Heading {
        visible: root.cfg_WallpaperMode === "qml"
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        Layout.topMargin: Kirigami.Units.largeSpacing
        level: 3
        text: i18n("Scene settings")
    }
    QQC2.Label {
        visible: root.cfg_WallpaperMode === "qml"
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        wrapMode: Text.WordWrap
        font: Kirigami.Theme.smallFont
        text: i18n("Declared by the scene itself, in a properties.json beside it.")
    }
    PropertyEditor {
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        visible: root.cfg_WallpaperMode === "qml"
        schema: sceneProps.schema
        values: sceneProps.props
        problem: sceneProps.problem
        // The panel owns the config key; the wallpaper only ever reads it.
        onChanged: function (key, value) {
            root.cfg_SceneProperties = sceneProps.withValue(root.cfg_QmlScene, key, value);
        }
    }

    // ---- file pickers ----
    Dialogs.FileDialog {
        id: imageDialog
        title: i18n("Choose an image")
        nameFilters: [ i18n("Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif)"), i18n("All files (*)") ]
        onAccepted: root.cfg_Image = root.localPath(selectedFile)
    }
    Dialogs.FileDialog {
        id: videoDialog
        title: i18n("Choose a video")
        nameFilters: [ i18n("Videos (*.mp4 *.webm *.mkv *.mov *.avi)"), i18n("All files (*)") ]
        onAccepted: root.cfg_Video = root.localPath(selectedFile)
    }
    Dialogs.FileDialog {
        id: sceneDialog
        title: i18n("Choose a QML scene or a shader")
        nameFilters: [ i18n("Scenes, shaders and scripts (*.qml *.frag *.glsl *.fsh *.js *.mjs)"),
                       i18n("All files (*)") ]
        onAccepted: root.cfg_QmlScene = root.localPath(selectedFile)
    }
    Dialogs.FileDialog {
        id: webDialog
        title: i18n("Choose an HTML page")
        nameFilters: [ i18n("Web pages (*.html *.htm)"), i18n("All files (*)") ]
        onAccepted: root.cfg_WebUrl = root.localPath(selectedFile)
    }
}
