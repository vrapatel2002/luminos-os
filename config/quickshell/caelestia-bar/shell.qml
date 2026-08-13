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
import qs.modules.dashboard as Dashboard
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

            // True while the pointer is on the edge tripwire OR on the OSD
            // itself. It has to be both, because they are two separate
            // surfaces: the strip loses the pointer the instant the OSD slides
            // out over the top of it.
            readonly property bool osdHovered: osdStripHover.containsMouse || osdSurfaceHover.hovered

            // show() is the only handle Wrapper.qml gives us on its hide Timer.
            // On ENTER it opens the OSD. On LEAVE it re-arms the same countdown,
            // which then reads hovered == false and closes - so hovering does
            // not need a second timer of its own. Guarded on screenState.osd so
            // that leaving cannot resurrect an OSD that already closed.
            onOsdHoveredChanged: if (osdHovered || screenState.osd)
                osd.show()

            // Same two-surface problem as the OSD: the top edge tripwire and
            // the dashboard itself are separate windows, and the pointer is
            // only ever on one of them.
            readonly property bool dashHovered: dashboardStripHover.containsMouse || dashboardSurfaceHover.hovered

            // The dashboard has no hide timer. Upstream drives it straight off
            // the pointer - Interactions.qml:211 is a bare
            // `screenState.dashboard = showDashboard` - so moving away closes
            // it immediately. But upstream also keeps a `dashboardShortcutActive`
            // flag (Interactions.qml:22, 213-219) so that a dashboard opened by
            // Meta+K, with the pointer somewhere else entirely, is not closed by
            // the next unrelated mouse move. This is that flag from the other
            // side: hover takes ownership the moment it opens or touches the
            // dashboard, and only an owner is allowed to close it.
            property bool dashOwnedByHover

            onDashHoveredChanged: {
                if (dashHovered) {
                    dashOwnedByHover = true;
                    screenState.dashboard = true;
                } else if (dashOwnedByHover) {
                    dashOwnedByHover = false;
                    screenState.dashboard = false;
                }
            }

            // [CHANGE: claude-code | 2026-08-13] The launcher gets the same
            // treatment as the dashboard above, because it had the same problem
            // and none of the cure. The bottom tripwire and the launcher are
            // two separate surfaces; the pointer is only ever on one. Without
            // the OR, walking off the strip and up into the launcher reads as a
            // leave and would slam it shut before you could type in it.
            readonly property bool launcherHovered: launcherStripHover.containsMouse || launcherSurfaceHover.hovered

            // Upstream never closes the launcher on unhover - Interactions.qml
            // :200-202 is a bare `if` with no `else`. It does not need one,
            // because it closes on click-outside instead, via
            // HyprlandFocusGrab (ContentWindow.qml:112-135). That is
            // hyprland_focus_grab_v1, which KWin does not implement - the KWin
            // binary has zero references to it - so on this machine that
            // handler is dead code and the launcher had no way out but Escape,
            // Meta+P, the logo button, or launching something.
            //
            // Closing on unhover is not the same signal, but it covers the
            // same ground: you cannot click on another window without moving
            // the pointer there, and moving there is the leave. The ownership
            // flag is why a launcher opened by Meta+P, with the pointer parked
            // over some other window, is not closed instantly by the next
            // stray mouse move - only hover may close what hover opened.
            //
            // ACCEPTED COST: hover-open it, then park the pointer off it while
            // typing, and it closes under you. Keyboard-opened ones are safe.
            property bool launcherOwnedByHover

            onLauncherHoveredChanged: {
                if (launcherHovered) {
                    launcherOwnedByHover = true;
                    screenState.launcher = true;
                } else if (launcherOwnedByHover) {
                    launcherOwnedByHover = false;
                    screenState.launcher = false;
                }
            }

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
                // [CHANGE: claude-code | 2026-08-13] Now a real panel. The
                // launcher reads `dashboard.nonAnimHeight` (launcher/Wrapper
                // .qml:20-24) to shrink itself when the dashboard is down, so
                // the two cannot overlap. While this was `absent` that read
                // would have produced undefined; it never fired, because it
                // sits behind `if (screenState.dashboard)` and the dashboard
                // could not be opened.
                readonly property var dashboard: dashboardPanel
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

                // [CHANGE: claude-code | 2026-08-13] Margin deleted. It used to
                // be Config.border.thickness, mirroring upstream, but upstream
                // earns that gap: it paints a 10px frame around the whole
                // screen and the panel's edge meets the frame's edge, so
                // nothing shows through. We do not paint that frame, so the
                // margin was just 10px of desktop showing under the launcher.
                // The OSD never had one, which is why it already looked right.
                anchors.bottom: true

                implicitWidth: launcher.implicitWidth
                implicitHeight: launcher.implicitHeight

                // Upstream's rounded backdrop is a blob in the sheet. A rounded
                // rect is the honest equivalent - it does not do the blob's
                // stretch-towards-the-bar goo, and it will not pretend to.
                StyledRect {
                    anchors.fill: launcher
                    radius: Tokens.rounding.extraLarge
                    // Now that it sits flat on the screen edge, rounding the
                    // two corners that touch it would show a sliver of desktop
                    // through each one. Square them off.
                    bottomLeftRadius: 0
                    bottomRightRadius: 0
                    color: Colours.tPalette.m3surface
                    opacity: launcher.opacity
                }

                // The other half of scope.launcherHovered. Without this the
                // pointer leaving the tripwire to enter the launcher reads as
                // a leave, and the launcher closes as you reach for it.
                HoverHandler {
                    id: launcherSurfaceHover
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

            // ── hover-to-open: nose the launcher up from the bottom edge ─────
            // [CHANGE: claude-code | 2026-08-13] The third way in, asked for by
            // Shawn. The other two already exist and are untouched here:
            // Meta+P (luminos-cael-launcher.desktop -> `ipc call drawers toggle
            // launcher`) and the distro logo at the top of the bar
            // (bar/components/OsIcon.qml:16-20, which flips the same bool).
            //
            // The numbers are upstream's, not invented. Interactions.qml:49-51
            // counts a point as "in the bottom panel" when
            //   y > height - max(Config.border.minThickness,
            //                    Config.border.thickness + <panel height>)
            // which with the launcher closed is a 10px band (thickness), and
            // withinPanelWidth (Interactions.qml:31-33) widens the launcher's
            // own width by Config.border.rounding (25) at each end.
            //
            // Upstream OPENS on hover and never closes on unhover -
            // Interactions.qml:200-202 is a bare `if (!launcher) launcher =
            // true`, with no matching else. That asymmetry was copied at
            // first and it was wrong here: upstream gets away with it because
            // click-outside closes the launcher for it, and that mechanism
            // does not exist on KWin. See scope.onLauncherHoveredChanged
            // above, which supplies the missing `else`. Escape, launching an
            // app, Meta+P and the logo button all still close it too.
            //
            // KNOWN COST, same shape as the OSD strip below: a layer-shell
            // surface eats pointer input over its whole area, and Wayland has
            // no way to say "send me motion but pass clicks through". So this
            // ~680 x 10 band at the bottom centre is dead to clicks. There is
            // no Plasma panel down there any more so it is empty desktop most
            // of the time, but a maximised window loses its bottom 10px in the
            // middle. Drop `implicitHeight` to Config.border.minThickness (2)
            // to shrink that 5x at the cost of a harder target.
            PanelWindow {
                id: launcherHoverStrip

                screen: scope.modelData
                color: "transparent"

                WlrLayershell.namespace: "caelestia-launcher-hover"
                // Top, not Overlay: the launcher is Overlay, so it comes out
                // ON TOP of this rather than fighting it for the pointer.
                WlrLayershell.layer: WlrLayer.Top
                // Never take the keyboard. A surface that steals focus at the
                // screen edge is a bug you cannot type your way out of.
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

                exclusiveZone: 0
                anchors.bottom: true

                implicitWidth: launcher.implicitWidth + Config.border.rounding * 2
                implicitHeight: Config.border.thickness

                // [CHANGE: claude-code | 2026-08-13] Now a bare hover source,
                // exactly like the dashboard strip. Opening AND closing both
                // moved up to scope.onLauncherHoveredChanged, which sees this
                // strip and the launcher surface as one zone. The old
                // edge-triggered open handler lived here to stop Escape being
                // undone by a pointer resting on the strip; that hazard is
                // gone, because with the margin deleted the launcher now
                // covers this strip whenever it is open.
                MouseArea {
                    id: launcherStripHover

                    anchors.fill: parent
                    hoverEnabled: true
                    // Do not pretend to handle clicks. It cannot pass them
                    // through either (see above), but at least nothing here
                    // silently swallows a press it might have acted on.
                    acceptedButtons: Qt.NoButton
                }
            }

            // ── the dashboard ────────────────────────────────────────────────
            // [CHANGE: claude-code | 2026-08-13] DECISION 68, STEP D part 1.
            // Upstream's own modules/dashboard/Wrapper.qml, unmodified, in a
            // window of its own - the same shape as the launcher and the OSD.
            // Tabs, media controls, system performance and weather all come
            // from Caelestia; nothing here re-creates any of them.
            PanelWindow {
                id: dashboardWindow

                screen: scope.modelData
                color: "transparent"

                // Same threaded-render-loop trap as the launcher and the OSD:
                // dashboard/Wrapper.qml:37 is `visible: offsetScale < 1` and
                // offsetScale is driven by a Behavior animation. A hidden
                // window gets no frames to advance that animation with, so
                // this would drop down once and then never again. The plain
                // bool flips instantly; OR-ing the animated one keeps the
                // window alive for the slide back up.
                visible: scope.screenState.dashboard || dashboardPanel.visible

                WlrLayershell.namespace: "caelestia-dashboard"
                WlrLayershell.layer: WlrLayer.Overlay
                // Never take the keyboard. Nothing in the dashboard accepts
                // typing - the tabs, media buttons, performance readouts and
                // weather are all pointer-driven, and the profile-picture
                // chooser opens a window of its own. Since this thing can open
                // on hover, taking focus would mean brushing the top of the
                // screen silently redirected your next keystroke.
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

                // It floats over whatever is there and must never reflow the
                // screen - the same rule as the launcher and the OSD.
                exclusiveZone: 0

                // The window covers the output, so the centring is done by
                // `dashboardPanel.anchors.horizontalCenter` below rather than
                // by layer-shell. That centres it on the WHOLE output, while
                // upstream centres it in the space to the RIGHT of the bar, so
                // it sits about half the bar width to the left of upstream's
                // position. The launcher has that same offset; the two agreeing
                // with each other matters more than either matching upstream.
                //
                // [CHANGE: claude-code | 2026-08-13] margins.top deleted, same
                // reason as the launcher: upstream's 10px gap is filled by a
                // frame it paints around the whole screen, and we paint no
                // such frame, so the gap was just desktop showing through.
                //
                // [CHANGE: claude-code | 2026-08-13] BUG-123. This window used
                // to be anchored `top` only and sized to the panel:
                //     implicitWidth:  dashboardPanel.implicitWidth
                //     implicitHeight: dashboardPanel.implicitHeight
                // That looked tidy and was the cause of the tab-switch stutter.
                // Upstream's dashboard/Content.qml:190-196 puts a `Behavior
                // { Anim {} }` on BOTH implicitWidth and implicitHeight, so the
                // dashboard grows and shrinks smoothly when you move between
                // Weather, Media, Performance and Dashboard. Bound straight to
                // a window, that means the layer-shell SURFACE is resized on
                // every frame of that animation - measured at 24 to 38 resizes
                // per switch, each one a configure round trip with the
                // compositor and a fresh render target. The animation the
                // resizing is meant to follow is the thing it stalls.
                //
                // So do what upstream does: cover the whole screen, never
                // resize, and use a mask so only the panel's own rectangle
                // takes pointer input - ContentWindow.qml:73-79 is exactly
                // this. Outside the mask the clicks go to whatever is behind,
                // so this does NOT bring back the swallow-the-screen bug that
                // separate windows were adopted to fix; the masked region is
                // the dashboard and nothing else.
                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                mask: Region {
                    item: dashboardPanel
                }

                // Upstream paints this backdrop with the sheet's blob, which
                // we do not have. A rounded rect is the honest equivalent,
                // exactly as for the launcher and the OSD.
                StyledRect {
                    anchors.fill: dashboardPanel
                    radius: Tokens.rounding.extraLarge
                    // Flat against the top edge now, so the two corners that
                    // touch it get squared off - a rounded corner there would
                    // show a sliver of desktop through it.
                    topLeftRadius: 0
                    topRightRadius: 0
                    color: Colours.tPalette.m3surface
                    opacity: dashboardPanel.opacity
                }

                Dashboard.Wrapper {
                    id: dashboardPanel

                    anchors.top: parent.top
                    anchors.horizontalCenter: parent.horizontalCenter

                    screenState: scope.screenState

                    // Once the dashboard is down, the pointer is on IT and not
                    // on the tripwire strip. Without this it would drop down
                    // and immediately close again under your cursor.
                    //
                    // [CHANGE: claude-code | 2026-08-13] This sits on the PANEL
                    // now, not on the window. The window is the whole screen as
                    // of BUG-123, and a hover handler that size would report
                    // "hovered" no matter where the pointer was, so the
                    // dashboard would never close on unhover.
                    HoverHandler {
                        id: dashboardSurfaceHover
                    }
                }
            }

            // ── hover-to-open: drop the dashboard down from the top edge ─────
            // [CHANGE: claude-code | 2026-08-13]
            //
            // The numbers are upstream's. Interactions.qml:43-46 counts a point
            // as "in the top panel" when
            //   y < max(Config.border.minThickness,
            //           Config.border.thickness + <panel height>)
            // which with the dashboard up is a 10px band (thickness), and
            // withinPanelWidth (Interactions.qml:31-33) widens the dashboard's
            // own width by Config.border.rounding (25) at each end.
            //
            // KNOWN COST, and it is the worst of the three strips: this is
            // roughly 900 x 10px across the TOP CENTRE of the screen, and it is
            // dead to clicks, because a layer-shell surface takes all pointer
            // input over its area and Wayland has no "motion yes, clicks no".
            // The top edge is expensive real estate - a maximised browser's tab
            // strip lives exactly there, and throwing the pointer at the top
            // edge to hit a tab is a real thing people do. Same trade BUG-110
            // already records for Hyprland's top drawer, over a wider band.
            // Drop `implicitHeight` to Config.border.minThickness (2) to shrink
            // it 5x, or cut `implicitWidth` to a fixed 200 or so, if the tab
            // strip turns out to matter more than the convenience.
            PanelWindow {
                id: dashboardHoverStrip

                screen: scope.modelData
                color: "transparent"

                WlrLayershell.namespace: "caelestia-dashboard-hover"
                // Top, not Overlay: the dashboard is Overlay, so it comes down
                // ON TOP of this rather than fighting it for the pointer.
                WlrLayershell.layer: WlrLayer.Top
                // Never take the keyboard, for the same reason as the
                // dashboard itself.
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

                exclusiveZone: 0
                anchors.top: true

                implicitWidth: dashboardPanel.implicitWidth + Config.border.rounding * 2
                implicitHeight: Config.border.thickness

                MouseArea {
                    id: dashboardStripHover

                    anchors.fill: parent
                    hoverEnabled: true
                    // Do not pretend to handle clicks. It cannot pass them
                    // through either (see above), but at least nothing here
                    // silently swallows a press it might have acted on.
                    acceptedButtons: Qt.NoButton
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

                // Once the OSD is out it covers the hover strip below, so the
                // strip stops seeing the pointer. Without this the thing would
                // slide out and then immediately time out under your cursor.
                HoverHandler {
                    id: osdSurfaceHover
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

                    // Wrapper's own hide Timer (Wrapper.qml:84-92) only hides
                    // when this is false, which is how "hover to keep it open"
                    // works. Upstream sets it from Interactions.qml - the
                    // full-screen sheet we deliberately do not have - so it is
                    // set here instead.
                    hovered: scope.osdHovered
                }
            }

            // ── hover-to-peek: nose the OSD out from the right edge ──────────
            // [CHANGE: claude-code | 2026-08-13] STEP 4, asked for by Shawn.
            //
            // A 2px-wide always-present strip at the right edge. Hovering it
            // calls the SAME show() a volume key press calls, so there is one
            // code path in and one hide Timer, not two.
            //
            // The numbers are upstream's, not invented: Interactions.qml:41
            // treats "in the right panel" as x > width - Config.border
            // .minThickness (= 2), and Interactions.qml:26-29 widens the
            // vertical band by Config.border.rounding (= 25) at each end.
            //
            // The height deliberately tracks the OSD and therefore COLLAPSES
            // when it is closed: Wrapper's content Loader is inactive while
            // hidden, so implicitHeight is 0 and this strip is 2x50px in the
            // middle of the right edge. Once the OSD is out it grows to cover
            // it, which is what carries the pointer through the slide-out
            // animation before the OSD surface itself is under the cursor.
            // That is not a bug to "fix" by pinning a height - a smaller strip
            // is a smaller dead zone, see below.
            //
            // KNOWN COST, accepted deliberately: a layer-shell surface eats
            // pointer input over its whole area, and Wayland has no way to say
            // "send me motion but pass clicks through". So those 2px x 50px
            // are dead to clicks. That is the same trade BUG-110 records for
            // the top edge, at roughly a thousandth of the area. It matters
            // most for a maximised window's scrollbar, which is ~14px wide -
            // you lose its outermost 2px for 50px of its travel.
            PanelWindow {
                id: osdHoverStrip

                screen: scope.modelData
                color: "transparent"

                WlrLayershell.namespace: "caelestia-osd-hover"
                // Top, not Overlay: the OSD itself is Overlay, so it comes out
                // ON TOP of this strip rather than fighting it for the pointer.
                WlrLayershell.layer: WlrLayer.Top
                // Never take the keyboard. This is a pointer tripwire, and a
                // surface that steals focus at the screen edge would be a bug
                // you could not type your way out of.
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

                exclusiveZone: 0
                anchors.right: true

                implicitWidth: Config.border.minThickness
                implicitHeight: osd.implicitHeight + Config.border.rounding * 2

                MouseArea {
                    id: osdStripHover

                    anchors.fill: parent
                    hoverEnabled: true
                    // Do not pretend to handle clicks. It cannot pass them
                    // through either (see above), but at least nothing here
                    // silently swallows a press it might have acted on.
                    acceptedButtons: Qt.NoButton
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
