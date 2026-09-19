/*
    CONTRACTS §4 conformance test for the per-scene property layer.
    [CHANGE: claude-code | 2026-09-19]  DECISION 118.
    SPDX-License-Identifier: GPL-3.0-or-later

    Run ON THE BOX — it needs a real QML engine:

        qml6 ~/luminos-os/tests/wallpaper/props_contract.qml ; echo $?

    Exit 0 = the contract holds. Every failing check prints what it actually got.

    The merge rules here are the QML copy of `merge_props()` / `validate_properties()`
    in scripts/luminos-wallpaper-pkg, which has its own 20-test Python suite. These
    cases are deliberately the SAME cases, so the pair cannot drift apart silently:
    a slider showing one number while the wallpaper renders another is exactly the
    bug two copies of a merge produce.
*/
import QtQuick
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/props"

Item {
    id: harness

    property int failures: 0

    function check(name, cond, got) {
        if (cond)
            console.log("  ok    " + name);
        else {
            console.log("  FAIL  " + name + "   got: " + JSON.stringify(got));
            harness.failures++;
        }
    }

    PropertyStore { id: store }

    Component.onCompleted: {
        console.log("CONTRACTS §4 — per-scene properties");

        // ---- 1. validate: unknown control types are SKIPPED, not fatal -----
        var v = store.validate({
            speed: { type: "slider", value: 1 },
            tint:  { type: "color",  value: "#fff" },
            weird: { type: "hologram", value: 3 },
            junk:  "not an object",
            empty: null
        });
        harness.check("known types kept", v.schema.speed !== undefined && v.schema.tint !== undefined,
                      Object.keys(v.schema));
        harness.check("unknown type dropped", v.schema.weird === undefined, v.schema.weird);
        harness.check("non-object dropped", v.schema.junk === undefined, v.schema.junk);
        harness.check("null entry dropped", v.schema.empty === undefined, v.schema.empty);
        harness.check("skipped names reported", v.skipped.length === 3, v.skipped);
        harness.check("all eight Lively types known", store.knownTypes.length === 8, store.knownTypes);

        // ---- 2. merge: saved wins, else default, else null ----------------
        var schema = {
            speed: { type: "slider", value: 1.0 },
            tint:  { type: "color",  value: "#d959a6" },
            noval: { type: "textbox" }
        };
        var merged = store.merge(schema, { speed: 2.5 });
        harness.check("saved value wins", merged.speed === 2.5, merged.speed);
        harness.check("default when nothing saved", merged.tint === "#d959a6", merged.tint);
        harness.check("null when the entry has no value", merged.noval === null, merged.noval);
        harness.check("merge returns exactly the schema's keys",
                      Object.keys(merged).length === 3, Object.keys(merged));
        harness.check("a saved key the schema does not declare is ignored",
                      store.merge(schema, { ghost: 9 }).ghost === undefined, "ghost leaked");

        // ---- 3. merge never throws on garbage -----------------------------
        harness.check("merge(null, null) is {}", Object.keys(store.merge(null, null)).length === 0, "threw");
        harness.check("merge(schema, 'string') falls back to defaults",
                      store.merge(schema, "nonsense").speed === 1.0, "threw");

        // ---- 4. the config string ------------------------------------------
        store.savedJson = '{"spectrum":{"bars":2},"shader":{"speed":3}}';
        harness.check("savedFor picks one scene", store.savedFor("spectrum").bars === 2,
                      store.savedFor("spectrum"));
        harness.check("savedFor of an unknown scene is {}",
                      Object.keys(store.savedFor("nope")).length === 0, store.savedFor("nope"));

        var next = JSON.parse(store.withValue("spectrum", "sensitivity", 1.4));
        harness.check("withValue adds the key", next.spectrum.sensitivity === 1.4, next);
        harness.check("withValue keeps the scene's other keys", next.spectrum.bars === 2, next);
        harness.check("withValue does not touch other scenes", next.shader.speed === 3, next);

        var cleared = JSON.parse(store.clear("spectrum"));
        harness.check("clear removes one scene only",
                      cleared.spectrum === undefined && cleared.shader.speed === 3, cleared);

        // ---- 5. a hand-mangled config must not stop the wallpaper ----------
        store.savedJson = "{this is not json";
        harness.check("malformed JSON degrades to defaults, no throw",
                      Object.keys(store.savedFor("spectrum")).length === 0, "threw");
        store.savedJson = '"a bare string"';
        harness.check("non-object JSON degrades to defaults",
                      Object.keys(store.savedFor("spectrum")).length === 0, "threw");

        console.log(harness.failures === 0
                    ? "PASS — property contract holds"
                    : "FAIL — " + harness.failures + " check(s) broken");
        Qt.exit(harness.failures === 0 ? 0 : 1);
    }
}
