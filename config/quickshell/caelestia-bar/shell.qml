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
//   - dashboard / sidebar / session menu / notifications / utilities
//   - the rounded screen border and 10px gap (painted by the sheet's blob)
//   - bar popouts.  A popouts Wrapper is instantiated because BarWrapper
//     requires one, but it is never shown and `checkPopout()` is never called
//     (that call lives in Interactions.qml, which belongs to the sheet).
//
// Run it by hand with:  qs -c caelestia-bar

pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Caelestia.Config
import qs.components
import qs.services
import qs.modules
import qs.modules.bar
import qs.modules.bar.popouts as BarPopouts
import qs.modules.launcher as Launcher
import qs.modules.osd as Osd

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

            // ── the OSD (volume / brightness) ────────────────────────────────
            // [CHANGE: claude-code | 2026-08-13] DECISION 68 follow-up.
            //
            // Nothing here drives the OSD. Osd/Wrapper.qml:51-73 is a
            // `Connections { target: Audio }` that calls show() whenever
            // PipeWire's volume changes - no matter WHO changed it. KDE's
            // kded `audioshortcutsservice` owns the volume keys and moves
            // PipeWire; Quickshell sees the same PipeWire node change and
            // pops this out. So there is deliberately no shortcut wiring
            // here, and none is needed.
            //
            // Brightness is NOT symmetrical - it needed the poller below.
            PanelWindow {
                id: osdWindow

                screen: scope.modelData
                color: "transparent"

                // Same threaded-render-loop trap as the launcher above:
                // Wrapper.qml:41 is `visible: offsetScale < 1`, and offsetScale
                // is driven by a Behavior animation. A hidden window gets no
                // frames to advance that animation with, so it would show once
                // and then never again. screenState.osd is a plain bool that
                // flips instantly; OR-ing the animated one keeps the window
                // alive long enough to play the slide back out.
                visible: scope.screenState.osd || osd.visible

                WlrLayershell.namespace: "caelestia-osd"
                // Overlay, not Top: an OSD that hides behind a fullscreen
                // video is not doing its job.
                WlrLayershell.layer: WlrLayer.Overlay

                // It floats on top of whatever is there. It must never shove
                // windows aside - a volume press should not reflow your screen.
                exclusiveZone: 0

                // Anchoring ONLY `right` makes layer-shell centre it vertically
                // against the right edge, which is where Caelestia puts it -
                // the same trick the launcher uses with bottom-only to get
                // horizontal centring. No margin: we do not paint upstream's
                // screen border, so there is no border to sit inside of.
                anchors.right: true

                implicitWidth: osd.implicitWidth
                implicitHeight: osd.implicitHeight

                // Upstream paints this backdrop with the sheet's blob, which we
                // do not have. A rounded rect is the honest equivalent, exactly
                // as for the launcher above.
                StyledRect {
                    anchors.fill: osd
                    radius: Tokens.rounding.extraLarge
                    color: Colours.tPalette.m3surface
                    opacity: osd.opacity
                }

                Osd.Wrapper {
                    id: osd

                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter

                    screen: scope.modelData
                    screenState: scope.screenState
                    // We have no sidebar and no session menu, so there is
                    // nothing here for the OSD to step aside for. Wrapper.qml:20
                    // only uses this to add a 12px nudge.
                    sidebarOrSessionVisible: false
                }
            }

            // ── brightness: let Caelestia see what powerdevil did ────────────
            // [CHANGE: claude-code | 2026-08-13]
            //
            // THIS IS BLUNT ON PURPOSE, and here is the honest reason.
            // services/Brightness.qml reads the backlight exactly once
            // (Component.onCompleted -> initBrightness) and afterwards only
            // updates when Caelestia itself calls setBrightness(). Nothing
            // watches the hardware. So KDE's powerdevil - which owns the
            // brightness keys, and should KEEP owning them, because it also
            // does the battery, lid and idle logic - moves the backlight and
            // Caelestia never finds out. The slider was correct at login and
            // stale forever after.
            //
            // This copies the value in; it never writes hardware. Assigning
            // `monitor.brightness` is precisely what makes the OSD appear,
            // because Osd/Wrapper.qml:75-82 shows on `onBrightnessChanged`.
            // It deliberately does NOT call setBrightness(), so it cannot
            // fight powerdevil for control of the panel.
            //
            // Why a poll and not an event: sysfs attributes do not raise
            // inotify events, so FileView.watchChanges genuinely cannot see
            // this file change - it is not a shortcut, it is the only option
            // short of a D-Bus subscription to powerdevil. A sysfs read costs
            // microseconds and forks nothing, which is far cheaper than the
            // `brightnessctl` subprocess the service already spawns on every
            // single set. FileView+Timer is the same pattern SysInfo.qml and
            // NetworkUsage.qml already use for /proc and /sys.
            //
            // The device is NOT hardcoded. `brightnessctl -m` here is the
            // Luminos shim in /usr/local/bin (PATH puts it ahead of /usr/bin),
            // which picks the backlight hanging off the DRM eDP connector -
            // the panel's own - rather than the phantom `nvidia_0` that reads
            // a permanent fake 100%. Asking the shim instead of re-walking
            // sysfs here keeps ONE place that knows which device is real, and
            // that place is already tested (BUG-098). Anything spelled cardN
            // or blN is PCIe enumeration order and breaks on a reboot.
            readonly property var blMonitor: Brightness.getMonitorForScreen(modelData)

            property string blPath
            property int blMax
            property bool blPrimed

            Process {
                running: true
                command: ["brightnessctl", "-m"]
                stdout: StdioCollector {
                    // device,class,current,percent,max
                    onStreamFinished: {
                        const f = text.trim().split(",");
                        if (f.length < 5)
                            return;
                        const max = parseInt(f[4]);
                        if (!f[0] || !(max > 0))
                            return;
                        scope.blMax = max;
                        scope.blPath = `/sys/class/backlight/${f[0]}/brightness`;
                    }
                }
            }

            FileView {
                id: blFile

                // Empty until the shim answers; printErrors would otherwise
                // spam the log once for the empty path.
                path: scope.blPath
                printErrors: false

                onLoaded: {
                    const raw = parseInt(text().trim());
                    if (!(scope.blMax > 0) || isNaN(raw))
                        return;

                    const v = Math.max(0, Math.min(1, raw / scope.blMax));

                    // The first read only records where we already are. Without
                    // this the OSD flies out once at login, for a change the
                    // user did not make.
                    if (!scope.blPrimed) {
                        scope.blPrimed = true;
                        return;
                    }

                    // Compare at the same 1% granularity the service itself
                    // uses (Brightness.qml:203-205), so our own writes - from
                    // dragging the slider, which does go through the hardware -
                    // do not come back around as a fresh "change" and bounce.
                    const m = scope.blMonitor;
                    if (m && Math.round(m.brightness * 100) !== Math.round(v * 100))
                        m.brightness = v;
                }
            }

            Timer {
                running: scope.blPath !== ""
                repeat: true
                interval: 250
                onTriggered: blFile.reload()
            }
        }
    }
}
