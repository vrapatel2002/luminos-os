// Allow-list: units matching a glob keep full rights while hidden.
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"os"
	"path"
	"strings"
)

var defaultAllow = []string{ // mirrors config/luminos/focus-allow.conf (CONTRACTS §6)
	"app-*konsole*", "app-*kitty*", "app-*Alacritty*", "app-*alacritty*", "app-*foot*", "app-*wezterm*",
	"app-*ghostty*", "app-*qbittorrent*", "app-*transmission*", "app-*steam*", "app-*lutris*", "app-*wine*",
	"app-*gamescope*", "app-*heroic*", "app-*luminos*", "app-com.anthropic.Claude-*.scope",
}

func LoadAllow(file string) []string { // one glob per line, blank/# lines skipped; no file → defaults
	b, err := os.ReadFile(file)
	if err != nil {
		return defaultAllow
	}
	var globs []string
	for _, line := range strings.Split(string(b), "\n") {
		if line = strings.TrimSpace(line); line != "" && !strings.HasPrefix(line, "#") {
			globs = append(globs, line)
		}
	}
	return globs
}

func Allowed(unit string, globs []string) bool { // bad globs never match
	for _, g := range globs {
		if ok, _ := path.Match(g, unit); ok {
			return true
		}
	}
	return false
}
