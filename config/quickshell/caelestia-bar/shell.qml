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
//   - sidebar (the notification LIST drawer) / session menu / utilities
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
import Caelestia.Blobs
import Caelestia.Config
import qs.components
import qs.services
import qs.modules
import qs.modules.bar
import qs.modules.bar.popouts as BarPopouts
import qs.modules.dashboard as Dashboard
import qs.modules.launcher as Launcher
import qs.modules.notifications as Notifications
import qs.modules.osd as Osd
import qs.modules.session as Session
import qs.modules.sidebar as Sidebar

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

            // [CHANGE: claude-code | 2026-08-13] Used to be two surfaces OR-ed
            // together - a 2px tripwire window and a HoverHandler on the OSD's
            // own window - because they were separate windows and the pointer
            // is only ever on one of them. The right edge is ONE window now
            // (see rightEdge below), so there is one pointer source and this is
            // just a rename.
            readonly property bool osdHovered: rightEdgeMouse.overOsd

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

            // ══ THE RIGHT EDGE: one window, four panels ══════════════════════
            // [CHANGE: claude-code | 2026-08-13] DECISION 68, the three-layer
            // right edge Shawn asked for:
            //
            //     drag in from the right edge  ->  1. volume / brightness (OSD)
            //     keep dragging                ->  2. power menu (session)
            //     keep dragging                ->  3. notification list (sidebar)
            //
            // plus the toasts, which sit at the top right and are not part of
            // the drag chain.
            //
            // WHY ONE WINDOW. These four used to be two or three separate
            // PanelWindows. That cannot produce the gesture, for two reasons
            // that are both about Wayland rather than QML:
            //
            //   - The panels have to PUSH EACH OTHER LEFT as they come out
            //     (upstream drawers/Panels.qml:41-97 is a chain of
            //     `anchors.rightMargin` bindings, one panel reading the next
            //     panel's margin and width). Anchors do not cross windows.
            //   - The drag has to keep receiving motion after the pointer has
            //     left the 2px edge strip it started in. On Wayland a button
            //     press gives the surface an implicit pointer grab, so motion
            //     keeps flowing to THAT surface until release - but only that
            //     one. Start the drag in the strip window and it dies the
            //     moment you cross into the panel window.
            //
            // So this is upstream's own shape: cover the whole output, never
            // resize, and use `mask` to hand back every pixel we are not
            // actually using. That is not a return of the old click-swallowing
            // bug - BUG-123 records that its cause was a MISSING mask, not a
            // big window. Size was never the problem; the input region was.
            //
            // ── notification toasts, top right ───────────────────────────────
            // STEP 1 of routing ALL notifications through Caelestia, asked for
            // by Shawn.
            //
            // This hosts upstream's notifications/Wrapper.qml unmodified. The
            // notification SERVER is not here - it lives in
            // services/Notifs.qml, a singleton that owns a NotificationServer.
            // Simply referencing Notifs (which Content.qml does, for its list
            // model) is what brings the singleton to life and makes us claim
            // the org.freedesktop.Notifications D-Bus name.
            //
            // THE HANDOVER PROBLEM, written down because it will bite again:
            // plasmashell claims that same name at login and REFUSES to give
            // it up - its RequestName has no ALLOW_REPLACEMENT flag, so our
            // request comes back with reply code 3 (EXISTS) and nothing
            // happens. Quickshell has no "replace" option and cannot force it.
            // What it DOES do is watch NameOwnerChanged and retry the moment
            // the name is released. So the handover is:
            //     systemctl --user restart plasma-plasmashell.service
            // once, while this shell is up. plasmashell drops the name on the
            // way down, we grab it in the gap, and plasmashell comes back
            // without it and stays healthy. Verified: after that,
            // `busctl --user call ... GetNameOwner` points at our qs process.
            //
            // Window shape is BUG-123's, not the OSD's: notifications/
            // Content.qml puts a `Behavior { Anim {} }` on implicitHeight, so
            // binding a window to that size would resize the wl_surface on
            // every frame of every notification arriving or leaving. Cover the
            // output, never resize, and mask down to the panel instead.
            PanelWindow {
                id: rightEdge

                screen: scope.modelData
                color: "transparent"

                // [CHANGE: claude-code | 2026-08-13] ALWAYS MAPPED now, where
                // this used to appear only when there was something to show.
                //
                // It has to be. The catch strip in the mask below is what the
                // pointer trips over to start the gesture, and a strip that
                // only exists once a panel is already open catches nothing.
                // Upstream's window is always up for exactly this reason.
                //
                // What makes that safe is that the mask is never empty and
                // never the whole screen: with everything closed it is a 2px
                // ribbon at the right edge, which is the entire cost of this
                // window when idle. The old worry - "an empty Region might mean
                // ALL input, turning the screen into a click sink" - does not
                // apply, because the region below always contains the strip.
                visible: true

                WlrLayershell.namespace: "caelestia-right-edge"
                // Overlay: a notification you cannot see over a fullscreen
                // video is not a notification, and an OSD behind a video is
                // not doing its job either.
                WlrLayershell.layer: WlrLayer.Overlay
                // Never take the keyboard. A toast that steals focus while you
                // are typing is worse than no toast at all - and this surface
                // is now permanently mapped, so taking focus would be a bug you
                // could not type your way out of.
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

                // It floats on top of whatever is there and must never shove
                // windows aside - a volume press should not reflow your screen.
                exclusiveZone: 0

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                // [CHANGE: claude-code | 2026-08-13] The input region: a thin
                // catch strip, plus whichever panels are out.
                //
                // An outer Region with no item and no size is the empty region
                // (upstream uses `Region {}` exactly that way in Exclusions.qml
                // to make a window click-through); child Regions default to
                // Union, so this reads "the strip OR any open panel, and
                // nothing else". A closed panel is 0px wide, so it contributes
                // nothing.
                //
                // The strip's numbers are upstream's, not invented:
                // Interactions.qml:41 treats "in the right panel" as
                // x > width - Config.border.minThickness (= 2), and
                // Interactions.qml:26-29 widens the vertical band by
                // Config.border.rounding (= 25) at each end.
                //
                // DELIBERATELY NARROWER THAN UPSTREAM: upstream's border runs
                // the full height of the screen, so you can start the gesture
                // anywhere down the right edge. This tracks the OSD's band
                // instead, which collapses to 2x50px in the middle of the edge
                // when everything is closed. The reason is the known cost
                // below; the gesture Shawn described starts where the volume
                // pops out, so that is where the tripwire is.
                //
                // KNOWN COST, accepted deliberately and unchanged from the old
                // hover strip: a layer-shell surface eats pointer input over
                // its whole area, and Wayland has no way to say "send me motion
                // but pass clicks through". So those 2x50px are dead to clicks.
                // Same trade BUG-110 records for the top edge, at roughly a
                // thousandth of the area. It matters most for a maximised
                // window's scrollbar, which is ~14px wide - you lose its
                // outermost 2px for 50px of its travel.
                mask: Region {
                    Region {
                        x: rightEdge.width - Config.border.minThickness
                        y: osdWrapper.y - Config.border.rounding
                        width: Config.border.minThickness
                        height: osdWrapper.height + Config.border.rounding * 2
                    }

                    Region {
                        item: osdWrapper
                    }

                    Region {
                        item: notifPanel
                    }

                    Region {
                        item: sessionWrapper
                    }

                    Region {
                        item: sidebarDrawer
                    }
                }

                // ── the backdrop: ONE shape, not four ────────────────────────
                // [CHANGE: claude-code | 2026-08-13] Was two separate
                // `StyledRect`s (one behind the OSD, one behind the session
                // panel) plus nothing at all behind the notifications and the
                // sidebar, which is why the three layers came out as three
                // floating pills with notches between them.
                //
                // Upstream never draws a rect per panel. Every background goes
                // into one signed-distance field - a `BlobGroup` - and each
                // panel contributes a `BlobRect` to it. The field is evaluated
                // with a SMOOTH minimum instead of a hard one, so two shapes
                // that touch grow a fillet between them and read as a single
                // surface. That is the whole trick; there is no code that
                // "joins" anything, the shapes just stop being separate.
                //
                // This is copied from drawers/ContentWindow.qml:149-249, minus
                // two things that do not exist here:
                //
                //   - `BlobInvertedRect`, upstream's rounded screen border.
                //     It is what swallows the outer corners so the panels look
                //     welded to the frame. We have no screen border (DECISION
                //     68 still lists it as not built), so the group ends in
                //     rounded corners at the right edge instead - the same
                //     shape the old rects had, so nothing gets worse.
                //   - the `layer.enabled` + `MultiEffect` drop shadow. That is
                //     a full-screen offscreen texture redrawn on every frame of
                //     every panel animation, on a permanently-mapped overlay.
                //     Not worth it for a shadow; the merge does not need it.
                //
                // The `+ bar.implicitWidth` / `+ borderThickness` offsets in
                // upstream's version are both 0 for us: this window contains
                // neither, and the panels are direct children, so their x/y are
                // already in this window's coordinates.
                //
                // Upstream writes these four as an inline `component PanelBg`.
                // Inline components have to be declared at the top of the
                // document, where the ids inside this Variants delegate are not
                // in scope, so they are written out longhand here.
                BlobGroup {
                    id: blobGroup

                    color: Colours.tPalette.m3surface
                    smoothing: Config.border.smoothing
                }

                // `deformScale` is the wobble: the blob overshoots when the
                // panel moves and settles back, like jelly. The matching
                // `transform: Matrix4x4 { matrix: <bg>.deformMatrix }` on each
                // panel below squashes the CONTENT the same way - without it
                // the backdrop would wobble and the text inside would sit dead
                // still, which looks worse than no wobble at all. The per-panel
                // amounts are upstream's.
                // `visible` gate, NOT copied from upstream - upstream needs no
                // such thing and this is why. A closed panel does not shrink to
                // nothing: it keeps its width and slides off the right of the
                // screen, so its blob leaves a 2px sliver hanging over the
                // edge. Upstream's own comment on the border blob calls it
                // "bulge from closed drawers" and thickens the border by 50px
                // to swallow it. We have no border to swallow anything with, so
                // a fully-closed panel drops out of the field instead.
                //
                // Measured before the gate: a 2px dark column at x=2878..2879
                // running y=400..1380 - the session panel's exact band. The old
                // StyledRects never showed it because they carried
                // `opacity: session.opacity`, which is 0 when closed.
                //
                // `offsetScale` is 1 closed and 0 open, so this only bites at
                // the very end of the animation - nothing pops.
                BlobRect {
                    id: osdBg

                    visible: osd.offsetScale < 1
                    group: blobGroup
                    x: osdWrapper.x + osd.x
                    y: osdWrapper.y
                    implicitWidth: osd.width
                    implicitHeight: osdWrapper.height
                    radius: Tokens.rounding.extraLarge
                    deformScale: (0.25 * Config.appearance.deformScale) / 10000
                }

                BlobRect {
                    id: sessionBg

                    visible: session.offsetScale < 1
                    group: blobGroup
                    x: sessionWrapper.x + session.x
                    y: sessionWrapper.y
                    implicitWidth: session.width
                    implicitHeight: sessionWrapper.height
                    radius: Tokens.rounding.extraLarge
                    deformScale: (0.2 * Config.appearance.deformScale) / 10000
                }

                BlobRect {
                    id: notifsBg

                    visible: notifPanel.height > 0
                    group: blobGroup
                    x: notifPanel.x
                    y: notifPanel.y
                    implicitWidth: notifPanel.width
                    implicitHeight: notifPanel.height
                    radius: Tokens.rounding.extraLarge
                    deformScale: (0.15 * Config.appearance.deformScale) / 10000
                }

                BlobRect {
                    id: sidebarBg

                    visible: sidebarDrawer.offsetScale < 1
                    group: blobGroup
                    x: sidebarDrawer.x
                    y: sidebarDrawer.y
                    implicitWidth: sidebarDrawer.width
                    // Upstream's line. Undoing the vertical deform here keeps
                    // the blob's BOTTOM where the panel's bottom is while the
                    // middle still wobbles; the +2 covers the seam.
                    implicitHeight: sidebarDrawer.height * (1 / sidebarBg.rawDeformMatrix.m22) + 2
                    radius: Tokens.rounding.extraLarge
                    // Barely any wobble on this one, upstream's value: it is
                    // the tallest panel, and the same angular overshoot moves
                    // its far end much further.
                    deformScale: (0.03 * Config.appearance.deformScale) / 10000
                }

                // ── LAYER 1: volume / brightness ─────────────────────────────
                // [CHANGE: claude-code | 2026-08-13] Moved in here from a
                // window of its own. The wrapper Item and the margin chain are
                // copied verbatim from upstream drawers/Panels.qml:41-58.
                //
                // The `rightMargin` binding is the push-left chain: the OSD
                // sits to the left of the session panel, which sits to the left
                // of the sidebar. Each panel reads the NEXT one's margin and
                // adds however much of it is currently on screen
                // (`width * (1 - offsetScale)`, which is 0 when closed and the
                // full width when open), so the whole row slides as one.
                //
                // `clip` matters more than it looks: while a panel to the right
                // is out, this one is squeezed and would otherwise draw over it.
                //
                // Nothing here DRIVES the OSD open on a volume key.
                // Osd/Wrapper.qml:51-73 is a `Connections { target: Audio }`
                // that calls show() whenever PipeWire's volume changes - no
                // matter who changed it. KDE's kded `audioshortcutsservice`
                // owns the volume keys and moves PipeWire; Quickshell sees the
                // same node change and pops this out. So there is deliberately
                // no shortcut wiring, and none is needed. Brightness is NOT
                // symmetrical - it needed the poller further down.
                Item {
                    id: osdWrapper

                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: sessionWrapper.anchors.rightMargin + session.width * (1 - session.offsetScale)

                    clip: sidebarDrawer.visible || session.visible

                    implicitWidth: osd.implicitWidth * (1 - osd.offsetScale)
                    implicitHeight: osd.implicitHeight

                    // The backdrop is `osdBg` above now, not a rect in here.

                    Osd.Wrapper {
                        id: osd

                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter

                        transform: Matrix4x4 {
                            matrix: osdBg.deformMatrix
                        }

                        screen: scope.modelData
                        screenState: scope.screenState
                        // Wrapper.qml:20 uses this for a 12px nudge so the OSD
                        // steps aside when something is out to its right. It
                        // was hard-coded false while those panels did not
                        // exist; they do now.
                        sidebarOrSessionVisible: sidebarDrawer.visible || session.visible

                        // Wrapper's own hide Timer (Wrapper.qml:84-92) only
                        // hides when this is false, which is how "hover to keep
                        // it open" works. Upstream sets it from
                        // Interactions.qml; we set it from the mouse area at
                        // the bottom of this window, which is the same thing.
                        hovered: scope.osdHovered
                    }
                }

                // ── LAYER 2: the power menu ──────────────────────────────────
                // [CHANGE: claude-code | 2026-08-13] NEW - this is the layer
                // that was missing. Structure copied verbatim from upstream
                // drawers/Panels.qml:74-97.
                //
                // session/Wrapper.qml needs exactly two things - `screenState`
                // and `sidebarVisible` - and session/Content.qml imports no
                // Hyprland anything (checked), so unlike most of this port
                // there is no stub to worry about.
                //
                // THE BUTTONS ARE NOT WIRED YET, on purpose: Shawn asked for
                // the three-layer gesture first and said the buttons come
                // later. They run `Config.session.commands.*`, whose defaults
                // are Hyprland dispatches that will silently do nothing under
                // Plasma - the usual null-is-false trap. Replacing them with
                // loginctl/qdbus is the follow-up, not this change.
                Item {
                    id: sessionWrapper

                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: sidebarDrawer.width * (1 - sidebarDrawer.offsetScale)

                    clip: sidebarDrawer.visible

                    implicitWidth: session.implicitWidth * (1 - session.offsetScale)
                    implicitHeight: session.implicitHeight

                    // The backdrop is `sessionBg` above now.

                    Session.Wrapper {
                        id: session

                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter

                        transform: Matrix4x4 {
                            matrix: sessionBg.deformMatrix
                        }

                        screenState: scope.screenState
                        sidebarVisible: sidebarDrawer.visible
                    }
                }

                // Still no utilities panel (upstream's bottom-right dock).
                // notifications/Content.qml only dereferences it inside
                // `if (screenState.utilities)`, which nothing ever sets here,
                // so an empty Item is safe rather than merely convenient.
                Item {
                    id: utilitiesStandin
                }

                Notifications.Wrapper {
                    id: notifPanel

                    anchors.top: parent.top
                    anchors.right: parent.right

                    screenState: scope.screenState
                    sidebarPanel: sidebarDrawer
                    // [CHANGE: claude-code | 2026-08-13] These two used to be
                    // zero-size stand-ins, because the real panels lived in
                    // other windows and Content.qml:38-42 clamps the toast list
                    // by reading `osdPanel.y` - a coordinate that is meaningless
                    // across windows. One window now, so they are the real
                    // things, exactly as upstream passes them.
                    osdPanel: osdWrapper
                    sessionPanel: sessionWrapper
                    utilitiesPanel: utilitiesStandin

                    transform: Matrix4x4 {
                        matrix: notifsBg.deformMatrix
                    }
                }

                // ── LAYER 3: the notification LIST, as a right-edge drawer ───
                // [CHANGE: claude-code | 2026-08-13] DECISION 68.
                //
                // Same window as the toasts on purpose, not convenience:
                // upstream anchors this to the notification panel's bottom
                // edge (drawers/Panels.qml:145-154) so the two stack down the
                // right side, and anchoring across windows is not a thing.
                //
                // Safe to bind an anchor to, unlike the notification panel:
                // sidebar/Wrapper.qml has a CONSTANT implicitWidth and slides
                // by animating anchors.rightMargin through `offsetScale`. It
                // never resizes, so BUG-123 (a wl_surface resized every frame)
                // cannot happen here.
                //
                // Upstream anchors the bottom to the utilities panel; we have
                // none, so it goes to the bottom of the screen. topMargin
                // cancels the -5 that notifications/Wrapper.qml:14 applies to
                // itself, exactly as upstream does.
                Sidebar.Wrapper {
                    id: sidebarDrawer

                    screenState: scope.screenState

                    anchors.top: notifPanel.bottom
                    anchors.bottom: parent.bottom
                    anchors.right: parent.right
                    anchors.topMargin: -notifPanel.anchors.topMargin

                    transform: Matrix4x4 {
                        matrix: sidebarBg.deformMatrix
                    }
                }

                // ── the gesture: press at the edge and drag inward ───────────
                // [CHANGE: claude-code | 2026-08-13] The three-layer chain
                // Shawn asked for. This is upstream's drawers/Interactions.qml
                // with everything that is not the right edge left out - it also
                // drives the bar, the launcher, the dashboard and the tray
                // popouts, and all of those already have their own working
                // handling in this file. Copying the lot would replace four
                // things that work in order to gain one that does not exist.
                //
                // THE DIRECTION IS INWARD, i.e. leftward, and that surprised me
                // enough to write down: you press ON the right edge and pull
                // TOWARDS the middle of the screen, like sliding a drawer out.
                // Upstream opens on `dragX < -threshold` (Interactions.qml:
                // 146-156) and closes on `dragX > threshold`.
                //
                // Why a press-drag works at all when the mask is 2px wide: on
                // Wayland a button press gives this surface an implicit pointer
                // grab, so every motion event keeps coming here until release,
                // however far out of the strip the pointer travels. Hover
                // without a button does NOT get that, which is why the OSD -
                // the only one that opens on hover alone - is the one panel
                // whose band the strip is cut to.
                //
                // NOT copied, deliberately: upstream's `dragMaskPadding`
                // (ContentWindow.qml:47-59) widens the catch area when the
                // workspace is empty. It decides that by asking Hyprland for
                // the window list, which under KWin returns null, and null
                // silently counts as false - so it would be a permanent 0 here
                // and is honest to leave out rather than carry as dead code.
                MouseArea {
                    id: rightEdgeMouse

                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.AllButtons

                    property point dragStart

                    // Upstream Interactions.qml:26-42, with two terms dropped:
                    // it offsets by the bar width and the border thickness
                    // because its panels live in an Item inset by both. Ours
                    // fill the output, so panel coordinates are already screen
                    // coordinates.
                    function withinPanelHeight(panel: Item, y: real): bool {
                        return y >= panel.y - Config.border.rounding && y <= panel.y + panel.height + Config.border.rounding;
                    }

                    function inRightPanel(panel: Item, x: real, y: real): bool {
                        return x > Math.min(width - Config.border.minThickness, panel.x) && withinPanelHeight(panel, y);
                    }

                    // Feeds scope.osdHovered, which feeds both the OSD's own
                    // hide Timer and the show() that opens it in the first
                    // place. The `Math.min` above is what makes one expression
                    // cover both states: closed, the panel is 0px wide and sits
                    // at x == width, so the test collapses to "within 2px of the
                    // edge"; open, it is the panel's own left edge.
                    //
                    // A binding, not an assignment in onPositionChanged, and it
                    // is worth knowing why it is sound: a function CALL inside a
                    // binding registers no reactive dependency (that is
                    // BUG-124's first half), so this re-evaluates only on the
                    // properties it reads directly - containsMouse, mouseX,
                    // mouseY. Those are exactly the pointer, which is the only
                    // input that matters here. Panel geometry changing without
                    // the pointer moving would go unnoticed, and that is fine:
                    // the panel only moves because the pointer did.
                    readonly property bool overOsd: containsMouse && inRightPanel(osdWrapper, mouseX, mouseY)

                    onPressed: event => dragStart = Qt.point(event.x, event.y)

                    // ── how these close again ────────────────────────────────
                    // Upstream Interactions.qml:67-92. Moving the pointer off
                    // the panels closes them; `containsMouse` goes false the
                    // moment the pointer leaves the input region, which with the
                    // mask above means "left the strip and every open panel".
                    //
                    // Note it is LEAVING that closes them, not clicking outside.
                    // Clicking outside cannot work and never will: everything
                    // outside the mask is handed to the window underneath, so
                    // this surface is never told the click happened. Upstream is
                    // the same. Grabbing the whole screen to hear about outside
                    // clicks would be the click-swallowing bug on purpose.
                    //
                    // [CHANGE: claude-code | 2026-08-13] The ownership flag is
                    // the fix for the drawer getting STUCK OPEN. I first left
                    // the sidebar out of this handler entirely, reasoning that
                    // Meta+N opens it with the pointer somewhere else and a bare
                    // leave-closes rule would let a stray mouse move slam it
                    // shut. True, but it traded a small annoyance for a real
                    // one: nothing closed it at all.
                    //
                    // This is upstream's `*ShortcutActive` idea in one variable,
                    // and the same shape as `dashOwnedByHover` further up this
                    // file: the pointer only earns the right to close a panel by
                    // having been inside it. So a drag opens and a leave closes;
                    // Meta+N with the pointer elsewhere is left alone until you
                    // actually go and touch the thing.
                    property bool ownedByPointer

                    onContainsMouseChanged: {
                        if (containsMouse) {
                            if (scope.screenState.sidebar || scope.screenState.session)
                                ownedByPointer = true;
                        } else if (ownedByPointer) {
                            ownedByPointer = false;
                            scope.screenState.session = false;
                            scope.screenState.sidebar = false;
                        }
                    }

                    onPositionChanged: event => {
                        const x = event.x;
                        const y = event.y;
                        const dragX = x - dragStart.x;

                        // LAYER 1 opens on hover alone, no button needed.
                        // Upstream Interactions.qml:122-127.
                        scope.screenState.osd = overOsd;

                        // Covers the last way the pointer can end up inside an
                        // open panel without a containsMouse edge: Meta+N fired
                        // while the pointer happened to be resting on the strip.
                        // A motion event only reaches us at all if the pointer is
                        // within the mask, so this cannot fire for a shortcut
                        // pressed with the pointer out in the middle of the
                        // screen - which is the case the flag exists to protect.
                        if (scope.screenState.sidebar || scope.screenState.session)
                            ownedByPointer = true;

                        if (!pressed)
                            return;

                        const startedAtEdge = dragStart.x > Math.min(width - Config.border.minThickness, sessionWrapper.x);

                        if (sidebarDrawer.offsetScale === 1) {
                            // Sidebar closed: the drag opens LAYER 2, and then
                            // LAYER 3 once layer 2 is all the way out.
                            // Upstream Interactions.qml:145-157.
                            if (startedAtEdge && withinPanelHeight(sessionWrapper, y)) {
                                if (dragX < -Config.session.dragThreshold) {
                                    scope.screenState.session = true;
                                    // The pointer opened it, so the pointer is
                                    // allowed to close it. Setting the flag here
                                    // and not only in onContainsMouseChanged is
                                    // the whole fix: during a drag the pointer is
                                    // ALREADY inside, so containsMouse never
                                    // changes and that handler never runs. Miss
                                    // this and the panel opens and never closes.
                                    ownedByPointer = true;
                                } else if (dragX > Config.session.dragThreshold) {
                                    scope.screenState.session = false;
                                }

                                if (session.offsetScale <= 0 && dragX < -Config.sidebar.dragThreshold) {
                                    scope.screenState.sidebar = true;
                                    ownedByPointer = true;
                                }
                            }
                        } else {
                            // Sidebar open: dragging back out towards the edge
                            // closes it. Upstream Interactions.qml:194-196.
                            if (inRightPanel(sidebarDrawer, dragStart.x, dragStart.y) && dragX > Config.sidebar.dragThreshold)
                                scope.screenState.sidebar = false;
                        }
                    }
                }

                // ── the one kick this port needs ─────────────────────────────
                // [CHANGE: claude-code | 2026-08-13] BUG-124.
                //
                // Without this, notifications arrive, are stored, and NEVER
                // draw. It is a genuine deadlock in upstream's own code that
                // only opens up when the panel is alone in a window:
                //
                //   notifications/Content.qml:29-57 sizes itself by asking the
                //   ListView for each delegate: `list.itemAtIndex(i).
                //   nonAnimHeight`. A function call is NOT a reactive
                //   dependency, so that binding re-runs on exactly one signal:
                //   `list.count` changing.
                //   Wrapper.qml:13 is `visible: height > 0`, and with nothing
                //   in the list the height is 0 - so the ListView starts life
                //   invisible and 0 (in fact -27) pixels tall.
                //   A ListView in that state never runs its layout pass, so
                //   when the model gains a row it creates no delegate and
                //   never emits countChanged. Measured: count reads 1 (that
                //   query goes straight to the model) while contentHeight is
                //   0 and the content item has no children at all.
                //   So the height binding never re-runs, the height stays 0,
                //   the panel stays invisible, and the view stays unlaid-out.
                //
                // Upstream never trips over it because its panels share ONE
                // window with the bar and the border, which are painting and
                // animating constantly; that traffic keeps the view's layout
                // pass running. Ours is a window of its own with nothing else
                // in it, so nothing ever pokes it. Same class of bug as
                // BUG-123: upstream code that assumed the single full-screen
                // sheet it was written for.
                //
                // forceLayout() runs that pass on demand. Measured, from an
                // empty list and one notify-send: before - contentHeight 0,
                // 0 delegates, panel height 0, invisible; after - contentHeight
                // 66, 1 delegate, panel height 88, visible.
                //
                // It fires on popupsChanged, so it covers the list emptying
                // again as well as filling. Qt.callLater collapses a burst of
                // notifications into one call after the bindings have settled.
                Connections {
                    target: Notifs

                    function onPopupsChanged(): void {
                        Qt.callLater(rightEdge.layOutNotifs);
                    }
                }

                // Upstream gives the ListView an id but no way to reach it
                // from outside, so find it by the thing we actually need.
                // Looking for the capability rather than walking a fixed path
                // of child indices means a reshuffle upstream leaves this
                // finding nothing - the same as today's behaviour - instead of
                // grabbing the wrong item.
                function layOutNotifs(): void {
                    const found = (function find(item) {
                        if (!item)
                            return null;
                        if (typeof item.forceLayout === "function")
                            return item;
                        for (const child of item.children ?? []) {
                            const hit = find(child);
                            if (hit)
                                return hit;
                        }
                        return null;
                    })(notifPanel);

                    if (found)
                        found.forceLayout();
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
