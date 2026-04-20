package main

/*
#cgo pkg-config: gtk4 gtk4-layer-shell-0
#include <gtk/gtk.h>
#include <gtk4-layer-shell.h>
#include <stdlib.h>

// Layer shell helpers (called from Go)
static void ls_init(GtkWindow *win) { gtk_layer_init_for_window(win); }
static void ls_set_layer(GtkWindow *win) { gtk_layer_set_layer(win, GTK_LAYER_SHELL_LAYER_OVERLAY); }
static void ls_anchor_bottom_right(GtkWindow *win, int bottom_margin, int right_margin) {
    gtk_layer_set_anchor(win, GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
    gtk_layer_set_anchor(win, GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);
    gtk_layer_set_margin(win, GTK_LAYER_SHELL_EDGE_BOTTOM, bottom_margin);
    gtk_layer_set_margin(win, GTK_LAYER_SHELL_EDGE_RIGHT, right_margin);
}
static void ls_set_namespace(GtkWindow *win, const char *ns) { gtk_layer_set_namespace(win, ns); }
static void ls_set_keyboard(GtkWindow *win) { gtk_layer_set_keyboard_mode(win, GTK_LAYER_SHELL_KEYBOARD_MODE_ON_DEMAND); }
*/
import "C"

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"unsafe"

	coreglib "github.com/diamondburned/gotk4/pkg/core/glib"
	"github.com/diamondburned/gotk4/pkg/gdk/v4"
	"github.com/diamondburned/gotk4/pkg/gio/v2"
	"github.com/diamondburned/gotk4/pkg/glib/v2"
	"github.com/diamondburned/gotk4/pkg/gtk/v4"
)

const (
	panelWidth  = 320
	barHeight   = 56 // panel bar height + margin
	rightMargin = 8
	css         = `
window { background: transparent; }

.qs-panel {
    background: rgba(30, 30, 30, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 16px;
}

.qs-section-title {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.8px;
    color: rgba(255, 255, 255, 0.4);
}

.qs-toggle-card {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    min-height: 52px;
    padding: 8px 12px;
}
.qs-toggle-card:hover { background: rgba(255, 255, 255, 0.10); }
.qs-toggle-active {
    background: rgba(0, 128, 255, 0.18);
    border-color: rgba(0, 128, 255, 0.35);
}
.qs-toggle-active:hover { background: rgba(0, 128, 255, 0.24); }

.qs-toggle-label {
    font-size: 12px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.92);
}
.qs-toggle-state {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
}

.qs-slider-row {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 4px 12px;
}
.qs-slider-icon {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
    min-width: 22px;
}
.qs-slider-value {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
    min-width: 32px;
}

scale trough {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-height: 4px;
}
scale trough highlight {
    background: rgba(0, 128, 255, 0.9);
    border-radius: 4px;
}
scale slider {
    background: white;
    border-radius: 50px;
    min-width: 14px;
    min-height: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4);
}

.qs-chip {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 50px;
    padding: 3px 10px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
}

.qs-pill {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 50px;
    padding: 6px 14px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.55);
}
.qs-pill:hover { background: rgba(255, 255, 255, 0.10); }
.qs-pill-active {
    background: rgba(0, 128, 255, 0.18);
    border-color: rgba(0, 128, 255, 0.35);
    color: rgba(0, 128, 255, 0.9);
}

.qs-divider {
    background: rgba(255, 255, 255, 0.07);
    min-height: 1px;
}

.qs-user-name {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
}
.qs-user-sub {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
}
.qs-avatar {
    min-width: 36px;
    min-height: 36px;
    border-radius: 50px;
    background: rgba(0, 128, 255, 0.18);
    font-size: 13px;
    font-weight: 700;
    color: rgba(0, 128, 255, 0.9);
}
`
)

// System helpers — shell out to standard CLI tools

func runCmd(name string, args ...string) string {
	out, _ := exec.Command(name, args...).Output()
	return strings.TrimSpace(string(out))
}

