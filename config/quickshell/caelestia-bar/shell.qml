//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1
//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded

// [CHANGE: claude-code | 2026-08-13]
//
// Caelestia's REAL bar and REAL launcher, each in its OWN window, instead of
// both being painted onto one surface that covers the whole screen.
//
// Nothing here re-creates either of them - it loads upstream's
// `modules/bar/BarWrapper.qml` and `modules/launcher/Wrapper.qml` unmodified,
// so the pixels are Caelestia's own.
//
// Why: the upstream shell paints everything onto `Drawers` -> `ContentWindow`,
// which anchors top+bottom+left+right (the entire screen) and relies on
// `hyprland_focus_grab_v1` to decide when to let clicks through.  KWin has no
// such protocol, so the Luminos patch made that surface swallow the whole
// screen whenever a panel opened - the "cursor moves but clicks do nothing"
// bug.  Windows this size cannot do that: outside them there is no surface.
//
// Still NOT here (deliberately - one step at a time, per Shawn 2026-08-13):
//   - dashboard / sidebar / session menu / osd / notifications / utilities
//   - the rounded screen border and 10px gap (painted by the sheet's blob)
//   - bar popouts.  A popouts Wrapper is instantiated because BarWrapper
//     requires one, but it is never shown and `checkPopout()` is never called
//     (that call lives in Interactions.qml, which belongs to the sheet).
//
// Run it by hand with:  qs -c caelestia-bar

pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Caelestia.Config
import qs.components
import qs.services
import qs.modules
import qs.modules.bar
import qs.modules.bar.popouts as BarPopouts
import qs.modules.launcher as Launcher

ShellRoot {
    id: root

    settings.watchFiles: false

    Binding {
        target: ShellState
        property: "shellRoot"
        value: root
    }

    // GoogleSansFlex - without this everything falls back to a system font and
    // stops looking like Caelestia.
    GSFLoader {}

    // Gives us the `drawers` IPC target, which is what the Meta+P .desktop
    // shortcut calls (`qs -p <config> ipc call drawers toggle launcher`).
    // Its CustomShortcuts are Hyprland-only and will log "unsupported" on KWin;
    // that is expected noise, already documented, not a new fault.
    Shortcuts {}

    Variants {
        model: Screens.screens

        Scope {
            id: scope

            required property ShellScreen modelData

            readonly property ScreenState screenState: ShellState.forScreen(modelData)

            // The launcher wants a `panels` object. In the upstream shell that is
            // the whole Panels item. It only ever reads four things off it:
            // `bar.implicitWidth` and `popouts.*` (WallpaperList.qml:26-31) and
            // `utilities.implicitWidth` / `dashboard.nonAnimHeight`, both behind
            // `if (screenState.…)` guards for panels we do not have. So a shim is
            // enough - and it keeps the launcher file itself unmodified.
            readonly property QtObject panelsShim: QtObject {
                readonly property var bar: barWindow.bar
                readonly property var popouts: barWindow.popouts
                readonly property var utilities: absent
                readonly property var dashboard: absent
            }

            // Zero-sized stand-in for the panels that do not exist here. Never
            // parented to a window, so it never renders.
            Item {
                id: absent
            }

            // ── the bar ──────────────────────────────────────────────────────
            PanelWindow {
                id: barWindow

                readonly property alias bar: bar
                readonly property alias popouts: popouts

                screen: scope.modelData
                color: "transparent"

                WlrLayershell.namespace: "caelestia-bar"
                WlrLayershell.layer: WlrLayer.Top

                anchors.top: true
                anchors.bottom: true
                anchors.left: true

                // The window is exactly as wide as the bar wants to be, and
                // reserves exactly that much - BarWrapper computes both already.
                implicitWidth: bar.implicitWidth
                exclusiveZone: bar.exclusiveZone

                // Upstream draws the strip's background with the sheet's blob
                // rect, which we no longer have, so draw it here.
                StyledRect {
                    anchors.fill: parent
                    color: Colours.tPalette.m3surface
                }

                BarPopouts.Wrapper {
                    id: popouts

                    screen: scope.modelData
                    offsetScale: 0
                    visible: false
                }

                BarWrapper {
                    id: bar

                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left

                    screen: scope.modelData
                    screenState: scope.screenState
                    popouts: popouts
                    fullscreen: false
                }
            }

            // ── the launcher ─────────────────────────────────────────────────
            // Bottom-centred, sized to its own content. Anchoring only `bottom`
            // makes layer-shell centre it horizontally, which is where Caelestia
            // puts it. exclusiveZone 0: it floats, it does not shove windows.
            PanelWindow {
                id: launcherWindow

                screen: scope.modelData
                color: "transparent"

                // Do NOT write `visible: launcher.visible`. Wrapper.qml:34 is
                // `visible: offsetScale < 1`, and offsetScale is driven by a
                // Behavior animation. With QSG_RENDER_LOOP=threaded a hidden window
                // gets no frames, so that animation never advances, so `visible`
                // never leaves false - the launcher opens exactly once and then the
                // key does nothing forever (`ipc call drawers isOpen launcher`
                // answers 1 the whole time, so it looks fine from outside).
                // screenState.launcher is a plain bool that flips instantly; OR-ing
                // the animated one keeps the window up for the closing animation.
                visible: scope.screenState.launcher || launcher.visible

                WlrLayershell.namespace: "caelestia-launcher"
                WlrLayershell.layer: WlrLayer.Overlay
                // KWin has no focus-grab protocol, so without Exclusive the
                // search field never gets the keyboard and the launcher is a
                // picture you cannot type into. Escape (launcher/Content.qml:86)
                // and Meta+P both still close it, and closing it hides this
                // window, which hands the keyboard straight back.
                WlrLayershell.keyboardFocus: scope.screenState.launcher ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

                exclusiveZone: 0

                anchors.bottom: true
                margins.bottom: Config.border.thickness

                implicitWidth: launcher.implicitWidth
                implicitHeight: launcher.implicitHeight

                // Upstream's rounded backdrop is a blob in the sheet. A rounded
                // rect is the honest equivalent - it does not do the blob's
                // stretch-towards-the-bar goo, and it will not pretend to.
                StyledRect {
                    anchors.fill: launcher
                    radius: Tokens.rounding.extraLarge
                    color: Colours.tPalette.m3surface
                    opacity: launcher.opacity
                }

                Launcher.Wrapper {
                    id: launcher

                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter

                    screen: scope.modelData
                    screenState: scope.screenState
                    panels: scope.panelsShim
                }
            }
        }
    }
}
