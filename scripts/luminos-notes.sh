#!/bin/bash
# luminos-notes.sh — SQLite based project notes
# [CHANGE: gemini-cli | 2026-04-26]

DB="$HOME/luminos-os/.notes.db"

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
        sqlite3 "$DB" "INSERT INTO notes (tag, note) VALUES ('$TAG', '$NOTE');"
        echo "Note added to $TAG."
        ;;
    search)
        TERM="$2"
        if [ -z "$TERM" ]; then
            echo "Usage: $0 search TERM"
            exit 1
        fi
        sqlite3 "$DB" "SELECT ts, tag, note FROM notes WHERE tag LIKE '%$TERM%' OR note LIKE '%$TERM%' ORDER BY ts DESC;"
        ;;
    list)
        sqlite3 "$DB" "SELECT ts, tag, note FROM notes ORDER BY ts DESC;"
        ;;
    *)
        echo "Usage: $0 {add|search|list}"
        exit 1
        ;;
esac
