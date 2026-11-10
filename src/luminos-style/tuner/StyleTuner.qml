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
        { g: "Space",  id: "sidebarBottomPx",lbl: "Sidebar bottom gap", unit: "px", min: 0, max: 80, step: 1,   def: 16 },
        // [CHANGE: claude-code | 2026-11-08] R6: search bar, icons, bottom buttons
        { g: "Search bar", id: "searchHeightPx", lbl: "Height",          unit: "px", min: 28, max: 72, step: 1, def: 48 },
        { g: "Search bar", id: "searchLeftPx",   lbl: "Left edge",       unit: "px", min: 0,  max: 48, step: 1, def: 16 },
        { g: "Search bar", id: "searchRightPx",  lbl: "Right edge",      unit: "px", min: 0,  max: 48, step: 1, def: 16 },
        { g: "Search bar", id: "searchTopPx",    lbl: "Space above",     unit: "px", min: 0,  max: 48, step: 1, def: 16 },
        { g: "Search bar", id: "searchBottomPx", lbl: "Space below",     unit: "px", min: 0,  max: 40, step: 1, def: 8 },
        { g: "Search bar", id: "showMenuButton", lbl: "Menu button (☰) next to search", kind: "toggle", def: 1 },
        { g: "Icons", id: "iconDiscColor",  lbl: "Circle colour", kind: "color", def: "" },
        { g: "Icons", id: "iconGlyphColor", lbl: "Icon colour",   kind: "color", def: "" },
        { g: "Icons", id: "iconGlyphPx",    lbl: "Icon size",       unit: "px", min: 12, max: 36, step: 1, def: 22 },
        { g: "Icons", id: "iconOffsetXPx",  lbl: "Move left / right", unit: "px", min: -16, max: 16, step: 1, def: 0 },
        { g: "Icons", id: "iconOffsetYPx",  lbl: "Move up / down",  unit: "px", min: -12, max: 12, step: 1, def: 0 },
        { g: "Bottom buttons", id: "buttonsLeftPx",   lbl: "Left edge",   unit: "px", min: 0, max: 64, step: 1, def: 6 },
        { g: "Bottom buttons", id: "buttonsRightPx",  lbl: "Right edge",  unit: "px", min: 0, max: 64, step: 1, def: 6 },
        { g: "Bottom buttons", id: "buttonsTopPx",    lbl: "Space above", unit: "px", min: 0, max: 48, step: 1, def: 6 },
        { g: "Bottom buttons", id: "buttonsBottomPx", lbl: "Space below (moves the bar up)", unit: "px", min: 0, max: 64, step: 1, def: 6 },
        { g: "Motion", id: "animationMs",    lbl: "Animation",      unit: "ms", min: 0,   max: 500,  step: 10,  def: 180 },
        // [CHANGE: claude-code | 2026-11-09] DECISION 182: Files (Dolphin) page. a: "files" = shown on the Files tab.
        { a: "files", g: "Sidebar", id: "filesPlaceRowPx",      lbl: "Row height",            unit: "px", min: 28, max: 80, step: 1, def: 44 },
        { a: "files", g: "Sidebar", id: "filesPlaceGapPx",      lbl: "Gap between rows",      unit: "px", min: 0,  max: 12, step: 1, def: 2 },
        { a: "files", g: "Sidebar", id: "filesPlaceDiscPx",     lbl: "Circle size (0 = no circle)", unit: "px", min: 0, max: 56, step: 1, def: 30 },
        { a: "files", g: "Sidebar", id: "filesPlaceGlyphPx",    lbl: "Icon size",             unit: "px", min: 10, max: 36, step: 1, def: 18 },
        { a: "files", g: "Sidebar", id: "filesPlacePadPx",      lbl: "Left edge",             unit: "px", min: 0,  max: 30, step: 1, def: 9 },
        { a: "files", g: "Sidebar", id: "filesPlaceTextGapPx",  lbl: "Gap after the circle",  unit: "px", min: 0,  max: 30, step: 1, def: 12 },
        { a: "files", g: "Sidebar", id: "filesPlaceTextScale",  lbl: "Name size",             unit: "×",  min: 0.7, max: 1.4, step: 0.05, def: 1 },
        { a: "files", g: "Sidebar", id: "filesPlaceRadiusPx",   lbl: "Highlight corners (−1 = pill)", unit: "px", min: -1, max: 30, step: 1, def: -1 },
        { a: "files", g: "Sidebar", id: "filesPlaceSelMix",     lbl: "Selected strength",     unit: "%",  min: 0,  max: 100, step: 1, def: 100 },
        { a: "files", g: "Sidebar", id: "filesPlaceHoverMix",   lbl: "Hover strength",        unit: "%",  min: 0,  max: 40, step: 1, def: 8 },
        { a: "files", g: "Sidebar", id: "filesPlaceDiscDim",    lbl: "Circle fade",           unit: "%",  min: 0,  max: 80, step: 1, def: 0 },
        { a: "files", g: "Sidebar", id: "filesPlaceGlyphInk",   lbl: "Icon brightness",       unit: "%",  min: 0,  max: 60, step: 1, def: 12 },
        { a: "files", g: "Sidebar", id: "filesPlaceBarPx",      lbl: "Drive bar thickness",   unit: "px", min: 1,  max: 10, step: 1, def: 4 },
        { a: "files", g: "Sidebar", id: "filesPlaceSmallScale", lbl: "\"Free of\" text size", unit: "×", min: 0.6, max: 1.1, step: 0.02, def: 0.82 },
        { a: "files", g: "Sidebar", id: "filesPlaceDriveRowPx", lbl: "Drive row height (min)", unit: "px", min: 24, max: 100, step: 1, def: 44 },
        { a: "files", g: "Sidebar", id: "filesPlaceDrivePadPx", lbl: "Drive row padding",     unit: "px", min: 0,  max: 24,  step: 1, def: 7 },
        { a: "files", g: "Sidebar", id: "filesPlaceDriveGapPx", lbl: "Name to bar gap",       unit: "px", min: 0,  max: 16,  step: 1, def: 4 },
        { a: "files", g: "Sidebar labels", id: "filesPlaceHeaderScale", lbl: "Label size",       unit: "×",  min: 0.6, max: 1.2, step: 0.02, def: 0.8 },
        { a: "files", g: "Sidebar labels", id: "filesPlaceHeaderTopPx", lbl: "Space above labels", unit: "px", min: 0, max: 40, step: 1, def: 14 },
        { a: "files", g: "Sidebar labels", id: "filesPlaceHeaderMix",   lbl: "Label brightness",   unit: "%",  min: 20, max: 100, step: 1, def: 50 },
        { a: "files", g: "Sidebar labels", id: "filesPlaceHeaderCaps",  lbl: "Capital letters", kind: "toggle", def: 1 },
        { a: "files", g: "Files area", id: "filesRoundSelection",  lbl: "Rounded highlight", kind: "toggle", def: 1 },
        { a: "files", g: "Files area", id: "filesItemRadiusPx",    lbl: "Highlight corners",  unit: "px", min: 0, max: 30, step: 1, def: 14 },
        { a: "files", g: "Files area", id: "filesItemSelMix",      lbl: "Selected strength",  unit: "%",  min: 20, max: 100, step: 1, def: 100 },
        { a: "files", g: "Files area", id: "filesItemHoverMix",    lbl: "Hover strength",     unit: "%",  min: 0, max: 30, step: 1, def: 7 },
        { a: "files", g: "Files area", id: "filesFolderFileGroups", lbl: "\"Folders\" / \"Files\" groups", kind: "toggle", def: 1 },
        { a: "files", g: "Size steps — Icons (zoom level)",   id: "filesZoomIcons0",   lbl: "S",  unit: "", min: 0, max: 10, step: 1, def: 3 },
        { a: "files", g: "Size steps — Icons (zoom level)",   id: "filesZoomIcons1",   lbl: "M",  unit: "", min: 0, max: 10, step: 1, def: 4 },
        { a: "files", g: "Size steps — Icons (zoom level)",   id: "filesZoomIcons2",   lbl: "L",  unit: "", min: 0, max: 10, step: 1, def: 5 },
        { a: "files", g: "Size steps — Icons (zoom level)",   id: "filesZoomIcons3",   lbl: "XL", unit: "", min: 0, max: 10, step: 1, def: 7 },
        { a: "files", g: "Size steps — Compact (zoom level)", id: "filesZoomCompact0", lbl: "S",  unit: "", min: 0, max: 10, step: 1, def: 1 },
        { a: "files", g: "Size steps — Compact (zoom level)", id: "filesZoomCompact1", lbl: "M",  unit: "", min: 0, max: 10, step: 1, def: 2 },
        { a: "files", g: "Size steps — Compact (zoom level)", id: "filesZoomCompact2", lbl: "L",  unit: "", min: 0, max: 10, step: 1, def: 3 },
        { a: "files", g: "Size steps — Compact (zoom level)", id: "filesZoomCompact3", lbl: "XL", unit: "", min: 0, max: 10, step: 1, def: 4 },
        { a: "files", g: "Size steps — List (zoom level)",    id: "filesZoomList0",    lbl: "S",  unit: "", min: 0, max: 10, step: 1, def: 0 },
        { a: "files", g: "Size steps — List (zoom level)",    id: "filesZoomList1",    lbl: "M",  unit: "", min: 0, max: 10, step: 1, def: 1 },
        { a: "files", g: "Size steps — List (zoom level)",    id: "filesZoomList2",    lbl: "L",  unit: "", min: 0, max: 10, step: 1, def: 2 },
        { a: "files", g: "Size steps — List (zoom level)",    id: "filesZoomList3",    lbl: "XL", unit: "", min: 0, max: 10, step: 1, def: 3 },
        { a: "files", g: "Menus and bars", id: "filesViewPanel",       lbl: "View button opens the Luminos panel", kind: "toggle", def: 1 },
        { a: "files", g: "Menus and bars", id: "filesViewPanelWidth",  lbl: "View panel width",  unit: "px", min: 260, max: 520, step: 5, def: 330 },
        { a: "files", g: "Menus and bars", id: "filesHamburgerLayout", lbl: "New ☰ menu layout", kind: "toggle", def: 1 },
        { a: "files", g: "Menus and bars", id: "filesSelectionBar",    lbl: "Action bar when files are selected", kind: "toggle", def: 1 },
        { a: "files", g: "Menus and bars", id: "filesNeutralBars",     lbl: "Grey bar (off = KDE's tinted bar)", kind: "toggle", def: 1 },
        { a: "files", g: "Menus and bars", id: "filesBarMix",          lbl: "Bar brightness",    unit: "%", min: 0, max: 30, step: 1, def: 7 },
        { a: "files", g: "Menus and bars", id: "filesUndoMessage",     lbl: "\"Moved to Trash · Undo\" message", kind: "toggle", def: 1 },
        { a: "files", g: "Menus and bars", id: "filesUndoMessageMs",   lbl: "Message stays for", unit: "ms", min: 1500, max: 20000, step: 500, def: 6000 }
    ]
    readonly property var swatches: ["", "#c4c0ff", "#a8c7fa", "#80d4c8", "#a6d49c", "#f2c46d", "#f4a7b9", "#3b3a45", "#e6e1e8", "#1b1a1f"]
    readonly property var presets: ({
        "Compact": { textSizePt: 9, pageTitlePx: 24, groupLabelPx: 11, cornerOuterPx: 16, cornerInnerPx: 3, cornerButtonPx: 10,
                     rowHeightPx: 48, rowGapPx: 2, cardPaddingPx: 14, sidebarWidthPx: 280, pageWidthPx: 700, iconCirclePx: 32, animationMs: 120 },
        "Current look": {},
        "Roomy":   { textSizePt: 11, pageTitlePx: 36, groupLabelPx: 13, cornerOuterPx: 32, cornerInnerPx: 6, cornerButtonPx: 20,
                     rowHeightPx: 72, rowGapPx: 6, cardPaddingPx: 26, sidebarWidthPx: 380, pageWidthPx: 900, iconCirclePx: 46, animationMs: 220 }
    })

    // [CHANGE: claude-code | 2026-11-09] DECISION 182: which tab is showing ("settings" or "files")
    property string page: Qt.application.arguments.indexOf("--files") >= 0 ? "files" : "settings" // luminos-style-tuner --files opens the Files tab
    readonly property var shown: win.knobs.filter(k => (k.a || "settings") === win.page)

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
        for (const k of knobs) if ((k.a || "settings") === page) values[k.id] = (map[k.id] !== undefined ? map[k.id] : k.def)
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
        for (const k of knobs) out[k.id] = (k.kind === "toggle") ? (values[k.id] ? 1 : 0) : values[k.id]
        const xhr = new XMLHttpRequest()
        xhr.open("PUT", filePath)
        xhr.send(JSON.stringify(out, null, 2) + "\n")
    }
    function presetMatches(name) {
        const p = presets[name]
        for (const k of knobs) if (!k.a && values[k.id] !== (p[k.id] !== undefined ? p[k.id] : k.def)) return false
        return true
    }

    Timer { id: saveTimer; interval: 60; onTriggered: win.save() }

    property bool dragging: false
    function reseed() {
        // bottom-button keys live only in System Settings' C++, so they come from the file itself
        let file = {}
        const xhr = new XMLHttpRequest()
        xhr.open("GET", filePath, false)
        try { xhr.send(); file = JSON.parse(xhr.responseText || "{}") } catch (e) { file = {} }
        const v = {}
        for (const k of knobs) {
            const fromStyle = Style[k.id]
            v[k.id] = fromStyle !== undefined ? fromStyle : (file[k.id] !== undefined ? file[k.id] : k.def)
            if (k.kind === "toggle") v[k.id] = v[k.id] ? 1 : 0
        }
        values = v
        revision++
    }
    Component.onCompleted: reseed()
    // follow edits made to the file by anything else (not while we are writing it ourselves)
    Connections {
        target: Style
        function onChanged() { if (!saveTimer.running && !win.dragging) win.reseed() }
    }

    header: QQC2.ToolBar {
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            RowLayout {
                Kirigami.Heading { text: "Style Tuner"; level: 3; Layout.fillWidth: true }
                QQC2.Button { text: "Undo"; enabled: win.revision >= 0 && win.undoStack.length > 0; onClicked: win.undo() }
            }
            QQC2.TabBar { // [CHANGE: claude-code | 2026-11-09] DECISION 182
                Layout.fillWidth: true
                currentIndex: win.page === "files" ? 1 : 0
                QQC2.TabButton { text: "System Settings"; onClicked: win.page = "settings" }
                QQC2.TabButton { text: "Files"; onClicked: win.page = "files" }
            }
            QQC2.Label {
                visible: win.page === "files"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.7
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                text: "Sidebar and highlight changes show at once in an open Files window. Size steps are used the next time you move the size slider; menu switches the next time you open that menu."
            }
            Flow {
                visible: win.page === "settings"
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
                model: win.shown
                ColumnLayout {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property var k: modelData
                    readonly property bool groupStart: index === 0 || win.shown[index - 1].g !== k.g
                    readonly property var val: win.revision >= 0 && win.values[k.id] !== undefined ? win.values[k.id] : k.def
                    readonly property bool isColor: k.kind === "color"
                    readonly property bool isToggle: k.kind === "toggle"
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
                        QQC2.Switch { // R7: on/off settings
                            visible: row.isToggle
                            checked: row.val ? true : false
                            onToggled: win.setValue(row.k.id, checked ? 1 : 0, true)
                            Accessible.name: row.k.lbl
                        }
                        QQC2.Label {
                            visible: !row.isColor && !row.isToggle
                            text: (row.isColor || row.isToggle) ? "" : (row.k.step < 1 ? Number(row.val).toFixed(row.k.step < 0.1 ? 2 : 1) : row.val) + " " + row.k.unit
                            font.family: "monospace"
                            color: row.val !== row.k.def ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
                        }
                        QQC2.ToolButton {
                            icon.name: "edit-undo"
                            display: QQC2.AbstractButton.IconOnly
                            text: "Reset " + row.k.lbl
                            opacity: !row.isToggle && row.val !== row.k.def ? 1 : 0
                            enabled: opacity > 0
                            onClicked: win.setValue(row.k.id, row.k.def, true)
                            QQC2.ToolTip.text: row.isColor ? "Back to the theme colour" : "Back to " + row.k.def + " " + row.k.unit
                            QQC2.ToolTip.visible: hovered
                        }
                    }
                    Flow { // colour choices; the first one is "use the theme colour"
                        visible: row.isColor
                        Layout.fillWidth: true
                        spacing: 8
                        Repeater {
                            model: row.isColor ? win.swatches : []
                            QQC2.AbstractButton {
                                required property string modelData
                                width: 32; height: 32
                                checkable: true
                                checked: row.val === modelData
                                onClicked: win.setValue(row.k.id, modelData, true)
                                QQC2.ToolTip.text: modelData === "" ? "Theme colour" : modelData
                                QQC2.ToolTip.visible: hovered
                                background: Rectangle {
                                    radius: width / 2
                                    color: parent.modelData === "" ? "transparent" : parent.modelData
                                    border.width: parent.checked ? 3 : 1
                                    border.color: parent.checked ? Kirigami.Theme.focusColor : Qt.alpha(Kirigami.Theme.textColor, 0.35)
                                    QQC2.Label { anchors.centerIn: parent; visible: parent.parent.modelData === ""; text: "A"; opacity: 0.7 }
                                }
                            }
                        }
                    }
                    QQC2.Slider {
                        visible: !row.isColor && !row.isToggle
                        Layout.fillWidth: true
                        from: (row.isColor || row.isToggle) ? 0 : row.k.min; to: (row.isColor || row.isToggle) ? 1 : row.k.max; stepSize: (row.isColor || row.isToggle) ? 0 : row.k.step
                        snapMode: QQC2.Slider.SnapAlways
                        value: (row.isColor || row.isToggle) ? 0 : row.val
                        onPressedChanged: { win.dragging = pressed; if (pressed) win.undoStack.push(win.snapshot()) }
                        onMoved: win.setValue(row.k.id, Math.round(value / row.k.step) * row.k.step, false)
                        Accessible.name: row.k.lbl
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing * 2
                QQC2.Button { text: win.page === "files" ? "Reset Files" : "Reset all"; icon.name: "edit-reset"; onClicked: win.setAll({}) }
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
