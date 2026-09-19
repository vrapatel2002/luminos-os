/*
    Luminos Live Wallpaper — per-scene properties.  SPEC §3.2, CONTRACTS §4.
    [CHANGE: claude-code | 2026-09-19]  DECISION 118, reader replaced 120.
    SPDX-License-Identifier: GPL-3.0-or-later

    One object, used by BOTH sides: the wallpaper reads `props`, the settings
    panel reads `schema` and calls `withValue()`. Two copies of merge logic that
    drift is how a slider ends up showing one number while the wallpaper renders
    another, so there is one copy and it lives here.

    The merge rules deliberately mirror `scripts/luminos-wallpaper-pkg`'s
    `validate_properties()` and `merge_props()` — same known-type set, same
    "unknown type is skipped, not fatal", same "saved wins, default otherwise,
    null if the entry has no value". That Python is the tested copy; this is the
    one that runs in plasmashell. Change one, change both, and run tests/wallpaper.

    The FILE READ is not done here: Qt 6.11 disables local file reads through
    XMLHttpRequest, and the version that used XHR could not tell "blocked" from
    "no file", so it reported a scene as having no settings while its settings
    file sat next to it (BUG-170). PropsReader.qml does the read, and is reached
    by URL so that an import missing in some context is a named warning rather
    than a broken settings dialog.
*/
import QtQuick

Item {
    id: store

    // Not rendered and not laid out — Qt Quick Layouts skip invisible items, so
    // this can sit in the settings panel's ColumnLayout without leaving a gap.
    visible: false
    width: 0
    height: 0

    // ---- inputs ---------------------------------------------------------
    // The file whose SIBLINGS hold properties.json: the scene for a built-in,
    // the .frag for a runtime shader — otherwise every shader on the machine
    // would share one settings panel (DECISION 119).
    property url sceneUrl: ""
    // The key inside SceneProperties. The scene string the user chose IS the id:
    // "spectrum" for a built-in, the path for a file. Stable, and it survives a
    // scene being renamed on disk the same way the setting does.
    property string sceneId: ""
    // The raw SceneProperties config string: {"<sceneId>": {"speed": 1.0}}
    property string savedJson: "{}"

    readonly property var knownTypes: ["slider", "color", "dropdown", "textbox",
                                       "checkbox", "file", "button", "label"]

    // ---- outputs --------------------------------------------------------
    property var schema: ({})          // validated, unknown types removed
    property bool loaded: false
    // Empty when all is well. Set ONLY when the schema could not be read — an
    // empty schema and an unreadable one must never look the same again.
    property string problem: ""

    readonly property var props: store.merge(store.schema, store.savedFor(store.sceneId))

    // ---- merge rules, mirrored from luminos-wallpaper-pkg ----------------
    function validate(raw) {
        var ok = {};
        if (!raw || typeof raw !== "object")
            return ok;
        for (var key in raw) {
            var v = raw[key];
            if (v && typeof v === "object" && store.knownTypes.indexOf(v.type) !== -1)
                ok[key] = v;
        }
        return ok;
    }

    function merge(schema, saved) {
        var result = {};
        if (!schema || typeof schema !== "object")
            return result;
        var safe = (saved && typeof saved === "object") ? saved : {};
        for (var key in schema) {
            if (safe[key] !== undefined) {
                result[key] = safe[key];
            } else {
                var entry = schema[key];
                result[key] = (entry && entry.value !== undefined) ? entry.value : null;
            }
        }
        return result;
    }

    // Never throws. A hand-edited config file is a thing that happens, and a
    // wallpaper that will not start because of one is worse than one that
    // starts on defaults and says so.
    function parseSaved() {
        try {
            var o = JSON.parse(store.savedJson || "{}");
            return (o && typeof o === "object") ? o : {};
        } catch (e) {
            console.warn("[LUMINOS-WP] SceneProperties is not valid JSON, using defaults:", e);
            return {};
        }
    }

    function savedFor(id) {
        var all = store.parseSaved();
        var mine = all[id];
        return (mine && typeof mine === "object") ? mine : {};
    }

    // Returns the NEW SceneProperties string. Does not write it — the settings
    // panel owns the config key, and a wallpaper that writes its own settings
    // behind the panel's back is how the two disagree.
    function withValue(id, key, value) {
        var all = store.parseSaved();
        if (!all[id] || typeof all[id] !== "object")
            all[id] = {};
        all[id][key] = value;
        return JSON.stringify(all);
    }

    function clear(id) {
        var all = store.parseSaved();
        delete all[id];
        return JSON.stringify(all);
    }

    // ---- schema loading, via PropsReader ---------------------------------
    function accept(schemaJson) {
        store.problem = "";
        if (("" + schemaJson).length === 0) {
            store.schema = ({});          // genuinely no properties.json: normal
            store.loaded = true;
            return;
        }
        try {
            store.schema = store.validate(JSON.parse(schemaJson));
        } catch (e) {
            store.reject("the properties reader returned something unparseable");
            return;
        }
        store.loaded = true;
    }

    function reject(why) {
        store.schema = ({});
        store.problem = "" + why;
        store.loaded = true;
        console.warn("[LUMINOS-WP] scene settings unavailable:", store.problem);
    }

    Loader {
        id: readerLoader
        source: "PropsReader.qml"
        onStatusChanged: {
            if (status === Loader.Error)
                store.reject("the properties reader could not be loaded here");
        }
        onLoaded: item.base = Qt.binding(() => "" + store.sceneUrl)
    }

    Connections {
        target: readerLoader.item
        ignoreUnknownSignals: true
        function onDone(schemaJson) { store.accept(schemaJson); }
        function onFailed(why) { store.reject(why); }
    }
}
