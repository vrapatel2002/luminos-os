// [CHANGE: claude-code | 2026-08-11] DECISION 66 — exercises the tab sleeper mailbox.
//
// Written because the endpoint's whole purpose is to make a silent system observable, and
// a mailbox that quietly accepts garbage or reports a stale number would be worse than no
// mailbox at all. Every case here is a negative test except the first.
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func get(t *testing.T) map[string]any {
	t.Helper()
	w := httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodGet, "/tabs", nil))
	var out map[string]any
	if err := json.NewDecoder(w.Body).Decode(&out); err != nil {
		t.Fatalf("GET returned undecodable body: %v", err)
	}
	return out
}

func TestNeverReportedIsNotZero(t *testing.T) {
	tabReportMu.Lock()
	tabReport = nil
	tabReportMu.Unlock()

	out := get(t)
	if out["reported"] != false {
		t.Fatalf("before any POST, reported should be false, got %v", out["reported"])
	}
	if _, ok := out["report"]; ok {
		t.Fatal("a report body was returned when nothing had ever reported")
	}
}

func TestRoundTrip(t *testing.T) {
	body := `{"asleep":14,"awake":2,"discarded":3,"level":"pressure","model":true,"cap":2,"free_gb":2.5}`
	w := httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodPost, "/tabs", strings.NewReader(body)))
	if w.Code != http.StatusNoContent {
		t.Fatalf("POST got %d, want 204", w.Code)
	}

	out := get(t)
	if out["reported"] != true {
		t.Fatal("reported should be true after a POST")
	}
	rep := out["report"].(map[string]any)
	if rep["asleep"].(float64) != 14 || rep["cap"].(float64) != 2 || rep["level"] != "pressure" {
		t.Fatalf("round trip lost data: %v", rep)
	}
	// The age is the whole point of storing a timestamp — a stale report must be
	// distinguishable from a fresh one.
	if _, ok := rep["age_seconds"]; !ok {
		t.Fatal("age_seconds missing — a stale report would look current")
	}
	if rep["at"].(float64) == 0 {
		t.Fatal("server did not stamp the report; a client could backdate it")
	}
}

func TestGarbageIsRejectedAndDoesNotClobber(t *testing.T) {
	good := `{"asleep":7,"level":"normal"}`
	w := httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodPost, "/tabs", strings.NewReader(good)))

	w = httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodPost, "/tabs", strings.NewReader("not json at all")))
	if w.Code != http.StatusBadRequest {
		t.Fatalf("garbage POST got %d, want 400", w.Code)
	}

	// A rejected write must leave the last good report intact, or one malformed sweep
	// would blind the readout until the next successful one.
	rep := get(t)["report"].(map[string]any)
	if rep["asleep"].(float64) != 7 {
		t.Fatalf("garbage POST clobbered the last good report: %v", rep)
	}
}

func TestOversizedBodyRejected(t *testing.T) {
	huge := `{"level":"` + strings.Repeat("x", 8192) + `"}`
	w := httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodPost, "/tabs", strings.NewReader(huge)))
	if w.Code != http.StatusBadRequest {
		t.Fatalf("oversized POST got %d, want 400 (MaxBytesReader should cut it off)", w.Code)
	}
}

func TestUnknownMethodRejected(t *testing.T) {
	w := httptest.NewRecorder()
	handleTabs(w, httptest.NewRequest(http.MethodDelete, "/tabs", nil))
	if w.Code != http.StatusMethodNotAllowed {
		t.Fatalf("DELETE got %d, want 405", w.Code)
	}
}

// detectModel must not fire on this test binary, whose own command line contains
// "luminos-ram" but no model. The pgrep version of this check could not make that
// distinction, which is why it reads /proc directly.
func TestDetectModelDoesNotFireOnItself(t *testing.T) {
	resetModelCache()
	running, name, rss := detectModel()
	t.Logf("detectModel() = running:%v name:%q rss:%.2fGB", running, name, rss)
	if running && rss < modelMinRSSGB {
		t.Fatalf("reported a model at %.2f GB, below the %.2f GB floor", rss, modelMinRSSGB)
	}
	if !running && name != "" {
		t.Fatalf("not running but named %q", name)
	}
}

// The negative test above passes trivially if the matcher is simply broken, so this one
// puts a real process on /proc with ".gguf" on its command line and requires a hit.
func TestDetectModelFiresOnAGgufProcess(t *testing.T) {
	// Two commands, not one: `sh -c 'sleep 20'` exec()s sleep over itself and the process
	// loses the .gguf from its command line entirely. The trailing `:` keeps the shell
	// alive as a real process holding the argument.
	cmd := exec.Command("/bin/sh", "-c", "sleep 20; :", "/tmp/pretend-model.gguf")
	if err := cmd.Start(); err != nil {
		t.Fatalf("could not start the stand-in process: %v", err)
	}
	defer func() { _ = cmd.Process.Kill(); _, _ = cmd.Process.Wait() }()

	// A shell holds a few MB, nowhere near the real floor, so drop it for this case only.
	// The floor is what separates "a model is loaded" from "something mentions a model";
	// the matcher underneath it is what this test is for.
	old := modelMinRSSGB
	modelMinRSSGB = 0
	defer func() { modelMinRSSGB = old }()

	resetModelCache()
	running, name, _ := detectModel()
	if !running || name != ".gguf" {
		t.Fatalf("did not detect a .gguf process: running=%v name=%q", running, name)
	}
}

// The 5-second cache is load-bearing — /meminfo is polled constantly — but a cache that
// never expires would pin the answer to whatever was true at boot.
func TestModelCacheExpires(t *testing.T) {
	resetModelCache()
	detectModel()
	modelCacheMu.Lock()
	fresh := time.Since(modelCacheAt) < time.Second
	modelCacheMu.Unlock()
	if !fresh {
		t.Fatal("cache timestamp was not set")
	}

	modelCacheMu.Lock()
	modelCacheAt = time.Now().Add(-10 * time.Second)
	modelCacheVal.running, modelCacheVal.name = true, "stale-lie"
	modelCacheMu.Unlock()

	if _, name, _ := detectModel(); name == "stale-lie" {
		t.Fatal("returned a 10-second-old cached answer; the cache never expires")
	}
}

func resetModelCache() {
	modelCacheMu.Lock()
	modelCacheAt = time.Time{}
	modelCacheVal.running, modelCacheVal.name, modelCacheVal.rssGB = false, "", 0
	modelCacheMu.Unlock()
}
