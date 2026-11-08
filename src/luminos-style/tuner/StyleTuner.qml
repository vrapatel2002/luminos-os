// [CHANGE: claude-code | 2026-11-08] Luminos Style Tuner (DECISION 176).
// Horizontal bars that write ~/.config/luminos/style.json. The forked KDE libraries watch
// that file (org.luminos.style), so open apps change while a bar moves. Text size and
// button corners are pushed to kdeglobals / darklyrc by luminos-style-apply (user path unit).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtCore
import org.kde.kirigami as Kirigami
import org.luminos.style

QQC2.ApplicationWindow {
    id: win
    title: "Style Tuner"
    width: 420; height: 860
    minimumWidth: 340; minimumHeight: 420
    visible: true

    readonly property var knobs: [
        { g: "Text",   id: "textSizePt",     lbl: "Text size",      unit: "pt", min: 8,   max: 14,   step: 0.5, def: 10 },
        { g: "Text",   id: "pageTitlePx",    lbl: "Page title",     unit: "px", min: 18,  max: 44,   step: 1,   def: 30 },
        { g: "Text",   id: "groupLabelPx",   lbl: "Group labels",   unit: "px", min: 9,   max: 18,   step: 0.5, def: 12 },
        { g: "Shape",  id: "cornerOuterPx",  lbl: "Outer corners",  unit: "px", min: 0,   max: 40,   step: 1,   def: 28 },
        { g: "Shape",  id: "cornerInnerPx",  lbl: "Inner corners",  unit: "px", min: 0,   max: 16,   step: 1,   def: 4 },
        { g: "Shape",  id: "cornerButtonPx", lbl: "Button corners", unit: "px", min: 0,   max: 24,   step: 1,   def: 16 },
        { g: "Space",  id: "rowHeightPx",    lbl: "Row height",     unit: "px", min: 44,  max: 90,   step: 1,   def: 60 },
        { g: "Space",  id: "rowGapPx",       lbl: "Row gap",        unit: "px", min: 0,   max: 12,   step: 1,   def: 4 },
        { g: "Space",  id: "cardPaddingPx",  lbl: "Card padding",   unit: "px", min: 8,   max: 40,   step: 1,   def: 20 },
        { g: "Space",  id: "sidebarWidthPx", lbl: "Sidebar width",  unit: "px", min: 240, max: 480,  step: 5,   def: 330 },
        { g: "Space",  id: "pageWidthPx",    lbl: "Page width",     unit: "px", min: 560, max: 1400, step: 10,  def: 756 },
        { g: "Space",  id: "iconCirclePx",   lbl: "Icon circles",   unit: "px", min: 24,  max: 56,   step: 1,   def: 40 },
        { g: "Motion", id: "animationMs",    lbl: "Animation",      unit: "ms", min: 0,   max: 500,  step: 10,  def: 180 }
    ]
    readonly property var presets: ({
        "Compact": { textSizePt: 9, pageTitlePx: 24, groupLabelPx: 11, cornerOuterPx: 16, cornerInnerPx: 3, cornerButtonPx: 10,
                     rowHeightPx: 48, rowGapPx: 2, cardPaddingPx: 14, sidebarWidthPx: 280, pageWidthPx: 700, iconCirclePx: 32, animationMs: 120 },
        "Current look": {},
        "Roomy":   { textSizePt: 11, pageTitlePx: 36, groupLabelPx: 13, cornerOuterPx: 32, cornerInnerPx: 6, cornerButtonPx: 20,
                     rowHeightPx: 72, rowGapPx: 6, cardPaddingPx: 26, sidebarWidthPx: 380, pageWidthPx: 900, iconCirclePx: 46, animationMs: 220 }
    })

    // current values; seeded from what the libraries are using right now (= the file, or defaults)
    property var values: ({})
    property var undoStack: []
    property int revision: 0   // bumps on every change so bindings refresh
    readonly property url filePath: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/luminos/style.json"

    function snapshot() { return JSON.parse(JSON.stringify(values)) }
    function setValue(id, v, pushUndo) {
        if (values[id] === v) return
        if (pushUndo) undoStack.push(snapshot())
        values[id] = v
        revision++
        saveTimer.restart()
    }
    function setAll(map) {
        undoStack.push(snapshot())
        for (const k of knobs) values[k.id] = (map[k.id] !== undefined ? map[k.id] : k.def)
        revision++
        saveTimer.restart()
    }
    function undo() {
        if (undoStack.length === 0) return
        values = undoStack.pop()
        revision++
        saveTimer.restart()
    }
    function save() {
        const out = {}
        for (const k of knobs) out[k.id] = values[k.id]
        const xhr = new XMLHttpRequest()
        xhr.open("PUT", filePath)
        xhr.send(JSON.stringify(out, null, 2) + "\n")
    }
    function presetMatches(name) {
        const p = presets[name]
        for (const k of knobs) if (values[k.id] !== (p[k.id] !== undefined ? p[k.id] : k.def)) return false
        return true
    }

    Timer { id: saveTimer; interval: 60; onTriggered: win.save() }

    Component.onCompleted: {
        const v = {}
        for (const k of knobs) v[k.id] = Style[k.id]
        values = v
        revision++
    }

    header: QQC2.ToolBar {
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            RowLayout {
                Kirigami.Heading { text: "Style Tuner"; level: 3; Layout.fillWidth: true }
                QQC2.Button { text: "Undo"; enabled: win.revision >= 0 && win.undoStack.length > 0; onClicked: win.undo() }
            }
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: ["Compact", "Current look", "Roomy"]
                    QQC2.Button {
                        required property string modelData
                        text: modelData
                        checkable: true
                        checked: win.revision >= 0 && win.presetMatches(modelData)
                        onClicked: win.setAll(win.presets[modelData])
                    }
                }
            }
        }
    }

    QQC2.ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 0
            Repeater {
                model: win.knobs
                ColumnLayout {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property var k: modelData
                    readonly property bool groupStart: index === 0 || win.knobs[index - 1].g !== k.g
                    readonly property real val: win.revision >= 0 && win.values[k.id] !== undefined ? win.values[k.id] : k.def
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing * 2
                    Layout.rightMargin: Kirigami.Units.largeSpacing * 2
                    spacing: 2
                    QQC2.Label {
                        visible: row.groupStart
                        text: row.k.g.toUpperCase()
                        font.letterSpacing: 1
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        opacity: 0.6
                        Layout.topMargin: Kirigami.Units.largeSpacing * 2
                        Layout.bottomMargin: Kirigami.Units.smallSpacing
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        QQC2.Label { text: row.k.lbl; Layout.fillWidth: true }
                        QQC2.Label {
                            text: (row.k.step < 1 ? row.val.toFixed(1) : row.val) + " " + row.k.unit
                            font.family: "monospace"
                            color: row.val !== row.k.def ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
                        }
                        QQC2.ToolButton {
                            icon.name: "edit-undo"
                            display: QQC2.AbstractButton.IconOnly
                            text: "Reset " + row.k.lbl
                            opacity: row.val !== row.k.def ? 1 : 0
                            enabled: opacity > 0
                            onClicked: win.setValue(row.k.id, row.k.def, true)
                            QQC2.ToolTip.text: "Back to " + row.k.def + " " + row.k.unit
                            QQC2.ToolTip.visible: hovered
                        }
                    }
                    QQC2.Slider {
                        Layout.fillWidth: true
                        from: row.k.min; to: row.k.max; stepSize: row.k.step
                        snapMode: QQC2.Slider.SnapAlways
                        value: row.val
                        onPressedChanged: if (pressed) win.undoStack.push(win.snapshot())
                        onMoved: win.setValue(row.k.id, Math.round(value / row.k.step) * row.k.step, false)
                        Accessible.name: row.k.lbl
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing * 2
                QQC2.Button { text: "Reset all"; icon.name: "edit-reset"; onClicked: win.setAll({}) }
                Item { Layout.fillWidth: true }
                QQC2.Label {
                    text: "Saved to ~/.config/luminos/style.json"
                    opacity: 0.6
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    elide: Text.ElideLeft
                    Layout.maximumWidth: scroll.availableWidth * 0.6
                }
            }
        }
    }
}
