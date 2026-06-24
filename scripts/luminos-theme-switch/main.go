// luminos-theme-switch — single source of truth for system light/dark mode.
// [CHANGE: claude-code | 2026-06-24]
//
// Propagates ONE mode (light|dark) across every toolkit at once:
//   - KDE Plasma  : plasma-apply-colorscheme  (Qt apps + xdg-desktop-portal-kde)
//   - gsettings   : color-scheme + gtk-theme  (GTK4/libadwaita + portal-gtk)
//   - GTK 3/4     : settings.ini theme name + prefer-dark flag
// Electron/Chromium/Flatpak apps follow automatically via the portal's
// org.freedesktop.appearance color-scheme, which KDE derives from the
// active Plasma scheme — so this one command de-fragments the whole desktop.
//
// Theme-agnostic: the light/dark *pair* lives in ~/.config/luminos/theme.conf.
// Swap in any scheme/GTK theme you like; the switcher just flips between them.
//
// Subcommands:
//   apply <light|dark>   apply a mode now and exit
//   auto                 pick mode from sun position now, apply, print next switch
//   daemon               long-running: flip at each sunrise/sunset (systemd --user)
//   status               print current mode, today's sun times, next switch
package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type config struct {
	LightScheme string
	DarkScheme  string
	LightGTK    string
	DarkGTK     string
	Latitude    float64
	Longitude   float64
	Mode        string // auto | light | dark
}

func defaultConfig() config {
	return config{
		LightScheme: "BreezeLight",
		DarkScheme:  "BreezeDark",
		LightGTK:    "Breeze",
		DarkGTK:     "Breeze-Dark",
		Latitude:    43.6532,  // Toronto (from system timezone) — edit to taste
		Longitude:   -79.3832,
		Mode:        "auto",
	}
}

func configPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "luminos", "theme.conf")
}

// loadConfig reads theme.conf, writing defaults on first run.
func loadConfig() config {
	cfg := defaultConfig()
	path := configPath()
	f, err := os.Open(path)
	if err != nil {
		writeDefaultConfig(path, cfg)
		return cfg
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		k = strings.TrimSpace(k)
		v = strings.TrimSpace(v)
		switch k {
		case "light_scheme":
			cfg.LightScheme = v
		case "dark_scheme":
			cfg.DarkScheme = v
		case "light_gtk":
			cfg.LightGTK = v
		case "dark_gtk":
			cfg.DarkGTK = v
		case "latitude":
			if n, e := strconv.ParseFloat(v, 64); e == nil {
				cfg.Latitude = n
			}
		case "longitude":
			if n, e := strconv.ParseFloat(v, 64); e == nil {
				cfg.Longitude = n
			}
		case "mode":
			cfg.Mode = v
		}
	}
	return cfg
}

func writeDefaultConfig(path string, cfg config) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return
	}
	content := fmt.Sprintf(`# Luminos theme — single source of truth for system light/dark mode.
# Edit the light/dark pair to match whatever themes you place; the
# day/night switcher just flips between them.

# Plasma color schemes (see: ls /usr/share/color-schemes/)
light_scheme=%s
dark_scheme=%s

# GTK theme names (see: ls /usr/share/themes/)
light_gtk=%s
dark_gtk=%s

# Location for sunrise/sunset (decimal degrees; east + / north +)
latitude=%.4f
longitude=%.4f

# auto = follow day/night | light = force light | dark = force dark
mode=%s
`, cfg.LightScheme, cfg.DarkScheme, cfg.LightGTK, cfg.DarkGTK,
		cfg.Latitude, cfg.Longitude, cfg.Mode)
	_ = os.WriteFile(path, []byte(content), 0o644)
}

// ── Propagation ────────────────────────────────────────────────────────────

