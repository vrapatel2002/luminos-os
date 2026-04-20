import app from "ags/gtk4/app"
import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createPoll } from "ags/time"
import { exec, execAsync } from "ags/process"
import Network from "gi://AstalNetwork"

// ─── Helpers ──────────────────────────────────────────────────────────
function getWorkspaceState(): { active: number; max: number } {
  try {
    const wss = JSON.parse(exec(["hyprctl", "workspaces", "-j"]))
    const act = JSON.parse(exec(["hyprctl", "activeworkspace", "-j"]))
    const ids = wss.filter((w: any) => w.id > 0).map((w: any) => w.id)
    return { active: act.id || 1, max: Math.max(5, ...ids) }
  } catch {
    return { active: 1, max: 5 }
  }
}

function getBrightness(): number {
  try {
    const cur = parseInt(exec("brightnessctl g").trim())
    const max = parseInt(exec("brightnessctl m").trim())
    return max > 0 ? Math.round((cur / max) * 100) : -1
  } catch {
    return -1
  }
}

function getVolume(): number {
  try {
    const out = exec("wpctl get-volume @DEFAULT_AUDIO_SINK@").trim()
    const m = out.match(/Volume:\s*([\d.]+)/)
    return m ? Math.round(parseFloat(m[1]) * 100) : -1
  } catch {
    return -1
  }
}

function getBattery(): { pct: number; charging: boolean } {
  try {
    const pct = parseInt(exec("cat /sys/class/power_supply/BAT0/capacity").trim())
    const st = exec("cat /sys/class/power_supply/BAT0/status").trim()
    return { pct, charging: st === "Charging" || st === "Full" }
  } catch {
    return { pct: -1, charging: false }
  }
}

function getWifiIcon(): string {
  try {
    const network = Network.get_default()
    const wifi = network.get_wifi()
    if (wifi && wifi.get_ssid()) return "network-wireless-signal-excellent-symbolic"
  } catch {}
  return "network-wireless-offline-symbolic"
}

function getBatteryIcon(pct: number, charging: boolean): string {
  if (pct < 0) return "battery-missing-symbolic"
  const level = Math.round(pct / 10) * 10
  const base = `battery-level-${level}`
  return charging ? `${base}-charging-symbolic` : `${base}-symbolic`
}

function getVolumeIcon(vol: number): string {
  if (vol < 0) return "audio-volume-muted-symbolic"
  if (vol === 0) return "audio-volume-muted-symbolic"
  if (vol < 33) return "audio-volume-low-symbolic"
  if (vol < 66) return "audio-volume-medium-symbolic"
  return "audio-volume-high-symbolic"
}

// ─── Bar ──────────────────────────────────────────────────────────────
export default function Bar(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

  // Reactive polls
  const wsDots = createPoll("●  ○  ○  ○  ○", 500, () => {
    const s = getWorkspaceState()
    const dots: string[] = []
    for (let i = 1; i <= s.max; i++) dots.push(i === s.active ? "●" : "○")
    return dots.join("  ")
  })

  const clock = createPoll("--:--", 1000, () => {
    const n = new Date()
    return `${String(n.getHours()).padStart(2, "0")}:${String(n.getMinutes()).padStart(2, "0")}`
  })

  const dateStr = createPoll("", 1000, () => {
    const n = new Date()
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return `${days[n.getDay()]} ${months[n.getMonth()]} ${n.getDate()}`
  })

  const wifiIcon = createPoll("network-wireless-offline-symbolic", 10000, getWifiIcon)
  const briText = createPoll("", 5000, () => {
    const b = getBrightness()
    return b >= 0 ? `${b}%` : ""
  })
  const volIcon = createPoll("audio-volume-high-symbolic", 3000, () => getVolumeIcon(getVolume()))
  const batIcon = createPoll("battery-missing-symbolic", 10000, () => {
    const b = getBattery()
    return getBatteryIcon(b.pct, b.charging)
  })
  const batText = createPoll("", 10000, () => {
    const b = getBattery()
    return b.pct >= 0 ? `${b.pct}%` : ""
  })

  return (
    <window
      visible
      name="luminos-bar"
      class="Bar"
      namespace="luminos-bar"
      gdkmonitor={gdkmonitor}
      exclusivity={Astal.Exclusivity.EXCLUSIVE}
      anchor={TOP | LEFT | RIGHT}
      application={app}
    >
      <centerbox class="bar-inner">
        {/* LEFT: workspace dots */}
        <button
          $type="start"
          class="ws-btn"
          halign={Gtk.Align.START}
          valign={Gtk.Align.CENTER}
          onClicked={() => execAsync(["hyprctl", "dispatch", "workspace", "+1"])}
        >
          <label class="workspaces" label={wsDots} />
        </button>

        {/* CENTER: clock + date */}
        <menubutton $type="center" class="clock-btn" halign={Gtk.Align.CENTER} valign={Gtk.Align.CENTER}>
          <box>
            <label class="clock" label={clock} />
            <label class="date" label={dateStr} marginStart={8} />
          </box>
          <popover>
            <Gtk.Calendar />
          </popover>
        </menubutton>

        {/* RIGHT: system tray icons */}
        <box $type="end" halign={Gtk.Align.END} valign={Gtk.Align.CENTER} marginEnd={8}>
          {/* Wi-Fi */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <image iconName={wifiIcon} />
            <popover>
              <box marginTop={8} marginBottom={8} marginStart={12} marginEnd={12}>
                <label label="Wi-Fi Networks" />
              </box>
            </popover>
          </menubutton>

          {/* Brightness */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <box>
              <image iconName="display-brightness-symbolic" />
              <label class="tray-text" label={briText} />
            </box>
            <popover>
              <box marginTop={8} marginBottom={8} marginStart={12} marginEnd={12}>
                <label label="Brightness" />
              </box>
            </popover>
          </menubutton>

          {/* Volume */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <image iconName={volIcon} />
            <popover>
              <box marginTop={8} marginBottom={8} marginStart={12} marginEnd={12}>
                <label label="Volume" />
              </box>
            </popover>
          </menubutton>

          {/* Battery */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <box>
              <image iconName={batIcon} />
              <label class="tray-text" label={batText} />
            </box>
            <popover>
              <box marginTop={8} marginBottom={8} marginStart={12} marginEnd={12}>
                <label label="Power" />
              </box>
            </popover>
          </menubutton>
        </box>
      </centerbox>
    </window>
  )
}
