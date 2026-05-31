#!/bin/bash
# luminos-extract — Right-click archive extractor for Dolphin
# [CHANGE: claude-code | 2026-05-31]
# Usage: luminos-extract <archive-file>
# Tools: tar (tar.*), 7z (rar/zip/7z — Linux-native, no unrar/winrar), gzip/bzip2/xz/zstd
# Extracts to a subfolder named after the archive (same directory).
# Single-file compression (.gz .bz2 .xz .zst) decompresses in-place.

FILE="$1"
BASENAME=$(basename "$FILE")
DIR=$(dirname "$FILE")
LOWER="${BASENAME,,}"

notify() {
    notify-send "Luminos Extract" "$1" --icon=package-x-generic 2>/dev/null || true
}

# --- Single-file decompression (no archive structure, decompress in-place) ---
case "$LOWER" in
    *.gz|*.bz2|*.xz|*.zst)
        # Only if NOT a tar.* (those fall through to archive section)
        case "$LOWER" in
            *.tar.gz|*.tar.bz2|*.tar.xz|*.tar.zst) ;;  # skip, handled below
            *.gz)
                notify "Extracting $BASENAME..."
                (cd "$DIR" && gzip -dk "$BASENAME") \
                    && notify "Done: ${BASENAME%.gz}" \
                    || { notify "Failed: $BASENAME"; exit 1; }
                exit 0 ;;
            *.bz2)
                notify "Extracting $BASENAME..."
                (cd "$DIR" && bzip2 -dk "$BASENAME") \
                    && notify "Done: ${BASENAME%.bz2}" \
                    || { notify "Failed: $BASENAME"; exit 1; }
                exit 0 ;;
            *.xz)
                notify "Extracting $BASENAME..."
                (cd "$DIR" && xz -dk "$BASENAME") \
                    && notify "Done: ${BASENAME%.xz}" \
                    || { notify "Failed: $BASENAME"; exit 1; }
                exit 0 ;;
            *.zst)
                notify "Extracting $BASENAME..."
                (cd "$DIR" && zstd -dk "$BASENAME") \
                    && notify "Done: ${BASENAME%.zst}" \
                    || { notify "Failed: $BASENAME"; exit 1; }
                exit 0 ;;
        esac ;;
esac

# --- Archive extraction → subfolder named after archive ---

# Strip extension to get clean folder name
case "$LOWER" in
    *.tar.gz)  FOLNAME="${BASENAME:0:${#BASENAME}-7}" ;;   # remove .tar.gz
    *.tar.bz2) FOLNAME="${BASENAME:0:${#BASENAME}-8}" ;;   # remove .tar.bz2
    *.tar.xz)  FOLNAME="${BASENAME:0:${#BASENAME}-7}" ;;   # remove .tar.xz
    *.tar.zst) FOLNAME="${BASENAME:0:${#BASENAME}-8}" ;;   # remove .tar.zst
    *.tgz)     FOLNAME="${BASENAME:0:${#BASENAME}-4}" ;;
    *.tbz2)    FOLNAME="${BASENAME:0:${#BASENAME}-5}" ;;
    *.rar)     FOLNAME="${BASENAME:0:${#BASENAME}-4}" ;;
    *.zip)     FOLNAME="${BASENAME:0:${#BASENAME}-4}" ;;
    *.7z)      FOLNAME="${BASENAME:0:${#BASENAME}-3}" ;;
    *.tar)     FOLNAME="${BASENAME:0:${#BASENAME}-4}" ;;
    *)         FOLNAME="${BASENAME}.extracted" ;;
esac

# Strip .partN / .part01 suffixes from multi-part RAR names
FOLNAME=$(echo "$FOLNAME" | sed 's/\.part[0-9]*$//')

DEST="$DIR/$FOLNAME"

# Avoid clobbering existing folder — append _2, _3, etc.
if [ -d "$DEST" ]; then
    i=2
    while [ -d "${DEST}_${i}" ]; do i=$((i+1)); done
    DEST="${DEST}_${i}"
fi

mkdir -p "$DEST"

notify "Extracting $BASENAME..."

case "$LOWER" in
    *.tar.gz|*.tgz)    tar -xf "$FILE" -C "$DEST" ;;
    *.tar.bz2|*.tbz2)  tar -xf "$FILE" -C "$DEST" ;;
    *.tar.xz)          tar -xf "$FILE" -C "$DEST" ;;
    *.tar.zst)         tar -xf "$FILE" -C "$DEST" ;;
    *.tar)             tar -xf "$FILE" -C "$DEST" ;;
    *.rar)             7z x "$FILE" -o"$DEST" ;;   # 7z handles RAR natively — no unrar
    *.zip)             7z x "$FILE" -o"$DEST" ;;
    *.7z)              7z x "$FILE" -o"$DEST" ;;
    *)                 7z x "$FILE" -o"$DEST" ;;
esac

if [ $? -eq 0 ]; then
    notify "Done: extracted to $(basename "$DEST")/"
    dolphin "$DEST" &
else
    notify "Failed: $BASENAME"
    rmdir "$DEST" 2>/dev/null
    exit 1
fi