func getVolume() int {
	out := runCmd("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
	// "Volume: 0.65"
	parts := strings.Fields(out)
	if len(parts) < 2 {
		return 0
	}
	f, _ := strconv.ParseFloat(parts[1], 64)
	return int(math.Round(f * 100))
}

func isMuted() bool {
	out := runCmd("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
	return strings.Contains(out, "MUTED")
}

func setVolume(pct int) {
	exec.Command("wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", fmt.Sprintf("%d%%", pct)).Run()
}

func toggleMute() {
	exec.Command("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle").Run()
}

func findBacklight() string {
	entries, _ := os.ReadDir("/sys/class/backlight")
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), "amdgpu") {
			return e.Name()
		}
	}
	if len(entries) > 0 {
		return entries[0].Name()
	}
	return ""
}

func getBrightness() int {
	dev := findBacklight()
	if dev == "" {
		return 50
	}
	cur, _ := os.ReadFile(fmt.Sprintf("/sys/class/backlight/%s/brightness", dev))
	max, _ := os.ReadFile(fmt.Sprintf("/sys/class/backlight/%s/max_brightness", dev))
	c, _ := strconv.Atoi(strings.TrimSpace(string(cur)))
	m, _ := strconv.Atoi(strings.TrimSpace(string(max)))
	if m == 0 {
		return 50
	}
	return int(math.Round(float64(c) / float64(m) * 100))
}

func setBrightness(pct int) {
	dev := findBacklight()
	if dev == "" {
		return
	}
	path := fmt.Sprintf("/sys/class/backlight/%s/brightness", dev)
	maxData, _ := os.ReadFile(fmt.Sprintf("/sys/class/backlight/%s/max_brightness", dev))
	m, _ := strconv.Atoi(strings.TrimSpace(string(maxData)))
	if m == 0 {
		return
	}
	val := int(math.Round(float64(pct) / 100 * float64(m)))
	if val < 1 {
		val = 1
	}
	// Try direct write first
	err := os.WriteFile(path, []byte(strconv.Itoa(val)), 0644)
	if err != nil {
		// Fallback to tee with sudo (no password if NOPASSWD configured)
		cmd := exec.Command("sudo", "tee", path)
		cmd.Stdin = strings.NewReader(strconv.Itoa(val))
		cmd.Run()
	}
}

func getWifiInfo() (on bool, ssid string) {
	status := runCmd("nmcli", "-t", "-f", "WIFI", "g")
	on = status == "enabled"
	if on {
		lines := strings.Split(runCmd("nmcli", "-t", "-f", "active,ssid", "dev", "wifi"), "\n")
		for _, l := range lines {
			if strings.HasPrefix(l, "yes:") {
				ssid = strings.TrimPrefix(l, "yes:")
				return
			}
		}
	}
	return
}

func toggleWifi(currentlyOn bool) {
	if currentlyOn {
		exec.Command("nmcli", "radio", "wifi", "off").Run()
	} else {
		exec.Command("nmcli", "radio", "wifi", "on").Run()
	}
}

func getBtInfo() (powered bool, deviceName string) {
	out := runCmd("bluetoothctl", "show")
	powered = strings.Contains(out, "Powered: yes")
	if powered {
		// Check connected devices
		devOut := runCmd("bluetoothctl", "devices", "Connected")
		lines := strings.Split(devOut, "\n")
		for _, l := range lines {
			l = strings.TrimSpace(l)
			if strings.HasPrefix(l, "Device ") {
				parts := strings.SplitN(l, " ", 3)
				if len(parts) >= 3 {
					deviceName = parts[2]
					return
				}
			}
		}
	}
	return
}

func toggleBt(currentlyOn bool) {
	if currentlyOn {
		exec.Command("bluetoothctl", "power", "off").Run()
	} else {
		exec.Command("bluetoothctl", "power", "on").Run()
	}
}

func getBattery() string {
	data, err := os.ReadFile("/sys/class/power_supply/BAT0/capacity")
	if err != nil {
		data, err = os.ReadFile("/sys/class/power_supply/BAT1/capacity")
	}
	if err != nil {
		return "N/A"
	}
	pct := strings.TrimSpace(string(data))
	status, _ := os.ReadFile("/sys/class/power_supply/BAT0/status")
	if status == nil {
		status, _ = os.ReadFile("/sys/class/power_supply/BAT1/status")
	}
	s := strings.TrimSpace(string(status))
	if s == "Charging" || s == "Full" {
		return pct + "% Charging"
	}
	return pct + "%"
}

func getUsername() string {
	return os.Getenv("USER")
}

