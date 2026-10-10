// [CHANGE: claude-code | 2026-10-10] Prints Kirigami.Units.cornerRadius for luminos-windowstyle-check (offscreen).
import QtQuick
import org.kde.kirigami as Kirigami
Item { Component.onCompleted: { console.log("cornerRadius=" + Kirigami.Units.cornerRadius); Qt.quit() } }
