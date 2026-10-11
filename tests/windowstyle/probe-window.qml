// [CHANGE: claude-code | 2026-10-10] Plain server-side-decorated test window for luminos-windowstyle-check.
// Body is exactly the palette Window colour, so the header (also palette Window per CONTRACTS) must vanish into it.
import QtQuick
import QtQuick.Controls
ApplicationWindow {
    title: "luminos-windowstyle-probe"; width: 800; height: 500; visible: true; color: palette.window
    Component.onCompleted: { raise(); requestActivate() } }