// Panel widget state
type panel struct {
	win          *gtk.Window
	volSlider    *gtk.Scale
	volLabel     *gtk.Label
	brightSlider *gtk.Scale
	brightLabel  *gtk.Label
	wifiCard     *gtk.Button
	wifiState    *gtk.Label
	btCard       *gtk.Button
	btState      *gtk.Label
	batteryChip  *gtk.Label
	dndPill      *gtk.Button
	nightPill    *gtk.Button

	wifiOn  bool
	btOn    bool
	dndOn   bool
	nightOn bool
}

func newPanel(app *gtk.Application) *panel {
	p := &panel{}

	appWin := gtk.NewApplicationWindow(app)
	p.win = &appWin.Window
	p.win.SetTitle("luminos-quick-settings")
	p.win.SetDecorated(false)
	p.win.SetResizable(false)
	p.win.SetDefaultSize(panelWidth, -1)

	// Layer shell setup via CGo
	cWin := (*C.GtkWindow)(unsafe.Pointer(coreglib.BaseObject(p.win).Native()))
	C.ls_init(cWin)
	C.ls_set_layer(cWin)
	C.ls_anchor_bottom_right(cWin, C.int(barHeight), C.int(rightMargin))
	ns := C.CString("luminos-quick-settings")
	C.ls_set_namespace(cWin, ns)
	C.free(unsafe.Pointer(ns))
	C.ls_set_keyboard(cWin)

	// CSS
	provider := gtk.NewCSSProvider()
	provider.LoadFromString(css)
	gtk.StyleContextAddProviderForDisplay(
		gdk.DisplayGetDefault(),
		provider,
		uint(gtk.STYLE_PROVIDER_PRIORITY_APPLICATION),
	)

	// Escape to close
	keyCtrl := gtk.NewEventControllerKey()
	keyCtrl.ConnectKeyPressed(func(keyval, keycode uint, state gdk.ModifierType) bool {
		if keyval == gdk.KEY_Escape {
			p.win.SetVisible(false)
			return true
		}
		return false
	})
	p.win.AddController(keyCtrl)

	// Close on focus loss
	coreglib.BaseObject(p.win).Connect("notify::is-active", func() {
		if !p.win.IsActive() {
			glib.IdleAdd(func() { p.win.SetVisible(false) })
		}
	})

	p.build()
	return p
}

func (p *panel) build() {
	scroll := gtk.NewScrolledWindow()
	scroll.SetPolicy(gtk.PolicyNever, gtk.PolicyAutomatic)
	scroll.SetMaxContentHeight(500)
	scroll.SetPropagateNaturalHeight(true)
	p.win.SetChild(scroll)

	root := gtk.NewBox(gtk.OrientationVertical, 8)
	root.AddCSSClass("qs-panel")
	scroll.SetChild(root)

	// User row
	p.buildUserRow(root)
	root.Append(makeDivider())

	// Connectivity
	addSectionTitle(root, "CONNECTIVITY")
	p.buildConnectivity(root)

	// Sliders
	addSectionTitle(root, "CONTROLS")
	p.buildSliders(root)

	root.Append(makeDivider())

	// Status
	addSectionTitle(root, "STATUS")
	p.buildStatus(root)

	root.Append(makeDivider())

	// Toggles
	p.buildToggles(root)
}

func (p *panel) buildUserRow(root *gtk.Box) {
	row := gtk.NewBox(gtk.OrientationHorizontal, 10)
	row.SetVAlign(gtk.AlignCenter)

	name := getUsername()
	initial := "U"
	if len(name) > 0 {
		initial = strings.ToUpper(name[:1])
	}
	avatar := gtk.NewLabel(initial)
	avatar.AddCSSClass("qs-avatar")
	avatar.SetHAlign(gtk.AlignCenter)
	avatar.SetVAlign(gtk.AlignCenter)
	row.Append(avatar)

	textBox := gtk.NewBox(gtk.OrientationVertical, 2)
	nameLabel := gtk.NewLabel(name)
	nameLabel.AddCSSClass("qs-user-name")
	nameLabel.SetHAlign(gtk.AlignStart)
	textBox.Append(nameLabel)

	sub := gtk.NewLabel("Luminos OS")
	sub.AddCSSClass("qs-user-sub")
	sub.SetHAlign(gtk.AlignStart)
	textBox.Append(sub)

	row.Append(textBox)
	root.Append(row)
}

