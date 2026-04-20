// zone_rules.go implements the rule-based zone classification for luminos-router Phase 1.
// Zone decisions are based on file magic bytes and PE import analysis using debug/pe.
// Phase 2 will add a Python ONNX classifier for edge cases that rules cannot resolve.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — router zone rules.
package main

import (
	"crypto/sha256"
	"debug/pe"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// anticheatSignatures are DLL names that indicate kernel-level anticheat.
// Apps importing these require a full KVM VM with GPU passthrough (Zone 4) because
// the drivers access kernel and hardware in ways Wine and Firecracker cannot virtualise.
var anticheatSignatures = []string{
	"easyanticheat",   // Easy Anti-Cheat (Fortnite, Apex, Rust, many others)
	"battleye",        // BattlEye (PUBG, Arma, Rainbow Six)
	"bedaisy",         // BattlEye kernel driver
	"vgk",             // Vanguard (Valorant) — most aggressive, requires bare-metal
	"mhyprot",         // miHoYo anticheat (Genshin Impact, Honkai)
	"nprotect",        // nProtect GameGuard
	"faceit",          // FACEIT anticheat (CS2 competitive)
	"uncheater",       // Uncheater anticheat
}

// firecrackerSignatures are DLL names indicating Windows APIs Wine cannot handle.
// These apps work better in a Firecracker microVM than in a flat Wine prefix (Zone 3).
var firecrackerSignatures = []string{
	"d3d12",          // DirectX 12 — Wine's DX12 support is incomplete for many titles
	"xgameruntime",   // Xbox Game Runtime (Game Pass titles)
	"xboxservices",   // Xbox services DLL
	"gameinput",      // GameInput (modern Xbox controller API)
	"windows.gaming", // Windows.Gaming namespace (UWP titles)
}

// elfMagic is the 4-byte signature identifying ELF (native Linux) binaries.
var elfMagic = [4]byte{0x7f, 'E', 'L', 'F'}

// ClassifyEXE determines which compatibility zone a file belongs to.
// Returns (zone 1-4, zone name, reason, error).
// Classification is deterministic — no randomness, no ML in Phase 1.
func ClassifyEXE(path string) (int, string, string, error) {
	if _, err := os.Stat(path); err != nil {
		return 0, "", "", fmt.Errorf("stat: %w", err)
	}

	// Read the first 4 bytes to distinguish ELF, PE, and unknown formats.
	header, err := readHeader(path, 4)
	if err != nil {
		return 0, "", "", fmt.Errorf("read header: %w", err)
	}

	// Zone 1: ELF magic — this is a native Linux binary despite the .exe extension.
	// This occurs when Linux games ship a .exe wrapper that is actually an ELF.
	if len(header) >= 4 && [4]byte(header[:4]) == elfMagic {
		return 1, "native", "ELF binary — run natively, no compatibility layer needed", nil
	}

	// Zone 1: Shell script (#!/...) — native Linux, no compatibility needed.
	if len(header) >= 2 && header[0] == '#' && header[1] == '!' {
		return 1, "native", "shell script — run natively", nil
	}

	// Not an MZ (PE) file — cannot do import analysis.
	// [CHANGE: gemini-cli | 2026-04-20] Return uncertain (0) so Phase 2 Python classifier can refine.
	if len(header) < 2 || header[0] != 'M' || header[1] != 'Z' {
		return 0, "uncertain", "non-PE binary format — handover to Python classifier", nil
	}

	// Parse PE imports for anticheat and DX12/Xbox API detection.
	imports, err := parsePEImports(path)
	if err != nil {
		// PE parse failure (truncated file, non-standard PE) — handover to Python.
		return 0, "uncertain", fmt.Sprintf("PE parse error (%v) — handover to Python", err), nil
	}

	// Zone 4: Anticheat detected — must use full KVM with GPU passthrough.
	// Check this before Zone 3 because anticheat apps may also use DX12.
	for _, sig := range anticheatSignatures {
		if importsContain(imports, sig) {
			return 4, "kvm", fmt.Sprintf("anticheat detected (%s) — requires KVM with GPU passthrough", sig), nil
		}
	}

	// Zone 3: DX12 or Xbox Game Runtime APIs — Firecracker gives better compat than flat Wine.
	for _, sig := range firecrackerSignatures {
		if importsContain(imports, sig) {
			return 3, "firecracker", fmt.Sprintf("unsupported API (%s) — Firecracker microVM recommended", sig), nil
		}
	}

	// Zone 2: Standard Windows PE with no known incompatibilities — Wine should work.
	// [CHANGE: gemini-cli | 2026-04-20] Return uncertain so Python heuristics can verify.
	return 0, "uncertain", "standard Windows PE — handover to Python for final verification", nil
	}
// readHeader reads the first n bytes of a file for magic number identification.
func readHeader(path string, n int) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	buf := make([]byte, n)
	read, err := io.ReadFull(f, buf)
	if err != nil && read == 0 {
		return nil, err
	}
	return buf[:read], nil
}

// parsePEImports uses Go's standard debug/pe package to extract imported DLL names.
// Returns an empty slice (not an error) if the PE has no imports section.
func parsePEImports(path string) ([]string, error) {
	f, err := pe.Open(path)
	if err != nil {
		return nil, fmt.Errorf("pe.Open: %w", err)
	}
	defer f.Close()
	libs, err := f.ImportedLibraries()
	if err != nil {
		// Some valid PE files have no imports section — return empty, not an error.
		return nil, nil
	}
	return libs, nil
}

// importsContain checks if any imported DLL name contains needle (case-insensitive).
// Windows DLL names are case-insensitive so we normalise before comparing.
func importsContain(imports []string, needle string) bool {
	needle = strings.ToLower(needle)
	for _, imp := range imports {
		if strings.Contains(strings.ToLower(imp), needle) {
			return true
		}
	}
	return false
}

// cacheKey returns a hex SHA-256 hash of the file path to use as the cache filename.
// Hashing the path avoids filesystem issues with special characters in game install paths.
func cacheKey(path string) string {
	h := sha256.Sum256([]byte(path))
	return hex.EncodeToString(h[:])
}

// saveCache writes a ClassifyResponse to the cache directory as a JSON file.
// Write failures are silently ignored — cache is an optimisation, not a requirement.
func saveCache(cacheDir, path string, resp ClassifyResponse) {
	if cacheDir == "" {
		return
	}
	b, err := json.Marshal(resp)
	if err != nil {
		return
	}
	cachePath := filepath.Join(cacheDir, cacheKey(path)+".json")
	os.WriteFile(cachePath, b, 0644) // Error intentionally ignored — best-effort cache.
}

// loadCache reads a previously-stored ClassifyResponse from the cache.
// Returns (response, true) on cache hit, (zero, false) on miss or corruption.
func loadCache(cacheDir, path string) (ClassifyResponse, bool) {
	if cacheDir == "" {
		return ClassifyResponse{}, false
	}
	cachePath := filepath.Join(cacheDir, cacheKey(path)+".json")
	data, err := os.ReadFile(cachePath)
	if err != nil {
		return ClassifyResponse{}, false
	}
	var resp ClassifyResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return ClassifyResponse{}, false
	}
	return resp, true
}
