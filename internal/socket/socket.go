// Package socket provides Unix socket client and server helpers for Luminos daemon IPC.
// The wire format is one JSON-encoded Message per connection (request → response).
// All four daemons use this package for communication with each other and with clients.
// [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — shared socket package.
package socket

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"time"
)

// Message is the IPC envelope for all Luminos daemon communication.
// Every daemon sends and receives this type over Unix sockets.
type Message struct {
	Type      string          `json:"type"`
	Payload   json.RawMessage `json:"payload,omitempty"`
	Timestamp time.Time       `json:"timestamp"`
	Source    string          `json:"source"`
}

// NewMessage constructs a Message with the current timestamp.
// payload may be any JSON-serialisable value, or nil.
func NewMessage(msgType, source string, payload interface{}) (Message, error) {
	m := Message{
		Type:      msgType,
		Source:    source,
		Timestamp: time.Now(),
	}
	if payload != nil {
		b, err := json.Marshal(payload)
		if err != nil {
			return Message{}, fmt.Errorf("marshal payload: %w", err)
		}
		m.Payload = json.RawMessage(b)
	}
	return m, nil
}

// NewListener creates a Unix socket listener at socketPath.
// Any stale socket file from a previous (crashed) run is removed before binding.
func NewListener(socketPath string) (net.Listener, error) {
	// Remove stale socket so bind doesn't fail with EADDRINUSE after a crash.
	os.Remove(socketPath)
	if err := os.MkdirAll(filepath.Dir(socketPath), 0755); err != nil {
		return nil, fmt.Errorf("mkdir %s: %w", filepath.Dir(socketPath), err)
	}
	l, err := net.Listen("unix", socketPath)
	if err != nil {
		return nil, fmt.Errorf("listen on %s: %w", socketPath, err)
	}
	return l, nil
}

// Serve accepts connections on l and calls handler for each incoming Message.
// The handler's return value is written back as a JSON response.
// Serve returns when ctx is cancelled (which closes the listener via the goroutine below).
func Serve(ctx context.Context, l net.Listener, handler func(Message) Message) {
	// Closing the listener from a separate goroutine unblocks the Accept() below.
	go func() {
		<-ctx.Done()
		l.Close()
	}()
	for {
		conn, err := l.Accept()
		if err != nil {
			// Accept fails when the listener is closed (ctx cancelled) — clean exit.
			return
		}
		go handleConn(conn, handler)
	}
}

// handleConn reads one request, calls handler, writes the response, then closes.
func handleConn(conn net.Conn, handler func(Message) Message) {
	defer conn.Close()
	// 5-second deadline covers both slow senders and slow handlers.
	conn.SetDeadline(time.Now().Add(5 * time.Second))

	var req Message
	if err := json.NewDecoder(conn).Decode(&req); err != nil {
		return // Malformed or empty request — drop silently.
	}
	resp := handler(req)
	json.NewEncoder(conn).Encode(resp) // Error ignored — client may have disconnected.
}

// Send connects to socketPath, sends msg, reads one response, and closes.
// Built-in 3-second timeout prevents daemons from blocking on a slow peer.
func Send(socketPath string, msg Message) (*Message, error) {
	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		return nil, fmt.Errorf("dial %s: %w", socketPath, err)
	}
	defer conn.Close()
	conn.SetDeadline(time.Now().Add(3 * time.Second))

	if err := json.NewEncoder(conn).Encode(msg); err != nil {
		return nil, fmt.Errorf("send: %w", err)
	}
	var resp Message
	if err := json.NewDecoder(conn).Decode(&resp); err != nil {
		return nil, fmt.Errorf("recv: %w", err)
	}
	return &resp, nil
}
