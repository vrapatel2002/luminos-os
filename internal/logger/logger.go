// Package logger provides structured timestamped logging for all Luminos OS daemons.
// Each daemon opens its own log file under /var/log/luminos/ and simultaneously
// writes to stdout so journald can capture it when running under systemd.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — shared logger package.
package logger

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"
)

// Level is a log severity. Only messages at or above the configured minimum are emitted.
type Level int

const (
	DEBUG Level = iota
	INFO
	WARN
	ERROR
)

func levelStr(l Level) string {
	switch l {
	case DEBUG:
		return "DEBUG"
	case INFO:
		return "INFO "
	case WARN:
		return "WARN "
	case ERROR:
		return "ERROR"
	default:
		return "?????"
	}
}

// Logger writes structured log lines to a file and stdout simultaneously.
type Logger struct {
	name  string
	min   Level
	inner *log.Logger
}

// New creates a Logger that tees output to logPath and stdout.
// The log directory is created if it does not exist.
func New(name, logPath string, min Level) (*Logger, error) {
	if err := os.MkdirAll(filepath.Dir(logPath), 0755); err != nil {
		return nil, fmt.Errorf("create log dir %s: %w", filepath.Dir(logPath), err)
	}
	f, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return nil, fmt.Errorf("open log file %s: %w", logPath, err)
	}
	return &Logger{
		name:  name,
		min:   min,
		inner: log.New(io.MultiWriter(os.Stdout, f), "", 0),
	}, nil
}

// NewStdout creates a Logger writing only to stdout.
// Used as a fallback when /var/log/luminos does not exist yet.
func NewStdout(name string, min Level) *Logger {
	return &Logger{
		name:  name,
		min:   min,
		inner: log.New(os.Stdout, "", 0),
	}
}

func (l *Logger) emit(level Level, format string, args ...interface{}) {
	if level < l.min {
		return
	}
	msg := fmt.Sprintf(format, args...)
	ts := time.Now().Format("2006-01-02T15:04:05")
	l.inner.Printf("%s [%s] %s: %s", ts, levelStr(level), l.name, msg)
}

// Debug logs verbose diagnostic output. Suppressed unless level is DEBUG.
func (l *Logger) Debug(format string, args ...interface{}) { l.emit(DEBUG, format, args...) }

// Info logs normal operational events (startup, state changes, classifications).
func (l *Logger) Info(format string, args ...interface{}) { l.emit(INFO, format, args...) }

// Warn logs unexpected but non-fatal conditions (temp spikes, missing optional services).
func (l *Logger) Warn(format string, args ...interface{}) { l.emit(WARN, format, args...) }

// Error logs failures that impair daemon operation.
func (l *Logger) Error(format string, args ...interface{}) { l.emit(ERROR, format, args...) }
