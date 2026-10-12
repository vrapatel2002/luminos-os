// [CHANGE: claude-code | 2026-10-12] Offscreen Kirigami.FormLayout probe (Phase 4). Prints fl=<JSON>: cards = visible
// rounded rects outside the controls (ShadowedRectangle corners / Rectangle radii, >= 90 % wide) [y,h,TL,TR,BL,BR]; ctl = each
// control's centre y; sliderBelow; secLine (section Separator drawn as a line); pointer (a visible "Pointer" text).
import QtQuick; import QtQuick.Controls; import QtQuick.Layouts
import org.kde.kirigami as Kirigami
Item { width: 600; height: 700
    Kirigami.FormLayout { id: fl; width: 600
        Kirigami.Separator { id: sec; Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Pointer" }
        ComboBox { id: combo; Kirigami.FormData.label: "Speed"; model: ["a", "b"] }
        SpinBox { id: spin; Kirigami.FormData.label: "Delay" }
        CheckBox { id: check; text: "Enable" }
        Switch { id: sw; Kirigami.FormData.label: "Tap" }
        Slider { id: sl; Kirigami.FormData.label: "Volume"; Layout.fillWidth: true }
        Kirigami.Separator { }
        TextField { id: tf; Kirigami.FormData.label: "Name" } }
    function walk(it, f) { f(it); if ([combo, spin, check, sw, sl, tf].indexOf(it) >= 0) return; for (var i = 0; i < it.children.length; i++) walk(it.children[i], f) }
    Timer { interval: 1200; running: true; onTriggered: {
        var cards = [], lab = null, pointer = false
        walk(fl, function (it) {
            if (it.visible && it.text === "Volume" && it !== sl) lab = it
            if (it.visible && it.opacity > 0 && it.text === "Pointer") pointer = true
            var k = it.corners || (it.topLeftRadius !== undefined && it.color !== undefined && it.color.a > 0 ? it : null)
            if (!k || !it.visible || it.width < fl.width * 0.9 || it.height < 2) return
            var y = it.mapToItem(fl, 0, 0).y
            cards.push([y, it.height, k.topLeftRadius, k.topRightRadius, k.bottomLeftRadius, k.bottomRightRadius].map(function (v) { return Math.round(v * 10) / 10 })) })
        var ctl = {}; [["combo", combo], ["spin", spin], ["check", check], ["sw", sw], ["sl", sl], ["tf", tf]].forEach(function (p) {
            ctl[p[0]] = Math.round(p[1].mapToItem(fl, 0, p[1].height / 2).y) })
        var sy = sl.mapToItem(fl, 0, 0).y, ly = lab ? lab.mapToItem(fl, 0, 0).y + lab.height : 1e9
        console.log("fl=" + JSON.stringify({ cards: cards, ctl: ctl, sliderBelow: sy > ly, labFound: !!lab, pointer: pointer,
            secLine: sec.visible && sec.opacity > 0 && sec.height >= 1 && sec.width > 0 })); Qt.quit() } }
}