func (p *panel) buildConnectivity(root *gtk.Box) {
	grid := gtk.NewGrid()
	grid.SetRowSpacing(6)
	grid.SetColumnSpacing(6)
	grid.SetHExpand(true)
	grid.SetMarginTop(4)

	p.wifiOn, _ = getWifiInfo()
	p.wifiCard, p.wifiState = makeToggleCard("Wi-Fi", "Off", p.wifiOn)
	p.wifiCard.ConnectClicked(func() {
		toggleWifi(p.wifiOn)
		p.wifiOn = !p.wifiOn
		updateToggleCard(p.wifiCard, p.wifiState, p.wifiOn)
	})

	p.btOn = getBtPowered()
	p.btCard, p.btState = makeToggleCard("Bluetooth", "Off", p.btOn)
	p.btCard.ConnectClicked(func() {
		toggleBt(p.btOn)
		p.btOn = !p.btOn
		updateToggleCard(p.btCard, p.btState, p.btOn)
	})

	grid.Attach(p.wifiCard, 0, 0, 1, 1)
	grid.Attach(p.btCard, 1, 0, 1, 1)
	root.Append(grid)
}

func (p *panel) buildSliders(root *gtk.Box) {
	// Brightness
	var brightRow *gtk.Box
	brightRow, p.brightSlider, p.brightLabel = makeSliderRow("☀", 5, 100)
	p.brightSlider.ConnectValueChanged(func() {
		pct := int(p.brightSlider.Value())
		p.brightLabel.SetText(fmt.Sprintf("%d%%", pct))
		setBrightness(pct)
	})
	root.Append(brightRow)

	// Volume
	var volRow *gtk.Box
	volRow, p.volSlider, p.volLabel = makeSliderRow("♪", 0, 100)
	p.volSlider.ConnectValueChanged(func() {
		pct := int(p.volSlider.Value())
		p.volLabel.SetText(fmt.Sprintf("%d%%", pct))
		setVolume(pct)
	})
	root.Append(volRow)

	// Mute button below volume
	muteBtn := gtk.NewButtonWithLabel("Mute Toggle")
	muteBtn.AddCSSClass("qs-pill")
	muteBtn.ConnectClicked(func() { toggleMute() })
	root.Append(muteBtn)
}

func (p *panel) buildStatus(root *gtk.Box) {
	row := gtk.NewBox(gtk.OrientationHorizontal, 6)
	row.SetHExpand(true)

	p.batteryChip = gtk.NewLabel("Battery: --")
	p.batteryChip.AddCSSClass("qs-chip")
	row.Append(p.batteryChip)

	root.Append(row)
}

func (p *panel) buildToggles(root *gtk.Box) {
	row := gtk.NewBox(gtk.OrientationHorizontal, 6)
	row.SetMarginTop(4)

	p.dndPill = gtk.NewButtonWithLabel("Do Not Disturb")
	p.dndPill.AddCSSClass("qs-pill")
	p.dndPill.ConnectClicked(func() {
		p.dndOn = !p.dndOn
		if p.dndOn {
			p.dndPill.AddCSSClass("qs-pill-active")
		} else {
			p.dndPill.RemoveCSSClass("qs-pill-active")
		}
	})
	row.Append(p.dndPill)

	p.nightPill = gtk.NewButtonWithLabel("Night Light")
	p.nightPill.AddCSSClass("qs-pill")
	p.nightPill.ConnectClicked(func() {
		p.nightOn = !p.nightOn
		if p.nightOn {
			p.nightPill.AddCSSClass("qs-pill-active")
			exec.Command("hyprctl", "keyword", "decoration:screen_shader",
				"/usr/share/luminos/shaders/nightlight.glsl").Run()
		} else {
			p.nightPill.RemoveCSSClass("qs-pill-active")
			exec.Command("hyprctl", "keyword", "decoration:screen_shader", "").Run()
		}
	})
	row.Append(p.nightPill)

	root.Append(row)
}

