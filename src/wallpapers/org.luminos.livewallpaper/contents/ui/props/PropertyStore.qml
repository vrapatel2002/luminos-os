/*
    Luminos Live Wallpaper — per-scene properties.  SPEC §3.2, CONTRACTS §4.
    [CHANGE: claude-code | 2026-09-19]  DECISION 118.
    SPDX-License-Identifier: GPL-3.0-or-later

    One object, used by BOTH sides: the wallpaper reads `props`, the settings
    panel reads `schema` and calls `withValue()`. Two copies of merge logic that
    drift is how a slider ends up showing one number while the wallpaper renders
    another, so there is one copy and it lives here.

    The merge rules deliberately mirror `scripts/luminos-wallpaper-pkg`'s
    `validate_properties()` and `merge_props()` line for line — same known-type
    set, same "unknown type is skipped, not fatal", same "saved wins, default
    otherwise, null if the entry has no value". That Python is the tested copy
    (20 tests, property-based); this is the one that runs in plasmashell. If you
    change one, change both, and run tests/wallpaper/ for the pair.
*/
import QtQuick

QtObject {
    id: store

    // ---- inputs ---------------------------------------------------------
    // CONTRACTS §4 says properties.json lives "beside the scene". For a package
    // that is unambiguous — one scene per folder. The built-ins share
    // scenes/, so <Scene>.properties.json is tried first and plain
    // properties.json second. Packages are unaffected; built-ins stop colliding.
    // For a runtime shader this is the .frag, not ShaderToy.qml — otherwise every
    // shader on the machine would share one settings panel (DECISION 119).
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
    property var skipped: []           // names dropped, for the log
    property bool loaded: false

    readonly property var props: store.merge(store.schema, store.savedFor(store.sceneId))

    // ---- merge rules, mirrored from luminos-wallpaper-pkg ----------------
    function validate(raw) {
        var ok = {}, out = [];
        if (!raw || typeof raw !== "object")
            return { schema: ok, skipped: out };
        for (var key in raw) {
            var v = raw[key];
            if (v && typeof v === "object" && store.knownTypes.indexOf(v.type) !== -1)
                ok[key] = v;
            else
                out.push(key);
        }
        return { schema: ok, skipped: out };
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

    // ---- schema loading --------------------------------------------------
    function candidates() {
        var s = ("" + store.sceneUrl);
        var slash = s.lastIndexOf("/");
        if (slash < 0)
            return [];
        var dir = s.substring(0, slash + 1);
        var file = s.substring(slash + 1).replace(/\.[^./]+$/, "");
        return [dir + file + ".properties.json", dir + "properties.json"];
    }

    function load() {
        store.loaded = false;
        store.schema = ({});
        store.skipped = [];
        var list = store.candidates();
        if (list.length === 0) {
            store.loaded = true;
            return;
        }
        store.tryNext(list, 0);
    }

    // A missing properties.json is the normal case, not an error: most scenes
    // have no settings. Only a malformed one is worth a warning.
    function tryNext(list, i) {
        if (i >= list.length) {
            store.loaded = true;
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return;
            var body = xhr.responseText;
            if (!body || body.length === 0) {
                store.tryNext(list, i + 1);
                return;
            }
            try {
                var res = store.validate(JSON.parse(body));
                store.schema = res.schema;
                store.skipped = res.skipped;
                if (res.skipped.length > 0)
                    console.warn("[LUMINOS-WP] properties.json: skipped unknown control types:",
                                 res.skipped.join(", "));
            } catch (e) {
                console.warn("[LUMINOS-WP] properties.json is malformed, scene gets no settings:",
                             list[i], e);
            }
            store.loaded = true;
        };
        xhr.open("GET", list[i]);
        xhr.send();
    }

    onSceneUrlChanged: store.load()
    Component.onCompleted: store.load()
}