// apply pushes a mode ("light"/"dark") to every toolkit.
func apply(cfg config, mode string) {
	scheme, gtk, preferDark := cfg.LightScheme, cfg.LightGTK, false
	if mode == "dark" {
		scheme, gtk, preferDark = cfg.DarkScheme, cfg.DarkGTK, true
	}

	// 1. KDE Plasma color scheme — also drives xdg-desktop-portal-kde, so
	//    Qt + Electron + Chromium apps pick up dark/light from here.
	run("plasma-apply-colorscheme", scheme)

	// 2. gsettings — drives GTK4/libadwaita and xdg-desktop-portal-gtk.
	cs := "prefer-light"
	if preferDark {
		cs = "prefer-dark"
	}
	run("gsettings", "set", "org.gnome.desktop.interface", "color-scheme", cs)
	run("gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk)

	// 3. GTK 3/4 settings.ini — for apps that read the file directly.
	home, _ := os.UserHomeDir()
	for _, p := range []string{
		filepath.Join(home, ".config", "gtk-3.0", "settings.ini"),
		filepath.Join(home, ".config", "gtk-4.0", "settings.ini"),
	} {
		updateGTKIni(p, gtk, preferDark)
	}

	fmt.Printf("luminos-theme: applied %s (scheme=%s gtk=%s)\n", mode, scheme, gtk)
}

// updateGTKIni rewrites the two theme keys under [Settings], preserving the rest.
func updateGTKIni(path, gtk string, preferDark bool) {
	data, err := os.ReadFile(path)
	if err != nil {
		return // file absent — skip silently
	}
	preferVal := "false"
	if preferDark {
		preferVal = "true"
	}
	wantTheme := "gtk-theme-name=" + gtk
	wantDark := "gtk-application-prefer-dark-theme=" + preferVal

	var out []string
	var setTheme, setDark bool
	for _, line := range strings.Split(string(data), "\n") {
		t := strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(t, "gtk-theme-name="):
			out = append(out, wantTheme)
			setTheme = true
		case strings.HasPrefix(t, "gtk-application-prefer-dark-theme="):
			out = append(out, wantDark)
			setDark = true
		default:
			out = append(out, line)
		}
	}
	// Insert any missing keys right after [Settings].
	if !setTheme || !setDark {
		var merged []string
		for _, line := range out {
			merged = append(merged, line)
			if strings.TrimSpace(line) == "[Settings]" {
				if !setTheme {
					merged = append(merged, wantTheme)
				}
				if !setDark {
					merged = append(merged, wantDark)
				}
			}
		}
		out = merged
	}
	_ = os.WriteFile(path, []byte(strings.Join(out, "\n")), 0o644)
}

func run(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "luminos-theme: %s failed: %v\n", name, err)
	}
}

// ── Sun calculation (NOAA / Almanac, zenith 90.833°, no deps) ───────────────

const zenith = 90.833

func deg2rad(d float64) float64 { return d * math.Pi / 180 }
func rad2deg(r float64) float64 { return r * 180 / math.Pi }

// sunEvent returns the local sunrise (rise=true) or sunset time for date.
// ok=false in polar edge cases (sun never rises/sets that day).
func sunEvent(date time.Time, lat, lng float64, rise bool) (t time.Time, ok bool) {
	N := float64(date.YearDay())
	lngHour := lng / 15

	var th float64
	if rise {
		th = 6
	} else {
		th = 18
	}
	tApprox := N + (th-lngHour)/24

	M := 0.9856*tApprox - 3.289
	L := M + 1.916*math.Sin(deg2rad(M)) + 0.020*math.Sin(deg2rad(2*M)) + 282.634
	L = norm360(L)

	RA := rad2deg(math.Atan(0.91764 * math.Tan(deg2rad(L))))
	RA = norm360(RA)
	// Put RA in the same quadrant as L.
	Lquad := math.Floor(L/90) * 90
	RAquad := math.Floor(RA/90) * 90
	RA = (RA + (Lquad - RAquad)) / 15

	sinDec := 0.39782 * math.Sin(deg2rad(L))
	cosDec := math.Cos(math.Asin(sinDec))

	cosH := (math.Cos(deg2rad(zenith)) - sinDec*math.Sin(deg2rad(lat))) /
		(cosDec * math.Cos(deg2rad(lat)))
	if cosH > 1 || cosH < -1 {
		return time.Time{}, false // sun never rises / never sets
	}

	var H float64
	if rise {
		H = 360 - rad2deg(math.Acos(cosH))
	} else {
		H = rad2deg(math.Acos(cosH))
	}
	H /= 15

	T := H + RA - 0.06571*tApprox - 6.622
	UT := norm24(T - lngHour)

	// UT is hours UTC on this calendar date.
	h := int(UT)
	m := int((UT - float64(h)) * 60)
	utc := time.Date(date.Year(), date.Month(), date.Day(), h, m, 0, 0, time.UTC)
	return utc.Local(), true
}

