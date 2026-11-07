package main

// [CHANGE: claude-code | 2026-11-07] LoadAllow/Allowed tests (CONTRACTS §4 allow.go, §6 default list).

import (
	"os"
	"path/filepath"
	"slices"
	"testing"
	"testing/quick"
)

var tfDefaultGlobs = []string{"app-*konsole*", "app-*kitty*", "app-*Alacritty*", "app-*alacritty*", "app-*foot*",
	"app-*wezterm*", "app-*ghostty*", "app-*qbittorrent*", "app-*transmission*", "app-*steam*", "app-*lutris*",
	"app-*wine*", "app-*gamescope*", "app-*heroic*", "app-*luminos*", "app-com.anthropic.Claude-*.scope"}

func TestLoadAllowMissingFileGivesDefaults(t *testing.T) {
	got := LoadAllow(filepath.Join(t.TempDir(), "nope.conf"))
	for _, g := range tfDefaultGlobs {
		if !slices.Contains(got, g) {
			t.Errorf("defaults %v lack %q", got, g)
		}
	}
}

func TestLoadAllowFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "focus-allow.conf")
	body := "# luminos-focus allow-list\n\napp-foo*\n# app-commented-out*\n\napp-*bar*.scope\n"
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	got := LoadAllow(path)
	slices.Sort(got)
	if want := []string{"app-*bar*.scope", "app-foo*"}; !slices.Equal(got, want) {
		t.Errorf("LoadAllow = %q, want %q (file replaces defaults; blank and # lines skipped)", got, want)
	}
}

func TestAllowed(t *testing.T) {
	cases := []struct {
		unit  string
		globs []string
		want  bool
	}{
		{"app-com.anthropic.Claude-1234.scope", tfDefaultGlobs, true},    // holds the Cowork VM
		{"app-com.anthropic.Claude@a1b2.service", tfDefaultGlobs, false}, // renderers: throttled when hidden
		{"app-com.google.Chrome-100.scope", tfDefaultGlobs, false},
		{"app-org.kde.konsole-555.scope", tfDefaultGlobs, true},
		{"app-steam@autostart.service", tfDefaultGlobs, true},
		{`app-google\x2dchrome@abc.service`, []string{"app-*chrome*"}, true},
		{`app-google\x2dchrome@abc.service`, []string{"app-google?x2dchrome@*.service"}, true},
		{`app-google\x2dchrome@abc.service`, []string{"app-*firefox*"}, false},
		{"app-foo.scope", nil, false},
		{"app-foo.scope", []string{"["}, false}, // bad pattern: no match, no panic
	}
	for _, c := range cases {
		if got := Allowed(c.unit, c.globs); got != c.want {
			t.Errorf("Allowed(%q, %q) = %v, want %v", c.unit, c.globs, got, c.want)
		}
	}
}

func TestAllowedProperty(t *testing.T) {
	const alphabet = "abcxyz019.-@_"
	prop := func(raw []byte) bool {
		unit := []byte("app-")
		for _, b := range raw {
			unit = append(unit, alphabet[int(b)%len(alphabet)])
		}
		u := string(unit)
		return Allowed(u, []string{u}) && Allowed(u, []string{"app-*"}) && !Allowed(u, nil) &&
			!Allowed(u, []string{u + "x"})
	}
	if err := quick.Check(prop, &quick.Config{MaxCount: 2000}); err != nil {
		t.Error(err)
	}
}
