package main

// [CHANGE: claude-code | 2026-11-07] StreamPIDs tests with pw-dump shaped JSON (CONTRACTS §4, audio.go).

import (
	"maps"
	"testing"
)

const tfPwDump = `[
  {"id": 0, "type": "PipeWire:Interface:Core", "info": {"name": "pipewire-0", "props": {"application.process.id": 900}}},
  {"id": 35, "type": "PipeWire:Interface:Client", "info": {"props": {"application.process.id": 4107, "application.name": "Chromium"}}},
  {"id": 40, "type": "PipeWire:Interface:Metadata", "props": {"metadata.name": "default"}, "metadata": [{"subject": 0, "key": "default.audio.sink", "value": {"name": "x"}}]},
  {"id": 50, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {"media.class": "Audio/Sink", "node.name": "alsa_output.pci", "application.process.id": 999}}},
  {"id": 61, "type": "PipeWire:Interface:Node", "info": {"max-input-ports": 0, "state": "running", "error": null, "props": {"media.class": "Stream/Output/Audio", "application.name": "Chromium", "application.process.id": 4101, "media.name": "Playback"}}},
  {"id": 62, "type": "PipeWire:Interface:Node", "info": {"state": "suspended", "props": {"media.class": "Stream/Output/Audio", "application.process.id": 4102}}},
  {"id": 63, "type": "PipeWire:Interface:Node", "info": {"state": "idle", "props": {"media.class": "Stream/Output/Audio", "application.process.id": 4103}}},
  {"id": 64, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {"media.class": "Stream/Input/Audio", "application.name": "Zoom", "application.process.id": 4104}}},
  {"id": 65, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {"media.class": "Stream/Output/Audio", "application.name": "no pid"}}},
  {"id": 66, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {"media.class": "Stream/Input/Video", "application.process.id": 4106}}},
  {"id": 67, "type": "PipeWire:Interface:Node", "info": {"state": "running", "props": {"media.class": "Video/Source", "application.process.id": 4108}}},
  {"id": 70, "type": "PipeWire:Interface:Link", "info": {"state": "active", "props": {"link.output.node": 61}}}
]`

func TestStreamPIDs(t *testing.T) {
	got := StreamPIDs([]byte(tfPwDump))
	want := map[int]bool{4101: true, 4104: true, 4106: true}
	if !maps.Equal(got, want) {
		t.Errorf("StreamPIDs = %v, want %v (running Stream/* nodes only)", got, want)
	}
}

func TestStreamPIDsBadInput(t *testing.T) {
	for _, in := range []string{"", "not json", "[1,2", "{}", `{"id": 61}`, "null", `[{"info": "x"}]`, "[]"} {
		if got := StreamPIDs([]byte(in)); len(got) != 0 {
			t.Errorf("StreamPIDs(%q) = %v, want empty", in, got)
		}
	}
	if got := StreamPIDs(nil); len(got) != 0 {
		t.Errorf("StreamPIDs(nil) = %v, want empty", got)
	}
}