func norm360(x float64) float64 {
	for x < 0 {
		x += 360
	}
	for x >= 360 {
		x -= 360
	}
	return x
}
func norm24(x float64) float64 {
	for x < 0 {
		x += 24
	}
	for x >= 24 {
		x -= 24
	}
	return x
}

// modeForNow returns "light"/"dark" and the next switch time.
func modeForNow(cfg config, now time.Time) (string, time.Time) {
	rise, okR := sunEvent(now, cfg.Latitude, cfg.Longitude, true)
	set, okS := sunEvent(now, cfg.Latitude, cfg.Longitude, false)
	if !okR || !okS {
		// Polar fallback: 07:00 light / 19:00 dark.
		rise = time.Date(now.Year(), now.Month(), now.Day(), 7, 0, 0, 0, time.Local)
		set = time.Date(now.Year(), now.Month(), now.Day(), 19, 0, 0, 0, time.Local)
	}
	switch {
	case now.Before(rise):
		return "dark", rise
	case now.Before(set):
		return "light", set
	default:
		// After sunset → dark until tomorrow's sunrise.
		tomorrow := now.AddDate(0, 0, 1)
		nr, ok := sunEvent(tomorrow, cfg.Latitude, cfg.Longitude, true)
		if !ok {
			nr = time.Date(tomorrow.Year(), tomorrow.Month(), tomorrow.Day(), 7, 0, 0, 0, time.Local)
		}
		return "dark", nr
	}
}

// ── Commands ────────────────────────────────────────────────────────────────

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	cfg := loadConfig()

	switch os.Args[1] {
	case "apply":
		if len(os.Args) < 3 || (os.Args[2] != "light" && os.Args[2] != "dark") {
			fmt.Fprintln(os.Stderr, "usage: luminos-theme-switch apply <light|dark>")
			os.Exit(2)
		}
		apply(cfg, os.Args[2])

	case "auto":
		mode, next := modeForNow(cfg, time.Now())
		apply(cfg, mode)
		fmt.Printf("luminos-theme: next switch at %s\n", next.Format("Mon 15:04"))

	case "status":
		printStatus(cfg)

	case "daemon":
		daemon(cfg)

	default:
		usage()
		os.Exit(2)
	}
}

func printStatus(cfg config) {
	now := time.Now()
	rise, okR := sunEvent(now, cfg.Latitude, cfg.Longitude, true)
	set, _ := sunEvent(now, cfg.Latitude, cfg.Longitude, false)
	mode, next := modeForNow(cfg, now)
	fmt.Printf("Location : %.4f, %.4f\n", cfg.Latitude, cfg.Longitude)
	if okR {
		fmt.Printf("Sunrise  : %s\n", rise.Format("15:04"))
		fmt.Printf("Sunset   : %s\n", set.Format("15:04"))
	} else {
		fmt.Println("Sun      : polar day/night (fallback 07:00/19:00)")
	}
	fmt.Printf("Mode now : %s (config mode=%s)\n", mode, cfg.Mode)
	fmt.Printf("Next     : %s -> %s\n", next.Format("Mon 15:04"), oppositeOf(mode))
}

func oppositeOf(m string) string {
	if m == "dark" {
		return "light"
	}
	return "dark"
}

// daemon applies the right mode now, then sleeps until each sun event.
func daemon(cfg config) {
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)

	// Forced mode short-circuits day/night.
	if cfg.Mode == "light" || cfg.Mode == "dark" {
		apply(cfg, cfg.Mode)
		fmt.Printf("luminos-theme: forced %s mode; idling\n", cfg.Mode)
		<-sigCh
		return
	}

	for {
		cfg = loadConfig() // re-read so config edits take effect each cycle
		mode, next := modeForNow(cfg, time.Now())
		apply(cfg, mode)
		wait := time.Until(next) + 30*time.Second // small buffer past the event
		if wait < time.Minute {
			wait = time.Minute
		}
		fmt.Printf("luminos-theme: %s now; next switch %s\n", mode, next.Format("Mon 15:04"))
		select {
		case <-time.After(wait):
		case <-sigCh:
			fmt.Println("luminos-theme: stopping")
			return
		}
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `luminos-theme-switch — system-wide light/dark, one source of truth

  apply <light|dark>   apply a mode now
  auto                 pick from sun position, apply, show next switch
  daemon               flip at each sunrise/sunset (systemd --user)
  status               show sun times and current/next mode

Config: ~/.config/luminos/theme.conf`)
}
