// [CHANGE: claude-code | 2026-11-08] smoke test: prints the values, then again after style.json changes.
import QtQuick
import org.luminos.style
QtObject {
    property real outer: Style.cornerOuterPx
    onOuterChanged: console.warn("LIVE cornerOuterPx=" + outer)
    Component.onCompleted: console.warn("START cornerOuterPx=" + Style.cornerOuterPx + " anim=" + Style.animationMs + " page=" + Style.pageWidthPx)
}
