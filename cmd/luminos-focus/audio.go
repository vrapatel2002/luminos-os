// Which pids own a running PipeWire stream (playback, or capture for calls).
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"context"
	"encoding/json"
	"log"
	"os/exec"
	"strings"
	"time"
)

// StreamPIDs returns application.process.id of every running "Stream/…" node; bad JSON → empty map.
func StreamPIDs(pwDumpJSON []byte) map[int]bool {
	var objs []struct {
		Info struct {
			State string         `json:"state"`
			Props map[string]any `json:"props"`
		} `json:"info"`
	}
	_ = json.Unmarshal(pwDumpJSON, &objs) // a type error still decodes the rest; a syntax error nothing
	out := map[int]bool{}
	for _, o := range objs {
		class, _ := o.Info.Props["media.class"].(string)
		if o.Info.State != "running" || !strings.HasPrefix(class, "Stream/") {
			continue
		}
		if pid, _ := o.Info.Props["application.process.id"].(float64); pid > 0 { // pw-dump writes it as a number
			out[int(pid)] = true
		}
	}
	return out
}

// [CHANGE: claude-code | 2026-11-07] pwDump: one pw-dump (3 s cap); nil on error so the exemption survives.
func pwDump() map[int]bool {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, "pw-dump").Output()
	if err != nil {
		log.Printf("pw-dump: %v", err)
		return nil
	}
	return StreamPIDs(out)
}
