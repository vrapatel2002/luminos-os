# dumbtv home for Roku

A home screen for the Roku TV with your apps and your inputs, and nothing else:
a clock, a 3-wide grid of app tiles, a row of HDMI/AV inputs. No ads, no sponsored
rows, no account, no analytics. [CHANGE: claude-code | 2026-10-27]

Roku port of the **dumbtv home** design (https://github.com/humblemuzzu/dumbtv, MIT —
see LICENSE-dumbtv). dumbtv itself is Fire TV / Android only (Java APK + ADB); Roku has no
ADB and no launcher replacement, so this is a separate BrightScript SceneGraph channel.

## How it works
- App list: the TV's own ECP `GET http://<tv>:8060/query/apps`; icons: `/query/icon/<id>`.
- Open an app or input: ECP `POST /launch/<id>` (inputs are `tvinput.hdmi1` …).
- Needs: Settings > System > Advanced system settings > Control by mobile apps > Network access = **Permissive**.
- Settings live in the TV's registry (section `dumbtv`).

## Remote
| Key | Does |
|---|---|
| Arrows | move |
| OK | open the app / switch input |
| ★ | options: move left/right, hide, accent, tile style (Original / Afterglow), inputs row, show hidden, reset |
| Back | jump to the first tile |

## Limits (Roku, not fixable from a channel)
- The Home button still goes to Roku's own home screen; open dumbtv home like any app.
- It is a developer-mode sideload: one dev channel at a time; it survives reboots but not a
  developer-mode reset.

## Install
`build.sh` makes `dist/dumbtv-roku.zip`. Open http://<tv-ip> (developer mode), sign in
(user `rokudev` + your dev password), Upload the zip, Install.
