// Package config loads daemon configuration from /etc/luminos/config.toml.
// If the file is absent, built-in defaults are returned so daemons can start
// without a full installation — useful for development on the G14.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — shared config package.
package config

import (
	"fmt"
	"os"

	"github.com/BurntSushi/toml"
)

// Config holds settings for all Luminos daemons.
// Fields map directly to TOML sections in /etc/luminos/config.toml.
type Config struct {
	Sockets  SocketConfig   `toml:"sockets"`
	Power    PowerConfig    `toml:"power"`
	Sentinel SentinelConfig `toml:"sentinel"`
	Router   RouterConfig   `toml:"router"`
	Log      LogConfig      `toml:"log"`
}

// SocketConfig contains the Unix socket paths used by each daemon.
// These match the paths defined in DAEMON_ARCHITECTURE.md §Socket Paths.
type SocketConfig struct {
	AI       string `toml:"ai"`
	Power    string `toml:"power"`
	Sentinel string `toml:"sentinel"`
	Router   string `toml:"router"`
}

// PowerConfig controls luminos-power's polling frequency.
type PowerConfig struct {
	PollIntervalSecs int `toml:"poll_interval_secs"`
}

// SentinelConfig controls luminos-sentinel's /proc polling frequency.
type SentinelConfig struct {
	PollIntervalMs int `toml:"poll_interval_ms"`
}

// RouterConfig controls the .exe classification cache location.
type RouterConfig struct {
	CacheDir string `toml:"cache_dir"`
}

// LogConfig controls log output location and verbosity.
type LogConfig struct {
	Dir   string `toml:"dir"`
	Level string `toml:"level"`
}

const configPath = "/etc/luminos/config.toml"

// Load reads /etc/luminos/config.toml.
// If the file does not exist, built-in defaults are returned without error.
func Load() (*Config, error) {
	cfg := defaults()
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		// Config file absent — use defaults. Expected during development / first boot.
		return cfg, nil
	}
	if _, err := toml.DecodeFile(configPath, cfg); err != nil {
		return nil, fmt.Errorf("parse %s: %w", configPath, err)
	}
	return cfg, nil
}

// defaults returns a Config with paths matching DAEMON_ARCHITECTURE.md and
// poll intervals tuned for the ROG G14 (2s AC check, 500ms process scan).
func defaults() *Config {
	home, _ := os.UserHomeDir()
	return &Config{
		Sockets: SocketConfig{
			AI:       "/run/luminos/ai.sock",
			Power:    "/run/luminos/power.sock",
			Sentinel: "/run/luminos/sentinel.sock",
			// Router runs per-user, so its socket lives in XDG_RUNTIME_DIR.
			// The actual path is resolved at runtime in luminos-router.
			Router: home + "/.cache/luminos/router.sock",
		},
		Power: PowerConfig{
			PollIntervalSecs: 2,
		},
		Sentinel: SentinelConfig{
			PollIntervalMs: 500,
		},
		Router: RouterConfig{
			CacheDir: home + "/.cache/luminos/router",
		},
		Log: LogConfig{
			Dir:   "/var/log/luminos",
			Level: "INFO",
		},
	}
}
