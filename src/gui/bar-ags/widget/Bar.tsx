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

function getBattery(): { pct: number; charging: boolean; timeLeft: string } {
  try {
    const pct = parseInt(exec("cat /sys/class/power_supply/BAT0/capacity").trim())
    const st = exec("cat /sys/class/power_supply/BAT0/status").trim()
    const charging = st === "Charging" || st === "Full"

    let timeLeft = ""
    try {
      const energyNow = parseInt(exec("cat /sys/class/power_supply/BAT0/energy_now").trim())
      const powerNow = parseInt(exec("cat /sys/class/power_supply/BAT0/power_now").trim())
      if (powerNow > 0) {
        const hours = Math.floor(energyNow / powerNow)
        const mins = Math.round(((energyNow / powerNow) - hours) * 60)
        timeLeft = `${hours}h ${mins}m remaining`
      }
    } catch {}

    return { pct, charging, timeLeft }
  } catch {
    return { pct: -1, charging: false, timeLeft: "" }
  }
}

function getWifiInfo(): { icon: string; ssid: string; strength: number } {
  try {
    const network = Network.get_default()
    const wifi = network.get_wifi()
    if (wifi) {
      const ssid = wifi.get_ssid() || ""
      const strength = wifi.get_strength()
      let icon = "network-wireless-offline-symbolic"
      if (ssid) {
        if (strength > 75) icon = "network-wireless-signal-excellent-symbolic"
        else if (strength > 50) icon = "network-wireless-signal-good-symbolic"
        else if (strength > 25) icon = "network-wireless-signal-ok-symbolic"
        else icon = "network-wireless-signal-weak-symbolic"
      }
      return { icon, ssid, strength }
    }
  } catch {}
  return { icon: "network-wireless-offline-symbolic", ssid: "", strength: 0 }
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

// ─── Workspace Dots ──────────────────────────────────────────────────
function WorkspaceDots() {
  const wsState = createPoll(
    JSON.stringify({ active: 1, max: 5 }),
    500,
    () => JSON.stringify(getWorkspaceState()),
  )

  return (
    <box class="ws-dots" halign={Gtk.Align.START} valign={Gtk.Align.CENTER}>
      {wsState.as((json: string) => {
        const s = JSON.parse(json)
        const dots = []
        for (let i = 1; i <= s.max; i++) {
          const active = i === s.active
          const ws = i
          dots.push(
            <button
              class={active ? "ws-dot active" : "ws-dot"}
              onClicked={() => execAsync(["hyprctl", "dispatch", "workspace", String(ws)])}
            >
              <label label={active ? "●" : "○"} />
            </button>,
          )
        }
        return dots
      })}
    </box>
  )
}

// ─── Brightness Popover ──────────────────────────────────────────────
function BrightnessPopover() {
  const briVal = createPoll("", 3000, () => {
    const b = getBrightness()
    return b >= 0 ? `${b}%` : "N/A"
  })

  return (
    <box orientation={Gtk.Orientation.VERTICAL} class="popover-content">
      <box class="popover-row" marginBottom={4}>
        <image iconName="display-brightness-symbolic" marginEnd={8} />
        <label label="Display" class="popover-title" hexpand halign={Gtk.Align.START} />
        <label label={briVal} class="popover-value" />
      </box>
      <Gtk.Scale
        class="popover-slider"
        hexpand
        drawValue={false}
        adjustment={
          new Gtk.Adjustment({
            lower: 0,
            upper: 100,
            value: Math.max(0, getBrightness()),
            stepIncrement: 5,
            pageIncrement: 10,
          })
        }
        onChangeValue={(_self: any, _scroll: any, value: number) => {
          const clamped = Math.round(Math.max(0, Math.min(100, value)))
          execAsync(["brightnessctl", "s", `${clamped}%`])
          return false
        }}
      />
    </box>
  )
}

// ─── Volume Popover ──────────────────────────────────────────────────
function VolumePopover() {
  const volVal = createPoll("", 3000, () => {
    const v = getVolume()
    return v >= 0 ? `${v}%` : "N/A"
  })
  const volIcn = createPoll("audio-volume-high-symbolic", 3000, () => getVolumeIcon(getVolume()))

  return (
    <box orientation={Gtk.Orientation.VERTICAL} class="popover-content">
      <box class="popover-row" marginBottom={4}>
        <image iconName={volIcn} marginEnd={8} />
        <label label="Sound" class="popover-title" hexpand halign={Gtk.Align.START} />
        <label label={volVal} class="popover-value" />
      </box>
      <Gtk.Scale
        class="popover-slider"
        hexpand
        drawValue={false}
        adjustment={
          new Gtk.Adjustment({
            lower: 0,
            upper: 100,
            value: Math.max(0, getVolume()),
            stepIncrement: 5,
            pageIncrement: 10,
          })
        }
        onChangeValue={(_self: any, _scroll: any, value: number) => {
          const clamped = Math.round(Math.max(0, Math.min(100, value))) / 100
          execAsync(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", String(clamped)])
          return false
        }}
      />
    </box>
  )
}

// ─── Wi-Fi Popover ───────────────────────────────────────────────────
function WifiPopover() {
  const wifiDetail = createPoll("Not connected", 10000, () => {
    const i = getWifiInfo()
    return i.ssid ? `${i.ssid}  (${i.strength}%)` : "Not connected"
  })

  return (
    <box orientation={Gtk.Orientation.VERTICAL} class="popover-content">
      <box class="popover-row">
        <image iconName="network-wireless-signal-excellent-symbolic" marginEnd={8} />
        <label label="Wi-Fi" class="popover-title" hexpand halign={Gtk.Align.START} />
      </box>
      <box class="popover-row" marginTop={4}>
        <label class="popover-detail" halign={Gtk.Align.START} label={wifiDetail} />
      </box>
      <button
        class="popover-action-btn"
        marginTop={8}
        onClicked={() => execAsync(["nm-connection-editor"])}
      >
        <label label="Network Settings..." />
      </button>
    </box>
  )
}

// ─── Battery Popover ─────────────────────────────────────────────────
function BatteryPopover() {
  const batPct = createPoll("", 15000, () => {
    const b = getBattery()
    return b.pct >= 0 ? `${b.pct}%` : "N/A"
  })
  const batIcn = createPoll("battery-missing-symbolic", 15000, () => {
    const b = getBattery()
    return getBatteryIcon(b.pct, b.charging)
  })
  const batStatus = createPoll("", 15000, () => {
    const b = getBattery()
    if (b.charging) return "Charging"
    return b.timeLeft || "On battery"
  })

  return (
    <box orientation={Gtk.Orientation.VERTICAL} class="popover-content">
      <box class="popover-row">
        <image iconName={batIcn} marginEnd={8} />
        <label label="Battery" class="popover-title" hexpand halign={Gtk.Align.START} />
        <label class="popover-value" label={batPct} />
      </box>
      <label class="popover-detail" halign={Gtk.Align.START} marginTop={4} label={batStatus} />
    </box>
  )
}

// ─── Bar ──────────────────────────────────────────────────────────────
export default function Bar(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

  // --- Reactive polls for bar icons ---
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

  const wifiIcon = createPoll("network-wireless-offline-symbolic", 10000, () => getWifiInfo().icon)
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
      <centerbox cssName="centerbox">
        {/* LEFT: workspace dots — click individual to switch */}
        <box $type="start">
          <WorkspaceDots />
        </box>

        {/* CENTER: clock + date — click for calendar */}
        <menubutton $type="center" class="clock-btn" halign={Gtk.Align.CENTER} valign={Gtk.Align.CENTER}>
          <box>
            <label class="clock" label={clock} />
            <label class="date" label={dateStr} marginStart={8} />
          </box>
          <popover>
            <Gtk.Calendar />
          </popover>
        </menubutton>

        {/* RIGHT: system icons */}
        <box $type="end" halign={Gtk.Align.END} valign={Gtk.Align.CENTER} marginEnd={8}>
          {/* Wi-Fi */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <image iconName={wifiIcon} />
            <popover>
              <WifiPopover />
            </popover>
          </menubutton>

          {/* Brightness */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <box>
              <image iconName="display-brightness-symbolic" />
              <label class="tray-text" label={briText} />
            </box>
            <popover>
              <BrightnessPopover />
            </popover>
          </menubutton>

          {/* Volume */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <image iconName={volIcon} />
            <popover>
              <VolumePopover />
            </popover>
          </menubutton>

          {/* Battery */}
          <menubutton class="tray-btn" valign={Gtk.Align.CENTER}>
            <box>
              <image iconName={batIcon} />
              <label class="tray-text" label={batText} />
            </box>
            <popover>
              <BatteryPopover />
            </popover>
          </menubutton>
        </box>
      </centerbox>
    </window>
  )
}
