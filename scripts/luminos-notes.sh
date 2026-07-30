#!/bin/bash
# luminos-notes.sh — SQLite based project notes
# [CHANGE: gemini-cli | 2026-04-26]

DB="$HOME/luminos-os/.notes.db"

# [CHANGE: claude-code | 2026-07-26] BUG-089 — values were interpolated raw into SQL, so any
# apostrophe (KDE's, don't, user's) made sqlite3 fail... and `echo "Note added"` ran anyway,
# unconditionally. Notes silently vanished while the script reported success. AGENTS.md makes
# this call mandatory after every task, so every apostrophe was a lost knowledge-base entry.
# Fix: double single quotes (SQL's own escape) and report the real exit status.
sql_quote() { printf "%s" "${1//\'/\'\'}"; }

# Create table if not exists
sqlite3 "$DB" "CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, ts DATETIME DEFAULT CURRENT_TIMESTAMP, tag TEXT, note TEXT);"

case "$1" in
    add)
        TAG="$2"
        NOTE="$3"
        if [ -z "$TAG" ] || [ -z "$NOTE" ]; then
            echo "Usage: $0 add TAG NOTE"
            exit 1
        fi
        if sqlite3 "$DB" "INSERT INTO notes (tag, note) VALUES ('$(sql_quote "$TAG")', '$(sql_quote "$NOTE")');"; then
            echo "Note added to $TAG."
        else
            echo "luminos-notes: FAILED to add note to $TAG — nothing was stored." >&2
            exit 1
        fi
        ;;
    search)
        TERM="$2"
        if [ -z "$TERM" ]; then
            echo "Usage: $0 search TERM"
            exit 1
        fi
        TERM_Q="$(sql_quote "$TERM")"
        sqlite3 "$DB" "SELECT ts, tag, note FROM notes WHERE tag LIKE '%$TERM_Q%' OR note LIKE '%$TERM_Q%' ORDER BY ts DESC;"
        ;;
    list)
        sqlite3 "$DB" "SELECT ts, tag, note FROM notes ORDER BY ts DESC;"
        ;;
    *)
        echo "Usage: $0 {add|search|list}"
        exit 1
        ;;
esac