func (p *panel) refresh() {
	// Volume
	vol := getVolume()
	p.volSlider.SetValue(float64(vol))
	p.volLabel.SetText(fmt.Sprintf("%d%%", vol))

	// Brightness
	bright := getBrightness()
	p.brightSlider.SetValue(float64(bright))
	p.brightLabel.SetText(fmt.Sprintf("%d%%", bright))

	// WiFi
	var ssid string
	p.wifiOn, ssid = getWifiInfo()
	if p.wifiOn && ssid != "" {
		p.wifiState.SetText(ssid)
	} else if p.wifiOn {
		p.wifiState.SetText("On")
	} else {
		p.wifiState.SetText("Off")
	}
	updateToggleCard(p.wifiCard, p.wifiState, p.wifiOn)

	// Bluetooth
	p.btOn = getBtPowered()
	if p.btOn {
		p.btState.SetText("On")
	} else {
		p.btState.SetText("Off")
	}
	updateToggleCard(p.btCard, p.btState, p.btOn)

	// Battery
	p.batteryChip.SetText("Battery: " + getBattery())
}

func (p *panel) toggle() {
	if p.win.IsVisible() {
		p.win.SetVisible(false)
	} else {
		p.refresh()
		p.win.SetVisible(true)
		p.win.Present()
	}
}

// Widget helpers

func addSectionTitle(root *gtk.Box, text string) {
	lbl := gtk.NewLabel(text)
	lbl.AddCSSClass("qs-section-title")
	lbl.SetHAlign(gtk.AlignStart)
	root.Append(lbl)
}

func makeDivider() *gtk.Box {
	d := gtk.NewBox(gtk.OrientationHorizontal, 0)
	d.AddCSSClass("qs-divider")
	d.SetMarginTop(6)
	d.SetMarginBottom(6)
	return d
}

func makeToggleCard(label, state string, active bool) (*gtk.Button, *gtk.Label) {
	btn := gtk.NewButton()
	btn.SetHExpand(true)

	box := gtk.NewBox(gtk.OrientationVertical, 2)
	box.SetHAlign(gtk.AlignStart)

	lbl := gtk.NewLabel(label)
	lbl.AddCSSClass("qs-toggle-label")
	lbl.SetHAlign(gtk.AlignStart)
	box.Append(lbl)

	stateLbl := gtk.NewLabel(state)
	stateLbl.AddCSSClass("qs-toggle-state")
	stateLbl.SetHAlign(gtk.AlignStart)
	box.Append(stateLbl)

	btn.SetChild(box)
	btn.AddCSSClass("qs-toggle-card")
	if active {
		btn.AddCSSClass("qs-toggle-active")
	}
	return btn, stateLbl
}

func updateToggleCard(btn *gtk.Button, stateLbl *gtk.Label, active bool) {
	if active {
		btn.AddCSSClass("qs-toggle-active")
	} else {
		btn.RemoveCSSClass("qs-toggle-active")
	}
	if active {
		stateLbl.SetText("On")
	} else {
		stateLbl.SetText("Off")
	}
}

func makeSliderRow(icon string, lo, hi float64) (*gtk.Box, *gtk.Scale, *gtk.Label) {
	row := gtk.NewBox(gtk.OrientationHorizontal, 6)
	row.AddCSSClass("qs-slider-row")
	row.SetHExpand(true)

	iconLbl := gtk.NewLabel(icon)
	iconLbl.AddCSSClass("qs-slider-icon")
	row.Append(iconLbl)

	slider := gtk.NewScaleWithRange(gtk.OrientationHorizontal, lo, hi, 1)
	slider.SetHExpand(true)
	slider.SetDrawValue(false)
	row.Append(slider)

	valLbl := gtk.NewLabel("--")
	valLbl.AddCSSClass("qs-slider-value")
	row.Append(valLbl)

	return row, slider, valLbl
}

// PID file for toggle via signal
const pidFile = "/tmp/luminos-quick-settings.pid"

func main() {
	// Write PID
	os.WriteFile(pidFile, []byte(fmt.Sprintf("%d", os.Getpid())), 0644)
	defer os.Remove(pidFile)

	app := gtk.NewApplication("com.luminos.quicksettings", gio.ApplicationFlagsNone)

	var p *panel

	// USR1 toggles panel
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGUSR1)

	app.ConnectActivate(func() {
		p = newPanel(app)
		p.refresh()
		p.win.Present()

		// Signal handler in glib main loop
		go func() {
			for range sigCh {
				glib.IdleAdd(func() {
					p.toggle()
				})
			}
		}()
	})

	os.Exit(app.Run(os.Args))
}
