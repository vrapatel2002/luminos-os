// [CHANGE: claude-code | 2026-06-14]
// GENERATED FROM design/luminos-tokens.json — DO NOT EDIT BY HAND.
// Regenerate with: scripts/luminos-theme-gen
//
// Canonical Luminos design-token component. Instantiable (NOT a pragma Singleton)
// so it can be copied verbatim into each self-contained Plasma package's
// contents/ui/Theme.qml and the HIVE app dir — avoids cross-module QML import-path
// runtime breakage. Usage:
//     Theme { id: theme }
//     color: theme.accent
//
// Easing arrays are ready for: easing.type: Easing.BezierSpline;
//                              easing.bezierCurve: theme.easeStandard
import QtQuick

QtObject {
    id: theme

    // ── Base surfaces ───────────────────────────────────────────────
    readonly property color bgBase:          "#0A0A0F"
    readonly property color surface:         "#13131A"
    readonly property color surfaceElevated: "#1C1C26"
    readonly property color surfaceOverlay:  Qt.rgba(1, 1, 1, 0.06)

    // ── Accent (electric blue — system default) ─────────────────────
    readonly property color accent:        "#0080FF"
    readonly property color accentHover:    "#0066CC"
    readonly property color accentPressed:  "#0052A3"
    readonly property color accentSubtle:   Qt.rgba(0, 0.502, 1, 0.12)
    readonly property color accentGlow:     Qt.rgba(0, 0.502, 1, 0.40)

    // ── Text ────────────────────────────────────────────────────────
    readonly property color textPrimary:    "#FFFFFF"
    readonly property color textSecondary:  "#8888AA"
    readonly property color textDisabled:   "#444466"

    // ── Borders / tracks ────────────────────────────────────────────
    readonly property color borderDefault:  Qt.rgba(1, 1, 1, 0.08)
    readonly property color borderFocus:     Qt.rgba(0, 0.502, 1, 0.60)
    readonly property color borderSubtle:    Qt.rgba(1, 1, 1, 0.04)
    readonly property color trackColor:      Qt.rgba(1, 1, 1, 0.12)

    // ── Status ──────────────────────────────────────────────────────
    readonly property color success:  "#00C896"
    readonly property color warning:  "#FFB020"
    readonly property color error:    "#FF4455"
    readonly property color info:     "#0080FF"

    // ── Radius (px) ─────────────────────────────────────────────────
    readonly property int radiusSharp:   0
    readonly property int radiusSm:       4
    readonly property int radiusMd:       8
    readonly property int radiusDefault: 12
    readonly property int radiusLg:      16
    readonly property int radiusFull:   999

    // ── Spacing (px) ────────────────────────────────────────────────
    readonly property int spaceMicro:  4
    readonly property int spaceSm:      8
    readonly property int spaceBase:   12
    readonly property int spaceMd:     16
    readonly property int spaceLg:     24
    readonly property int spaceXl:     32
    readonly property int spaceXxl:    48

    // ── Motion (ms) ─────────────────────────────────────────────────
    readonly property int durInstant:   0
    readonly property int durFast:     100
    readonly property int durDefault:  200
    readonly property int durSlow:     350

    // ── Easing (cubic-bezier → BezierSpline form, ends at 1,1) ──────
    readonly property var easeStandard: [0.4, 0.0, 0.2, 1.0, 1.0, 1.0]
    readonly property var easeEnter:    [0.0, 0.0, 0.2, 1.0, 1.0, 1.0]
    readonly property var easeExit:     [0.4, 0.0, 1.0, 1.0, 1.0, 1.0]
    readonly property var easeSpring:   [0.34, 1.56, 0.64, 1.0, 1.0, 1.0]

    // ── Misc ────────────────────────────────────────────────────────
    readonly property int blurStrength:    20
    readonly property string fontPrimary:  "Inter"
    readonly property string fontMono:     "JetBrains Mono"

    // ── HIVE sub-brand (warm — OPEN DECISION: keep warm vs unify blue) ─
    readonly property color hiveAccent:  "#D4784A"
    readonly property color hiveDanger:  "#E05555"

    readonly property color hiveDarkBg:          "#1E1E1E"
    readonly property color hiveDarkSurface:     "#2A2A2A"
    readonly property color hiveDarkBorder:      "#444444"
    readonly property color hiveDarkText:        "#E8E6E3"
    readonly property color hiveDarkSubtle:      "#888580"
    readonly property color hiveDarkLabel:       "#9A9590"
    readonly property color hiveDarkUserBubble:  "#333028"
    readonly property color hiveDarkAiBubble:    "#1E1E1E"
    readonly property color hiveDarkSeparator:   "#333333"
    readonly property color hiveDarkScrollbar:   "#555555"
    readonly property color hiveDarkHover:       "#3A3A3A"
    readonly property color hiveDarkBorderHover: "#555555"

    readonly property color hiveLightBg:          "#FAF9F6"
    readonly property color hiveLightSurface:     "#FFFFFF"
    readonly property color hiveLightBorder:      "#E5E2DC"
    readonly property color hiveLightText:        "#2D2B28"
    readonly property color hiveLightSubtle:      "#A39E96"
    readonly property color hiveLightLabel:       "#5A5650"
    readonly property color hiveLightUserBubble:  "#F0EDE8"
    readonly property color hiveLightAiBubble:    "#FAF9F6"
    readonly property color hiveLightSeparator:   "#E8E5E0"
    readonly property color hiveLightScrollbar:   "#CCCCCC"
    readonly property color hiveLightHover:       "#F5F3EF"
    readonly property color hiveLightBorderHover: "#D1CEC8"
}
