/*
    Luminos Live Wallpaper — the web renderer, in a file of its own.
    SPDX-License-Identifier: GPL-3.0-or-later

    [CHANGE: claude-code | 2026-09-16] DECISION 112.

    THIS FILE EXISTS FOR ONE REASON: the `import QtWebEngine` below.

    It used to sit at the top of main.qml, which meant plasmashell mapped
    libQt6WebEngineCore.so - the whole of Chromium, ~130-150 MB - on every login,
    in EVERY mode. The mode switching was already correct: `modeLoader` uses
    sourceComponent, so a WebEngineView is never CREATED while a video is
    playing, and no Chromium child processes spawn. But a QML `import` is not
    conditional. It runs when the file containing it is loaded, and main.qml is
    always loaded.

    A QML file that is never loaded never runs its imports. So the web renderer
    lives here and main.qml reaches it through a Loader by FILENAME. In image,
    GIF, video and YouTube mode, Chromium is now never mapped at all.

    Nothing about the web wallpaper's behaviour changed - the body below is the
    old `webComp` verbatim. The only edit is that it no longer reaches out to
    `root`: it cannot, from a separate file, so the four things it needs arrive
    as properties bound by the Loader in main.qml.
*/
import QtQuick
import QtWebEngine
// PropertyStore imports nothing but QtQuick; the file read behind it is a
// subprocess, not a browser. Safe to pull in here. [CHANGE: claude-code | 2026-09-20]
import "props"

Item {
    id: webRoot

    // Bound by main.qml's Loader.onLoaded. Plain properties rather than
    // `required`, because a Loader can only pass required properties through
    // setSource(), which cannot carry bindings - and these must stay live.
    property url webSource
    property bool interactive: false
    property color bgColor: "black"
    property bool shouldPlay: true
    // The raw SceneProperties config string, passed through untouched — the
    // same key QML mode uses, keyed by the page's URL. BUG-183.
    property string sceneProperties: "{}"

    // Cursor position, written here and read by main.qml's injector.
    property real cursorX: 0
    property real cursorY: 0

    property alias webView: web

    anchors.fill: parent

    WebEngineView {
        id: web
        anchors.fill: parent
        url: webRoot.webSource
        // Full interactivity steals desktop clicks, so it is opt-in.
        enabled: webRoot.interactive
        backgroundColor: webRoot.bgColor
        settings.showScrollBars: false
        settings.playbackRequiresUserGesture: false

        function applyState() {
            web.lifecycleState = webRoot.shouldPlay
                ? WebEngineView.LifecycleState.Active
                : WebEngineView.LifecycleState.Frozen;
        }
        onLoadingChanged: function(info) {
            var ok = (info.status === WebEngineView.LoadSucceededStatus);
            if (ok)
                web.applyState();
            // A Lively page draws nothing until its properties arrive, so this
            // must flip on load and OFF on a reload — see LivelyApi.qml.
            lively.ready = ok;
        }
    }

    // CONTRACTS §4. Defaults from the page's own LivelyProperties.json (or a
    // properties.json beside it), saved values on top.
    PropertyStore {
        id: propStore
        sceneUrl: webRoot.webSource
        sceneId: "" + webRoot.webSource
        savedJson: webRoot.sceneProperties
    }

    LivelyApi {
        id: lively
        view: web
        schema: propStore.schema
        values: propStore.props
        playing: webRoot.shouldPlay
    }

    onShouldPlayChanged: web.applyState()

    // Cursor-follow without stealing clicks (non-interactive mode).
    MouseArea {
        anchors.fill: parent
        enabled: !webRoot.interactive
        visible: enabled
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        onPositionChanged: function(m) {
            webRoot.cursorX = m.x;
            webRoot.cursorY = m.y;
        }
    }
}
