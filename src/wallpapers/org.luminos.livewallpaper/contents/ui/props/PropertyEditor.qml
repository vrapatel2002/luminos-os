/*
    Luminos Live Wallpaper — the settings panel a scene declares for itself.
    SPEC §3.2, CONTRACTS §4.  [CHANGE: claude-code | 2026-09-19] DECISION 118.
    SPDX-License-Identifier: GPL-3.0-or-later

    Eight control types, matching Lively's one for one, so a LivelyProperties.json
    maps on with no type left over. The panel is GENERATED from the scene's
    properties.json — nothing here knows what any scene's settings are, which is
    the point: ship a properties.json, get a panel, no glue code.

    Rows are Label + control, not a Kirigami.FormLayout: a Repeater inside a
    FormLayout has to hand FormData up through a delegate, and a panel that
    sometimes loses its labels is worse than one a few pixels off the KDE grid.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import org.kde.kquickcontrols as KQuickControls
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: editor

    // PropertyStore.schema (validated) and the merged current values.
    property var schema: ({})
    property var values: ({})

    signal changed(string key, var value)

    readonly property var keys: {
        var out = [];
        if (editor.schema && typeof editor.schema === "object")
            for (var k in editor.schema)
                out.push(k);
        return out;
    }
    readonly property bool hasAny: editor.keys.length > 0

    function val(key) {
        if (editor.values && editor.values[key] !== undefined)
            return editor.values[key];
        var d = editor.schema[key];
        return (d && d.value !== undefined) ? d.value : null;
    }
    function num(v, fallback) {
        var n = Number(v);
        return isNaN(n) ? fallback : n;
    }

    spacing: Kirigami.Units.smallSpacing

    Repeater {
        model: editor.keys

        RowLayout {
            id: row
            required property string modelData

            readonly property var def: editor.schema[row.modelData] || ({})
            readonly property string ctl: "" + (row.def.type || "")

            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            QQC2.Label {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 8
                Layout.alignment: Qt.AlignVCenter
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                visible: row.ctl !== "label"
                text: ("" + (row.def.label || row.modelData)) + ":"
            }

            Loader {
                id: ld
                Layout.fillWidth: true
                // An unknown control type falls through to the read-only label
                // rather than vanishing — CONTRACTS §4: "unknown control type ->
                // skipped, rest still rendered". PropertyStore has already dropped
                // types it does not know, so this is belt and braces.
                sourceComponent: ctl[row.ctl] !== undefined ? ctl[row.ctl] : ctl.label
                // Handed over EXPLICITLY, not through the Loader's context: whether
                // a Component declared outside the Loader resolves the Loader's own
                // properties is a scoping rule I cannot test from here, and a panel
                // that silently edits the wrong key is not a bug you notice fast.
                onLoaded: {
                    ld.item.pdef = row.def;
                    ld.item.pkey = row.modelData;   // last: the bindings key off it
                }
            }
        }
    }

    QQC2.Label {
        visible: !editor.hasAny
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font: Kirigami.Theme.smallFont
        text: i18n("This scene declares no settings. A scene gets a panel here by shipping a properties.json beside it.")
    }
    PropertyControls {
        id: ctl
        editor: editor
    }
}
