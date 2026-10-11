// [CHANGE: claude-code | 2026-10-11] Offscreen QQC2 probe (cwd = temp dir, software backend so grabToImage works).
// Prints switch-indicator=WxH (stock 36x18) and handle=<Slider handle width>; saves row<i>.png (each 56 px ItemDelegate,
// sections A,A,A,B,B,B, current = 1), track.png (Slider background), radio.png (checked indicator).
import QtQuick
import QtQuick.Controls
Item {
    width: 420; height: 600
    ListView { id: lv; width: 400; height: 400; currentIndex: 1
        model: ListModel { ListElement { g: "A" } ListElement { g: "A" } ListElement { g: "A" }
                           ListElement { g: "B" } ListElement { g: "B" } ListElement { g: "B" } }
        section.property: "g"; section.delegate: Label { text: section; height: 20 }
        delegate: ItemDelegate { width: ListView.view.width; height: 56; text: "Row " + index + "\nSubtitle"; highlighted: ListView.isCurrentItem } }
    Slider { id: sl; y: 420; width: 300; value: 0.5 }
    RadioButton { id: rb; y: 470; checked: true; text: "x" }
    Switch { id: sw; y: 520; checked: true; text: "x" }
    property int pending: 8; function done() { if (--pending === 0) Qt.quit() }
    function save(item, f) { if (item) item.grabToImage(function (r) { r.saveToFile(f); done() }); else done() }
    Timer { interval: 1200; running: true; onTriggered: {   // corners animate <= 500 ms
        console.log("switch-indicator=" + sw.indicator.implicitWidth + "x" + sw.indicator.implicitHeight)
        console.log("handle=" + (sl.handle ? sl.handle.width : -1))
        for (var i = 0; i < 6; i++) save(lv.itemAtIndex(i), "row" + i + ".png")   // whole delegate: the row paints over its insets
        save(sl.background, "track.png"); save(rb.indicator, "radio.png") } }
}
