// [CHANGE: claude-code | 2026-10-11] Offscreen Kirigami probe: cornerRadius=, icondisc=<round opaque items around the icon>,
// seps=<visible separators>, fcrects=y:h:TL/TR/BL/BR;.. (ShadowedRectangles in the card). Stock: icondisc=0, seps=2, none.
import QtQuick; import QtQuick.Controls
import org.kde.kirigami as Kirigami; import org.kde.kirigami.delegates as KD
import org.kde.kirigamiaddons.formcard as FormCard
Item {
    width: 500; height: 500
    ItemDelegate { id: d; width: 400; highlighted: true
        contentItem: KD.IconTitleSubtitle { title: "Bluetooth"; subtitle: "x"; icon.name: "preferences-system-bluetooth" } }
    FormCard.FormCard { id: card; y: 100; width: 480
        FormCard.FormTextDelegate { id: a; text: "First" }
        FormCard.FormDelegateSeparator { id: s1 }
        FormCard.FormTextDelegate { id: b; text: "Middle" }
        FormCard.FormDelegateSeparator { id: s2 }
        FormCard.FormTextDelegate { id: c; text: "Last" } }
    function walk(it, f) { f(it); for (var i = 0; i < it.children.length; i++) walk(it.children[i], f) }
    Timer { interval: 1200; running: true; onTriggered: {   // corners animate <= 500 ms
        console.log("cornerRadius=" + Kirigami.Units.cornerRadius)
        var icons = [], discs = []
        walk(d, function (it) { if (/^Icon[_(]/.test(String(it)) && it.width > 0) icons.push(it) })
        var ic = icons[0], c0 = ic ? ic.mapToItem(d, ic.width / 2, ic.height / 2) : null
        if (ic) walk(d, function (it) {
            if (typeof it.radius !== "number" || !it.visible || it.width < ic.width || Math.abs(it.width - it.height) > 1) return
            if (it.radius < it.width / 2 - 1 || (it.color !== undefined && it.color.a === 0)) return
            var p = it.mapToItem(d, 0, 0)
            if (c0.x > p.x && c0.x < p.x + it.width && c0.y > p.y && c0.y < p.y + it.height) discs.push(String(it)) })
        console.log("icondisc=" + (ic ? discs.length : -1) + " (icon " + (ic ? ic.width + "px" : "not found") + ") " + discs.join(","))
        console.log("seps=" + [s1, s2].filter(function (s) { return s.visible && s.opacity > 0 && s.height > 0 }).length);
        var rs = []; walk(card, function (it) { if (it.corners && it.visible && it.height >= 2) { var k = it.corners
            rs.push(Math.round(it.mapToItem(card, 0, 0).y) + ":" + it.height + ":" + [k.topLeftRadius, k.topRightRadius, k.bottomLeftRadius, k.bottomRightRadius].join("/")) } })
        console.log("fcrects=" + rs.sort(function (p, q) { return parseInt(p) - parseInt(q) }).join(";")); Qt.quit() } }
}
