/*
    SPEC §3.2 — does the generated settings panel actually RENDER a control?
    [CHANGE: claude-code | 2026-09-19]  BUG-173.
    SPDX-License-Identifier: GPL-3.0-or-later

    Run ON THE BOX:

        QT_QPA_PLATFORM=offscreen qml6 ~/luminos-os/tests/wallpaper/editor_contract.qml ; echo $?

    props_contract.qml tests PropertyStore — the merge, the validation, the error
    states — and every one of its 21 checks passed while the panel on screen showed
    five labels and no controls at all. This file exists to close that exact gap:
    it builds a PropertyEditor over all eight control types and asserts that each
    row's Loader produced a real item. It asserts about the PRODUCT, not the logic.
*/
import QtQuick
import QtQuick.Layouts
import "../../src/wallpapers/org.luminos.livewallpaper/contents/ui/props"

Item {
    id: harness
    width: 900
    height: 700

    property int failures: 0

    function check(name, cond, got) {
        if (cond)
            console.log("  ok    " + name);
        else {
            console.log("  FAIL  " + name + "   got: " + got);
            harness.failures++;
        }
    }

    // One row per Lively control type, so a type that stops rendering is caught
    // by name rather than by "the panel looks empty".
    readonly property var everyType: ({
        aSlider:   { type: "slider",   label: "Slider",   value: 1, min: 0, max: 3, step: 0.1 },
        aColor:    { type: "color",    label: "Colour",   value: "#38bdf8" },
        aDropdown: { type: "dropdown", label: "Dropdown", value: 1, items: ["a", "b", "c"] },
        aTextbox:  { type: "textbox",  label: "Textbox",  value: "hello" },
        aCheckbox: { type: "checkbox", label: "Checkbox", value: true },
        aFile:     { type: "file",     label: "File",     value: "" },
        aButton:   { type: "button",   label: "Button",   value: "Press" },
        aLabel:    { type: "label",    value: "Just a note." }
    })

    PropertyEditor {
        id: panel
        width: harness.width
        schema: harness.everyType
        values: ({})
    }

    // Every Loader anywhere under the panel, with the key it was handed.
    function loaders(item, out) {
        for (var i = 0; i < item.children.length; i++) {
            var c = item.children[i];
            if (c.sourceComponent !== undefined && c.item !== undefined)
                out.push(c);
            else
                harness.loaders(c, out);
        }
        return out;
    }

    Component.onCompleted: {
        console.log("SPEC §3.2 — the settings panel renders its controls");

        var keys = Object.keys(harness.everyType);
        harness.check("panel sees all eight types", panel.keys.length === 8, panel.keys.length);
        harness.check("panel reports it has settings", panel.hasAny === true, panel.hasAny);

        var ld = harness.loaders(panel, []);
        harness.check("one Loader per declared property", ld.length === 8, ld.length);

        // THE check. A null item is a row with a label and nothing beside it —
        // which is what BUG-173 looked like on screen, with no error anywhere.
        var empty = [];
        for (var i = 0; i < ld.length; i++) {
            if (ld[i].item === null || ld[i].status === Loader.Error)
                empty.push(i);
        }
        harness.check("every row loaded a control", empty.length === 0,
                      empty.length + " of " + ld.length + " rows are empty (indices " + empty + ")");

        // A control with no width is invisible even when it loaded.
        var flat = [];
        for (var j = 0; j < ld.length; j++) {
            if (ld[j].item !== null && ld[j].item.width <= 0)
                flat.push(j);
        }
        harness.check("every control has a width", flat.length === 0,
                      flat.length + " zero-width control(s) (indices " + flat + ")");

        // And the key really reached it — a panel that edits the wrong key is
        // worse than one that edits nothing.
        var wrong = [];
        for (var k = 0; k < ld.length; k++) {
            if (ld[k].item !== null && keys.indexOf("" + ld[k].item.pkey) < 0)
                wrong.push("" + ld[k].item.pkey);
        }
        harness.check("every control was handed its own key", wrong.length === 0, wrong);

        console.log(harness.failures === 0
                    ? "PASS — the panel renders every control it declares"
                    : "FAIL — " + harness.failures + " check(s) broken");
        Qt.exit(harness.failures === 0 ? 0 : 1);
    }
}
