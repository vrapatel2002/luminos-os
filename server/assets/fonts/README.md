# server/assets/fonts — what these binaries are
# [CHANGE: claude-code | 2026-09-13]

Four `.woff2` files, served by `luminos-hub` and `luminos-space` from `/fonts/<name>.woff2`.

They are committed rather than fetched because of the "zero third-party requests" invariant
(WEB_UI_PROMPT.md §4.2). A Google Fonts `<link>` would make a LAN-and-tailnet-only page
depend on the public internet, and would tell a third party every time the page was opened.
There is no build step: these files are the artefact, checked in.

## Files

| file | face | weight | bytes | sha256 |
|---|---|---:|---:|---|
| `archivo-500.woff2` | Archivo | 500 | 11072 | `42e0e82c2e7858005cf2cab037db11f8ea53791e6a8796d0f15a055d8cb2d70a` |
| `archivo-800.woff2` | Archivo | 800 | 11024 | `39c187136337b76370b3929e40b5d5e0bb20dc9d6cda8d0cc3f1a95398769e28` |
| `jetbrainsmono-400.woff2` | JetBrains Mono | 400 | 7884 | `d1bd368acac1c3bb112e7fd0f5f6c5359005ba3878ad4ec16aa724423250adaf` |
| `jetbrainsmono-800.woff2` | JetBrains Mono | 800 | 7988 | `8523c8c5d80ea7b6ec87a22e3826c26a5fb8abc74565240aadbdf4c2102bef3a` |

Total **37,968 bytes** against a 60 KB budget.

## Sources

- **Archivo** — OFL-1.1. Variable source `Archivo[wdth,wght].ttf` from
  `https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/`, downloaded 2026-09-13
  (658,596 bytes). Axes `wght 100–900`, `wdth 62–125`. Instanced to static cuts at
  `wght=500` and `wght=800`, `wdth=100`.
- **JetBrains Mono** — OFL-1.1. Arch package `ttf-jetbrains-mono 2.304-2`, files
  `/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf` and `-ExtraBold.ttf`.

## How they were made

```bash
U="U+0020-007E,U+00A0,U+00B7,U+00D7,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2026,U+2192,U+00C0-00FF,U+0100-017F"

# JetBrains Mono
pyftsubset /usr/share/fonts/TTF/JetBrainsMono-Regular.ttf --unicodes="$U" \
  --layout-features="kern,tnum" --no-hinting --desubroutinize \
  --flavor=woff2 --output-file=jetbrainsmono-400.woff2

# Archivo: instance the variable font first, then subset
python3 -c "
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
f = TTFont('archivo.ttf')
instantiateVariableFont(f, {'wght': 500, 'wdth': 100}, inplace=True)
f.save('_a500.ttf')"
pyftsubset _a500.ttf --unicodes="$U" --layout-features="kern" --no-hinting \
  --desubroutinize --flavor=woff2 --output-file=archivo-500.woff2
```

`fontTools 4.65.0`, `pyftsubset` from the Arch `python-fonttools` package.

## Two choices worth knowing about

**`--no-hinting` and dropping the ligature tables is where almost all the weight went.** A
naive Latin-1 subset of JetBrains Mono Regular came out at **29,348 bytes**; the same glyph
coverage without hinting instructions and without `liga`/`calt` is **7,884**. Hinting does
nothing on the phone and laptop screens these pages are read on, and JetBrains Mono's
ligatures are code ligatures (`=>`, `!=`, `->`) which never appear in a release name or a
byte count. `tnum` is kept deliberately — tabular figures are the whole reason this face
carries the numbers.

**The unicode range is Latin-1 plus Latin Extended-A, not plain ASCII.** ASCII alone is
~3 KB smaller per file, and it would have been wrong: the library holds titles like
`Amélie` and transliterated anime titles, and a missing glyph falls back to a system font
mid-word, which looks broken in exactly the place the design is trying to look deliberate.

## Re-subsetting

If a page starts needing a character outside the range, add it to `U` and rebuild — do not
add a second font file. Check the total stays under 60 KB.
