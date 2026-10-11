// [CHANGE: claude-code | 2026-10-10] Prints a checked QQC2 Switch's indicator size for luminos-windowstyle-check (offscreen).
// Stock qqc2-desktop-style 6.30.0-1 printed "switch-indicator=36x18" (gridUnit*2 x gridUnit) -> FAILs the 52x32 M3 check.
import QtQuick
import QtQuick.Controls
Item { Switch { id: s; checked: true; text: "x"; Component.onCompleted: { console.log("switch-indicator=" + s.indicator.implicitWidth + "x" + s.indicator.implicitHeight); Qt.quit() } } }
