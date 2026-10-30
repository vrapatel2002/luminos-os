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

ColumnLayout {
    id: root

    // Assigned by the KDE wallpaper KCM; declared so assignment doesn't warn.
    property var configDialog
    property var wallpaperConfiguration

    // --- config keys (auto-bound by KDE) ---
    property string cfg_WallpaperMode
    property string cfg_WallpaperModeDefault: "image"
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

    // Where the bundled sample web wallpapers live once installed.
    readonly property string samplesDir:
        Qt.resolvedUrl("../samples").toString().replace("file://", "")

    function localPath(url) {
        var s = "" + url;
        return s.indexOf("file://") === 0 ? s.substring(7) : s;
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true

        // ---- Type selector ------------------------------------------
        QQC2.ComboBox {
            id: modeCombo
            Kirigami.FormData.label: i18n("Type:")
            textRole: "text"
            valueRole: "val"
            model: [
                { text: i18n("Image"),          val: "image" },
                { text: i18n("Video"),          val: "video" },
                { text: i18n("Web (HTML / JS)"), val: "web" }
            ]
            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(root.cfg_WallpaperMode))
            onActivated: root.cfg_WallpaperMode = currentValue
        }

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
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: i18n("Any HTML/CSS/JS or WebGL page. Local files and Shadertoy-style shaders work. YouTube links are auto-resolved for video mode.")
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
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: root.cfg_WallpaperMode === "video"
                ? i18n("Stretch fills the screen edge-to-edge. Center and Tile fall back to Stretch for video.")
                : i18n("Stretch fills the screen edge-to-edge with no black bars (slight distortion if the image shape differs from the screen).")
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Background colour:")
            KQuickControls.ColorButton {
                id: colorButton
                color: root.cfg_BackgroundColor
                onColorChanged: root.cfg_BackgroundColor = color
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
        id: webDialog
        title: i18n("Choose an HTML page")
        nameFilters: [ i18n("Web pages (*.html *.htm)"), i18n("All files (*)") ]
        onAccepted: root.cfg_WebUrl = root.localPath(selectedFile)
    }
}
