// Luminos Media — one window for every photo and video.
// [CHANGE: claude-code | 2026-11-08]  DECISION 180
//
// Run through /usr/local/bin/luminos-media (the wrapper sets the session env, the
// VA-API shim, and the stderr bridge that carries "move to Trash" out of QML).
//
// Light on purpose (measured, see docs/media/README.md):
//  - photos: decoded at window size only; full resolution is decoded only after you
//    zoom past "fit", and dropped again when you go back to fit or move on.
//  - videos: Qt Multimedia (ffmpeg backend), hardware-decoded on the AMD 780M.
//  - the folder strip and its thumbnails exist only while the strip is open.
//  - nothing is cached to disk; closing the window ends the process.
import QtQuick
import QtQuick.Window
import QtQuick.Dialogs
import QtMultimedia
import Qt.labs.folderlistmodel

Window {
    id: root
    visible: true
    width: 1280; height: 820
    minimumWidth: 480; minimumHeight: 320
    color: c.win
    title: (cur.name !== "" ? cur.name + " — " : "") + "Luminos Media"

    // ── Palette (the live Nexus dark scheme) ────────────────────────────────
    QtObject {
        id: c
        readonly property color win: "#09090b"
        readonly property color glass: Qt.rgba(24/255, 23/255, 27/255, 0.80)
        readonly property color row: "#29282d"
        readonly property color rowHi: "#34333b"
        readonly property color sel: "#46455f"
        readonly property color accent: "#c4c0ff"
        readonly property color fg: "#e6e1e8"
        readonly property color fg2: "#c9c5d0"
        readonly property color fg3: "#928f99"
        readonly property color vid: "#f2c46d"
        readonly property string sans: "Google Sans Flex"
        readonly property string mono: "Roboto Mono"
        readonly property string icons: "Material Symbols Rounded"
    }

    // ── File types ──────────────────────────────────────────────────────────
    readonly property var imageExt: ["jpg","jpeg","jpe","jfif","png","apng","gif","webp","heic","heif","hif","avif",
        "jxl","bmp","tif","tiff","svg","svgz","ico","tga","psd","xcf","kra","ora","exr","hdr","qoi","pcx","pbm","pgm",
        "ppm","pnm","xbm","xpm","jp2","j2k","dds","jxr","wdp",
        "arw","cr2","cr3","crw","nef","nrw","orf","raf","rw2","rwl","pef","srw","dng","x3f","3fr","erf","kdc","mrw","mos","iiq","sr2","srf"]
    readonly property var videoExt: ["mp4","m4v","mkv","webm","mov","qt","avi","mpg","mpeg","mpe","m2v","ts","m2ts","mts",
        "3gp","3g2","wmv","asf","flv","ogv","ogm","divx","vob","mxf","f4v","rm","rmvb","y4m","nut"]
    readonly property var animExt: ["gif","apng"]     // WebP only when its header says animated (see webpCheck)
    readonly property var nameFilters: imageExt.concat(videoExt).map(function(e){ return "*." + e })

    function ext(path) { var m = /\.([^.\/]+)$/.exec(path); return m ? m[1].toLowerCase() : "" }
    function isVideo(path) { return videoExt.indexOf(ext(path)) >= 0 }
    function baseName(path) { return path.substring(path.lastIndexOf("/") + 1) }
    function dirOf(path) { return path.substring(0, path.lastIndexOf("/")) }
    function toUrl(path) { return "file://" + encodeURI(path).replace(/#/g, "%23").replace(/\?/g, "%3F") }
    function fromUrl(u) { var s = u.toString(); return s.indexOf("file://") === 0 ? decodeURIComponent(s.substring(7)) : s }
    function fmtTime(ms) {
        var s = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60
        return (h ? h + ":" + (m < 10 ? "0" : "") + m : m) + ":" + (x < 10 ? "0" : "") + x
    }
    function fmtSize(b) {
        if (!(b > 0)) return ""
        var u = ["B","KB","MB","GB"], i = 0; while (b >= 1024 && i < 3) { b /= 1024; i++ }
        return (i ? b.toFixed(b < 10 ? 1 : 0) : b) + " " + u[i]
    }

    // ── What is open ────────────────────────────────────────────────────────
    property string startPath: {
        var a = Qt.application.arguments, i = a.indexOf("--")
        for (var k = i + 1; i >= 0 && k < a.length; k++) if (a[k].indexOf("--luminos-") !== 0) return a[k]
        return ""
    }
    property int index: -1
    QtObject {
        id: cur
        readonly property bool inModel: root.index >= 0 && root.index < folder.count
        property string path: inModel ? folder.get(root.index, "filePath") : root.startPath
        property url url: inModel ? folder.get(root.index, "fileUrl") : (root.startPath !== "" ? root.toUrl(root.startPath) : "")
        property string name: path !== "" ? root.baseName(path) : ""
        property bool video: path !== "" && root.isVideo(path)
        property bool anim: root.animExt.indexOf(root.ext(path)) >= 0 || (root.ext(path) === "webp" && root.webpAnimated === path)
        property real bytes: root.index >= 0 && root.index < folder.count ? folder.get(root.index, "fileSize") : 0
        property var modified: root.index >= 0 && root.index < folder.count ? folder.get(root.index, "fileModified") : undefined
    }

    FolderListModel {
        id: folder
        folder: root.startPath !== "" ? root.toUrl(root.dirOf(root.startPath)) : ""
        nameFilters: root.nameFilters
        caseSensitive: false
        showDirs: false
        showHidden: false
        sortField: FolderListModel.Name
        sortCaseSensitive: false
        onStatusChanged: if (status === FolderListModel.Ready) root.relocate()
        onCountChanged: if (status === FolderListModel.Ready) root.relocate()
    }
    // Keep pointing at the same file when the folder changes under us (a file trashed,
    // added, renamed). If the current file vanished, stay at the same position.
    property string wantPath: startPath
    function relocate() {
        if (folder.count === 0) { index = -1; return }
        var i = -1
        for (var k = 0; k < folder.count; k++) if (folder.get(k, "filePath") === wantPath) { i = k; break }
        if (i < 0) i = Math.max(0, Math.min(index, folder.count - 1))
        if (i !== index) index = i
        wantPath = folder.get(index, "filePath")
    }
    function go(step) {
        if (folder.count < 2) return
        index = (index + step + folder.count) % folder.count
        wantPath = folder.get(index, "filePath")
    }
    function openPath(p) {
        startPath = p; wantPath = p; index = -1
        folder.folder = toUrl(dirOf(p))
    }

    // A still WebP is decoded at window size like any photo; only an animated one needs
    // AnimatedImage (which can't downscale without stretching). The VP8X header's flag
    // byte says which — read once per WebP (they are small).
    property string webpAnimated: ""
    function webpCheck() {
        var p = cur.path
        if (ext(p) !== "webp" || webpAnimated === p) return
        var x = new XMLHttpRequest()
        x.open("GET", cur.url); x.responseType = "arraybuffer"
        x.onreadystatechange = function() {
            if (x.readyState !== XMLHttpRequest.DONE || !x.response || p !== cur.path) return
            var b = new Uint8Array(x.response, 0, Math.min(32, x.response.byteLength))
            if (b.length > 20 && String.fromCharCode(b[12], b[13], b[14], b[15]) === "VP8X" && (b[20] & 2)) root.webpAnimated = p
        }
        x.send()
    }
    // Everything per-file resets when the PATH changes (index can change before cur.path does).
    Connections { target: cur; function onPathChanged() { root.resetView(); root.webpCheck() } }
    Component.onCompleted: webpCheck()
    property real zoom: 1        // multiple of "fit": 1 = fits the window
    property real panX: 0
    property real panY: 0
    property int  rot: 0
    property bool fillMode: false
    function resetView() { zoom = 1; panX = 0; panY = 0; rot = 0; info.parsed = false; info.wpx = 0; info.dims = ""; info.open && info.parse() }

    // ── Stage ───────────────────────────────────────────────────────────────
    Item {
        id: stage
        anchors.fill: parent
        clip: true
        readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1

        // Size of the decoded-at-window-size picture (or the animated one): it sets the
        // aspect and the fit. Full resolution never changes the on-screen size.
        readonly property real bw: cur.anim ? animImg.implicitWidth : (fitImg.status === Image.Ready ? fitImg.implicitWidth : 0)
        readonly property real bh: cur.anim ? animImg.implicitHeight : (fitImg.status === Image.Ready ? fitImg.implicitHeight : 0)
        // Smaller than the window: decoded at its own size, so this IS the original.
        readonly property bool small: bw < width * dpr - 2 && bh < height * dpr - 2
        readonly property real origW: full.status === Image.Ready ? full.implicitWidth : (small ? bw : info.wpx)
        readonly property bool sideways: root.rot % 180 !== 0
        readonly property real fitScale: {
            if (bw <= 0) return 1
            var w = sideways ? bh : bw, h = sideways ? bw : bh
            if (root.fillMode) return Math.max(width / w, height / h)
            var s = Math.min(width / w, height / h)
            return small ? Math.min(s, 1) : s      // never blow a small picture up when fitting
        }
        readonly property real scale: fitScale * root.zoom
        Item {
            id: photo
            visible: !cur.video && cur.path !== ""
            width: stage.bw * stage.scale
            height: stage.bh * stage.scale
            x: (stage.width - width) / 2 + root.panX
            y: (stage.height - height) / 2 + root.panY
            rotation: root.rot
            Behavior on rotation { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

            // Decoded at window size: what you see when the photo fits.
            Image {
                id: fitImg
                anchors.fill: parent
                visible: !cur.anim && full.status !== Image.Ready
                source: !cur.video && !cur.anim ? cur.url : ""
                sourceSize: Qt.size(Math.ceil(stage.width * stage.dpr), Math.ceil(stage.height * stage.dpr))
                asynchronous: true; cache: false; autoTransform: true; smooth: true; mipmap: true
            }
            // Full resolution: only while zoomed past fit.
            Image {
                id: full
                anchors.fill: parent
                visible: status === Image.Ready && !cur.anim
                source: !cur.video && !stage.small && root.zoom > 1.01 ? cur.url : ""
                asynchronous: true; cache: false; autoTransform: true; smooth: true; mipmap: true
            }
            // Animated GIF / WebP / APNG.
            AnimatedImage {
                id: animImg
                anchors.fill: parent
                visible: cur.anim
                source: cur.anim ? cur.url : ""
                asynchronous: true; cache: false; smooth: true
                playing: visible
            }
        }

        Text {
            anchors.centerIn: parent
            visible: !cur.video && cur.path !== "" && (cur.anim ? animImg.status === Image.Error : fitImg.status === Image.Error)
            text: "Can't show this picture.\n" + cur.name
            color: c.fg3; font.family: c.sans; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter
        }

        // Video
        VideoOutput {
            id: vout
            anchors.fill: parent
            visible: cur.video
            fillMode: root.fillMode ? VideoOutput.PreserveAspectCrop : VideoOutput.PreserveAspectFit
        }
        MediaPlayer {
            id: player
            source: cur.video ? cur.url : ""
            videoOutput: vout
            audioOutput: AudioOutput { id: audio; muted: controls.muted; volume: controls.volume }
            loops: controls.loop ? MediaPlayer.Infinite : 1
            playbackRate: controls.speed
            onSourceChanged: if (source.toString() !== "") play()
            onErrorOccurred: function(e, s) { console.warn("luminos-media: " + s) }
        }
        Text {
            anchors.centerIn: parent
            visible: cur.video && player.error !== MediaPlayer.NoError
            text: "Can't play this video.\n" + player.errorString
            color: c.fg3; font.family: c.sans; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter
        }
        // Big play glyph when paused.
        Rectangle {
            anchors.centerIn: parent
            width: 76; height: 76; radius: 38
            color: Qt.rgba(0.035, 0.035, 0.043, 0.55)
            visible: cur.video && player.playbackState !== MediaPlayer.PlayingState && player.error === MediaPlayer.NoError && player.mediaStatus !== MediaPlayer.LoadingMedia
            Text { anchors.centerIn: parent; text: "play_arrow"; font.family: c.icons; font.pixelSize: 44; color: c.fg }
        }

        // Empty state
        Column {
            anchors.centerIn: parent
            visible: cur.path === ""
            spacing: 14
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "photo_library"; font.family: c.icons; font.pixelSize: 56; color: c.fg3 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Open a photo or video, or drop one here"; color: c.fg2; font.family: c.sans; font.pixelSize: 16 }
            Pill { anchors.horizontalCenter: parent.horizontalCenter; IconButton { icon: "folder_open"; tip: "Open (Ctrl+O)"; onClicked: picker.open() } }
        }

        // Pan, wheel zoom, click to play, double-click to fill.
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: root.zoom > 1 && !cur.video ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.ArrowCursor
            property real sx; property real sy; property real px; property real py; property bool moved
            onPressed: function(m) { keys.forceActiveFocus(); sx = m.x; sy = m.y; px = root.panX; py = root.panY; moved = false; chrome.wake() }
            onPositionChanged: function(m) {
                chrome.wake()
                if (!pressed) return
                if (Math.abs(m.x - sx) + Math.abs(m.y - sy) > 4) moved = true
                if (root.zoom > 1) { root.panX = px + m.x - sx; root.panY = py + m.y - sy }
            }
            onClicked: if (!moved && cur.video) controls.togglePlay()
            onDoubleClicked: root.toggleFill()
            onWheel: function(w) {
                chrome.wake()
                if (cur.video) { controls.seekBy(w.angleDelta.y > 0 ? 5000 : -5000); return }
                root.zoomBy(w.angleDelta.y > 0 ? 1.15 : 1 / 1.15, w.x, w.y)
            }
        }
    }

    function zoomBy(f, cx, cy) {
        if (cur.video || stage.bw <= 0) return
        var nz = Math.max(1, Math.min(40, zoom * f))
        if (nz === zoom) return
        if (nz <= 1.001) { zoomFit(); return }
        if (cx === undefined) { cx = stage.width / 2; cy = stage.height / 2 }
        // Keep the point under the cursor still.
        var ox = cx - stage.width / 2 - panX, oy = cy - stage.height / 2 - panY
        panX -= ox * (nz / zoom - 1); panY -= oy * (nz / zoom - 1)
        zoom = nz
    }
    function zoomFit() { zoom = 1; panX = 0; panY = 0 }
    function zoomActual() {            // 1 image pixel = 1 screen pixel
        if (stage.origW <= 0 || stage.bw <= 0) return
        var z = stage.origW / (stage.bw * stage.fitScale * stage.dpr)
        if (z > 1.001) { zoom = z; panX = 0; panY = 0 } else zoomFit()
    }
    function toggleFill() { fillMode = !fillMode; zoomFit(); toast.show(fillMode ? "Fill window" : "Fit to window") }

    DropArea {
        anchors.fill: parent
        onDropped: function(d) { if (d.hasUrls) root.openPath(root.fromUrl(d.urls[0])) }
    }
    FileDialog {
        id: picker
        title: "Open"
        nameFilters: ["Photos and videos (" + root.nameFilters.join(" ") + ")", "All files (*)"]
        currentFolder: cur.path !== "" ? root.toUrl(root.dirOf(cur.path)) : ""
        onAccepted: root.openPath(root.fromUrl(selectedFile))
    }

    // ── Chrome (fades when idle) ────────────────────────────────────────────
    Item {
        id: chrome
        anchors.fill: parent
        opacity: awake ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 240 } }
        property bool awake: true
        function wake() { awake = true; idle.restart() }
        Timer { id: idle; interval: 2500; onTriggered: if (!info.open && !strip.open && !chrome.hovered) chrome.awake = false }
        property bool hovered: topHover.hovered || bottomHover.hovered || navL.hovered || navR.hovered

        // Top bar
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 80
            gradient: Gradient { GradientStop { position: 0; color: Qt.rgba(0.035,0.035,0.043,0.85) } GradientStop { position: 1; color: "transparent" } }
            HoverHandler { id: topHover }
            Row {
                anchors { left: parent.left; leftMargin: 18; verticalCenter: parent.verticalCenter; verticalCenterOffset: -8 }
                width: parent.width - rightTools.width - 50
                Column {
                    width: parent.width
                    Text { width: parent.width; text: cur.name; color: c.fg; font.family: c.sans; font.pixelSize: 15; font.weight: Font.Medium; elide: Text.ElideMiddle }
                    Text {
                        width: parent.width; elide: Text.ElideRight
                        color: c.fg3; font.family: c.mono; font.pixelSize: 12
                        text: {
                            var p = []
                            if (cur.video) { if (player.metaData.value(MediaMetaData.Resolution)) { var r = player.metaData.value(MediaMetaData.Resolution); p.push(r.width + " × " + r.height) } }
                            else if (full.status === Image.Ready) p.push(full.implicitWidth + " × " + full.implicitHeight)
                            else if (info.dims !== "") p.push(info.dims)
                            p.push(root.ext(cur.path).toUpperCase())
                            if (cur.bytes > 0) p.push(root.fmtSize(cur.bytes))
                            return p.join(" · ")
                        }
                    }
                }
            }
            Row {
                id: rightTools
                anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter; verticalCenterOffset: -8 }
                spacing: 10
                Pill {
                    visible: !cur.video && cur.path !== ""
                    IconButton { icon: "zoom_out"; tip: "Zoom out (−)"; onClicked: root.zoomBy(1 / 1.25) }
                    Rectangle {
                        width: 52; height: 38; radius: 19; color: zl.containsMouse ? c.rowHi : "transparent"
                        Text { anchors.centerIn: parent; color: c.fg2; font.family: c.mono; font.pixelSize: 12
                               text: root.zoom <= 1.001 ? (root.fillMode ? "Fill" : "Fit")
                                     : (stage.origW > 0 ? Math.round(photo.width * stage.dpr / stage.origW * 100) + "%" : root.zoom.toFixed(1) + "×") }
                        MouseArea { id: zl; anchors.fill: parent; hoverEnabled: true; onClicked: root.zoomFit() }
                    }
                    IconButton { icon: "zoom_in"; tip: "Zoom in (+)"; onClicked: root.zoomBy(1.25) }
                    IconButton { icon: "rotate_right"; tip: "Rotate (R)"; onClicked: root.rot = (root.rot + 90) % 360 }
                }
                Pill {
                    IconButton { icon: "grid_view"; tip: "Folder (G)"; on: strip.open; onClicked: strip.open = !strip.open }
                    IconButton { icon: "info"; tip: "Details (I)"; on: info.open; onClicked: info.toggle() }
                    IconButton { icon: "delete"; tip: "Move to Trash (Del)"; enabled: cur.path !== ""; onClicked: root.trash() }
                    IconButton { icon: "folder_open"; tip: "Open (Ctrl+O)"; onClicked: picker.open() }
                }
            }
        }

        // Side arrows
        Rectangle {
            id: navLr
            anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
            width: 48; height: 48; radius: 24; color: navL.hovered ? c.rowHi : c.glass; visible: folder.count > 1
            Text { anchors.centerIn: parent; text: "chevron_left"; font.family: c.icons; font.pixelSize: 28; color: c.fg }
            HoverHandler { id: navL }
            TapHandler { onTapped: root.go(-1) }
        }
        Rectangle {
            anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
            width: 48; height: 48; radius: 24; color: navR.hovered ? c.rowHi : c.glass; visible: folder.count > 1
            Text { anchors.centerIn: parent; text: "chevron_right"; font.family: c.icons; font.pixelSize: 28; color: c.fg }
            HoverHandler { id: navR }
            TapHandler { onTapped: root.go(1) }
        }

        // Bottom
        Rectangle {
            id: bottom
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: col.height + 28
            gradient: Gradient { GradientStop { position: 0; color: "transparent" } GradientStop { position: 1; color: Qt.rgba(0.035,0.035,0.043,0.9) } }
            HoverHandler { id: bottomHover }
            Column {
                id: col
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 14 }
                spacing: 10
                // Video bar
                Rectangle {
                    id: controls
                    visible: cur.video
                    width: parent.width; height: 46; radius: 23; color: c.glass
                    property bool muted: false
                    property real volume: 1
                    property bool loop: false
                    property real speed: 1
                    readonly property var speeds: [1, 1.25, 1.5, 2, 0.5]
                    function togglePlay() {
                        if (player.playbackState === MediaPlayer.PlayingState) player.pause()
                        else { if (player.mediaStatus === MediaPlayer.EndOfMedia) player.position = 0; player.play() }
                    }
                    function seekBy(ms) { if (player.seekable) player.position = Math.max(0, Math.min(player.duration, player.position + ms)) }
                    Row {
                        anchors { fill: parent; leftMargin: 4; rightMargin: 12 }
                        spacing: 8
                        IconButton { anchors.verticalCenter: parent.verticalCenter; icon: player.playbackState === MediaPlayer.PlayingState ? "pause" : "play_arrow"; tip: "Play / pause (Space)"; onClicked: controls.togglePlay() }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: root.fmtTime(seek.dragging ? seek.dragMs : player.position); color: c.fg2; font.family: c.mono; font.pixelSize: 12 }
                        Item {
                            id: seek
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - tail.width - 8; height: 24
                            property bool dragging: false
                            property real dragMs: 0
                            readonly property real frac: player.duration > 0 ? (dragging ? dragMs : player.position) / player.duration : 0
                            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; radius: 2; color: c.rowHi }
                            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * player.bufferProgress; height: 4; radius: 2; color: "#4a4852"; visible: player.bufferProgress < 1 }
                            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * seek.frac; height: 4; radius: 2; color: c.accent }
                            Rectangle { anchors.verticalCenter: parent.verticalCenter; x: parent.width * seek.frac - 7; width: 14; height: 14; radius: 7; color: c.accent }
                            MouseArea {
                                anchors.fill: parent
                                function at(mx) { return Math.max(0, Math.min(1, mx / width)) * player.duration }
                                onPressed: function(m) { seek.dragging = true; seek.dragMs = at(m.x) }
                                onPositionChanged: function(m) { if (pressed) seek.dragMs = at(m.x) }
                                onReleased: function(m) { player.position = at(m.x); seek.dragging = false }
                            }
                        }
                        Row {
                            id: tail
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            Text { anchors.verticalCenter: parent.verticalCenter; text: root.fmtTime(player.duration); color: c.fg2; font.family: c.mono; font.pixelSize: 12 }
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: spt.width + 20; height: 28; radius: 14; color: spm.containsMouse ? c.rowHi : c.row
                                Text { id: spt; anchors.centerIn: parent; text: controls.speed + "×"; color: c.fg; font.family: c.mono; font.pixelSize: 12 }
                                MouseArea { id: spm; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { var s = controls.speeds; controls.speed = s[(s.indexOf(controls.speed) + 1) % s.length]; toast.show("Speed " + controls.speed + "×") } }
                            }
                            IconButton { icon: controls.muted ? "volume_off" : "volume_up"; tip: "Mute (M)"; on: controls.muted; onClicked: { controls.muted = !controls.muted; toast.show(controls.muted ? "Muted" : "Sound on") } }
                            IconButton { icon: "repeat"; tip: "Loop (L)"; on: controls.loop; onClicked: { controls.loop = !controls.loop; toast.show(controls.loop ? "Loop on" : "Loop off") } }
                        }
                    }
                }
                Item {
                    width: parent.width; height: 18
                    Text { anchors.left: parent.left; color: c.fg3; font.family: c.mono; font.pixelSize: 12
                           text: folder.count > 0 ? (root.index + 1) + " / " + folder.count + " · " + root.dirOf(cur.path).replace(/^\/home\/[^\/]+/, "~") : "" }
                    Text { anchors.right: parent.right; visible: root.width > 760; color: c.fg3; font.family: c.sans; font.pixelSize: 12
                           text: "← → move · Space play · F fill · I details · G folder" }
                }
            }
        }
    }

    // ── Folder strip (built only while open) ────────────────────────────────
    Rectangle {
        id: strip
        property bool open: false
        anchors { left: parent.left; right: parent.right }
        height: 100
        y: open ? parent.height - height : parent.height
        Behavior on y { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
        color: Qt.rgba(14/255, 13/255, 17/255, 0.95)
        visible: y < parent.height
        Loader {
            anchors.fill: parent
            active: strip.open || strip.visible
            sourceComponent: ListView {
                id: lv
                anchors { fill: parent; margins: 12 }
                orientation: ListView.Horizontal
                spacing: 8
                model: folder
                clip: true
                currentIndex: root.index
                Component.onCompleted: positionViewAtIndex(root.index, ListView.Center)
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                delegate: Rectangle {
                    required property int index
                    required property string fileName
                    required property url fileUrl
                    required property string filePath
                    readonly property bool vid: root.isVideo(fileName)
                    width: 118; height: 76; radius: 10; color: c.row
                    border.width: index === root.index ? 2 : 0; border.color: c.accent
                    clip: true
                    Image {
                        anchors { fill: parent; margins: index === root.index ? 3 : 0 }
                        visible: !vid
                        source: vid ? "" : fileUrl
                        sourceSize: Qt.size(236, 152)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true; cache: false; autoTransform: true
                    }
                    Text { anchors.centerIn: parent; visible: vid; text: "movie"; font.family: c.icons; font.pixelSize: 30; color: c.vid }
                    Rectangle {
                        anchors { left: parent.left; bottom: parent.bottom; margins: 6 }
                        width: tg.width + 10; height: 16; radius: 4; color: Qt.rgba(0.035,0.035,0.043,0.75)
                        Text { id: tg; anchors.centerIn: parent; text: root.ext(fileName).toUpperCase(); font.family: c.mono; font.pixelSize: 10; color: vid ? c.vid : c.fg2 }
                    }
                    MouseArea { anchors.fill: parent; onClicked: { root.index = index; root.wantPath = filePath } }
                }
            }
        }
    }

    // ── Details sheet ───────────────────────────────────────────────────────
    Rectangle {
        id: info
        property bool open: false
        property bool parsed: false
        property string dims: ""
        property real wpx: 0
        property var rows: []
        width: Math.min(340, root.width * 0.86)
        anchors { top: parent.top; bottom: parent.bottom }
        x: open ? parent.width - width : parent.width
        Behavior on x { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
        visible: x < parent.width
        color: Qt.rgba(14/255, 13/255, 17/255, 0.96)

        function toggle() { open = !open; if (open) parse() }
        function parse() {
            if (parsed || cur.path === "") { build(); return }
            parsed = true; exif = ({}); dims = ""; wpx = 0
            build()
            if (cur.video) return
            // Read the file once, here only (never on a plain image switch), and pull
            // the size + camera tags out of it. Videos use Qt's own metadata instead.
            var x = new XMLHttpRequest(), want = cur.path
            x.open("GET", root.toUrl(want)); x.responseType = "arraybuffer"
            x.onreadystatechange = function() {
                if (x.readyState !== XMLHttpRequest.DONE || want !== cur.path || !x.response) return
                var r = meta.read(new Uint8Array(x.response), root.ext(want))
                info.exif = r; if (r.w) { info.dims = r.w + " × " + r.h; info.wpx = r.w }
                info.build()
            }
            x.send()
        }
        property var exif: ({})
        function build() {
            var R = [["Name", cur.name], ["Type", root.ext(cur.path).toUpperCase()]]
            if (cur.bytes > 0) R.push(["Size", root.fmtSize(cur.bytes)])
            if (cur.video) {
                var m = player.metaData, res = m.value(MediaMetaData.Resolution)
                if (res) R.push(["Dimensions", res.width + " × " + res.height])
                R.push(["Length", root.fmtTime(player.duration)])
                var vc = m.value(MediaMetaData.VideoCodec), ac = m.value(MediaMetaData.AudioCodec), fr = m.value(MediaMetaData.VideoFrameRate)
                if (vc !== undefined) R.push(["Video", m.stringValue(MediaMetaData.VideoCodec) + (fr ? " · " + Math.round(fr * 100) / 100 + " fps" : "")])
                if (ac !== undefined) R.push(["Audio", m.stringValue(MediaMetaData.AudioCodec)])
            } else {
                var e = info.exif
                if (full.status === Image.Ready) R.push(["Dimensions", full.implicitWidth + " × " + full.implicitHeight])
                else if (info.dims !== "") R.push(["Dimensions", info.dims])
                if (e.date) R.push(["Taken", e.date])
                if (e.camera) R.push(["Camera", e.camera])
                if (e.lens) R.push(["Lens", e.lens])
                var ex = [e.exposure, e.fnum, e.iso].filter(function(v) { return !!v }).join(" · ")
                if (ex) R.push(["Exposure", ex])
            }
            if (cur.modified) R.push(["Modified", Qt.formatDateTime(cur.modified, "yyyy-MM-dd hh:mm")])
            R.push(["Folder", root.dirOf(cur.path).replace(/^\/home\/[^\/]+/, "~")])
            rows = R
        }
        Connections { target: player; function onMetaDataChanged() { if (info.open && cur.video) info.build() } function onDurationChanged() { if (info.open && cur.video) info.build() } }
        Connections { target: full; function onStatusChanged() { if (info.open) info.build() } }

        Column {
            anchors { fill: parent; margins: 16; topMargin: 18 }
            spacing: 4
            Item {
                width: parent.width; height: 44
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Details"; color: c.fg; font.family: c.sans; font.pixelSize: 18; font.weight: Font.Medium }
                IconButton { anchors { right: parent.right; verticalCenter: parent.verticalCenter } icon: "close"; tip: "Close"; onClicked: info.open = false }
            }
            Repeater {
                model: info.rows
                Rectangle {
                    required property var modelData
                    required property int index
                    width: parent.width; height: Math.max(42, val.implicitHeight + 22)
                    color: c.row
                    topLeftRadius: index === 0 ? 18 : 4; topRightRadius: topLeftRadius
                    bottomLeftRadius: index === info.rows.length - 1 ? 18 : 4; bottomRightRadius: bottomLeftRadius
                    Text { id: key; anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter } text: modelData[0]; color: c.fg3; font.family: c.sans; font.pixelSize: 14 }
                    Text { id: val; anchors { right: parent.right; rightMargin: 14; left: key.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
                           text: modelData[1]; color: c.fg2; font.family: c.mono; font.pixelSize: 13; horizontalAlignment: Text.AlignRight; wrapMode: Text.WrapAnywhere }
                }
            }
        }
    }

    // ── Toast ───────────────────────────────────────────────────────────────
    Rectangle {
        id: toast
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 76 }
        width: tt.width + 28; height: 34; radius: 17; color: c.glass
        opacity: 0; visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        Text { id: tt; anchors.centerIn: parent; color: c.fg; font.family: c.sans; font.pixelSize: 13 }
        Timer { id: tth; interval: 1300; onTriggered: toast.opacity = 0 }
        function show(m) { tt.text = m; opacity = 1; tth.restart() }
    }

    // ── Trash: QML cannot touch the filesystem beyond XHR, so the request goes out
    // on stderr and the wrapper runs `gio trash` on it (only for files in the open folder).
    function trash() {
        if (cur.path === "") return
        var p = cur.path
        if (cur.video) player.stop()
        console.warn("LUMINOS_MEDIA_TRASH:" + p)
        toast.show("Moved " + baseName(p) + " to Trash")
        // The folder model sees the file go and relocate() keeps the position.
    }

    // ── Keys ────────────────────────────────────────────────────────────────
    onActiveChanged: if (active) keys.forceActiveFocus()
    Item {
        id: keys
        focus: true
        Keys.onPressed: function(k) {
            chrome.wake()
            var ctrl = k.modifiers & Qt.ControlModifier, shift = k.modifiers & Qt.ShiftModifier
            switch (k.key) {
            case Qt.Key_Right: if (cur.video && shift) controls.seekBy(10000); else root.go(1); break
            case Qt.Key_Left:  if (cur.video && shift) controls.seekBy(-10000); else root.go(-1); break
            case Qt.Key_PageDown: root.go(1); break
            case Qt.Key_PageUp: root.go(-1); break
            case Qt.Key_Home: if (folder.count) { root.index = 0; root.wantPath = folder.get(0, "filePath") } break
            case Qt.Key_End: if (folder.count) { root.index = folder.count - 1; root.wantPath = folder.get(folder.count - 1, "filePath") } break
            case Qt.Key_Space: if (cur.video) controls.togglePlay(); else root.go(1); break
            case Qt.Key_Up: if (cur.video) controls.volume = Math.min(1, controls.volume + 0.1); else root.zoomBy(1.25); break
            case Qt.Key_Down: if (cur.video) controls.volume = Math.max(0, controls.volume - 0.1); else root.zoomBy(1 / 1.25); break
            case Qt.Key_Plus: case Qt.Key_Equal: root.zoomBy(1.25); break
            case Qt.Key_Minus: root.zoomBy(1 / 1.25); break
            case Qt.Key_0: root.zoomFit(); break
            case Qt.Key_1: root.zoomActual(); break
            case Qt.Key_R: root.rot = (root.rot + (shift ? 270 : 90)) % 360; break
            case Qt.Key_F: root.toggleFill(); break
            case Qt.Key_F11: root.visibility = root.visibility === Window.FullScreen ? Window.Windowed : Window.FullScreen; break
            case Qt.Key_I: info.toggle(); break
            case Qt.Key_G: strip.open = !strip.open; break
            case Qt.Key_M: controls.muted = !controls.muted; break
            case Qt.Key_L: controls.loop = !controls.loop; toast.show(controls.loop ? "Loop on" : "Loop off"); break
            case Qt.Key_Delete: root.trash(); break
            case Qt.Key_O: if (ctrl) picker.open(); else return; break
            case Qt.Key_Q: case Qt.Key_W: if (ctrl) Qt.quit(); else return; break
            case Qt.Key_Escape:
                if (info.open) info.open = false
                else if (strip.open) strip.open = false
                else if (root.visibility === Window.FullScreen) root.visibility = Window.Windowed
                else Qt.quit()
                break
            default: return
            }
            k.accepted = true
        }
    }

    // ── Self-test output (luminos-media FILE --luminos-debug): one state line a second ──
    Timer {
        running: Qt.application.arguments.indexOf("--luminos-debug") >= 0
        repeat: true; interval: 1000
        onTriggered: console.log("LMDBG " + JSON.stringify({ file: cur.name, video: cur.video, index: root.index, count: folder.count,
            fit: fitImg.status, full: full.status, anim: animImg.status, bw: stage.bw, bh: stage.bh, shown: Math.round(photo.width) + "x" + Math.round(photo.height),
            zoom: root.zoom, play: player.playbackState, pos: player.position, dur: player.duration, media: player.mediaStatus, err: player.errorString }))
    }

    // ── Self-test (luminos-media FILE --luminos-selftest): drives the UI logic and logs results ──
    Timer {
        id: st
        property int step: 0
        running: Qt.application.arguments.indexOf("--luminos-selftest") >= 0
        repeat: true; interval: 1500
        function say(k, v) { console.log("LMTEST " + k + " " + JSON.stringify(v)) }
        onTriggered: {
            switch (step++) {
            case 0: say("open", { file: cur.name, fit: fitImg.status, count: folder.count, index: root.index }); root.zoomBy(3); break
            case 1: say("zoom3x", { zoom: root.zoom, full: full.status, fullW: full.implicitWidth, label: Math.round(photo.width * stage.dpr / Math.max(1, stage.origW) * 100) + "%" }); root.zoomFit(); break
            case 2: say("fitAgain", { zoom: root.zoom, fullReleased: full.source.toString() === "" }); info.toggle(); break
            case 3: say("details", info.rows); strip.open = true; break
            case 4: say("strip", { open: strip.open, visible: strip.visible }); strip.open = false; root.go(1); break
            case 5: say("next", { file: cur.name, index: root.index, video: cur.video }); break
            case 6: say("nextDetails", info.rows); root.go(1); break
            case 7: say("next2", { file: cur.name, video: cur.video, play: player.playbackState, pos: player.position }); break
            case 8:
                if (Qt.application.arguments.indexOf("--luminos-selftest-trash") >= 0) {
                    for (var k = 0; k < folder.count; k++) if (folder.get(k, "fileName") === "zz-trashme.png") { root.index = k; root.wantPath = folder.get(k, "filePath") }
                    say("beforeTrash", { file: cur.name, count: folder.count }); root.trash()
                }
                break
            case 10: say("afterTrash", { file: cur.name, count: folder.count, index: root.index }); break
            case 11: Qt.quit()
            }
        }
    }

    // ── Small components ────────────────────────────────────────────────────
    component Pill: Rectangle {
        default property alias content: row.data
        width: row.width + 8; height: 46; radius: 23; color: c.glass
        Row { id: row; anchors.centerIn: parent; spacing: 2 }
    }
    component IconButton: Rectangle {
        property string icon
        property string tip
        property bool on: false
        signal clicked
        width: 38; height: 38; radius: 19
        color: on ? c.sel : (ma.containsMouse ? c.rowHi : "transparent")
        opacity: enabled ? 1 : 0.4
        Text { anchors.centerIn: parent; text: parent.icon; font.family: c.icons; font.pixelSize: 22; color: c.fg }
        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: parent.clicked() }
    }

    // ── Header / EXIF reader (JPEG, TIFF-based RAW, HEIC/AVIF, PNG, GIF, WebP) ─
    QtObject {
        id: meta
        function u16(b, o, le) { return le ? b[o] | b[o+1] << 8 : b[o] << 8 | b[o+1] }
        function u32(b, o, le) { return le ? (b[o] | b[o+1] << 8 | b[o+2] << 16 | b[o+3] << 24) >>> 0 : (b[o] << 24 | b[o+1] << 16 | b[o+2] << 8 | b[o+3]) >>> 0 }
        function find(b, s, from, to) {
            var n = s.length; to = Math.min(to || b.length, b.length) - n
            outer: for (var i = from || 0; i <= to; i++) { for (var j = 0; j < n; j++) if (b[i+j] !== s.charCodeAt(j)) continue outer; return i }
            return -1
        }
        function str(b, o, n) { var s = ""; for (var i = 0; i < n && b[o+i]; i++) s += String.fromCharCode(b[o+i]); return s.trim() }
        function tiff(b, t, r) {
            if (t < 0 || t + 8 > b.length) return
            var le = b[t] === 0x49; if (!le && b[t] !== 0x4d) return
            function val(e) {
                var type = u16(b, e + 2, le), cnt = u32(b, e + 4, le), size = [0,1,1,2,4,8,1,1,2,4,8,4,8][type] || 1
                var off = size * cnt > 4 ? t + u32(b, e + 8, le) : e + 8
                if (off + size * cnt > b.length) return undefined
                if (type === 2) return str(b, off, cnt)
                if (type === 3) return u16(b, off, le)
                if (type === 4) return u32(b, off, le)
                if (type === 5 || type === 10) { var d = u32(b, off + 4, le); return d ? u32(b, off, le) / d : 0 }
                return undefined
            }
            function ifd(o, depth) {
                if (o <= 0 || t + o + 2 > b.length || depth > 3) return
                var n = u16(b, t + o, le)
                for (var k = 0; k < n; k++) {
                    var e = t + o + 2 + k * 12; if (e + 12 > b.length) return
                    var tag = u16(b, e, le)
                    switch (tag) {
                    case 0x010f: r.make = val(e); break
                    case 0x0110: r.model = val(e); break
                    case 0x9003: r.date = val(e); break
                    case 0x0132: if (!r.date) r.date = val(e); break
                    case 0x829a: var x = val(e); if (x) r.exposure = x >= 1 ? x + " s" : "1/" + Math.round(1 / x) + " s"; break
                    case 0x829d: var f = val(e); if (f) r.fnum = "f/" + (Math.round(f * 10) / 10); break
                    case 0x8827: r.iso = "ISO " + val(e); break
                    case 0x920a: var fl = val(e); if (fl) r.focal = Math.round(fl) + " mm"; break
                    case 0xa434: r.lensModel = val(e); break
                    case 0xa002: if (!r.w) r.w = val(e); break
                    case 0xa003: if (!r.h) r.h = val(e); break
                    case 0x8769: ifd(val(e), depth + 1); break
                    }
                }
            }
            ifd(u32(b, t + 4, le), 0)
        }
        function read(b, ext) {
            var r = {}
            try {
                if (b[0] === 0xff && b[1] === 0xd8) {                       // JPEG
                    var o = 2
                    while (o + 9 < b.length && b[o] === 0xff) {
                        var m = b[o+1], len = u16(b, o + 2, false)
                        if (m === 0xe1 && str(b, o + 4, 4) === "Exif") tiff(b, o + 10, r)
                        if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) { r.h = u16(b, o + 5, false); r.w = u16(b, o + 7, false); break }
                        o += 2 + len
                    }
                } else if (b[0] === 0x89 && b[1] === 0x50) { r.w = u32(b, 16, false); r.h = u32(b, 20, false) }   // PNG
                else if (str(b, 0, 3) === "GIF") { r.w = u16(b, 6, true); r.h = u16(b, 8, true) }
                else if (str(b, 0, 4) === "RIFF" && str(b, 8, 4) === "WEBP") {
                    var k = str(b, 12, 4)
                    if (k === "VP8X") { r.w = 1 + (b[24] | b[25] << 8 | b[26] << 16); r.h = 1 + (b[27] | b[28] << 8 | b[29] << 16) }
                    else if (k === "VP8 ") { r.w = u16(b, 26, true) & 0x3fff; r.h = u16(b, 28, true) & 0x3fff }
                    else if (k === "VP8L") { var v = u32(b, 21, true); r.w = (v & 0x3fff) + 1; r.h = (v >> 14 & 0x3fff) + 1 }
                } else if (str(b, 4, 4) === "ftyp") {                       // HEIC / AVIF
                    var best = 0, p = 0
                    while ((p = find(b, "ispe", p + 1, 1 << 20)) > 0) {
                        var w = u32(b, p + 8, false), h = u32(b, p + 12, false)
                        if (w * h > best) { best = w * h; r.w = w; r.h = h }
                    }
                    // Find the Exif block by its TIFF header. Searching for "Exif" is wrong here:
                    // the first hit is the item TYPE name in the iinf box, not the data.
                    var mm = find(b, "MM\0\x2a\0\0\0\x08", 0), ii = find(b, "II\x2a\0\x08\0\0\0", 0)
                    var t0 = mm < 0 ? ii : (ii < 0 ? mm : Math.min(mm, ii))
                    if (t0 >= 0) tiff(b, t0, r)
                } else if ((b[0] === 0x49 && b[1] === 0x49) || (b[0] === 0x4d && b[1] === 0x4d)) {   // TIFF / most RAW
                    tiff(b, 0, r)
                } else {
                    var e2 = find(b, "Exif\0\0", 0, 1 << 20); if (e2 >= 0) tiff(b, e2 + 6, r)
                }
            } catch (err) { console.log("luminos-media: metadata " + err) }
            if (r.make || r.model) {
                var mk = r.make || "", md = r.model || ""
                r.camera = md.indexOf(mk.split(" ")[0]) === 0 ? md : (mk + " " + md).trim()
            }
            if (r.lensModel || r.focal) r.lens = [r.focal, r.lensModel].filter(function(v) { return !!v }).join(" · ")
            if (r.date) r.date = r.date.replace(/^(\d{4}):(\d{2}):(\d{2})/, "$1-$2-$3").substring(0, 16)
            return r
        }
    }
}
