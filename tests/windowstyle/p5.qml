// [CHANGE: claude-code | 2026-10-12] Phase 5 offscreen probe. motion=<JSON>: [h,TL,TR,BL,BR] of the largest Rectangle in rows
// 0..2 (no sections) 100 ms after the current row moved 0 -> 1, and settled; saves frame/framedsv/plainsv.png (backgrounds),
// disabled.png (disabled CheckBox on palette Window), header.png (InlineViewHeader on palette Window).
import QtQuick; import QtQuick.Controls
import org.kde.kirigami as Kirigami
Item { width: 420; height: 640
    ListView { id: lv; width: 400; height: 180; currentIndex: 0; model: 3
        delegate: ItemDelegate { width: ListView.view.width; height: 56; text: "Row " + index; highlighted: ListView.isCurrentItem } }
    Frame { id: fr; y: 190; width: 300; height: 100 }
    ScrollView { id: fsv; y: 300; width: 300; height: 100; Kirigami.StyleHints.showFramedBackground: true; ListView { model: 3; delegate: Label { text: "x" } } }
    ScrollView { id: psv; y: 410; width: 300; height: 100; ListView { model: 3; delegate: Label { text: "x" } } }
    Rectangle { id: hdr; x: 100; y: 520; width: 300; height: 50; color: Kirigami.Theme.backgroundColor
        Kirigami.InlineViewHeader { width: parent.width; text: "Devices" } }
    Rectangle { id: dis; y: 520; width: 60; height: 40; color: Kirigami.Theme.backgroundColor; CheckBox { anchors.centerIn: parent; enabled: false } }
    function radii(d) { var best = null
        function walk(it) { if (it.topLeftRadius !== undefined && it.visible && (!best || it.width * it.height > best.width * best.height)) best = it
                            for (var i = 0; i < it.children.length; i++) walk(it.children[i]) }
        if (d && d.background) walk(d.background)
        return best ? [best.height, best.topLeftRadius, best.topRightRadius, best.bottomLeftRadius, best.bottomRightRadius].map(function (v) { return Math.round(v * 10) / 10 }) : null }
    property var early: []; property real t0: 0; property real dt: 0
    Timer { interval: 1200; running: true; onTriggered: { lv.currentIndex = 1; t0 = Date.now(); t2.start(); t3.start();
        [[fr, "frame"], [fsv, "framedsv"], [psv, "plainsv"], [dis, "disabled"], [hdr, "header"]].forEach(function (p) {
            var b = p[0] === dis || p[0] === hdr ? p[0] : p[0].background
            if (b && b.visible) b.grabToImage(function (r) { r.saveToFile(p[1] + ".png") }) }) } }
    Timer { id: t2; interval: 100; onTriggered: { dt = Date.now() - t0; early = [0, 1, 2].map(function (i) { return radii(lv.itemAtIndex(i)) }) }}
    Timer { id: t3; interval: 1500; onTriggered: { console.log("motion=" + JSON.stringify({ ms: dt, early: early,
        end: [0, 1, 2].map(function (i) { return radii(lv.itemAtIndex(i)) }) })); Qt.quit() } }
}
