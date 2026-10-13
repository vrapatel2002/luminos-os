// [CHANGE: claude-code | 2026-10-12] Phase 6 offscreen probe: p6=<JSON> radii/heights of Menu, ToolTip, InlineMessage and the
// round discs in a PlaceholderMessage, sem=<JSON> View Positive/Neutral/Negative bg+text as apps get them (KColorScheme); saves tooltip.png, sep.png (MenuSeparator), sb.png (idle ScrollBar), msg.png (info bar).
import QtQuick; import QtQuick.Controls
import org.kde.kirigami as Kirigami
ApplicationWindow { id: win; width: 700; height: 700; visible: true
    Menu { id: menu; MenuItem { text: "Open" } MenuSeparator { } MenuItem { text: "Quit" } }
    ToolTip { id: tt; text: "Hello tooltip"; x: 300; y: 600; visible: true; delay: 0; timeout: -1 }
    ScrollBar { id: sb; x: 650; y: 300; height: 200; orientation: Qt.Vertical; size: 0.3; position: 0.2; policy: ScrollBar.AlwaysOn }
    Kirigami.InlineMessage { id: msg; x: 300; y: 20; width: 340; type: Kirigami.MessageType.Information; text: "Info"; visible: true }
    Kirigami.PlaceholderMessage { id: ph; x: 300; y: 200; width: 300; icon.name: "input-keyboard"; text: "Nothing here" }
    Item { id: viewSet; Kirigami.Theme.colorSet: Kirigami.Theme.View; Kirigami.Theme.inherit: false }
    function walk(it, f) { f(it); for (var i = 0; i < it.children.length; i++) walk(it.children[i], f) }
    function rad(bg) { var best = null   // radius of the largest rounded rect (Rectangle radii or ShadowedRectangle corners)
        if (bg) walk(bg, function (it) { if ((it.radius !== undefined || it.corners) && it.visible && (!best || it.width * it.height > best.width * best.height)) best = it })
        if (!best) return -1; var k = best.corners, r = k ? Math.max(k.topLeftRadius, k.bottomRightRadius) : Math.max(best.radius, best.topLeftRadius || 0)
        return Math.min(r < 0 ? best.radius : r, best.height / 2) }
    function save(item, f) { if (item) item.grabToImage(function (r) { r.saveToFile(f) }) }
    Component.onCompleted: menu.popup(0, 0)
    Timer { interval: 1200; running: true; onTriggered: {
        var discs = []; walk(ph, function (it) { if (it.radius !== undefined && it.visible && Math.abs(it.width - it.height) <= 1 && it.radius >= it.width / 2 - 1 && it.color.a > 0) discs.push(Math.round(it.width)) })
        var T = viewSet.Kirigami.Theme, hex = function (c) { return [c.r, c.g, c.b].map(function (v) { return Math.round(v * 255) }) }
        console.log("sem=" + JSON.stringify({ pos: [hex(T.positiveBackgroundColor), hex(T.positiveTextColor)], neu: [hex(T.neutralBackgroundColor),
            hex(T.neutralTextColor)], neg: [hex(T.negativeBackgroundColor), hex(T.negativeTextColor)] }))
        console.log("p6=" + JSON.stringify({ menuR: rad(menu.background), items: [menu.itemAt(0).height, menu.itemAt(2).height], ttR: rad(tt.background),
            msgR: rad(msg.background), discs: discs, sbW: sb.width }))
        save(tt.background, "tooltip.png"); save(menu.itemAt(1), "sep.png"); save(sb, "sb.png"); save(msg.background, "msg.png") } }
    Timer { interval: 1800; running: true; onTriggered: Qt.quit() }
}
