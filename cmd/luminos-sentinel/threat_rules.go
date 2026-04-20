// threat_rules.go implements rule-based threat detection for luminos-sentinel Phase 1.
// Phase 3 will supplement these rules with NPU ML classification via the npu service.
// Keeping rules in a separate file means they can be updated without touching main.go.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — sentinel threat rules.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Process holds the information about a running process needed for rule evaluation.
// All fields are read from /proc/[pid]/ at the moment a new PID is first seen.
type Process struct {
	PID     int
	ExePath string   // Resolved path of the process executable (/proc/[pid]/exe symlink).
	CmdLine string   // Command line with null bytes replaced by spaces.
	Maps    string   // Content of /proc/[pid]/maps — reveals mapped credential files.
	FDPaths []string // Resolved paths of all open file descriptors (/proc/[pid]/fd/*).
}

// Violation describes a triggered threat rule. One Violation per triggered rule.
type Violation struct {
	RuleName    string
	Description string
}

// protectedPatterns are path substrings that Wine/Proton processes must never access.
// Substrings (not exact paths) cover any user's home directory, e.g. /.ssh/ matches
// /home/alice/.ssh/id_rsa and /root/.ssh/authorized_keys.
// Rule basis: LUMINOS_PROJECT_SCOPE.md §Feature 5 — Sentinel Security.
var protectedPatterns = []string{
	"/.ssh/",
	"/.gnupg/",
	"/etc/passwd",
	"/etc/shadow",
}

// wineSignatures are substrings found in exe paths or command lines for Wine/Proton processes.
// Proton wraps Wine so both share the same signature patterns.
var wineSignatures = []string{
	"wine",
	"proton",
	"steam/ubuntu12_32", // Proton's bundled 32-bit Wine
	"steam/ubuntu12_64", // Proton's bundled 64-bit Wine
	"wine64",
	"wine32",
}

// ReadProcess reads /proc/[pid]/ fields needed to evaluate threat rules.
// Returns an error if the process has already exited — this is common for short-lived
// processes and should not be treated as an alarm.
func ReadProcess(pid int) (*Process, error) {
	procDir := fmt.Sprintf("/proc/%d", pid)

	// exe is a symlink to the real binary path on disk.
	exePath, err := os.Readlink(procDir + "/exe")
	if err != nil {
		return nil, fmt.Errorf("readlink exe: %w", err)
	}

	// cmdline is null-byte separated; replace nulls for readable logging.
	cmdBytes, err := os.ReadFile(procDir + "/cmdline")
	if err != nil {
		return nil, fmt.Errorf("read cmdline: %w", err)
	}

	// maps reveals every file the process has mapped into memory,
	// including shared libraries, data files, and credential files.
	mapsBytes, err := os.ReadFile(procDir + "/maps")
	if err != nil {
		return nil, fmt.Errorf("read maps: %w", err)
	}

	return &Process{
		PID:     pid,
		ExePath: exePath,
		CmdLine: strings.ReplaceAll(string(cmdBytes), "\x00", " "),
		Maps:    string(mapsBytes),
		FDPaths: readFDPaths(pid),
	}, nil
}

// readFDPaths resolves all symlinks in /proc/[pid]/fd/ to find currently-open files.
// Errors on individual file descriptors are silently ignored — the fd may close at any time.
func readFDPaths(pid int) []string {
	fdDir := fmt.Sprintf("/proc/%d/fd", pid)
	entries, err := os.ReadDir(fdDir)
	if err != nil {
		return nil
	}
	paths := make([]string, 0, len(entries))
	for _, e := range entries {
		target, err := os.Readlink(filepath.Join(fdDir, e.Name()))
		if err == nil {
			paths = append(paths, target)
		}
	}
	return paths
}

// isWineProcess returns true if the process matches any Wine or Proton signature.
// Both exe path and cmdline are checked because Proton sometimes launches as
// /usr/bin/python3 with wine arguments in the cmdline.
func isWineProcess(proc *Process) bool {
	lower := strings.ToLower(proc.ExePath + " " + proc.CmdLine)
	for _, sig := range wineSignatures {
		if strings.Contains(lower, sig) {
			return true
		}
	}
	return false
}

// CheckThreatRules evaluates all Phase 1 rules against the given process.
// Returns one Violation per triggered rule; returns nil if none trigger.
func CheckThreatRules(proc *Process) []Violation {
	// Rules only apply to Wine/Proton processes — ignore native Linux processes.
	if !isWineProcess(proc) {
		return nil
	}

	var violations []Violation
	for _, pattern := range protectedPatterns {
		if hasAccessToPattern(proc, pattern) {
			violations = append(violations, Violation{
				RuleName: "wine_credential_access",
				Description: fmt.Sprintf(
					"Wine/Proton pid=%d has access to protected path pattern %q",
					proc.PID, pattern,
				),
			})
		}
	}
	return violations
}

// hasAccessToPattern returns true if the protected pattern appears in any open
// file descriptor path or in the process memory map.
func hasAccessToPattern(proc *Process, pattern string) bool {
	// Check open file descriptors — catches files the process currently has open.
	for _, fd := range proc.FDPaths {
		if strings.Contains(fd, pattern) {
			return true
		}
	}
	// Check memory maps — catches files mapped into the process's address space.
	if strings.Contains(proc.Maps, pattern) {
		return true
	}
	return false
}
